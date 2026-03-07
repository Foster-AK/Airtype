"""tests/test_model_manager_hf_progress.py — HF 進度轉接器與 repo 下載單元測試。

驗證：
- _HfProgressAdapter 正確彙總多檔案進度
- _download_hf_repo 逐檔直接下載、進度彙總、ignore pattern 過濾
"""

import json
from pathlib import Path
from unittest import mock

import pytest


@pytest.fixture
def manifest_file(tmp_path: Path) -> Path:
    """建立最小 manifest.json 供 ModelManager 使用。"""
    manifest = {
        "models": [
            {
                "id": "test-hf-repo",
                "filename": "test-repo.zip",
                "size_bytes": 1000,
                "urls": ["https://huggingface.co/org/test-repo"],
                "fallback_urls": [],
                "sha256": "",
            }
        ]
    }
    p = tmp_path / "manifest.json"
    p.write_text(json.dumps(manifest), encoding="utf-8")
    return p


class TestSharedProgressAndAdapter:
    """_SharedProgress + _HfProgressAdapter 單元測試。"""

    def test_single_file_progress(self):
        """單一檔案的進度應正確回報。"""
        from airtype.utils.model_manager import _SharedProgress, _HfProgressAdapter

        callback_calls: list[tuple] = []

        def cb(downloaded, total, percent, eta):
            callback_calls.append((downloaded, total, percent, eta))

        shared = _SharedProgress(callback=cb)
        adapter = _HfProgressAdapter(total=1000, shared=shared)
        adapter.update(200)
        adapter.update(300)
        adapter.update(500)
        adapter.close()

        assert len(callback_calls) >= 3
        # 百分比應遞增
        percents = [c[2] for c in callback_calls]
        assert percents == sorted(percents)
        # 最終應達 100%
        assert callback_calls[-1][2] == pytest.approx(100.0)

    def test_multi_file_progress_aggregation(self):
        """多檔案的進度應彙總為單一百分比。"""
        from airtype.utils.model_manager import _SharedProgress, _HfProgressAdapter

        callback_calls: list[tuple] = []

        def cb(downloaded, total, percent, eta):
            callback_calls.append((downloaded, total, percent, eta))

        shared = _SharedProgress(callback=cb)
        # 檔案 A: 600 bytes, 檔案 B: 400 bytes → 總共 1000
        a = _HfProgressAdapter(total=600, shared=shared)
        b = _HfProgressAdapter(total=400, shared=shared)

        a.update(300)  # 300/1000 = 30%
        b.update(200)  # 500/1000 = 50%
        a.update(300)  # 800/1000 = 80%
        b.update(200)  # 1000/1000 = 100%
        a.close()
        b.close()

        # total 應為 1000
        assert callback_calls[-1][1] == 1000
        assert callback_calls[-1][0] == 1000
        assert callback_calls[-1][2] == pytest.approx(100.0)

        # 百分比遞增
        percents = [c[2] for c in callback_calls]
        assert percents == sorted(percents)

    def test_tqdm_api_compatibility(self):
        """_HfProgressAdapter 應實作 tqdm 最小 API。"""
        from airtype.utils.model_manager import _SharedProgress, _HfProgressAdapter

        shared = _SharedProgress(callback=lambda *a: None)
        adapter = _HfProgressAdapter(total=100, shared=shared)

        # context manager
        with adapter as a:
            assert a is adapter

        # set_description / set_postfix 不拋出例外
        adapter2 = _HfProgressAdapter(total=50, shared=shared)
        adapter2.set_description("downloading")
        adapter2.set_postfix(speed="1MB/s")
        adapter2.close()

    def test_adapter_without_total(self):
        """total 為 None 或 0 時應不拋出例外。"""
        from airtype.utils.model_manager import _SharedProgress, _HfProgressAdapter

        shared = _SharedProgress(callback=lambda *a: None)
        adapter = _HfProgressAdapter(total=None, shared=shared)
        adapter.update(100)
        adapter.close()

    @pytest.fixture(autouse=False)
    def _reset_lock(self):
        """確保 _lock 在測試前後都被重置，即使測試失敗也不洩漏狀態。"""
        from airtype.utils.model_manager import _HfProgressAdapter
        _HfProgressAdapter._lock = None
        yield
        _HfProgressAdapter._lock = None

    def test_get_lock_returns_lock_and_caches(self, _reset_lock):
        """get_lock() 應回傳 Lock 實例且多次呼叫回傳同一物件。"""
        from airtype.utils.model_manager import _HfProgressAdapter

        lock1 = _HfProgressAdapter.get_lock()
        lock2 = _HfProgressAdapter.get_lock()
        assert hasattr(lock1, "acquire") and hasattr(lock1, "release")
        assert lock1 is lock2

    def test_set_lock(self, _reset_lock):
        """set_lock() 應設定 class-level lock。"""
        import threading
        from airtype.utils.model_manager import _HfProgressAdapter

        custom_lock = threading.Lock()
        _HfProgressAdapter.set_lock(custom_lock)
        assert _HfProgressAdapter._lock is custom_lock
        assert _HfProgressAdapter.get_lock() is custom_lock

    def test_positional_iterable_and_iter(self):
        """__init__ 接受 positional iterable 且 __iter__ 正確迭代。"""
        from airtype.utils.model_manager import _SharedProgress, _HfProgressAdapter

        shared = _SharedProgress(callback=lambda *a: None)
        adapter = _HfProgressAdapter(iter([1, 2, 3]), shared=shared, total=3)
        result = list(adapter)
        assert result == [1, 2, 3]

    def test_shared_optional_update_no_error(self):
        """shared 為 None 時 update() 不應報錯。"""
        from airtype.utils.model_manager import _HfProgressAdapter

        adapter = _HfProgressAdapter(total=10)
        adapter.update(5)
        adapter.close()


