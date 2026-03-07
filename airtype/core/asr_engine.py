"""ASR 引擎抽象層。

定義 ASREngine Protocol、結果資料模型（ASRResult、PartialResult、ASRSegment、HotWord）
與 ASREngineRegistry，作為 Qwen3-ASR、Breeze-ASR-25、sherpa-onnx 等引擎的共用介面。

符合 PRD §6.3.1（ASR 引擎抽象——Protocol 類別）。
相依：01-project-setup（設定、日誌記錄）。
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Optional, Protocol, runtime_checkable

import numpy as np

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# manifest inference_engine → 實際 ENGINE_ID 的別名映射
# 當 manifest 中的 inference_engine 值與 ENGINE_ID 不一致時使用。
# ---------------------------------------------------------------------------

_INFERENCE_ENGINE_ALIAS: dict[str, str] = {
    "chatllm-vulkan": "qwen3-vulkan",
    "sherpa-onnx": "sherpa-sensevoice",
}

# 支援真實串流辨識的 manifest inference_engine 值
STREAMING_CAPABLE_ENGINES: frozenset[str] = frozenset({
    "sherpa-onnx",
})

# manifest 路徑（支援 PyInstaller 打包環境）
from airtype.utils.paths import get_manifest_path as _get_manifest_path

_MANIFEST_PATH = _get_manifest_path()

# ---------------------------------------------------------------------------
# 模型家族 → 引擎 ID 後備映射表（當 manifest 查詢失敗時使用）
# 新增 ASR 引擎時需同步更新此映射。
# value 清單為優先順序（openvino > pytorch-cuda > vulkan）。
# ---------------------------------------------------------------------------

_MODEL_ENGINE_MAP: dict[str, list[str]] = {
    "qwen3-asr-1.7b-openvino": ["qwen3-openvino"],
    "qwen3-asr-0.6b-openvino": ["qwen3-openvino"],
    "qwen3-asr-1.7b": ["qwen3-pytorch-cuda"],
    "qwen3-asr-1.7b-vulkan": ["qwen3-vulkan"],
    "qwen3-asr-0.6b-vulkan": ["qwen3-vulkan"],
    "qwen3-asr-0.6b-vulkan-q4": ["qwen3-vulkan"],
    "breeze-asr-25": ["breeze-asr-25"],
    "sensevoice-small": ["sherpa-sensevoice"],
    "sherpa-sensevoice": ["sherpa-sensevoice"],
    "sherpa-paraformer": ["sherpa-paraformer"],
}


# ---------------------------------------------------------------------------
# 資料模型
# ---------------------------------------------------------------------------


@dataclass
class HotWord:
    """ASR 熱詞（加權詞彙提示）。"""

    word: str
    weight: int


@dataclass
class ASRSegment:
    """ASR 辨識結果中的單一時間段。"""

    text: str
    start: float  # 秒
    end: float    # 秒


@dataclass
class ASRResult:
    """批次辨識的完整結果。

    Attributes:
        text: 完整辨識文字。
        language: 語言代碼（例如 "zh-TW"、"en"）。
        confidence: 辨識信心分數（0.0–1.0）。
        segments: 時間段列表（含時間戳記的文字片段）。
    """

    text: str
    language: str
    confidence: float
    segments: list[ASRSegment] = field(default_factory=list)


@dataclass
class PartialResult:
    """串流辨識的部分結果。

    Attributes:
        text: 目前部分辨識文字。
        is_final: 若為 True 代表此段落辨識已完成。
    """

    text: str
    is_final: bool


# ---------------------------------------------------------------------------
# ASREngine Protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class ASREngine(Protocol):
    """ASR 引擎統一介面（結構子型別 Protocol）。

    所有 ASR 引擎實作（Qwen3-ASR、Breeze-ASR-25、sherpa-onnx 等）
    均須提供此介面定義的方法，無需繼承本 Protocol。

    使用方式::

        class MyEngine:
            def load_model(self, model_path, config): ...
            def recognize(self, audio): ...
            # ... 其餘方法 ...

        engine: ASREngine = MyEngine()  # 靜態型別檢查通過
    """

    def load_model(self, model_path: str, config: dict[str, Any]) -> None:
        """載入 ASR 模型至記憶體。

        Args:
            model_path: 模型檔案或目錄路徑。
            config: 引擎特定設定（量化、執行緒數等）。
        """
        ...

    def recognize(self, audio: np.ndarray) -> ASRResult:
        """批次辨識整段音訊，回傳完整結果。

        Args:
            audio: 16kHz mono PCM float32 numpy 陣列。

        Returns:
            ASRResult 含文字、語言、信心分數與時間段。
        """
        ...

    def recognize_stream(self, chunk: np.ndarray) -> PartialResult:
        """串流辨識單一音訊塊，回傳部分結果。

        Args:
            chunk: 單一音訊塊（16kHz mono PCM float32）。

        Returns:
            PartialResult 含部分文字與 is_final 旗標。
        """
        ...

    def set_hot_words(self, words: list[HotWord]) -> None:
        """設定 ASR 熱詞以提升特定詞彙辨識率。

        Args:
            words: HotWord 列表，含詞彙與加權分數。
        """
        ...

    def set_context(self, context_text: str) -> None:
        """設定語境文字以輔助辨識（例如來自當前文件的文字）。

        Args:
            context_text: 語境提示文字。
        """
        ...

    def get_supported_languages(self) -> list[str]:
        """回傳此引擎支援的語言代碼清單。

        Returns:
            語言代碼清單（例如 ["zh-TW", "en", "ja"]）。
        """
        ...

    def unload(self) -> None:
        """卸載模型並釋放記憶體與 GPU 資源。"""
        ...


# ---------------------------------------------------------------------------
# 引擎登錄檔
# ---------------------------------------------------------------------------


class ASREngineRegistry:
    """ASR 引擎工廠登錄檔。

    維護字串引擎 ID 至工廠 callable 的對應，支援執行時動態切換引擎。
    切換策略：先確認新引擎可建立（KeyError 防衛）→ 卸載舊引擎 → 設定新引擎。

    使用方式::

        registry = ASREngineRegistry()
        registry.register_engine("qwen3-openvino", QwenOpenVINOEngine)
        registry.load_default_engine(config)  # 載入 voice.asr_model 指定引擎

        result = registry.active_engine.recognize(audio)
        registry.set_active_engine("breeze-asr-25")  # 執行時切換
    """

    def __init__(self) -> None:
        self._factories: dict[str, Callable[[], ASREngine]] = {}
        self._active: Optional[ASREngine] = None
        self._active_id: Optional[str] = None
        # 閒置卸載監控（懶加載與按需模型管理，符合 PRD §10.1）
        self._idle_unloader = None  # type: Optional[Any]
        self._idle_timeout_sec: float = 5.0 * 60  # 預設 5 分鐘

    # ------------------------------------------------------------------
    # 登錄
    # ------------------------------------------------------------------

    def register_engine(self, engine_id: str, factory: Callable[[], ASREngine]) -> None:
        """以字串 ID 登錄引擎工廠。

        Args:
            engine_id: 引擎識別字串（例如 "qwen3-openvino"、"breeze-asr-25"）。
            factory: 無參數 callable，呼叫後回傳 ASREngine 實例。
        """
        self._factories[engine_id] = factory
        logger.debug("已登錄 ASR 引擎：%s", engine_id)

    def get_engine(self, engine_id: str) -> ASREngine:
        """建立並回傳指定 ID 的引擎新實例。

        Args:
            engine_id: 已登錄的引擎 ID。

        Returns:
            新建立的 ASREngine 實例。

        Raises:
            KeyError: 若 engine_id 未登錄。
        """
        if engine_id not in self._factories:
            raise KeyError(f"未知的 ASR 引擎 ID：{engine_id!r}")
        return self._factories[engine_id]()

    # ------------------------------------------------------------------
    # 切換
    # ------------------------------------------------------------------

    def set_active_engine(self, engine_id: str) -> None:
        """切換作用中引擎。

        策略：先確認新引擎可建立（若未登錄則在此拋出 KeyError，舊引擎不受影響），
        再卸載舊引擎，最後設定新引擎。

        Args:
            engine_id: 要切換至的引擎 ID。

        Raises:
            KeyError: 若 engine_id 未登錄（舊引擎保持不變）。
        """
        # 先確認新引擎存在；若失敗則 KeyError 在此拋出，舊引擎不受影響
        new_engine = self.get_engine(engine_id)

        # 停止舊引擎的閒置監控（切換時不再需要監控舊引擎）
        if self._idle_unloader is not None:
            self._idle_unloader.stop()
            self._idle_unloader = None

        # 卸載目前引擎
        if self._active is not None:
            try:
                self._active.unload()
                logger.debug("已卸載 ASR 引擎：%s", self._active_id)
            except Exception as exc:  # noqa: BLE001
                logger.warning("卸載 ASR 引擎 %r 時發生錯誤：%s", self._active_id, exc)

        self._active = new_engine
        self._active_id = engine_id
        logger.info("已切換至 ASR 引擎：%s", engine_id)

        # 建立並啟動新引擎的閒置卸載監控（首次使用時由 notify_used() 啟動計時）
        from airtype.utils.idle_unloader import IdleUnloader  # noqa: PLC0415

        self._idle_unloader = IdleUnloader(
            unload_fn=self._perform_idle_unload,
            timeout_sec=self._idle_timeout_sec,
        )
        self._idle_unloader.start()

    # ------------------------------------------------------------------
    # 屬性
    # ------------------------------------------------------------------

    @property
    def active_engine(self) -> Optional[ASREngine]:
        """目前作用中的引擎實例，若無則為 None。"""
        return self._active

    @property
    def active_engine_id(self) -> Optional[str]:
        """目前作用中的引擎 ID，若無則為 None。"""
        return self._active_id

    @property
    def registered_ids(self) -> list[str]:
        """已登錄的所有引擎 ID 清單。"""
        return list(self._factories.keys())

    # ------------------------------------------------------------------
    # 閒置卸載管理（懶加載與按需模型管理）
    # ------------------------------------------------------------------

    def set_idle_timeout(self, timeout_sec: float) -> None:
        """設定閒置卸載逾時時間（秒）。

        變更僅對下次 ``set_active_engine()`` 後生效（重建 IdleUnloader 時套用）。

        Args:
            timeout_sec: 閒置逾時秒數（預設 300 秒 = 5 分鐘）。
        """
        self._idle_timeout_sec = timeout_sec

    def notify_used(self) -> None:
        """通知登錄檔作用中引擎剛被使用，重設閒置計時器。

        應在每次呼叫 ``engine.recognize()`` 之前呼叫，
        以確保引擎在使用期間不被閒置卸載。
        """
        if self._idle_unloader is not None:
            self._idle_unloader.mark_used()

    def shutdown(self) -> None:
        """關閉登錄檔：停止閒置監控並卸載作用中引擎。

        應用程式關閉時呼叫，確保資源正確釋放。
        """
        if self._idle_unloader is not None:
            self._idle_unloader.stop()
            self._idle_unloader = None
        if self._active is not None:
            try:
                self._active.unload()
            except Exception as exc:  # noqa: BLE001
                logger.warning("shutdown 時卸載 ASR 引擎失敗：%s", exc)
            self._active = None
            self._active_id = None
        logger.debug("ASREngineRegistry 已關閉")

    def _perform_idle_unload(self) -> None:
        """由 IdleUnloader 在閒置逾時後呼叫，卸載作用中引擎並清除引用。

        執行於 IdleUnloader 的背景執行緒中。
        """
        if self._active is not None:
            try:
                self._active.unload()
                logger.info("閒置逾時卸載 ASR 引擎：%s，RAM 已釋放", self._active_id)
            except Exception as exc:  # noqa: BLE001
                logger.warning("閒置卸載 ASR 引擎失敗（%s）：%s", self._active_id, exc)
            self._active = None
            self._active_id = None

    # ------------------------------------------------------------------
    # 啟動載入
    # ------------------------------------------------------------------

    @staticmethod
    def _resolve_engine_from_manifest(model_id: str) -> Optional[str]:
        """查詢 manifest 取得模型對應的引擎 ID。

        讀取 models/manifest.json，找到 id == model_id 的條目，
        取得其 inference_engine 欄位，再透過 _INFERENCE_ENGINE_ALIAS 轉換。
        找不到時回傳 None。
        """
        try:
            with _MANIFEST_PATH.open(encoding="utf-8") as f:
                manifest = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return None

        for entry in manifest.get("models", []):
            if entry.get("id") == model_id:
                engine = entry.get("inference_engine", "")
                return _INFERENCE_ENGINE_ALIAS.get(engine, engine) or None
        return None

    @staticmethod
    def _resolve_model_path_from_manifest(model_id: str) -> Optional[str]:
        """從 manifest 解析模型的本機存放路徑。

        查詢 manifest 中 model_id 對應的 filename，組合為
        ``~/.airtype/models/{filename}``（單檔）或
        ``~/.airtype/models/{stem}/``（zip 解壓目錄）。

        Returns:
            模型路徑字串，若 manifest 中找不到則回傳 None。
        """
        try:
            with _MANIFEST_PATH.open(encoding="utf-8") as f:
                manifest = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return None
        for entry in manifest.get("models", []):
            if entry.get("id") == model_id:
                filename = entry.get("filename", "")
                if not filename:
                    return None
                models_dir = Path.home() / ".airtype" / "models"
                # zip 類模型解壓為目錄（去掉 .zip 副檔名）
                if filename.endswith(".zip"):
                    return str(models_dir / Path(filename).stem)
                return str(models_dir / filename)
        return None

    def _prepare_active_engine(self, model_id: str) -> None:
        """嘗試為當前作用中引擎設定模型路徑（延遲載入）。

        若引擎有 ``prepare`` 方法，從 manifest 解析模型路徑後呼叫之。
        失敗時僅記錄警告，不阻擋引擎登錄。
        """
        engine = self._active
        if engine is None or not hasattr(engine, "prepare"):
            return
        model_path = self._resolve_model_path_from_manifest(model_id)
        if model_path:
            try:
                engine.prepare(model_path)
                logger.debug("已設定引擎模型路徑：%s", model_path)
            except Exception as exc:  # noqa: BLE001
                logger.warning("設定引擎模型路徑失敗：%s", exc)
        else:
            logger.warning(
                "無法從 manifest 解析模型 %r 的本機路徑，引擎將在首次辨識時失敗",
                model_id,
            )

    def load_default_engine(self, config) -> None:
        """依設定的 voice.asr_model + voice.asr_inference_backend 載入預設引擎。

        解析策略：
        1. 直接匹配：若 model_id 為已登錄的引擎 ID，直接使用
        2. Manifest 解析：查詢 manifest 的 inference_engine 欄位，
           確定該模型需要的引擎 ID
        3. 家族映射後備：若 model_id 在 _MODEL_ENGINE_MAP 中，依 backend 選擇引擎
           - auto：遍歷候選清單，選第一個已登錄的引擎
           - 特定值：篩選包含 backend 子字串的引擎 ID
        4. 失敗：記錄 WARNING 並保持無作用中引擎

        Args:
            config: AirtypeConfig 實例。
        """
        model_id: str = config.voice.asr_model
        backend: str = config.voice.asr_inference_backend

        # 階段 1：直接匹配引擎 ID
        if model_id in self._factories:
            try:
                self.set_active_engine(model_id)
                self._prepare_active_engine(model_id)
                logger.debug("load_default_engine 直接匹配：%s", model_id)
                return
            except KeyError:
                pass

        # 階段 2：Manifest 解析——根據模型條目的 inference_engine 決定引擎
        manifest_engine = self._resolve_engine_from_manifest(model_id)
        if manifest_engine and manifest_engine in self._factories:
            self.set_active_engine(manifest_engine)
            self._prepare_active_engine(model_id)
            logger.debug(
                "load_default_engine manifest 解析：%s → %s",
                model_id, manifest_engine,
            )
            return

        # 階段 3：家族映射後備
        candidates = _MODEL_ENGINE_MAP.get(model_id)
        if candidates is not None:
            if backend == "auto":
                for engine_id in candidates:
                    if engine_id in self._factories:
                        self.set_active_engine(engine_id)
                        self._prepare_active_engine(model_id)
                        logger.debug(
                            "load_default_engine 家族映射（auto）：%s → %s",
                            model_id, engine_id,
                        )
                        return
            else:
                for engine_id in candidates:
                    if backend in engine_id and engine_id in self._factories:
                        self.set_active_engine(engine_id)
                        self._prepare_active_engine(model_id)
                        logger.debug(
                            "load_default_engine 家族映射（%s）：%s → %s",
                            backend, model_id, engine_id,
                        )
                        return

        # 階段 4：失敗
        logger.warning(
            "設定指定的 ASR 模型 %r（backend=%r）無法解析為已登錄引擎，保持無作用中引擎",
            model_id, backend,
        )
