"""模型下載管理器。

提供 ModelManager 負責從 HuggingFace 或備用 URL 下載 ASR 模型，
包含進度回報、SHA-256 完整性驗證、備用 URL 自動重試、下載前磁碟空間驗證
以及中斷後續傳（Range header + .tmp 暫存檔）。

符合 specs/model-download/spec.md 與 PRD §6.3.7。
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import shutil
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, List, Optional

logger = logging.getLogger(__name__)

# 預設每塊下載大小（bytes）
_CHUNK_SIZE = 1024 * 1024  # 1 MB

# 下載逾時設定（秒）：連線需快速建立，但每次 chunk 讀取允許較長等待（適應 CDN 慢速）
_DOWNLOAD_TIMEOUT_CONNECT = 15.0
_DOWNLOAD_TIMEOUT_READ = 300.0  # HuggingFace Xet CDN 偶爾 chunk 延遲，給足時間


# ---------------------------------------------------------------------------
# 例外類別
# ---------------------------------------------------------------------------


class DownloadError(Exception):
    """模型下載或完整性驗證失敗。"""


class DiskSpaceError(Exception):
    """磁碟空間不足，無法啟動下載。

    Attributes:
        required_bytes:  模型所需空間（bytes）
        available_bytes: 目前可用空間（bytes）
    """

    def __init__(self, required_bytes: int, available_bytes: int) -> None:
        self.required_bytes = required_bytes
        self.available_bytes = available_bytes
        super().__init__(
            f"磁碟空間不足：required={required_bytes // (1024**2)} MB，"
            f"available={available_bytes // (1024**2)} MB"
        )


# ---------------------------------------------------------------------------
# 資料類別
# ---------------------------------------------------------------------------


@dataclass
class ModelInfo:
    """模型清單條目。

    Attributes:
        id:            模型唯一識別字串
        filename:      本地儲存檔名
        size_bytes:    模型檔案大小（bytes）
        urls:          主要下載 URL 列表
        fallback_urls: 備用下載 URL 列表
        sha256:        SHA-256 校驗碼（十六進位字串，小寫）
    """

    id: str
    filename: str
    size_bytes: int
    urls: List[str]
    fallback_urls: List[str]
    sha256: str


# 進度回報 callback 類型：(downloaded_bytes, total_bytes, percent, eta_seconds)
ProgressCallback = Callable[[int, int, float, float], None]


# ---------------------------------------------------------------------------
# 輔助函式
# ---------------------------------------------------------------------------


def _silent_unlink(path: Path) -> None:
    """靜默刪除檔案（不存在或無權限時忽略）。"""
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass


def _dir_size(path: Path) -> int:
    """遞迴計算目錄總大小（bytes），跳過 .cache 子目錄。"""
    total = 0
    try:
        for f in path.rglob("*"):
            if ".cache" in f.parts:
                continue
            if f.is_file():
                total += f.stat().st_size
    except OSError:
        pass
    return total


# ---------------------------------------------------------------------------
# HuggingFace 進度轉接器
# ---------------------------------------------------------------------------


class _SharedProgress:
    """多個 _HfProgressAdapter 實例共享的進度彙總物件。"""

    def __init__(self, callback: ProgressCallback) -> None:
        self._callback = callback
        self.total_bytes = 0
        self.downloaded_bytes = 0
        self._start_time = time.monotonic()

    def add_total(self, n: int) -> None:
        self.total_bytes += n

    def add_downloaded(self, n: int) -> None:
        self.downloaded_bytes += n
        self._report()

    def _report(self) -> None:
        total = self.total_bytes
        downloaded = self.downloaded_bytes
        if total > 0:
            percent = downloaded / total * 100.0
            elapsed = time.monotonic() - self._start_time
            if elapsed > 0 and downloaded > 0:
                rate = downloaded / elapsed
                remaining = total - downloaded
                eta = remaining / rate if rate > 0 else 0.0
            else:
                eta = 0.0
        else:
            percent = 0.0
            eta = 0.0
        try:
            self._callback(downloaded, total, percent, eta)
        except Exception:  # noqa: BLE001
            pass


class _HfProgressAdapter:
    """tqdm-compatible wrapper，將 snapshot_download 的逐檔進度轉為彙總 callback。

    實作完整的 tqdm class protocol 以相容 tqdm.contrib.concurrent.thread_map：
    get_lock / set_lock / __init__(iterable) / __iter__ / update / close。
    """

    _lock: Any = None

    def __init__(
        self,
        iterable: Any = None,
        *,
        total: int | None = None,
        shared: Optional[_SharedProgress] = None,
        **_kwargs: Any,
    ) -> None:
        self._iterable = iterable
        self._total = total or 0
        self._shared = shared
        if self._total > 0 and self._shared is not None:
            self._shared.add_total(self._total)

    def __iter__(self):
        if self._iterable is not None:
            for item in self._iterable:
                self.update(1)
                yield item

    def update(self, n: int = 1) -> None:
        if self._shared:
            self._shared.add_downloaded(n)

    def close(self) -> None:
        pass

    def set_description(self, *_args: Any, **_kwargs: Any) -> None:
        pass

    def set_postfix(self, *_args: Any, **_kwargs: Any) -> None:
        pass

    def __enter__(self) -> _HfProgressAdapter:
        return self

    def __exit__(self, *_args: Any) -> None:
        self.close()

    @classmethod
    def get_lock(cls) -> Any:
        """回傳 threading.Lock，快取於 cls._lock。"""
        import threading
        if cls._lock is None:
            cls._lock = threading.Lock()
        return cls._lock

    @classmethod
    def set_lock(cls, lock: Any) -> None:
        """設定 class-level lock（供 thread_map 的 ThreadPoolExecutor initializer 使用）。"""
        cls._lock = lock


# ---------------------------------------------------------------------------
# 模型下載管理器
# ---------------------------------------------------------------------------


class ModelManager:
    """ASR 模型下載管理器。

    讀取 ``models/manifest.json`` 取得可用模型清單，並提供：
    - 帶進度回報的下載
    - 下載後 SHA-256 完整性驗證（失敗時自動重試備用 URL）
    - 備用 URL 自動重試
    - 下載前磁碟空間驗證
    - 中斷後續傳：以 ``.tmp`` 暫存檔 + ``Range`` header 支援斷點續傳

    Args:
        manifest_path: manifest JSON 檔案路徑。
        download_dir:  模型儲存目錄（預設 ``~/.airtype/models``）。

    Raises:
        FileNotFoundError: manifest 檔案不存在。
        ValueError:        manifest JSON 格式無效。
    """

    def __init__(
        self,
        manifest_path: Optional[str] = None,
        download_dir: Optional[str] = None,
    ) -> None:
        if manifest_path is None:
            from airtype.utils.paths import get_manifest_path

            manifest_path = str(get_manifest_path())
        self._manifest_path = Path(manifest_path)
        self._download_dir = Path(
            download_dir or os.path.expanduser("~/.airtype/models")
        )
        self._models: dict[str, ModelInfo] = {}
        self._manifest_entries: list[dict] = []
        self._load_manifest()

    # ------------------------------------------------------------------
    # 公開 API
    # ------------------------------------------------------------------

    def list_models(self) -> List[ModelInfo]:
        """回傳所有已知模型的 ModelInfo 列表。"""
        return list(self._models.values())

    def list_models_by_category(self, category: str) -> list[dict]:
        """依類別篩選並回傳 manifest 條目列表。

        Args:
            category: 模型類別，有效值為 "asr" 或 "llm"。
                      傳入未知類別時回傳空 list，不拋出例外。

        Returns:
            符合指定類別的 manifest 條目 dict 列表。
            每個 dict 包含 manifest 中的所有欄位（id, description, category 等）。
        """
        return [entry for entry in self._manifest_entries if entry.get("category") == category]

    def is_downloaded(self, model_id: str) -> bool:
        """回傳指定模型是否已下載至本地。

        Args:
            model_id: 模型 ID。

        Returns:
            True 若對應的模型檔案（或目錄）已存在於 download_dir。
        """
        info = self._models.get(model_id)
        if info is None:
            return False
        dest = self._download_dir / info.filename
        if dest.exists():
            return True
        # 支援目錄型模型（如 OpenVINO repo）：.zip → 去掉副檔名的目錄
        if info.filename.endswith(".zip"):
            dir_dest = self._download_dir / info.filename[:-4]
            return dir_dest.is_dir()
        return False

    def delete_model(self, model_id: str) -> bool:
        """刪除已下載的模型檔案。

        Args:
            model_id: 模型 ID（需存在於 manifest）。

        Returns:
            True 若檔案成功刪除，False 若檔案不存在。

        Raises:
            KeyError: model_id 不在 manifest 中。
        """
        if model_id not in self._models:
            raise KeyError(f"模型 '{model_id}' 不在 manifest 中")
        info = self._models[model_id]
        dest = self._download_dir / info.filename
        deleted = False
        # 嘗試刪除檔案
        if dest.is_file():
            try:
                dest.unlink()
                logger.info("已刪除模型檔案：%s", dest)
                deleted = True
            except OSError as exc:
                logger.error("刪除模型檔案失敗：%s", exc)
        # 對 .zip 類型，額外嘗試刪除去掉 .zip 後綴的目錄
        if info.filename.endswith(".zip"):
            dir_path = self._download_dir / info.filename[:-4]
            if dir_path.is_dir():
                try:
                    shutil.rmtree(dir_path)
                    logger.info("已刪除模型目錄：%s", dir_path)
                    deleted = True
                except OSError as exc:
                    logger.error("刪除模型目錄失敗：%s", exc)
        return deleted

    def get_model_path(self, model_id: str) -> Optional[str]:
        """回傳已下載模型的絕對路徑。

        Args:
            model_id: 模型 ID。

        Returns:
            已下載模型的絕對路徑字串；若未下載或 model_id 未知則回傳 None。
        """
        info = self._models.get(model_id)
        if info is None:
            return None
        dest = self._download_dir / info.filename
        if dest.exists():
            return str(dest.resolve())
        # 支援目錄型模型（如 OpenVINO repo）：.zip → 去掉副檔名的目錄
        if info.filename.endswith(".zip"):
            dir_dest = self._download_dir / info.filename[:-4]
            if dir_dest.is_dir():
                return str(dir_dest.resolve())
        return None

    def download(
        self,
        model_id: str,
        progress_callback: Optional[ProgressCallback] = None,
    ) -> str:
        """下載指定模型至本地目錄。

        下載前先驗證磁碟空間，下載後以 SHA-256 驗證完整性。
        若主 URL 失敗（包含校驗和不符），自動嘗試備用 URL。
        支援中斷後續傳：下載過程使用 ``.tmp`` 暫存檔，下一次呼叫時
        若暫存檔存在會以 ``Range`` header 從斷點繼續。

        Args:
            model_id:          模型 ID（需存在於 manifest）。
            progress_callback: 可選進度回報函式，簽名為
                               ``(downloaded, total, percent, eta) -> None``。

        Returns:
            下載完成後的本地檔案路徑（字串）。

        Raises:
            KeyError:       model_id 不在 manifest 中。
            DiskSpaceError: 磁碟空間不足。
            DownloadError:  所有 URL 均失敗。
        """
        if model_id not in self._models:
            raise KeyError(f"模型 '{model_id}' 不在 manifest 中")

        info = self._models[model_id]
        self._validate_disk_space(info.size_bytes)

        self._download_dir.mkdir(parents=True, exist_ok=True)
        dest = self._download_dir / info.filename
        tmp_dest = dest.with_suffix(dest.suffix + ".tmp")

        # 無 token 時直接走 Fallback URL（避免對 gated URL 的無意義 401 錯誤）
        hf_token = self._get_hf_token()
        primary_is_hf = any("huggingface.co" in u for u in info.urls)
        if not hf_token and primary_is_hf and info.fallback_urls:
            all_urls = list(info.fallback_urls)
            logger.debug("無 HuggingFace token，跳過主 URL，直接使用 fallback URLs")
        else:
            all_urls = list(info.urls) + list(info.fallback_urls)
        last_exc: Optional[Exception] = None

        for i, url in enumerate(all_urls):
            # 切換至新 URL 時清除前一次的暫存檔（避免以不相容內容續傳）
            if i > 0:
                _silent_unlink(tmp_dest)
            try:
                logger.info("開始下載（url=%s）", url)

                # HuggingFace repo URL（非 /resolve/main/ 直連）→ 用 snapshot_download
                if self._is_hf_repo_url(url):
                    repo_id = self._extract_hf_repo_id(url)
                    repo_dest = self._download_hf_repo(
                        repo_id, info.filename, progress_callback,
                        expected_size=info.size_bytes,
                    )
                    logger.info("下載完成（HF repo）：%s", repo_dest)
                    return str(repo_dest)

                self._download_url(url, dest, info.size_bytes, progress_callback)
                # 驗證完整性
                self._verify_sha256(dest, info.sha256)
                logger.info("下載完成並通過驗證：%s", dest)
                return str(dest)
            except DownloadError as exc:
                # SHA-256 驗證失敗（dest 已被刪除）：清除暫存，嘗試下一個 URL
                logger.warning("校驗和驗證失敗，嘗試下一個 URL：%s", exc)
                _silent_unlink(tmp_dest)
                last_exc = exc
            except Exception as exc:  # noqa: BLE001
                logger.warning("URL 下載失敗（%s）：%s，嘗試下一個 URL", url, exc)
                last_exc = exc

        # 所有 URL 均失敗：清除殘留的暫存檔
        _silent_unlink(tmp_dest)
        raise DownloadError(
            f"模型 '{model_id}' 所有 URL 均下載失敗。最後錯誤：{last_exc}"
        )

    # ------------------------------------------------------------------
    # 私有方法
    # ------------------------------------------------------------------

    @staticmethod
    def _is_hf_repo_url(url: str) -> bool:
        """判斷 URL 是否為 HuggingFace repo 頁面（非直連檔案）。"""
        return (
            "huggingface.co/" in url
            and "/resolve/" not in url
            and "/blob/" not in url
        )

    @staticmethod
    def _extract_hf_repo_id(url: str) -> str:
        """從 HuggingFace URL 提取 repo ID（例如 'dseditor/Qwen3-ASR-0.6B-INT8_ASYM-OpenVINO'）。"""
        # https://huggingface.co/dseditor/Qwen3-ASR-0.6B-INT8_ASYM-OpenVINO
        from urllib.parse import urlparse
        path = urlparse(url).path.strip("/")
        # path = "dseditor/Qwen3-ASR-0.6B-INT8_ASYM-OpenVINO"
        parts = path.split("/")
        if len(parts) >= 2:
            return "/".join(parts[:2])
        return path

    # HF repo 下載時排除的檔案 pattern
    _HF_IGNORE_PATTERNS = [
        "*.int8.onnx",
        "test_wavs/*",
        "optimizer.bin",
        "scheduler.bin",
        "random_states_*.pkl",
        "*.png",
        "*.jpg",
    ]

    def _list_hf_repo_files(self, repo_id: str) -> list[dict]:
        """用 HF API 取得 repo 檔案清單（不依賴 huggingface_hub）。

        Returns:
            [{"rfilename": "model.bin", "size": 12345}, ...]
        """
        import httpx

        api_url = f"https://huggingface.co/api/models/{repo_id}"
        headers: dict[str, str] = {}
        token = self._get_hf_token()
        if token:
            headers["Authorization"] = f"Bearer {token}"

        resp = httpx.get(
            api_url,
            headers=headers,
            follow_redirects=True,
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("siblings", [])

    @staticmethod
    def _matches_ignore_pattern(filename: str, patterns: list[str]) -> bool:
        """檢查 filename 是否匹配任一 ignore pattern。"""
        from fnmatch import fnmatch
        return any(fnmatch(filename, p) for p in patterns)

    def _download_hf_repo(
        self,
        repo_id: str,
        filename: str,
        progress_callback: Optional[ProgressCallback],
        expected_size: int = 0,
    ) -> Path:
        """逐檔直接下載 HuggingFace repo（不依賴 huggingface_hub snapshot_download）。

        對於多檔案模型（如 OpenVINO IR），zip filename 去掉副檔名作為目錄名。
        使用 HF API 列出檔案清單，再以 resolve URL 逐檔下載，
        重用 _download_url() 的續傳與進度回報基礎設施。
        """
        if filename.endswith(".zip"):
            dir_name = filename[:-4]
        else:
            dir_name = filename
        local_dir = self._download_dir / dir_name
        local_dir.mkdir(parents=True, exist_ok=True)

        logger.info("列出 HF repo 檔案：%s", repo_id)
        siblings = self._list_hf_repo_files(repo_id)

        files_to_download = [
            s for s in siblings
            if not self._matches_ignore_pattern(
                s.get("rfilename", ""), self._HF_IGNORE_PATTERNS,
            )
        ]
        logger.info(
            "HF repo %s：%d 個檔案待下載（已過濾 %d 個）",
            repo_id, len(files_to_download),
            len(siblings) - len(files_to_download),
        )

        # 計算總大小：優先用 API 回傳的 size，否則用 manifest 的 expected_size
        api_total = sum(s.get("size", 0) for s in files_to_download)
        total_size = api_total if api_total > 0 else expected_size

        total_downloaded = 0
        for file_info in files_to_download:
            rfilename = file_info.get("rfilename", "")
            file_size = file_info.get("size", 0)
            resolve_url = (
                f"https://huggingface.co/{repo_id}/resolve/main/{rfilename}"
            )
            dest = local_dir / rfilename
            dest.parent.mkdir(parents=True, exist_ok=True)

            # 已下載且大小一致 → 跳過
            if dest.exists() and file_size > 0 and dest.stat().st_size == file_size:
                total_downloaded += file_size
                logger.debug("跳過已下載檔案：%s（%d bytes）", rfilename, file_size)
                continue

            # 包裝 callback 以彙總整體進度
            file_cb: Optional[ProgressCallback] = None
            if progress_callback and total_size > 0:
                base = total_downloaded

                def _file_progress(
                    dl: int, _tot: int, _pct: float, eta: float,
                    _base: int = base, _total: int = total_size,
                ) -> None:
                    overall_dl = _base + dl
                    overall_pct = min(overall_dl / _total * 100.0, 99.9)
                    progress_callback(overall_dl, _total, overall_pct, eta)

                file_cb = _file_progress

            logger.info("下載 HF 檔案：%s（%d bytes）", rfilename, file_size)
            self._download_url(resolve_url, dest, file_size, file_cb)
            total_downloaded += file_size

        # 最終強制報 100%
        if progress_callback:
            actual = total_downloaded if total_downloaded > 0 else _dir_size(local_dir)
            final_total = max(actual, total_size)
            progress_callback(final_total, final_total, 100.0, 0.0)

        return local_dir

    def _load_manifest(self) -> None:
        """從 manifest JSON 載入模型清單。"""
        if not self._manifest_path.exists():
            raise FileNotFoundError(f"manifest 不存在：{self._manifest_path}")

        try:
            data = json.loads(self._manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"manifest JSON 格式無效：{exc}") from exc

        models_raw = data.get("models", [])
        self._manifest_entries = list(models_raw)
        for entry in models_raw:
            info = ModelInfo(
                id=entry["id"],
                filename=entry["filename"],
                size_bytes=entry["size_bytes"],
                urls=entry.get("urls", []),
                fallback_urls=entry.get("fallback_urls", []),
                sha256=entry.get("sha256", ""),
            )
            self._models[info.id] = info

        logger.debug("已載入 manifest：%d 個模型", len(self._models))

    def _validate_disk_space(self, required_bytes: int) -> None:
        """驗證下載目錄是否有足夠磁碟空間。

        Args:
            required_bytes: 所需空間（bytes）。

        Raises:
            DiskSpaceError: 可用空間不足。
        """
        check_path = self._download_dir
        # 若目錄尚未建立，以父目錄檢查
        if not check_path.exists():
            check_path = check_path.parent
            if not check_path.exists():
                check_path = Path(os.path.expanduser("~"))

        try:
            usage = shutil.disk_usage(str(check_path))
            available = usage.free
        except OSError as exc:
            logger.warning("無法取得磁碟空間資訊：%s", exc)
            return  # 無法取得時放行，以免誤擋

        if available < required_bytes:
            raise DiskSpaceError(
                required_bytes=required_bytes,
                available_bytes=available,
            )
        logger.debug(
            "磁碟空間充足：required=%d MB，available=%d MB",
            required_bytes // (1024 * 1024),
            available // (1024 * 1024),
        )

    def _get_hf_token(self) -> Optional[str]:
        """依優先順序取得 HuggingFace Access Token。

        來源優先順序：
        1. 系統 keyring（config.get_api_key("huggingface")）
        2. 環境變數 HF_TOKEN
        3. ~/.cache/huggingface/token 快取檔

        Returns:
            Token 字串，或 None（三個來源均無 token 時）。

        注意：Token 明文不會出現在 log 中；僅記錄是否找到 token。
        """
        # 1. 系統 keyring（最安全，專案既有模式）
        try:
            from airtype.config import get_api_key  # noqa: PLC0415
            token = get_api_key("huggingface")
            if token:
                logger.debug("已從 keyring 取得 HuggingFace token")
                return token
        except Exception:  # noqa: BLE001
            pass

        # 2. 環境變數 HF_TOKEN（CI/CD 環境常用）
        token = os.environ.get("HF_TOKEN")
        if token:
            logger.debug("已從環境變數 HF_TOKEN 取得 HuggingFace token")
            return token

        # 3. ~/.cache/huggingface/token（huggingface-cli login 快取）
        cache_path = Path.home() / ".cache" / "huggingface" / "token"
        if cache_path.exists():
            try:
                token = cache_path.read_text(encoding="utf-8").strip()
                if token:
                    logger.debug("已從快取檔取得 HuggingFace token")
                    return token
            except OSError:
                pass

        logger.debug("未找到 HuggingFace token")
        return None

    def _download_url(
        self,
        url: str,
        dest: Path,
        total_size: int,
        progress_callback: Optional[ProgressCallback],
    ) -> None:
        """從 URL 下載檔案至 dest，支援中斷後續傳與進度回報。

        下載過程使用 ``dest.suffix + ".tmp"`` 暫存檔。
        若暫存檔已存在（前次中斷），發送 ``Range`` header 從斷點繼續；
        伺服器若不支援 Range（回應 200 而非 206），自動從頭重新下載。
        下載完成後將暫存檔 rename 至 ``dest``。

        Args:
            url:               下載 URL。
            dest:              最終本地路徑（rename 目標）。
            total_size:        預期檔案大小（bytes），用於進度計算。
            progress_callback: 可選進度回報函式。

        Raises:
            Exception: httpx 連線錯誤或 HTTP 狀態錯誤。
        """
        import httpx

        tmp_path = dest.with_suffix(dest.suffix + ".tmp")

        # 斷點偵測：若暫存檔存在，從其大小作為 offset
        offset = 0
        if tmp_path.exists():
            offset = tmp_path.stat().st_size
            logger.debug("發現暫存檔（%d bytes），嘗試續傳：%s", offset, url)

        headers: dict[str, str] = {}
        if offset > 0:
            headers["Range"] = f"bytes={offset}-"

        # HuggingFace URL 自動注入 Authorization Bearer header
        if "huggingface.co" in url:
            hf_token = self._get_hf_token()
            if hf_token:
                headers["Authorization"] = f"Bearer {hf_token}"
                logger.debug("已附加 HuggingFace Authorization header")

        downloaded = offset
        start_time = time.monotonic()

        with httpx.stream(
            "GET",
            url,
            follow_redirects=True,
            timeout=httpx.Timeout(
                connect=_DOWNLOAD_TIMEOUT_CONNECT,
                read=_DOWNLOAD_TIMEOUT_READ,
                write=_DOWNLOAD_TIMEOUT_CONNECT,
                pool=_DOWNLOAD_TIMEOUT_CONNECT,
            ),
            headers=headers,
        ) as response:
            # 判斷伺服器是否支援 Range
            is_partial = (response.status_code == 206)

            if not is_partial:
                if response.status_code != 200:
                    response.raise_for_status()
                # 伺服器回應 200（不支援 Range 或無需續傳）：從頭開始
                if offset > 0:
                    logger.debug("伺服器不支援 Range，重新下載：%s", url)
                offset = 0
                downloaded = 0

            file_mode = "ab" if is_partial else "wb"

            # 更新 total_size（優先使用伺服器回應的 Content-Length）
            content_length_str = response.headers.get("content-length")
            if content_length_str:
                try:
                    cl = int(content_length_str)
                    # 206 回應的 Content-Length 是剩餘部分
                    total_size = offset + cl if is_partial else cl
                except ValueError:
                    pass

            with open(tmp_path, file_mode) as f:
                for chunk in response.iter_bytes(chunk_size=_CHUNK_SIZE):
                    if not chunk:
                        continue
                    f.write(chunk)
                    downloaded += len(chunk)

                    if progress_callback is not None:
                        elapsed = time.monotonic() - start_time
                        percent = (downloaded / total_size * 100.0) if total_size > 0 else 0.0
                        if elapsed > 0 and downloaded > 0 and total_size > 0:
                            rate = downloaded / elapsed
                            remaining = total_size - downloaded
                            eta = remaining / rate if rate > 0 else 0.0
                        else:
                            eta = 0.0
                        try:
                            progress_callback(downloaded, total_size, percent, eta)
                        except Exception:  # noqa: BLE001
                            pass  # 不因 callback 例外中斷下載

        # 下載完成：rename 暫存檔至最終路徑
        tmp_path.rename(dest)

    def _verify_sha256(self, path: Path, expected: str) -> None:
        """計算並驗證檔案的 SHA-256 校驗碼。

        Args:
            path:     本地檔案路徑。
            expected: 預期的 SHA-256 十六進位字串（小寫）。

        Raises:
            DownloadError: 校驗碼不符。
        """
        if not expected:
            # S2：空校驗碼以 WARNING 提示，不靜默跳過
            logger.warning(
                "模型 '%s' 無 SHA-256 預期值，跳過完整性驗證（建議更新 manifest.json）",
                path.name,
            )
            return

        hasher = hashlib.sha256()
        with open(path, "rb") as f:
            while chunk := f.read(8192):
                hasher.update(chunk)
        actual = hasher.hexdigest()

        if actual != expected.lower():
            logger.error(
                "SHA-256 驗證失敗（file=%s）：expected=%s actual=%s",
                path.name,
                expected,
                actual,
            )
            try:
                path.unlink()
                logger.info("已刪除損壞的下載檔案：%s", path)
            except OSError as exc:
                logger.warning("刪除損壞檔案失敗：%s", exc)
            raise DownloadError(
                f"SHA-256 驗證失敗（{path.name}）："
                f"expected={expected[:8]}…, actual={actual[:8]}…"
            )

        logger.debug("SHA-256 驗證通過：%s", path.name)
