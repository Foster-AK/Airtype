"""tests/test_model_manager_hf_progress.py — HF 進度轉接器單元測試。

驗證：
- _HfProgressAdapter 正確彙總多檔案進度
- callback 被呼叫多次且百分比遞增
- 無 callback 時不注入 tqdm_class
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


class TestDownloadHfRepoProgress:
    """_download_hf_repo 方法整合測試。"""

    def test_injects_tqdm_class_with_callback(
        self, manifest_file: Path, tmp_path: Path
    ):
        """有 progress_callback 時應傳入 tqdm_class。"""
        from airtype.utils.model_manager import ModelManager

        callback_calls: list[tuple] = []

        def cb(downloaded, total, percent, eta):
            callback_calls.append((downloaded, total, percent, eta))

        mgr = ModelManager(
            manifest_path=str(manifest_file),
            download_dir=str(tmp_path / "models"),
        )

        def fake_snapshot_download(*, repo_id, local_dir, ignore_patterns, tqdm_class):
            # 模擬 huggingface_hub 建立兩個 tqdm 實例
            bar1 = tqdm_class(total=500)
            bar2 = tqdm_class(total=500)
            bar1.update(250)
            bar2.update(250)
            bar1.update(250)
            bar2.update(250)
            bar1.close()
            bar2.close()
            return local_dir

        with mock.patch(
            "airtype.utils.model_manager.snapshot_download",
            side_effect=fake_snapshot_download,
        ):
            mgr._download_hf_repo("org/test-repo", "test-repo.zip", cb)

        # callback 應被呼叫多次
        assert len(callback_calls) >= 4
        # 百分比應遞增
        percents = [c[2] for c in callback_calls]
        assert percents == sorted(percents)

    def test_no_tqdm_class_without_callback(
        self, manifest_file: Path, tmp_path: Path
    ):
        """無 progress_callback 時不應注入 tqdm_class。"""
        from airtype.utils.model_manager import ModelManager

        mgr = ModelManager(
            manifest_path=str(manifest_file),
            download_dir=str(tmp_path / "models"),
        )

        call_kwargs: dict = {}

        def fake_snapshot_download(**kwargs):
            call_kwargs.update(kwargs)
            return kwargs.get("local_dir", "")

        with mock.patch(
            "airtype.utils.model_manager.snapshot_download",
            side_effect=fake_snapshot_download,
        ):
            mgr._download_hf_repo("org/test-repo", "test-repo.zip", None)

        assert "tqdm_class" not in call_kwargs
