"""模型下載管理器測試。

涵蓋：
- 帶進度回報的模型下載（mock httpx）
- SHA-256 完整性驗證（校驗碼匹配/不匹配）
- 備用下載 URL（主 URL 失敗時重試）
- 磁碟空間驗證
- 模型 manifest 讀取
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, call, mock_open, patch

from airtype.utils.model_manager import (
    DownloadError,
    DiskSpaceError,
    ModelManager,
    ModelInfo,
)


# ---------------------------------------------------------------------------
# 測試輔助
# ---------------------------------------------------------------------------


def _sha256_of(data: bytes) -> str:
    """計算 bytes 的 SHA-256 十六進位字串。"""
    return hashlib.sha256(data).hexdigest()


# ---------------------------------------------------------------------------
# 3.3a 帶進度回報的下載測試
# ---------------------------------------------------------------------------


class TestModelDownloadProgress(unittest.TestCase):
    """下載進度回報測試：callback 應週期性被呼叫。"""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.manifest_path = Path(self.tmp) / "manifest.json"
        content = b"fake model content"
        self.expected_hash = _sha256_of(content)
        self.fake_content = content

        manifest = {
            "models": [
                {
                    "id": "test-model",
                    "filename": "model.bin",
                    "size_bytes": len(content),
                    "urls": ["https://example.com/model.bin"],
                    "fallback_urls": [],
                    "sha256": self.expected_hash,
                }
            ]
        }
        self.manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    def test_progress_callback_invoked(self):
        """下載時應至少呼叫一次 progress callback。"""
        progress_calls = []

        def progress_cb(downloaded, total, percent, eta):
            progress_calls.append((downloaded, total, percent))

        manager = ModelManager(
            manifest_path=str(self.manifest_path),
            download_dir=self.tmp,
        )

        # mock httpx 下載
        fake_response = MagicMock()
        fake_response.headers = {"content-length": str(len(self.fake_content))}
        fake_response.iter_bytes.return_value = iter([self.fake_content])
        fake_response.__enter__ = lambda s: s
        fake_response.__exit__ = MagicMock(return_value=False)

        with patch("httpx.stream", return_value=fake_response):
            manager.download("test-model", progress_callback=progress_cb)

        self.assertGreater(len(progress_calls), 0)

    def test_progress_values_increase(self):
        """progress callback 的 downloaded 值應遞增。"""
        progress_calls = []

        chunk1 = b"chunk_one_data"
        chunk2 = b"chunk_two_data"
        full = chunk1 + chunk2
        expected_hash = _sha256_of(full)

        # 更新 manifest
        manifest = {
            "models": [
                {
                    "id": "test-model-2",
                    "filename": "model2.bin",
                    "size_bytes": len(full),
                    "urls": ["https://example.com/model2.bin"],
                    "fallback_urls": [],
                    "sha256": expected_hash,
                }
            ]
        }
        self.manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

        def progress_cb(downloaded, total, percent, eta):
            progress_calls.append(downloaded)

        manager = ModelManager(
            manifest_path=str(self.manifest_path),
            download_dir=self.tmp,
        )

        fake_response = MagicMock()
        fake_response.headers = {"content-length": str(len(full))}
        fake_response.iter_bytes.return_value = iter([chunk1, chunk2])
        fake_response.__enter__ = lambda s: s
        fake_response.__exit__ = MagicMock(return_value=False)

        with patch("httpx.stream", return_value=fake_response):
            manager.download("test-model-2", progress_callback=progress_cb)

        # downloaded 應單調遞增
        self.assertGreater(len(progress_calls), 1)
        for i in range(1, len(progress_calls)):
            self.assertGreaterEqual(progress_calls[i], progress_calls[i - 1])


# ---------------------------------------------------------------------------
# 3.3b SHA-256 完整性驗證測試
# ---------------------------------------------------------------------------


class TestDownloadIntegrityVerification(unittest.TestCase):
    """SHA-256 完整性驗證測試。"""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def _make_manifest(self, model_id: str, sha256: str, content_size: int) -> str:
        manifest = {
            "models": [
                {
                    "id": model_id,
                    "filename": f"{model_id}.bin",
                    "size_bytes": content_size,
                    "urls": [f"https://example.com/{model_id}.bin"],
                    "fallback_urls": [],
                    "sha256": sha256,
                }
            ]
        }
        path = Path(self.tmp) / "manifest.json"
        path.write_text(json.dumps(manifest), encoding="utf-8")
        return str(path)

    def test_checksum_match_marks_model_available(self):
        """SHA-256 匹配時，下載的檔案應存在且可用。"""
        content = b"valid model bytes"
        expected_hash = _sha256_of(content)
        manifest_path = self._make_manifest("valid-model", expected_hash, len(content))

        manager = ModelManager(manifest_path=manifest_path, download_dir=self.tmp)

        fake_response = MagicMock()
        fake_response.headers = {"content-length": str(len(content))}
        fake_response.iter_bytes.return_value = iter([content])
        fake_response.__enter__ = lambda s: s
        fake_response.__exit__ = MagicMock(return_value=False)

        with patch("httpx.stream", return_value=fake_response):
            result_path = manager.download("valid-model")

        self.assertTrue(os.path.exists(result_path))

    def test_checksum_mismatch_deletes_file(self):
        """SHA-256 不匹配時，應刪除下載檔案並拋出 DownloadError。"""
        content = b"corrupted model bytes"
        wrong_hash = "a" * 64  # 錯誤的 SHA-256
        manifest_path = self._make_manifest("bad-model", wrong_hash, len(content))

        manager = ModelManager(manifest_path=manifest_path, download_dir=self.tmp)

        fake_response = MagicMock()
        fake_response.headers = {"content-length": str(len(content))}
        fake_response.iter_bytes.return_value = iter([content])
        fake_response.__enter__ = lambda s: s
        fake_response.__exit__ = MagicMock(return_value=False)

        with patch("httpx.stream", return_value=fake_response):
            with self.assertRaises(DownloadError):
                manager.download("bad-model")

        # 損壞的檔案應已刪除
        dest_path = Path(self.tmp) / "bad-model.bin"
        self.assertFalse(dest_path.exists())


# ---------------------------------------------------------------------------
# 3.3c 備用下載 URL 測試
# ---------------------------------------------------------------------------


class TestFallbackDownloadUrls(unittest.TestCase):
    """備用 URL 測試：主 URL 失敗時自動重試備用 URL。"""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        content = b"fallback model content"
        self.content = content
        self.expected_hash = _sha256_of(content)

    def _make_manifest(self, urls, fallback_urls):
        manifest = {
            "models": [
                {
                    "id": "fallback-model",
                    "filename": "fallback-model.bin",
                    "size_bytes": len(self.content),
                    "urls": urls,
                    "fallback_urls": fallback_urls,
                    "sha256": self.expected_hash,
                }
            ]
        }
        path = Path(self.tmp) / "manifest.json"
        path.write_text(json.dumps(manifest), encoding="utf-8")
        return str(path)

    def test_fallback_url_used_when_primary_fails(self):
        """主 URL 失敗時應自動嘗試備用 URL。"""
        import httpx

        manifest_path = self._make_manifest(
            urls=["https://primary.example.com/model.bin"],
            fallback_urls=["https://fallback.example.com/model.bin"],
        )
        manager = ModelManager(manifest_path=manifest_path, download_dir=self.tmp)

        call_count = [0]

        def mock_stream(method, url, **kwargs):
            call_count[0] += 1
            if "primary" in url:
                raise httpx.ConnectError("primary failed")
            # fallback 成功
            fake_response = MagicMock()
            fake_response.headers = {"content-length": str(len(self.content))}
            fake_response.iter_bytes.return_value = iter([self.content])
            fake_response.__enter__ = lambda s: s
            fake_response.__exit__ = MagicMock(return_value=False)
            return fake_response

        with patch("httpx.stream", side_effect=mock_stream):
            result_path = manager.download("fallback-model")

        self.assertEqual(call_count[0], 2)  # 主 URL + 備用 URL 各呼叫一次
        self.assertTrue(os.path.exists(result_path))

    def test_all_urls_fail_raises_download_error(self):
        """所有 URL 均失敗時應拋出 DownloadError。"""
        import httpx

        manifest_path = self._make_manifest(
            urls=["https://primary.example.com/model.bin"],
            fallback_urls=["https://fallback.example.com/model.bin"],
        )
        manager = ModelManager(manifest_path=manifest_path, download_dir=self.tmp)

        with patch("httpx.stream", side_effect=httpx.ConnectError("all failed")):
            with self.assertRaises(DownloadError):
                manager.download("fallback-model")


# ---------------------------------------------------------------------------
# 1.3 download() 無 Token 直接走 Fallback URL 測試
# ---------------------------------------------------------------------------


class TestNoTokenFallbackSkip(unittest.TestCase):
    """Spec scenario: 無 HuggingFace token 時直接使用 fallback URL，跳過主 HF URL。"""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.fallback_content = b"fallback model content"
        self.expected_hash = _sha256_of(self.fallback_content)

    def _make_manifest(self, primary_urls, fallback_urls):
        manifest = {
            "models": [
                {
                    "id": "gated-model",
                    "filename": "gated-model.bin",
                    "size_bytes": len(self.fallback_content),
                    "urls": primary_urls,
                    "fallback_urls": fallback_urls,
                    "sha256": self.expected_hash,
                }
            ]
        }
        path = Path(self.tmp) / "manifest.json"
        path.write_text(json.dumps(manifest), encoding="utf-8")
        return str(path)

    def test_no_token_hf_primary_skips_to_fallback(self):
        """無 token 且主 URL 為 HuggingFace 時，應跳過主 URL 直接使用 fallback URL。"""
        primary_url = "https://huggingface.co/Qwen/Qwen3-ASR-1.7B/resolve/main/model.bin"
        fallback_url = "https://mirror.example.com/model.bin"

        manifest_path = self._make_manifest([primary_url], [fallback_url])

        called_urls = []

        def mock_stream(method, url, **kwargs):
            called_urls.append(url)
            fake = MagicMock()
            fake.status_code = 200
            fake.headers = {"content-length": str(len(self.fallback_content))}
            fake.iter_bytes.return_value = iter([self.fallback_content])
            fake.raise_for_status = MagicMock()
            fake.__enter__ = lambda s: s
            fake.__exit__ = MagicMock(return_value=False)
            return fake

        env_without_hf = {k: v for k, v in os.environ.items() if k != "HF_TOKEN"}
        manager = ModelManager(manifest_path=manifest_path, download_dir=self.tmp)

        with patch("airtype.config.get_api_key", return_value=None), \
             patch.dict(os.environ, env_without_hf, clear=True), \
             patch("pathlib.Path.home", return_value=Path(self.tmp)), \
             patch("httpx.stream", side_effect=mock_stream):
            manager.download("gated-model")

        # 主 HuggingFace URL 不應被呼叫
        self.assertNotIn(primary_url, called_urls)
        # fallback URL 應被呼叫
        self.assertIn(fallback_url, called_urls)

    def test_with_token_uses_primary_hf_url(self):
        """有 token 時應使用主 HuggingFace URL（不跳過）。"""
        primary_url = "https://huggingface.co/Qwen/Qwen3-ASR-1.7B/resolve/main/model.bin"
        fallback_url = "https://mirror.example.com/model.bin"

        manifest_path = self._make_manifest([primary_url], [fallback_url])

        called_urls = []

        def mock_stream(method, url, **kwargs):
            called_urls.append(url)
            fake = MagicMock()
            fake.status_code = 200
            fake.headers = {"content-length": str(len(self.fallback_content))}
            fake.iter_bytes.return_value = iter([self.fallback_content])
            fake.raise_for_status = MagicMock()
            fake.__enter__ = lambda s: s
            fake.__exit__ = MagicMock(return_value=False)
            return fake

        manager = ModelManager(manifest_path=manifest_path, download_dir=self.tmp)

        with patch("airtype.config.get_api_key", return_value="hf_valid_token"), \
             patch("httpx.stream", side_effect=mock_stream):
            manager.download("gated-model")

        # 有 token 時應嘗試主 URL
        self.assertIn(primary_url, called_urls)

    def test_no_token_no_fallback_uses_primary(self):
        """無 token 且無 fallback URL 時，應仍嘗試主 URL（符合規格「無 fallback 則走主 URL」）。"""
        primary_url = "https://huggingface.co/Qwen/Qwen3-ASR-1.7B/resolve/main/model.bin"

        manifest_path = self._make_manifest([primary_url], [])

        called_urls = []

        def mock_stream(method, url, **kwargs):
            called_urls.append(url)
            fake = MagicMock()
            fake.status_code = 200
            fake.headers = {"content-length": str(len(self.fallback_content))}
            fake.iter_bytes.return_value = iter([self.fallback_content])
            fake.raise_for_status = MagicMock()
            fake.__enter__ = lambda s: s
            fake.__exit__ = MagicMock(return_value=False)
            return fake

        env_without_hf = {k: v for k, v in os.environ.items() if k != "HF_TOKEN"}
        manager = ModelManager(manifest_path=manifest_path, download_dir=self.tmp)

        with patch("airtype.config.get_api_key", return_value=None), \
             patch.dict(os.environ, env_without_hf, clear=True), \
             patch("pathlib.Path.home", return_value=Path(self.tmp)), \
             patch("httpx.stream", side_effect=mock_stream):
            manager.download("gated-model")

        # 無 fallback 時應嘗試主 URL
        self.assertIn(primary_url, called_urls)


# ---------------------------------------------------------------------------
# 3.3d 磁碟空間驗證測試
# ---------------------------------------------------------------------------


class TestDiskSpaceValidation(unittest.TestCase):
    """磁碟空間驗證：空間不足時應拒絕下載。"""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def _make_manifest(self, model_id: str, size_bytes: int) -> str:
        manifest = {
            "models": [
                {
                    "id": model_id,
                    "filename": f"{model_id}.bin",
                    "size_bytes": size_bytes,
                    "urls": [f"https://example.com/{model_id}.bin"],
                    "fallback_urls": [],
                    "sha256": "a" * 64,
                }
            ]
        }
        path = Path(self.tmp) / "manifest.json"
        path.write_text(json.dumps(manifest), encoding="utf-8")
        return str(path)

    def test_insufficient_disk_space_raises_error(self):
        """磁碟空間不足時應拋出 DiskSpaceError，且不啟動下載。"""
        # 模型宣稱需要 10GB，但只有 1GB 可用
        model_size = 10 * 1024 * 1024 * 1024  # 10 GB
        available = 1 * 1024 * 1024 * 1024    # 1 GB

        manifest_path = self._make_manifest("large-model", model_size)
        manager = ModelManager(manifest_path=manifest_path, download_dir=self.tmp)

        fake_usage = MagicMock()
        fake_usage.free = available

        with patch("shutil.disk_usage", return_value=fake_usage):
            with self.assertRaises(DiskSpaceError) as ctx:
                manager.download("large-model")

        err = ctx.exception
        self.assertIn("required", str(err).lower() + str(type(err)).lower() + repr(err).lower())

    def test_sufficient_disk_space_allows_download(self):
        """磁碟空間充足時應允許下載。"""
        content = b"small model"
        expected_hash = _sha256_of(content)
        size_bytes = len(content)
        available = 100 * 1024 * 1024  # 100 MB

        manifest = {
            "models": [
                {
                    "id": "small-model",
                    "filename": "small-model.bin",
                    "size_bytes": size_bytes,
                    "urls": ["https://example.com/small.bin"],
                    "fallback_urls": [],
                    "sha256": expected_hash,
                }
            ]
        }
        manifest_path = Path(self.tmp) / "manifest.json"
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

        manager = ModelManager(manifest_path=str(manifest_path), download_dir=self.tmp)

        fake_usage = MagicMock()
        fake_usage.free = available

        fake_response = MagicMock()
        fake_response.headers = {"content-length": str(size_bytes)}
        fake_response.iter_bytes.return_value = iter([content])
        fake_response.__enter__ = lambda s: s
        fake_response.__exit__ = MagicMock(return_value=False)

        with patch("shutil.disk_usage", return_value=fake_usage):
            with patch("httpx.stream", return_value=fake_response):
                result_path = manager.download("small-model")

        self.assertTrue(os.path.exists(result_path))


# ---------------------------------------------------------------------------
# 3.3e 模型 manifest 測試
# ---------------------------------------------------------------------------


class TestModelManifest(unittest.TestCase):
    """模型 manifest 測試：初始化時應載入並解析 manifest。"""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def test_manifest_loaded_on_init(self):
        """初始化時應讀取 manifest 並取得可用模型列表。"""
        manifest = {
            "models": [
                {
                    "id": "model-a",
                    "filename": "model-a.bin",
                    "size_bytes": 1024,
                    "urls": ["https://example.com/model-a.bin"],
                    "fallback_urls": [],
                    "sha256": "a" * 64,
                },
                {
                    "id": "model-b",
                    "filename": "model-b.bin",
                    "size_bytes": 2048,
                    "urls": ["https://example.com/model-b.bin"],
                    "fallback_urls": ["https://backup.example.com/model-b.bin"],
                    "sha256": "b" * 64,
                },
            ]
        }
        path = Path(self.tmp) / "manifest.json"
        path.write_text(json.dumps(manifest), encoding="utf-8")

        manager = ModelManager(manifest_path=str(path), download_dir=self.tmp)
        models = manager.list_models()

        self.assertEqual(len(models), 2)
        ids = [m.id for m in models]
        self.assertIn("model-a", ids)
        self.assertIn("model-b", ids)

    def test_model_info_fields(self):
        """ModelInfo 應包含 id, filename, size_bytes, urls, fallback_urls, sha256。"""
        info = ModelInfo(
            id="test",
            filename="test.bin",
            size_bytes=1024,
            urls=["https://example.com/test.bin"],
            fallback_urls=[],
            sha256="a" * 64,
        )
        self.assertEqual(info.id, "test")
        self.assertEqual(info.filename, "test.bin")
        self.assertEqual(info.size_bytes, 1024)
        self.assertEqual(len(info.urls), 1)

    def test_is_downloaded_returns_false_when_not_present(self):
        """模型檔案不存在時 is_downloaded 應回傳 False。"""
        manifest = {
            "models": [
                {
                    "id": "absent-model",
                    "filename": "absent.bin",
                    "size_bytes": 1024,
                    "urls": ["https://example.com/absent.bin"],
                    "fallback_urls": [],
                    "sha256": "a" * 64,
                }
            ]
        }
        path = Path(self.tmp) / "manifest.json"
        path.write_text(json.dumps(manifest), encoding="utf-8")

        manager = ModelManager(manifest_path=str(path), download_dir=self.tmp)
        self.assertFalse(manager.is_downloaded("absent-model"))

    def test_is_downloaded_returns_true_when_file_exists(self):
        """模型檔案已存在時 is_downloaded 應回傳 True。"""
        manifest = {
            "models": [
                {
                    "id": "present-model",
                    "filename": "present.bin",
                    "size_bytes": 5,
                    "urls": ["https://example.com/present.bin"],
                    "fallback_urls": [],
                    "sha256": "a" * 64,
                }
            ]
        }
        path = Path(self.tmp) / "manifest.json"
        path.write_text(json.dumps(manifest), encoding="utf-8")

        # 建立假的已下載檔案
        (Path(self.tmp) / "present.bin").write_bytes(b"hello")

        manager = ModelManager(manifest_path=str(path), download_dir=self.tmp)
        self.assertTrue(manager.is_downloaded("present-model"))

    def test_unknown_model_raises_key_error(self):
        """請求不存在的模型 ID 應拋出 KeyError 或 ValueError。"""
        manifest = {"models": []}
        path = Path(self.tmp) / "manifest.json"
        path.write_text(json.dumps(manifest), encoding="utf-8")

        manager = ModelManager(manifest_path=str(path), download_dir=self.tmp)

        with self.assertRaises((KeyError, ValueError)):
            manager.download("nonexistent-model")


# ---------------------------------------------------------------------------
# W1：SHA-256 失敗後重試備用 URL
# ---------------------------------------------------------------------------


class TestChecksumFailureRetry(unittest.TestCase):
    """W1 修正驗證：校驗和失敗時應嘗試備用 URL。"""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def test_checksum_failure_retries_fallback_url(self):
        """主 URL 下載成功但 SHA-256 不符時，應自動嘗試備用 URL。"""
        bad_content = b"corrupted_content_bytes"
        good_content = b"correct_content_bytes!"
        expected_hash = _sha256_of(good_content)

        manifest = {
            "models": [
                {
                    "id": "retry-model",
                    "filename": "retry.bin",
                    "size_bytes": len(good_content),
                    "urls": ["https://primary.example.com/retry.bin"],
                    "fallback_urls": ["https://fallback.example.com/retry.bin"],
                    "sha256": expected_hash,
                }
            ]
        }
        manifest_path = Path(self.tmp) / "manifest.json"
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

        call_count = [0]

        def mock_stream(method, url, **kwargs):
            call_count[0] += 1
            content = bad_content if "primary" in url else good_content
            fake_response = MagicMock()
            fake_response.status_code = 200
            fake_response.headers = {"content-length": str(len(content))}
            fake_response.iter_bytes.return_value = iter([content])
            fake_response.raise_for_status = MagicMock()
            fake_response.__enter__ = lambda s: s
            fake_response.__exit__ = MagicMock(return_value=False)
            return fake_response

        manager = ModelManager(manifest_path=str(manifest_path), download_dir=self.tmp)

        with patch("httpx.stream", side_effect=mock_stream):
            result_path = manager.download("retry-model")

        # 主 URL + 備用 URL 各呼叫一次
        self.assertEqual(call_count[0], 2)
        # 最終檔案應為備用 URL 的正確內容
        self.assertEqual(Path(result_path).read_bytes(), good_content)

    def test_checksum_failure_all_urls_raises_download_error(self):
        """所有 URL 下載均通過但 SHA-256 均不符時，應拋出 DownloadError。"""
        bad_content = b"always_corrupted_bytes"
        expected_hash = "a" * 64  # 永遠不匹配

        manifest = {
            "models": [
                {
                    "id": "always-bad",
                    "filename": "bad.bin",
                    "size_bytes": len(bad_content),
                    "urls": ["https://primary.example.com/bad.bin"],
                    "fallback_urls": ["https://fallback.example.com/bad.bin"],
                    "sha256": expected_hash,
                }
            ]
        }
        manifest_path = Path(self.tmp) / "manifest.json"
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

        def mock_stream(method, url, **kwargs):
            fake_response = MagicMock()
            fake_response.status_code = 200
            fake_response.headers = {"content-length": str(len(bad_content))}
            fake_response.iter_bytes.return_value = iter([bad_content])
            fake_response.raise_for_status = MagicMock()
            fake_response.__enter__ = lambda s: s
            fake_response.__exit__ = MagicMock(return_value=False)
            return fake_response

        manager = ModelManager(manifest_path=str(manifest_path), download_dir=self.tmp)

        with patch("httpx.stream", side_effect=mock_stream):
            with self.assertRaises(DownloadError):
                manager.download("always-bad")

        # 下載失敗後，最終目標檔案不應存在
        self.assertFalse((Path(self.tmp) / "bad.bin").exists())


# ---------------------------------------------------------------------------
# W2：中斷後續傳（Range header + .tmp 暫存檔）
# ---------------------------------------------------------------------------


class TestResumeDownload(unittest.TestCase):
    """W2 修正驗證：下載中斷後應以 Range header 續傳。"""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def _make_manifest(self, model_id: str, filename: str,
                       size_bytes: int, sha256: str) -> str:
        manifest = {
            "models": [
                {
                    "id": model_id,
                    "filename": filename,
                    "size_bytes": size_bytes,
                    "urls": [f"https://example.com/{filename}"],
                    "fallback_urls": [],
                    "sha256": sha256,
                }
            ]
        }
        path = Path(self.tmp) / "manifest.json"
        path.write_text(json.dumps(manifest), encoding="utf-8")
        return str(path)

    def test_range_header_sent_when_tmp_file_exists(self):
        """暫存檔已存在時，應以 Range header 從斷點繼續下載。"""
        existing = b"existing_partial_"   # 17 bytes：模擬前次已下載的部分
        remaining = b"remaining_content"  # 17 bytes：本次補充下載
        full_content = existing + remaining
        expected_hash = _sha256_of(full_content)

        manifest_path = self._make_manifest(
            "resume-model", "resume.bin", len(full_content), expected_hash
        )

        # 預先建立暫存檔（模擬前次中斷後殘留的部分下載）
        dest = Path(self.tmp) / "resume.bin"
        tmp_path = dest.with_suffix(dest.suffix + ".tmp")
        tmp_path.write_bytes(existing)

        captured_kwargs: dict = {}

        def mock_stream(method, url, **kwargs):
            captured_kwargs.update(kwargs)
            fake_response = MagicMock()
            fake_response.status_code = 206  # Partial Content
            fake_response.headers = {"content-length": str(len(remaining))}
            fake_response.iter_bytes.return_value = iter([remaining])
            fake_response.raise_for_status = MagicMock()
            fake_response.__enter__ = lambda s: s
            fake_response.__exit__ = MagicMock(return_value=False)
            return fake_response

        manager = ModelManager(manifest_path=manifest_path, download_dir=self.tmp)

        with patch("httpx.stream", side_effect=mock_stream):
            result_path = manager.download("resume-model")

        # 應傳送 Range header，從暫存檔大小作為 offset
        self.assertIn("headers", captured_kwargs)
        self.assertIn("Range", captured_kwargs["headers"])
        self.assertEqual(
            captured_kwargs["headers"]["Range"],
            f"bytes={len(existing)}-",
        )

        # 最終檔案應包含完整內容（existing + remaining）
        self.assertEqual(Path(result_path).read_bytes(), full_content)

    def test_no_range_header_when_no_tmp_file(self):
        """無暫存檔時，不應傳送 Range header（全新下載）。"""
        content = b"fresh_download_content"
        expected_hash = _sha256_of(content)

        manifest_path = self._make_manifest(
            "fresh-model", "fresh.bin", len(content), expected_hash
        )

        captured_kwargs: dict = {}

        def mock_stream(method, url, **kwargs):
            captured_kwargs.update(kwargs)
            fake_response = MagicMock()
            fake_response.status_code = 200
            fake_response.headers = {"content-length": str(len(content))}
            fake_response.iter_bytes.return_value = iter([content])
            fake_response.raise_for_status = MagicMock()
            fake_response.__enter__ = lambda s: s
            fake_response.__exit__ = MagicMock(return_value=False)
            return fake_response

        manager = ModelManager(manifest_path=manifest_path, download_dir=self.tmp)

        with patch("httpx.stream", side_effect=mock_stream):
            manager.download("fresh-model")

        # headers 不應包含 Range
        headers_sent = captured_kwargs.get("headers", {})
        self.assertNotIn("Range", headers_sent)

    def test_server_ignores_range_falls_back_to_full_download(self):
        """伺服器不支援 Range（回應 200）時，應捨棄暫存重新完整下載。"""
        existing = b"stale_partial_bytes"
        full_content = b"complete_fresh_content"
        expected_hash = _sha256_of(full_content)

        manifest_path = self._make_manifest(
            "no-range-model", "no-range.bin", len(full_content), expected_hash
        )

        # 建立暫存檔
        dest = Path(self.tmp) / "no-range.bin"
        tmp_path = dest.with_suffix(dest.suffix + ".tmp")
        tmp_path.write_bytes(existing)

        def mock_stream(method, url, **kwargs):
            fake_response = MagicMock()
            fake_response.status_code = 200  # 不支援 Range，回應完整內容
            fake_response.headers = {"content-length": str(len(full_content))}
            fake_response.iter_bytes.return_value = iter([full_content])
            fake_response.raise_for_status = MagicMock()
            fake_response.__enter__ = lambda s: s
            fake_response.__exit__ = MagicMock(return_value=False)
            return fake_response

        manager = ModelManager(manifest_path=manifest_path, download_dir=self.tmp)

        with patch("httpx.stream", side_effect=mock_stream):
            result_path = manager.download("no-range-model")

        # 最終檔案應為完整的新內容（不含舊暫存）
        self.assertEqual(Path(result_path).read_bytes(), full_content)

    def test_tmp_file_cleaned_up_after_successful_download(self):
        """下載成功後，暫存檔應已被 rename（不再以 .tmp 存在）。"""
        content = b"clean_download_content"
        expected_hash = _sha256_of(content)

        manifest_path = self._make_manifest(
            "clean-model", "clean.bin", len(content), expected_hash
        )

        def mock_stream(method, url, **kwargs):
            fake_response = MagicMock()
            fake_response.status_code = 200
            fake_response.headers = {"content-length": str(len(content))}
            fake_response.iter_bytes.return_value = iter([content])
            fake_response.raise_for_status = MagicMock()
            fake_response.__enter__ = lambda s: s
            fake_response.__exit__ = MagicMock(return_value=False)
            return fake_response

        manager = ModelManager(manifest_path=manifest_path, download_dir=self.tmp)

        with patch("httpx.stream", side_effect=mock_stream):
            result_path = manager.download("clean-model")

        # .tmp 檔案不應存在
        tmp_path = Path(result_path).with_suffix(Path(result_path).suffix + ".tmp")
        self.assertFalse(tmp_path.exists())
        # 最終檔案應存在
        self.assertTrue(Path(result_path).exists())


# ---------------------------------------------------------------------------
# 5.2 list_models_by_category() 單元測試
# ---------------------------------------------------------------------------


class TestListModelsByCategory(unittest.TestCase):
    """list_models_by_category() 測試：分類過濾 ASR / LLM 模型。"""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.manifest = {
            "models": [
                {
                    "id": "asr-model-1",
                    "filename": "asr1.bin",
                    "size_bytes": 100,
                    "category": "asr",
                    "description": "ASR Model 1",
                    "inference_engine": "qwen3-openvino",
                    "has_thinking_mode": False,
                    "thinking_disable_token": None,
                    "urls": ["https://example.com/asr1.bin"],
                    "fallback_urls": [],
                    "sha256": "",
                },
                {
                    "id": "asr-model-2",
                    "filename": "asr2.bin",
                    "size_bytes": 200,
                    "category": "asr",
                    "description": "ASR Model 2",
                    "inference_engine": "sherpa-onnx",
                    "has_thinking_mode": False,
                    "thinking_disable_token": None,
                    "urls": ["https://example.com/asr2.bin"],
                    "fallback_urls": [],
                    "sha256": "",
                },
                {
                    "id": "llm-model-1",
                    "filename": "llm1.gguf",
                    "size_bytes": 1000,
                    "category": "llm",
                    "description": "LLM Model 1",
                    "inference_engine": "llama-cpp",
                    "has_thinking_mode": False,
                    "thinking_disable_token": None,
                    "urls": ["https://example.com/llm1.gguf"],
                    "fallback_urls": [],
                    "sha256": "",
                },
            ]
        }
        path = Path(self.tmp) / "manifest.json"
        path.write_text(json.dumps(self.manifest), encoding="utf-8")
        self.manifest_path = str(path)

    def test_list_asr_models_returns_only_asr(self):
        """list_models_by_category('asr') 應只回傳 ASR 條目。"""
        manager = ModelManager(manifest_path=self.manifest_path, download_dir=self.tmp)
        result = manager.list_models_by_category("asr")
        self.assertEqual(len(result), 2)
        for entry in result:
            self.assertEqual(entry["category"], "asr")

    def test_list_llm_models_returns_only_llm(self):
        """list_models_by_category('llm') 應只回傳 LLM 條目。"""
        manager = ModelManager(manifest_path=self.manifest_path, download_dir=self.tmp)
        result = manager.list_models_by_category("llm")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["id"], "llm-model-1")
        self.assertEqual(result[0]["category"], "llm")

    def test_unknown_category_returns_empty_list(self):
        """list_models_by_category('unknown') 應回傳空 list，不拋出例外。"""
        manager = ModelManager(manifest_path=self.manifest_path, download_dir=self.tmp)
        result = manager.list_models_by_category("unknown")
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 0)

    def test_result_contains_description_and_id(self):
        """回傳條目應包含 description 與 id 欄位（供 UI 下拉選單使用）。"""
        manager = ModelManager(manifest_path=self.manifest_path, download_dir=self.tmp)
        result = manager.list_models_by_category("asr")
        for entry in result:
            self.assertIn("id", entry)
            self.assertIn("description", entry)

    def test_asr_models_not_in_llm_results(self):
        """ASR 模型不應出現在 LLM 查詢結果中。"""
        manager = ModelManager(manifest_path=self.manifest_path, download_dir=self.tmp)
        llm_ids = [e["id"] for e in manager.list_models_by_category("llm")]
        self.assertNotIn("asr-model-1", llm_ids)
        self.assertNotIn("asr-model-2", llm_ids)

    def test_manifest_without_category_field_not_returned(self):
        """manifest 條目若無 category 欄位，不應出現在任何分類查詢結果中。"""
        manifest_no_cat = {
            "models": [
                {
                    "id": "legacy-model",
                    "filename": "legacy.bin",
                    "size_bytes": 100,
                    "urls": ["https://example.com/legacy.bin"],
                    "fallback_urls": [],
                    "sha256": "",
                }
            ]
        }
        path = Path(self.tmp) / "manifest_no_cat.json"
        path.write_text(json.dumps(manifest_no_cat), encoding="utf-8")
        manager = ModelManager(manifest_path=str(path), download_dir=self.tmp)
        result = manager.list_models_by_category("asr")
        self.assertEqual(len(result), 0)

    def test_thinking_mode_fields_readable_from_manifest(self):
        """has_thinking_mode=true 時，thinking_disable_token 應為非空字串且可從 manifest 讀取。"""
        manifest = {
            "models": [
                {
                    "id": "qwen3-thinking-model",
                    "filename": "qwen3.gguf",
                    "size_bytes": 1000,
                    "category": "llm",
                    "description": "Qwen3 with thinking mode",
                    "inference_engine": "llama-cpp",
                    "has_thinking_mode": True,
                    "thinking_disable_token": "/no_think",
                    "urls": ["https://example.com/qwen3.gguf"],
                    "fallback_urls": [],
                    "sha256": "",
                }
            ]
        }
        path = Path(self.tmp) / "manifest_thinking.json"
        path.write_text(json.dumps(manifest), encoding="utf-8")
        manager = ModelManager(manifest_path=str(path), download_dir=self.tmp)
        result = manager.list_models_by_category("llm")
        self.assertEqual(len(result), 1)
        entry = result[0]
        self.assertTrue(entry["has_thinking_mode"])
        self.assertIsNotNone(entry["thinking_disable_token"])
        self.assertIsInstance(entry["thinking_disable_token"], str)
        self.assertGreater(len(entry["thinking_disable_token"]), 0)

    def test_thinking_mode_false_has_null_disable_token(self):
        """has_thinking_mode=false 的條目，thinking_disable_token 應為 null。"""
        manifest = {
            "models": [
                {
                    "id": "no-thinking-model",
                    "filename": "model.gguf",
                    "size_bytes": 100,
                    "category": "llm",
                    "description": "No thinking mode",
                    "inference_engine": "llama-cpp",
                    "has_thinking_mode": False,
                    "thinking_disable_token": None,
                    "urls": ["https://example.com/model.gguf"],
                    "fallback_urls": [],
                    "sha256": "",
                }
            ]
        }
        path = Path(self.tmp) / "manifest_no_thinking.json"
        path.write_text(json.dumps(manifest), encoding="utf-8")
        manager = ModelManager(manifest_path=str(path), download_dir=self.tmp)
        result = manager.list_models_by_category("llm")
        entry = result[0]
        self.assertFalse(entry["has_thinking_mode"])
        self.assertIsNone(entry["thinking_disable_token"])


# ---------------------------------------------------------------------------
# 1.3 delete_model 測試
# ---------------------------------------------------------------------------


class TestDeleteModel(unittest.TestCase):
    """ModelManager.delete_model() 測試。"""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.manifest_path = Path(self.tmp) / "manifest.json"
        manifest = {
            "models": [
                {
                    "id": "test-asr",
                    "filename": "test_asr.bin",
                    "size_bytes": 100,
                    "category": "asr",
                    "description": "Test ASR",
                    "urls": ["https://example.com/test_asr.bin"],
                    "fallback_urls": [],
                    "sha256": "",
                }
            ]
        }
        self.manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        self.manager = ModelManager(
            manifest_path=str(self.manifest_path),
            download_dir=self.tmp,
        )

    def test_delete_existing_file_returns_true(self):
        """刪除已存在的模型檔案應回傳 True 並實際刪除。"""
        model_file = Path(self.tmp) / "test_asr.bin"
        model_file.write_bytes(b"fake model")
        result = self.manager.delete_model("test-asr")
        self.assertTrue(result)
        self.assertFalse(model_file.exists())

    def test_delete_nonexistent_file_returns_false(self):
        """刪除不存在的模型檔案應回傳 False 且不拋出例外。"""
        result = self.manager.delete_model("test-asr")
        self.assertFalse(result)

    def test_delete_unknown_model_id_raises_key_error(self):
        """傳入未知 model_id 應拋出 KeyError。"""
        with self.assertRaises(KeyError):
            self.manager.delete_model("nonexistent-model")


# ---------------------------------------------------------------------------
# 1.4 get_model_path 測試
# ---------------------------------------------------------------------------


class TestGetModelPath(unittest.TestCase):
    """ModelManager.get_model_path() 測試。"""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.manifest_path = Path(self.tmp) / "manifest.json"
        manifest = {
            "models": [
                {
                    "id": "test-asr",
                    "filename": "test_asr.bin",
                    "size_bytes": 100,
                    "category": "asr",
                    "description": "Test ASR",
                    "urls": ["https://example.com/test_asr.bin"],
                    "fallback_urls": [],
                    "sha256": "",
                }
            ]
        }
        self.manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        self.manager = ModelManager(
            manifest_path=str(self.manifest_path),
            download_dir=self.tmp,
        )

    def test_get_path_of_downloaded_model(self):
        """已下載模型應回傳絕對路徑字串。"""
        model_file = Path(self.tmp) / "test_asr.bin"
        model_file.write_bytes(b"fake model")
        result = self.manager.get_model_path("test-asr")
        self.assertIsNotNone(result)
        self.assertIsInstance(result, str)
        self.assertTrue(Path(result).is_absolute())
        self.assertTrue(Path(result).exists())

    def test_get_path_of_non_downloaded_model(self):
        """未下載模型應回傳 None。"""
        result = self.manager.get_model_path("test-asr")
        self.assertIsNone(result)

    def test_get_path_of_unknown_model_id(self):
        """未知 model_id 應回傳 None。"""
        result = self.manager.get_model_path("nonexistent-model")
        self.assertIsNone(result)


# ---------------------------------------------------------------------------
# 4.1 _get_hf_token() 單元測試
# ---------------------------------------------------------------------------


class TestGetHFToken(unittest.TestCase):
    """_get_hf_token() 測試：驗證 HuggingFace Token 來源優先順序。"""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        manifest = {"models": []}
        path = Path(self.tmp) / "manifest.json"
        path.write_text(json.dumps(manifest), encoding="utf-8")
        self.manager = ModelManager(manifest_path=str(path), download_dir=self.tmp)

    def test_keyring_token_takes_priority(self):
        """keyring 有 token 時應優先回傳 keyring 的 token。"""
        with patch("airtype.config.get_api_key", return_value="hf_keyring_token"), \
             patch.dict(os.environ, {"HF_TOKEN": "hf_env_token"}):
            token = self.manager._get_hf_token()
        self.assertEqual(token, "hf_keyring_token")

    def test_env_var_used_when_no_keyring(self):
        """keyring 無 token 時應使用環境變數 HF_TOKEN。"""
        with patch("airtype.config.get_api_key", return_value=None), \
             patch.dict(os.environ, {"HF_TOKEN": "hf_env_token"}):
            token = self.manager._get_hf_token()
        self.assertEqual(token, "hf_env_token")

    def test_cache_file_used_when_no_keyring_or_env(self):
        """keyring 和環境變數均無 token 時應使用快取檔。"""
        cache_dir = Path(self.tmp) / ".cache" / "huggingface"
        cache_dir.mkdir(parents=True)
        (cache_dir / "token").write_text("hf_cached_token", encoding="utf-8")

        env_without_hf = {k: v for k, v in os.environ.items() if k != "HF_TOKEN"}
        with patch("airtype.config.get_api_key", return_value=None), \
             patch.dict(os.environ, env_without_hf, clear=True), \
             patch("pathlib.Path.home", return_value=Path(self.tmp)):
            token = self.manager._get_hf_token()
        self.assertEqual(token, "hf_cached_token")

    def test_returns_none_when_no_token_available(self):
        """三個來源均無 token 時應回傳 None。"""
        env_without_hf = {k: v for k, v in os.environ.items() if k != "HF_TOKEN"}
        with patch("airtype.config.get_api_key", return_value=None), \
             patch.dict(os.environ, env_without_hf, clear=True), \
             patch("pathlib.Path.home", return_value=Path(self.tmp)):
            token = self.manager._get_hf_token()
        self.assertIsNone(token)

    def test_token_value_not_in_log(self):
        """token 明文不應出現在 log 訊息中。"""
        import logging
        with patch("airtype.config.get_api_key", return_value="secret_hf_token"):
            with self.assertLogs("airtype.utils.model_manager", level=logging.DEBUG) as cm:
                self.manager._get_hf_token()
        for msg in cm.output:
            self.assertNotIn("secret_hf_token", msg)


# ---------------------------------------------------------------------------
# 4.2 _download_url() Authorization header 測試
# ---------------------------------------------------------------------------


class TestDownloadUrlAuthHeader(unittest.TestCase):
    """_download_url() HuggingFace Authorization header 注入測試。"""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        content = b"model content"
        self.content = content
        manifest = {
            "models": [
                {
                    "id": "hf-model",
                    "filename": "hf_model.bin",
                    "size_bytes": len(content),
                    "urls": ["https://huggingface.co/org/repo/resolve/main/model.bin"],
                    "fallback_urls": [],
                    "sha256": _sha256_of(content),
                },
                {
                    "id": "other-model",
                    "filename": "other_model.bin",
                    "size_bytes": len(content),
                    "urls": ["https://example.com/model.bin"],
                    "fallback_urls": [],
                    "sha256": _sha256_of(content),
                },
            ]
        }
        path = Path(self.tmp) / "manifest.json"
        path.write_text(json.dumps(manifest), encoding="utf-8")
        self.manager = ModelManager(manifest_path=str(path), download_dir=self.tmp)

    def _make_fake_response(self, content=None):
        if content is None:
            content = self.content
        fake = MagicMock()
        fake.status_code = 200
        fake.headers = {"content-length": str(len(content))}
        fake.iter_bytes.return_value = iter([content])
        fake.raise_for_status = MagicMock()
        fake.__enter__ = lambda s: s
        fake.__exit__ = MagicMock(return_value=False)
        return fake

    def test_hf_url_injects_authorization_header(self):
        """HuggingFace URL 下載時應注入 Authorization Bearer header。"""
        captured = {}

        def mock_stream(method, url, **kwargs):
            captured.update(kwargs)
            return self._make_fake_response()

        with patch("airtype.config.get_api_key", return_value="hf_test_token"), \
             patch("httpx.stream", side_effect=mock_stream):
            dest = Path(self.tmp) / "hf_model.bin"
            self.manager._download_url(
                "https://huggingface.co/org/repo/resolve/main/model.bin",
                dest, len(self.content), None,
            )

        self.assertIn("headers", captured)
        self.assertIn("Authorization", captured["headers"])
        self.assertEqual(captured["headers"]["Authorization"], "Bearer hf_test_token")

    def test_non_hf_url_no_authorization_header(self):
        """非 HuggingFace URL 不應注入 Authorization header。"""
        captured = {}

        def mock_stream(method, url, **kwargs):
            captured.update(kwargs)
            return self._make_fake_response()

        with patch("airtype.config.get_api_key", return_value="hf_test_token"), \
             patch("httpx.stream", side_effect=mock_stream):
            dest = Path(self.tmp) / "other_model.bin"
            self.manager._download_url(
                "https://example.com/model.bin",
                dest, len(self.content), None,
            )

        headers_sent = captured.get("headers", {})
        self.assertNotIn("Authorization", headers_sent)

    def test_hf_url_no_token_no_authorization_header(self):
        """HuggingFace URL 但無 token 時，不應注入 Authorization header。"""
        captured = {}

        def mock_stream(method, url, **kwargs):
            captured.update(kwargs)
            return self._make_fake_response()

        env_without_hf = {k: v for k, v in os.environ.items() if k != "HF_TOKEN"}
        with patch("airtype.config.get_api_key", return_value=None), \
             patch.dict(os.environ, env_without_hf, clear=True), \
             patch("pathlib.Path.home", return_value=Path(self.tmp)), \
             patch("httpx.stream", side_effect=mock_stream):
            dest = Path(self.tmp) / "hf_model_notoken.bin"
            self.manager._download_url(
                "https://huggingface.co/org/repo/resolve/main/model.bin",
                dest, len(self.content), None,
            )

        headers_sent = captured.get("headers", {})
        self.assertNotIn("Authorization", headers_sent)


if __name__ == "__main__":
    unittest.main()