class TestMatchesIgnorePattern:
    """_matches_ignore_pattern 單元測試。"""

    def test_matches_wildcard(self):
        from airtype.utils.model_manager import ModelManager
        assert ModelManager._matches_ignore_pattern("model.int8.onnx", ["*.int8.onnx"])

    def test_matches_directory_pattern(self):
        from airtype.utils.model_manager import ModelManager
        assert ModelManager._matches_ignore_pattern("test_wavs/audio.wav", ["test_wavs/*"])

    def test_no_match(self):
        from airtype.utils.model_manager import ModelManager
        assert not ModelManager._matches_ignore_pattern("model.bin", ["*.onnx", "*.png"])

    def test_exact_match(self):
        from airtype.utils.model_manager import ModelManager
        assert ModelManager._matches_ignore_pattern("optimizer.bin", ["optimizer.bin"])


class TestDownloadHfRepoProgress:
    """_download_hf_repo 方法整合測試（逐檔直接下載）。"""

    def test_downloads_files_individually_with_progress(
        self, manifest_file: Path, tmp_path: Path
    ):
        """應逐檔下載並彙總進度回報。"""
        from airtype.utils.model_manager import ModelManager

        callback_calls: list[tuple] = []

        def cb(downloaded, total, percent, eta):
            callback_calls.append((downloaded, total, percent, eta))

        mgr = ModelManager(
            manifest_path=str(manifest_file),
            download_dir=str(tmp_path / "models"),
        )

        fake_siblings = [
            {"rfilename": "config.json", "size": 200},
            {"rfilename": "model.bin", "size": 800},
        ]

        downloaded_urls: list[str] = []

        def fake_download_url(url, dest, total_size, progress_cb):
            downloaded_urls.append(url)
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(b"\x00" * total_size)
            if progress_cb:
                progress_cb(total_size, total_size, 100.0, 0.0)

        with mock.patch.object(mgr, "_list_hf_repo_files", return_value=fake_siblings), \
             mock.patch.object(mgr, "_download_url", side_effect=fake_download_url):
            result = mgr._download_hf_repo("org/test-repo", "test-repo.zip", cb, expected_size=1000)

        # 應下載 2 個檔案
        assert len(downloaded_urls) == 2
        assert "config.json" in downloaded_urls[0]
        assert "model.bin" in downloaded_urls[1]

        # 最終應報 100%
        assert callback_calls[-1][2] == pytest.approx(100.0)
        assert callback_calls[-1][0] == callback_calls[-1][1]

        # 回傳目錄路徑
        assert result == tmp_path / "models" / "test-repo"

    def test_skips_already_downloaded_files(
        self, manifest_file: Path, tmp_path: Path
    ):
        """已存在且大小一致的檔案應被跳過。"""
        from airtype.utils.model_manager import ModelManager

        mgr = ModelManager(
            manifest_path=str(manifest_file),
            download_dir=str(tmp_path / "models"),
        )

        # 預先建立檔案
        model_dir = tmp_path / "models" / "test-repo"
        model_dir.mkdir(parents=True)
        (model_dir / "config.json").write_bytes(b"\x00" * 200)

        fake_siblings = [
            {"rfilename": "config.json", "size": 200},
            {"rfilename": "model.bin", "size": 800},
        ]

        downloaded_urls: list[str] = []

        def fake_download_url(url, dest, total_size, progress_cb):
            downloaded_urls.append(url)
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(b"\x00" * total_size)

        with mock.patch.object(mgr, "_list_hf_repo_files", return_value=fake_siblings), \
             mock.patch.object(mgr, "_download_url", side_effect=fake_download_url):
            mgr._download_hf_repo("org/test-repo", "test-repo.zip", None)

        # config.json 應被跳過，只下載 model.bin
        assert len(downloaded_urls) == 1
        assert "model.bin" in downloaded_urls[0]

    def test_no_progress_without_callback(
        self, manifest_file: Path, tmp_path: Path
    ):
        """無 progress_callback 時不應報錯。"""
        from airtype.utils.model_manager import ModelManager

        mgr = ModelManager(
            manifest_path=str(manifest_file),
            download_dir=str(tmp_path / "models"),
        )

        fake_siblings = [{"rfilename": "model.bin", "size": 500}]

        def fake_download_url(url, dest, total_size, progress_cb):
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(b"\x00" * total_size)
            assert progress_cb is None

        with mock.patch.object(mgr, "_list_hf_repo_files", return_value=fake_siblings), \
             mock.patch.object(mgr, "_download_url", side_effect=fake_download_url):
            mgr._download_hf_repo("org/test-repo", "test-repo.zip", None)

    def test_applies_ignore_patterns(
        self, manifest_file: Path, tmp_path: Path
    ):
        """應正確過濾 ignore patterns 匹配的檔案。"""
        from airtype.utils.model_manager import ModelManager

        mgr = ModelManager(
            manifest_path=str(manifest_file),
            download_dir=str(tmp_path / "models"),
        )

        fake_siblings = [
            {"rfilename": "model.bin", "size": 500},
            {"rfilename": "model.int8.onnx", "size": 300},
            {"rfilename": "test_wavs/audio.wav", "size": 100},
            {"rfilename": "optimizer.bin", "size": 200},
            {"rfilename": "photo.png", "size": 50},
        ]

        downloaded_files: list[str] = []

        def fake_download_url(url, dest, total_size, progress_cb):
            downloaded_files.append(dest.name)
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(b"\x00" * total_size)

        with mock.patch.object(mgr, "_list_hf_repo_files", return_value=fake_siblings), \
             mock.patch.object(mgr, "_download_url", side_effect=fake_download_url):
            mgr._download_hf_repo("org/test-repo", "test-repo.zip", None)

        # 只有 model.bin 應被下載（其餘都被 ignore patterns 過濾）
        assert downloaded_files == ["model.bin"]
