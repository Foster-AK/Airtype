"""模型管理設定頁面測試（TDD）。

涵蓋：
- 9.1 SettingsModelsPage 建立、QTabBar 兩個 tab、預設 ASR tab
- 9.2 ModelCardWidget 顯示（名稱、描述、大小）、推薦徽章顯示/隱藏
- 9.3 _format_size() 單元測試（MB/GB 格式化）
- 9.4 ModelCardWidget 三種狀態切換（未下載/下載中/已下載）
- 9.5 DownloadWorker（mock ModelManager.download）：progress/finished/error Signal
- 9.6 刪除流程：確認對話框觸發、刪除成功後卡片狀態切換
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture(scope="session")
def qapp():
    """建立或重用 QApplication。若 PySide6 不可用則跳過。"""
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    yield app


@pytest.fixture()
def dummy_config(tmp_path):
    """建立使用臨時目錄的 AirtypeConfig。"""
    from airtype.config import AirtypeConfig
    import airtype.config as cfg_mod

    original_file = cfg_mod.CONFIG_FILE
    cfg_mod.CONFIG_FILE = tmp_path / "config.json"

    cfg = AirtypeConfig()
    cfg.save(cfg_mod.CONFIG_FILE)
    yield cfg

    cfg_mod.CONFIG_FILE = original_file


@pytest.fixture()
def fake_manifest(tmp_path):
    """建立假 manifest 和已下載的模型檔案，供 ModelManager 使用。"""
    manifest_data = {
        "models": [
            {
                "id": "asr-model-1",
                "filename": "asr1.bin",
                "size_bytes": 650 * 1024 * 1024,
                "category": "asr",
                "description": "Test ASR Model 1",
                "urls": ["https://example.com/asr1.bin"],
                "fallback_urls": [],
                "sha256": "",
            },
            {
                "id": "asr-model-2",
                "filename": "asr2.bin",
                "size_bytes": 1700 * 1024 * 1024,
                "category": "asr",
                "description": "Test ASR Model 2",
                "urls": ["https://example.com/asr2.bin"],
                "fallback_urls": [],
                "sha256": "",
            },
            {
                "id": "llm-model-1",
                "filename": "llm1.gguf",
                "size_bytes": 2 * 1024 * 1024 * 1024,
                "category": "llm",
                "description": "Test LLM Model 1",
                "urls": ["https://example.com/llm1.gguf"],
                "fallback_urls": [],
                "sha256": "",
            },
        ]
    }
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest_data), encoding="utf-8")
    download_dir = tmp_path / "models"
    download_dir.mkdir()
    return {"manifest_path": str(manifest_path), "download_dir": str(download_dir)}


def _make_page(qapp, dummy_config, fake_manifest, recommended_model=None):
    """建立 SettingsModelsPage，mock ModelManager 使用 fake_manifest。

    使用 patch 模組層級的 ModelManager/HardwareDetector 而非 patch PySide6 class methods，
    避免 PySide6 metaclass 衝突導致 access violation。
    """
    pytest.importorskip("PySide6")
    from airtype.utils.model_manager import ModelManager
    from airtype.ui.settings_models import SettingsModelsPage

    mgr = ModelManager(
        manifest_path=fake_manifest["manifest_path"],
        download_dir=fake_manifest["download_dir"],
    )

    mock_caps = MagicMock()
    mock_path = MagicMock()
    mock_path.model = recommended_model

    with patch("airtype.ui.settings_models.SettingsModelsPage._init_model_manager",
               lambda self: (
                   setattr(self, "_model_manager", mgr) or
                   setattr(self, "_recommended_model", recommended_model)
               )):
        page = SettingsModelsPage(config=dummy_config)

    return page


# ─────────────────────────────────────────────────────────────────────────────
# 9.1 SettingsModelsPage 基本結構
# ─────────────────────────────────────────────────────────────────────────────


class TestScrollAreaHorizontalPolicy:
    """Task 1.1：QScrollArea 水平捲軸停用測試。"""

    def test_scroll_area_no_horizontal_scrollbar(self, qapp, dummy_config, fake_manifest):
        """QScrollArea 應停用水平捲軸（ScrollBarAlwaysOff）。"""
        pytest.importorskip("PySide6")
        from PySide6.QtCore import Qt
        page = _make_page(qapp, dummy_config, fake_manifest)
        assert page._scroll.horizontalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAlwaysOff


class TestSettingsModelsPageCreation:
    """SettingsModelsPage 建立與基本結構測試。"""

    def test_page_importable(self):
        """SettingsModelsPage 應可匯入。"""
        from airtype.ui.settings_models import SettingsModelsPage

    def test_page_creates_without_error(self, qapp, dummy_config, fake_manifest):
        """SettingsModelsPage 應可正常建立。"""
        page = _make_page(qapp, dummy_config, fake_manifest)
        assert page is not None

    def test_tab_bar_has_two_tabs(self, qapp, dummy_config, fake_manifest):
        """QTabBar 應有兩個 tab（ASR 和 LLM）。"""
        pytest.importorskip("PySide6")
        page = _make_page(qapp, dummy_config, fake_manifest)
        assert page._tab_bar.count() == 2

    def test_default_tab_is_asr(self, qapp, dummy_config, fake_manifest):
        """預設應選取 ASR tab（index 0）。"""
        page = _make_page(qapp, dummy_config, fake_manifest)
        assert page._tab_bar.currentIndex() == 0

    def test_asr_tab_populates_cards(self, qapp, dummy_config, fake_manifest):
        """預設 ASR tab 應填充 ASR 模型卡片。"""
        page = _make_page(qapp, dummy_config, fake_manifest)
        # 應有 2 個 ASR 卡片
        assert len(page._cards) == 2


# ─────────────────────────────────────────────────────────────────────────────
# 9.2 ModelCardWidget 顯示
# ─────────────────────────────────────────────────────────────────────────────


class TestModelCardWidget:
    """ModelCardWidget 顯示測試。"""

    def _make_card(self, qapp, dummy_config, entry: dict, is_downloaded=False, is_recommended=False):
        pytest.importorskip("PySide6")
        from airtype.ui.settings_models import ModelCardWidget
        return ModelCardWidget(
            entry,
            is_downloaded=is_downloaded,
            is_recommended=is_recommended,
            config=dummy_config,
        )

    def _entry(self):
        return {
            "id": "test-model",
            "description": "Test Model Description",
            "size_bytes": 650 * 1024 * 1024,
        }

    def test_card_shows_description(self, qapp, dummy_config):
        """卡片應顯示模型描述作為標題。"""
        card = self._make_card(qapp, dummy_config, self._entry())
        assert card._name_label.text() == "Test Model Description"

    def test_card_shows_size_mb(self, qapp, dummy_config):
        """卡片應顯示人類可讀的檔案大小（MB）。"""
        entry = {"id": "m", "description": "M", "size_bytes": 650 * 1024 * 1024}
        card = self._make_card(qapp, dummy_config, entry)
        assert "650 MB" in card._size_label.text()

    def test_card_shows_size_gb(self, qapp, dummy_config):
        """超過 1 GB 的模型應顯示 GB 格式。"""
        entry = {"id": "m", "description": "M", "size_bytes": 1700 * 1024 * 1024}
        card = self._make_card(qapp, dummy_config, entry)
        assert "GB" in card._size_label.text()

    def test_recommended_badge_visible_when_recommended(self, qapp, dummy_config):
        """硬體推薦模型應顯示推薦徽章（使用 isHidden 避免父 widget 可見性影響）。"""
        card = self._make_card(qapp, dummy_config, self._entry(), is_recommended=True)
        assert not card._badge.isHidden()

    def test_recommended_badge_hidden_when_not_recommended(self, qapp, dummy_config):
        """非推薦模型不應顯示推薦徽章。"""
        card = self._make_card(qapp, dummy_config, self._entry(), is_recommended=False)
        assert not card._badge.isVisible()

    def test_card_name_label_shows_part_before_bracket(self, qapp, dummy_config):
        """描述含全形括號時，名稱行應只顯示括號前的部分。"""
        entry = {"id": "m", "description": "Qwen3-ASR（繁中優化版）", "size_bytes": 100 * 1024 * 1024}
        card = self._make_card(qapp, dummy_config, entry)
        assert card._name_label.text() == "Qwen3-ASR"

    def test_card_desc_label_shows_content_inside_bracket(self, qapp, dummy_config):
        """描述含全形括號時，說明行應顯示括號內的文字。"""
        entry = {"id": "m", "description": "Qwen3-ASR（繁中優化版）", "size_bytes": 100 * 1024 * 1024}
        card = self._make_card(qapp, dummy_config, entry)
        assert not card._desc_label.isHidden()
        assert "繁中優化版" in card._desc_label.text()

    def test_card_desc_label_hidden_when_no_bracket(self, qapp, dummy_config):
        """描述不含全形括號時，說明行應隱藏。"""
        card = self._make_card(qapp, dummy_config, self._entry())
        assert card._desc_label.isHidden()

    def test_card_shows_full_description_when_no_bracket(self, qapp, dummy_config):
        """描述不含全形括號時，名稱行應顯示完整描述文字。"""
        card = self._make_card(qapp, dummy_config, self._entry())
        assert card._name_label.text() == "Test Model Description"

    def test_action_widget_width_is_90(self, qapp, dummy_config):
        """動作區 widget 寬度應為 90px。"""
        card = self._make_card(qapp, dummy_config, self._entry())
        assert card._action_widget.maximumWidth() == 90

    def test_download_btn_width_is_80(self, qapp, dummy_config):
        """下載按鈕寬度應為 80px。"""
        card = self._make_card(qapp, dummy_config, self._entry())
        assert card._download_btn.maximumWidth() == 80

    def test_progress_bar_width_is_80(self, qapp, dummy_config):
        """進度條寬度應為 80px。"""
        card = self._make_card(qapp, dummy_config, self._entry())
        assert card._progress_bar.maximumWidth() == 80

    def test_cancel_btn_width_is_80(self, qapp, dummy_config):
        """取消按鈕寬度應為 80px。"""
        card = self._make_card(qapp, dummy_config, self._entry())
        assert card._cancel_btn.maximumWidth() == 80

    def test_delete_btn_width_is_80(self, qapp, dummy_config):
        """刪除按鈕寬度應為 80px。"""
        card = self._make_card(qapp, dummy_config, self._entry(), is_downloaded=True)
        assert card._delete_btn.maximumWidth() == 80


# ─────────────────────────────────────────────────────────────────────────────
# 9.3 _format_size() 單元測試
# ─────────────────────────────────────────────────────────────────────────────


class TestFormatSize:
    """_format_size() 格式化函式測試。"""

    def test_mb_format(self):
        """小於 1 GB 應回傳 MB 格式。"""
        from airtype.ui.settings_models import _format_size
        assert _format_size(650 * 1024 * 1024) == "650 MB"

    def test_gb_format(self):
        """大於或等於 1 GB 應回傳 GB 格式（一位小數）。"""
        from airtype.ui.settings_models import _format_size
        result = _format_size(1700 * 1024 * 1024)
        assert result.endswith(" GB")
        assert "1.7" in result

    def test_exactly_1gb(self):
        """正好 1 GB 應回傳 '1.0 GB'。"""
        from airtype.ui.settings_models import _format_size
        assert _format_size(1024 * 1024 * 1024) == "1.0 GB"

    def test_small_mb(self):
        """100 MB 應回傳 '100 MB'。"""
        from airtype.ui.settings_models import _format_size
        assert _format_size(100 * 1024 * 1024) == "100 MB"


# ─────────────────────────────────────────────────────────────────────────────
# 9.4 ModelCardWidget 三種狀態切換
# ─────────────────────────────────────────────────────────────────────────────


class TestModelCardState:
    """ModelCardWidget 三種狀態切換測試。"""

    def _make_card(self, qapp, dummy_config, is_downloaded=False):
        pytest.importorskip("PySide6")
        from airtype.ui.settings_models import ModelCardWidget
        entry = {"id": "test", "description": "Test", "size_bytes": 100 * 1024 * 1024}
        return ModelCardWidget(entry, is_downloaded=is_downloaded, is_recommended=False, config=dummy_config)

    def test_initial_state_idle(self, qapp, dummy_config):
        """未下載模型初始應顯示下載按鈕（使用 isHidden 避免父 widget 可見性影響）。"""
        card = self._make_card(qapp, dummy_config, is_downloaded=False)
        assert not card._download_btn.isHidden()
        assert card._progress_container.isHidden()
        assert card._downloaded_container.isHidden()

    def test_initial_state_downloaded(self, qapp, dummy_config):
        """已下載模型初始應顯示已下載狀態。"""
        card = self._make_card(qapp, dummy_config, is_downloaded=True)
        assert card._download_btn.isHidden()
        assert card._progress_container.isHidden()
        assert not card._downloaded_container.isHidden()

    def test_set_downloading(self, qapp, dummy_config):
        """set_downloading() 應切換至下載中狀態。"""
        card = self._make_card(qapp, dummy_config)
        card.set_downloading()
        assert card._download_btn.isHidden()
        assert not card._progress_container.isHidden()
        assert card._downloaded_container.isHidden()

    def test_set_downloaded(self, qapp, dummy_config):
        """set_downloaded() 應切換至已下載狀態。"""
        card = self._make_card(qapp, dummy_config)
        card.set_downloaded()
        assert card._download_btn.isHidden()
        assert card._progress_container.isHidden()
        assert not card._downloaded_container.isHidden()

    def test_set_idle(self, qapp, dummy_config):
        """set_idle() 應切換回未下載狀態。"""
        card = self._make_card(qapp, dummy_config, is_downloaded=True)
        card.set_idle()
        assert not card._download_btn.isHidden()
        assert card._progress_container.isHidden()
        assert card._downloaded_container.isHidden()

    def test_update_progress(self, qapp, dummy_config):
        """update_progress() 應更新進度條數值與百分比 label。"""
        card = self._make_card(qapp, dummy_config)
        card.set_downloading()
        card.update_progress(42)
        assert card._progress_bar.value() == 42
        assert "42%" in card._percent_label.text()


# ─────────────────────────────────────────────────────────────────────────────
# 9.5 DownloadWorker Signal 測試
# ─────────────────────────────────────────────────────────────────────────────


class TestDownloadWorker:
    """DownloadWorker Signal 發射測試。"""

    def test_worker_emits_finished_on_success(self, qapp):
        """下載成功時應發射 finished Signal。"""
        pytest.importorskip("PySide6")
        from airtype.ui.settings_models import DownloadWorker

        mock_mgr = MagicMock()
        mock_mgr.download.return_value = "/fake/path/model.bin"

        finished_paths = []
        worker = DownloadWorker(mock_mgr, "test-model")
        worker.finished.connect(lambda p: finished_paths.append(p))

        worker.run()  # 直接呼叫 run()，不用 start()

        assert len(finished_paths) == 1
        assert finished_paths[0] == "/fake/path/model.bin"

    def test_worker_emits_error_on_failure(self, qapp):
        """下載失敗時應發射 error Signal。"""
        pytest.importorskip("PySide6")
        from airtype.ui.settings_models import DownloadWorker

        mock_mgr = MagicMock()
        mock_mgr.download.side_effect = Exception("Connection failed")

        errors = []
        worker = DownloadWorker(mock_mgr, "test-model")
        worker.error.connect(lambda e: errors.append(e))

        worker.run()

        assert len(errors) == 1
        assert "Connection failed" in errors[0]

    def test_worker_emits_progress(self, qapp):
        """下載過程中應發射 progress Signal。"""
        pytest.importorskip("PySide6")
        from airtype.ui.settings_models import DownloadWorker

        progress_values = []

        def fake_download(model_id, progress_callback):
            progress_callback(500000, 1000000, 50.0, 2.0)
            return "/fake/model.bin"

        mock_mgr = MagicMock()
        mock_mgr.download.side_effect = fake_download

        worker = DownloadWorker(mock_mgr, "test-model")
        worker.progress.connect(lambda p: progress_values.append(p))

        worker.run()

        assert 50 in progress_values

    def test_worker_cancel_stops_download(self, qapp):
        """cancel() 後下載應中斷且不發射 finished。"""
        pytest.importorskip("PySide6")
        from airtype.ui.settings_models import DownloadWorker

        finished_calls = []

        def fake_download(model_id, progress_callback):
            # 第一次 callback 後檢查取消
            progress_callback(100, 1000, 10.0, 5.0)
            return "/fake/model.bin"

        mock_mgr = MagicMock()
        mock_mgr.download.side_effect = fake_download

        worker = DownloadWorker(mock_mgr, "test-model")
        worker.finished.connect(lambda p: finished_calls.append(p))
        worker.cancel()  # 預先取消

        worker.run()

        assert len(finished_calls) == 0


# ─────────────────────────────────────────────────────────────────────────────
# 9.6 刪除流程測試
# ─────────────────────────────────────────────────────────────────────────────


class TestDeleteFlow:
    """模型刪除流程測試。"""

    def test_delete_triggers_confirmation_dialog(self, qapp, dummy_config):
        """點擊刪除按鈕應顯示確認對話框（mock QMessageBox）。"""
        pytest.importorskip("PySide6")
        from PySide6.QtWidgets import QMessageBox
        from airtype.ui.settings_models import ModelCardWidget

        entry = {"id": "test-model", "description": "Test Model", "size_bytes": 100 * 1024 * 1024}
        card = ModelCardWidget(entry, is_downloaded=True, is_recommended=False, config=dummy_config)

        with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.No) as mock_q, \
             patch.object(QMessageBox, "warning"):
            card._on_delete_clicked()
            mock_q.assert_called_once()

    def test_confirm_deletion_emits_signal(self, qapp, dummy_config):
        """確認刪除後應發射 delete_requested Signal。"""
        pytest.importorskip("PySide6")
        from PySide6.QtWidgets import QMessageBox
        from airtype.ui.settings_models import ModelCardWidget

        entry = {"id": "test-model", "description": "Test Model", "size_bytes": 100 * 1024 * 1024}
        card = ModelCardWidget(entry, is_downloaded=True, is_recommended=False, config=dummy_config)

        deleted_ids = []
        card.delete_requested.connect(lambda mid: deleted_ids.append(mid))

        with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes), \
             patch.object(QMessageBox, "warning"):
            card._on_delete_clicked()

        assert "test-model" in deleted_ids

    def test_cancel_deletion_no_signal(self, qapp, dummy_config):
        """取消刪除對話框不應發射 delete_requested Signal。"""
        pytest.importorskip("PySide6")
        from PySide6.QtWidgets import QMessageBox
        from airtype.ui.settings_models import ModelCardWidget

        entry = {"id": "test-model", "description": "Test Model", "size_bytes": 100 * 1024 * 1024}
        card = ModelCardWidget(entry, is_downloaded=True, is_recommended=False, config=dummy_config)

        deleted_ids = []
        card.delete_requested.connect(lambda mid: deleted_ids.append(mid))

        with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.No), \
             patch.object(QMessageBox, "warning"):
            card._on_delete_clicked()

        assert len(deleted_ids) == 0

    def test_delete_success_sets_idle_state(self, qapp, dummy_config, fake_manifest):
        """刪除成功後卡片應切換至未下載（idle）狀態。"""
        pytest.importorskip("PySide6")
        from PySide6.QtWidgets import QMessageBox
        from airtype.utils.model_manager import ModelManager
        from airtype.ui.settings_models import SettingsModelsPage

        # 建立已下載的模型檔案
        model_file = Path(fake_manifest["download_dir"]) / "asr1.bin"
        model_file.write_bytes(b"fake model")

        mgr = ModelManager(
            manifest_path=fake_manifest["manifest_path"],
            download_dir=fake_manifest["download_dir"],
        )

        # 使用 lambda patch 避免 PySide6 metaclass 衝突
        with patch("airtype.ui.settings_models.SettingsModelsPage._init_model_manager",
                   lambda self: (
                       setattr(self, "_model_manager", mgr) or
                       setattr(self, "_recommended_model", None)
                   )):
            page = SettingsModelsPage(config=dummy_config)

        # 找到 asr-model-1 卡片（asr1.bin 已存在，應為已下載狀態）
        card = page._find_card("asr-model-1")
        assert card is not None
        assert not card._downloaded_container.isHidden()

        # 模擬確認刪除
        with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes), \
             patch.object(QMessageBox, "warning"):
            page._on_delete_requested("asr-model-1")

        assert not card._download_btn.isHidden()
        assert card._downloaded_container.isHidden()


# ─────────────────────────────────────────────────────────────────────────────
# 4.3 HuggingFace Token UI 欄位測試
# ─────────────────────────────────────────────────────────────────────────────


class TestHFTokenUI:
    """HuggingFace Token UI 欄位測試。"""

    def test_hf_token_input_field_exists(self, qapp, dummy_config, fake_manifest):
        """設定頁面應有 HF Token 輸入欄位。"""
        page = _make_page(qapp, dummy_config, fake_manifest)
        assert hasattr(page, "_hf_token_input")

    def test_hf_token_input_is_password_mode(self, qapp, dummy_config, fake_manifest):
        """HF Token 輸入欄位應使用密碼遮罩模式。"""
        pytest.importorskip("PySide6")
        from PySide6.QtWidgets import QLineEdit
        page = _make_page(qapp, dummy_config, fake_manifest)
        assert page._hf_token_input.echoMode() == QLineEdit.EchoMode.Password

    def test_hf_token_input_saves_to_keyring(self, qapp, dummy_config, fake_manifest):
        """輸入 token 並按 Enter 後應存入 keyring。"""
        page = _make_page(qapp, dummy_config, fake_manifest)
        with patch("airtype.config.set_api_key") as mock_set:
            page._hf_token_input.setText("hf_new_token")
            page._on_hf_token_save()
        mock_set.assert_called_once_with("huggingface", "hf_new_token")

    def test_hf_token_clear_removes_from_keyring(self, qapp, dummy_config, fake_manifest):
        """清除按鈕應呼叫 set_api_key 移除 token。"""
        page = _make_page(qapp, dummy_config, fake_manifest)
        with patch("airtype.config.set_api_key") as mock_set:
            page._on_hf_token_clear()
        mock_set.assert_called_once_with("huggingface", "")

    def test_hf_token_clear_btn_exists(self, qapp, dummy_config, fake_manifest):
        """設定頁面應有 HF Token 清除按鈕。"""
        page = _make_page(qapp, dummy_config, fake_manifest)
        assert hasattr(page, "_hf_token_clear_btn")


# ─────────────────────────────────────────────────────────────────────────────
# 4.4 401 錯誤 UI 提示測試
# ─────────────────────────────────────────────────────────────────────────────


class TestHF401ErrorGuidance:
    """HuggingFace 401 Error Guidance UI 測試。"""

    def test_401_error_shows_hf_token_guidance(self, qapp, dummy_config, fake_manifest):
        """下載失敗且錯誤包含 '401' 時，應顯示 HF token 設定引導訊息。"""
        pytest.importorskip("PySide6")
        from PySide6.QtWidgets import QMessageBox
        page = _make_page(qapp, dummy_config, fake_manifest)

        warning_msgs = []
        with patch.object(
            QMessageBox, "warning",
            side_effect=lambda *args, **kw: warning_msgs.append(args)
        ):
            page._on_download_error("asr-model-1", "HTTP 401 Unauthorized")

        assert len(warning_msgs) == 1
        # 訊息應包含 HF token 相關引導（不應是標準的 download_error 格式）
        msg_text = str(warning_msgs[0])
        assert "401" not in msg_text or "token" in msg_text.lower() or "huggingface" in msg_text.lower()

    def test_non_401_error_shows_standard_message(self, qapp, dummy_config, fake_manifest):
        """非 401 錯誤應顯示標準錯誤訊息。"""
        pytest.importorskip("PySide6")
        from PySide6.QtWidgets import QMessageBox
        page = _make_page(qapp, dummy_config, fake_manifest)

        warning_msgs = []
        with patch.object(
            QMessageBox, "warning",
            side_effect=lambda *args, **kw: warning_msgs.append(args)
        ):
            page._on_download_error("asr-model-1", "Connection timeout")

        assert len(warning_msgs) == 1
