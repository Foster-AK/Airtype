"""設定視窗單元測試（TDD）。

涵蓋：
- 任務 1.1：SettingsWindow 建立、QStackedWidget 分頁切換
- 任務 1.2：widget 變更時自動儲存（500ms 防抖動）

純 Python 測試不依賴 PySide6，可在任何環境執行。
Qt 元件測試在 PySide6 可用時執行。
"""

from __future__ import annotations

import sys
import time

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
    from airtype.config import AirtypeConfig, CONFIG_FILE
    import airtype.config as cfg_mod

    original_file = cfg_mod.CONFIG_FILE
    cfg_mod.CONFIG_FILE = tmp_path / "config.json"

    cfg = AirtypeConfig()
    cfg.save(cfg_mod.CONFIG_FILE)
    yield cfg

    cfg_mod.CONFIG_FILE = original_file


# ─────────────────────────────────────────────────────────────────────────────
# Task 1.1：SettingsWindow 建立與分頁切換
# ─────────────────────────────────────────────────────────────────────────────


class TestSettingsWindowCreation:
    """SettingsWindow 建立測試。"""

    def test_settings_window_importable(self):
        """SettingsWindow 應可匯入。"""
        from airtype.ui.settings_window import SettingsWindow

    def test_settings_window_has_stacked_widget(self, qapp, dummy_config):
        """SettingsWindow 應包含 QStackedWidget。"""
        pytest.importorskip("PySide6")
        from PySide6.QtWidgets import QStackedWidget
        from airtype.ui.settings_window import SettingsWindow

        win = SettingsWindow(config=dummy_config)
        assert win.stacked is not None
        assert isinstance(win.stacked, QStackedWidget)

    def test_settings_window_has_nav_list(self, qapp, dummy_config):
        """SettingsWindow 應包含左側 QListWidget 導覽。"""
        pytest.importorskip("PySide6")
        from PySide6.QtWidgets import QListWidget
        from airtype.ui.settings_window import SettingsWindow

        win = SettingsWindow(config=dummy_config)
        assert win.nav_list is not None
        assert isinstance(win.nav_list, QListWidget)

    def test_settings_window_page_count(self, qapp, dummy_config):
        """SettingsWindow 應有 8 個分頁（一般、語音、模型管理、外觀、快捷鍵、LLM 潤飾、辭典、關於）。"""
        pytest.importorskip("PySide6")
        from airtype.ui.settings_window import SettingsWindow

        win = SettingsWindow(config=dummy_config)
        assert win.stacked.count() == 8

    def test_settings_window_nav_count(self, qapp, dummy_config):
        """導覽列表應有 8 個項目。"""
        pytest.importorskip("PySide6")
        from airtype.ui.settings_window import SettingsWindow

        win = SettingsWindow(config=dummy_config)
        assert win.nav_list.count() == 8

    def test_page_models_constant_is_2(self, qapp, dummy_config):
        """PAGE_MODELS 常數應為 2。"""
        from airtype.ui.settings_window import PAGE_MODELS
        assert PAGE_MODELS == 2

    def test_navigate_to_models_page(self, qapp, dummy_config):
        """點選「模型管理」應切換至模型管理頁面（index 2）。"""
        pytest.importorskip("PySide6")
        from airtype.ui.settings_window import SettingsWindow, PAGE_MODELS

        win = SettingsWindow(config=dummy_config)
        win.nav_list.setCurrentRow(PAGE_MODELS)
        assert win.stacked.currentIndex() == PAGE_MODELS


class TestSettingsWindowNavigation:
    """分頁導覽切換測試。"""

    def test_navigate_to_voice_page(self, qapp, dummy_config):
        """點選「語音」應切換至語音設定頁（index 1）。"""
        pytest.importorskip("PySide6")
        from airtype.ui.settings_window import SettingsWindow, PAGE_VOICE

        win = SettingsWindow(config=dummy_config)
        win.nav_list.setCurrentRow(PAGE_VOICE)
        assert win.stacked.currentIndex() == PAGE_VOICE

    def test_navigate_to_appearance_page(self, qapp, dummy_config):
        """點選「外觀」應切換至外觀設定頁（index 3）。"""
        pytest.importorskip("PySide6")
        from airtype.ui.settings_window import SettingsWindow, PAGE_APPEARANCE

        win = SettingsWindow(config=dummy_config)
        win.nav_list.setCurrentRow(PAGE_APPEARANCE)
        assert win.stacked.currentIndex() == PAGE_APPEARANCE

    def test_initial_page_is_general(self, qapp, dummy_config):
        """預設應顯示一般設定頁（index 0）。"""
        pytest.importorskip("PySide6")
        from airtype.ui.settings_window import SettingsWindow, PAGE_GENERAL

        win = SettingsWindow(config=dummy_config)
        assert win.stacked.currentIndex() == PAGE_GENERAL


# ─────────────────────────────────────────────────────────────────────────────
# Task 1.2：自動儲存防抖動
# ─────────────────────────────────────────────────────────────────────────────


class TestAutoSaveDebounce:
    """自動儲存防抖動邏輯測試。"""

    def test_debounce_timer_attribute_exists(self, qapp, dummy_config):
        """SettingsWindow 應有 _save_timer 屬性（QTimer）。"""
        pytest.importorskip("PySide6")
        from PySide6.QtCore import QTimer
        from airtype.ui.settings_window import SettingsWindow

        win = SettingsWindow(config=dummy_config)
        assert hasattr(win, "_save_timer")
        assert isinstance(win._save_timer, QTimer)

    def test_debounce_timer_interval_500ms(self, qapp, dummy_config):
        """防抖動計時器間隔應為 500ms。"""
        pytest.importorskip("PySide6")
        from airtype.ui.settings_window import SettingsWindow

        win = SettingsWindow(config=dummy_config)
        assert win._save_timer.interval() == 500

    def test_debounce_timer_is_single_shot(self, qapp, dummy_config):
        """防抖動計時器應為 single-shot 模式。"""
        pytest.importorskip("PySide6")
        from airtype.ui.settings_window import SettingsWindow

        win = SettingsWindow(config=dummy_config)
        assert win._save_timer.isSingleShot()

    def test_schedule_save_starts_timer(self, qapp, dummy_config):
        """schedule_save() 應啟動計時器。"""
        pytest.importorskip("PySide6")
        from airtype.ui.settings_window import SettingsWindow

        win = SettingsWindow(config=dummy_config)
        win._save_timer.stop()
        win.schedule_save()
        assert win._save_timer.isActive()


# ─────────────────────────────────────────────────────────────────────────────
# SettingsVoicePage._refresh_devices() 測試
# ─────────────────────────────────────────────────────────────────────────────


class TestSettingsVoicePageDeviceRefresh:
    """_refresh_devices() 直接單元測試（W-1 修正）。"""

    def _make_page(self, qapp, dummy_config):
        """建立 SettingsVoicePage（以空裝置清單避免真實 sounddevice 呼叫）。"""
        pytest.importorskip("PySide6")
        from unittest.mock import patch

        with patch("airtype.ui.settings_voice.list_input_devices", return_value=[]):
            from airtype.ui.settings_voice import SettingsVoicePage
            page = SettingsVoicePage(config=dummy_config, schedule_save_fn=None)
        return page

    def test_default_item_is_first(self, qapp, dummy_config):
        """下拉第一項應為系統預設（itemData='default'）。"""
        pytest.importorskip("PySide6")
        from unittest.mock import patch

        page = self._make_page(qapp, dummy_config)
        assert page._device_combo.itemData(0) == "default"

    def test_refresh_populates_device_names(self, qapp, dummy_config):
        """_refresh_devices() 應將裝置名稱加入下拉選單，itemData 為裝置名稱。"""
        pytest.importorskip("PySide6")
        from unittest.mock import patch

        page = self._make_page(qapp, dummy_config)
        fake_devices = [
            {"index": 1, "name": "麥克風 A"},
            {"index": 3, "name": "麥克風 C"},
        ]
        with patch("airtype.ui.settings_voice.list_input_devices", return_value=fake_devices):
            page._refresh_devices()

        assert page._device_combo.count() == 3  # default + 2 devices
        assert page._device_combo.itemText(1) == "麥克風 A"
        assert page._device_combo.itemData(1) == "麥克風 A"
        assert page._device_combo.itemText(2) == "麥克風 C"
        assert page._device_combo.itemData(2) == "麥克風 C"

    def test_refresh_restores_saved_device(self, qapp, dummy_config):
        """_refresh_devices() 應從 config 還原已選裝置（依名稱匹配）。"""
        pytest.importorskip("PySide6")
        from unittest.mock import patch

        dummy_config.voice.input_device = "麥克風 C"
        page = self._make_page(qapp, dummy_config)

        fake_devices = [
            {"index": 1, "name": "麥克風 A"},
            {"index": 3, "name": "麥克風 C"},
        ]
        with patch("airtype.ui.settings_voice.list_input_devices", return_value=fake_devices):
            page._refresh_devices()

        assert page._device_combo.currentData() == "麥克風 C"

    def test_refresh_with_no_devices_shows_only_default(self, qapp, dummy_config):
        """無裝置時下拉選單應只有系統預設項目。"""
        pytest.importorskip("PySide6")
        from unittest.mock import patch

        page = self._make_page(qapp, dummy_config)
        with patch("airtype.ui.settings_voice.list_input_devices", return_value=[]):
            page._refresh_devices()

        assert page._device_combo.count() == 1
        assert page._device_combo.itemData(0) == "default"


# ─────────────────────────────────────────────────────────────────────────────
# 9.8 語音設定頁：已下載模型篩選測試
# ─────────────────────────────────────────────────────────────────────────────


class TestVoicePageDownloadedModels:
    """語音設定頁下拉只列已下載模型測試。"""

    def _make_voice_page(self, qapp, dummy_config):
        """建立 SettingsVoicePage，mock ModelManager 與硬體偵測。"""
        pytest.importorskip("PySide6")
        from unittest.mock import patch, MagicMock

        with patch("airtype.ui.settings_voice.list_input_devices", return_value=[]):
            from airtype.ui.settings_voice import SettingsVoicePage
            page = SettingsVoicePage(config=dummy_config, schedule_save_fn=None)
        return page

    def test_only_downloaded_models_shown(self, qapp, dummy_config):
        """dropdown 應只列出已下載的模型（is_downloaded=True）。"""
        pytest.importorskip("PySide6")
        from unittest.mock import patch, MagicMock

        mock_mgr = MagicMock()
        mock_mgr.list_models_by_category.return_value = [
            {"id": "asr-model-1", "description": "ASR Model 1"},
            {"id": "asr-model-2", "description": "ASR Model 2"},
        ]
        mock_mgr.is_downloaded.side_effect = lambda mid: mid == "asr-model-1"

        with patch("airtype.ui.settings_voice.list_input_devices", return_value=[]):
            from airtype.ui.settings_voice import SettingsVoicePage
            page = SettingsVoicePage(config=dummy_config, schedule_save_fn=None)
            page._model_manager = mock_mgr
            page._asr_manifest_entries = mock_mgr.list_models_by_category("asr")
            page._populate_asr_combo()

        # 只有 asr-model-1 已下載，應出現在 combo
        model_ids = [page._asr_combo.itemData(i) for i in range(page._asr_combo.count())]
        assert "asr-model-1" in model_ids
        assert "asr-model-2" not in model_ids

    def test_no_downloaded_models_shows_placeholder(self, qapp, dummy_config):
        """無已下載模型時 dropdown 應顯示 placeholder 並 disable。"""
        pytest.importorskip("PySide6")
        from unittest.mock import MagicMock, patch

        mock_mgr = MagicMock()
        mock_mgr.list_models_by_category.return_value = [
            {"id": "asr-model-1", "description": "ASR Model 1"},
        ]
        mock_mgr.is_downloaded.return_value = False

        with patch("airtype.ui.settings_voice.list_input_devices", return_value=[]):
            from airtype.ui.settings_voice import SettingsVoicePage
            page = SettingsVoicePage(config=dummy_config, schedule_save_fn=None)
            page._model_manager = mock_mgr
            page._asr_manifest_entries = mock_mgr.list_models_by_category("asr")
            page._populate_asr_combo()

        assert page._asr_combo.count() == 1
        assert not page._asr_combo.isEnabled()
        assert not page._asr_no_model_label.isHidden()


# ─────────────────────────────────────────────────────────────────────────────
# Task 1.1 & 1.2：導覽面板 QSS 樣式測試（fix-settings-nav-focus-outline）
# ─────────────────────────────────────────────────────────────────────────────


class TestNavPanelStylesheet:
    """Navigation Panel Focus Indicator 與 Navigation Panel Selection Style 測試。"""

    def test_nav_list_qss_has_outline_zero(self, qapp, dummy_config):
        """Navigation Panel Focus Indicator：QListWidget QSS 應包含 outline: 0。"""
        pytest.importorskip("PySide6")
        from airtype.ui.settings_window import SettingsWindow

        win = SettingsWindow(config=dummy_config)
        qss = win.nav_list.styleSheet()
        assert "outline: 0" in qss, f"期望 QSS 包含 'outline: 0'，實際 QSS：{qss!r}"

    def test_nav_list_qss_has_selection_background(self, qapp, dummy_config):
        """Navigation Panel Selection Style：選取項目 QSS 應包含 background: #0a84ff。"""
        pytest.importorskip("PySide6")
        from airtype.ui.settings_window import SettingsWindow

        win = SettingsWindow(config=dummy_config)
        qss = win.nav_list.styleSheet()
        assert "#0a84ff" in qss, f"期望 QSS 包含 '#0a84ff'，實際 QSS：{qss!r}"

    def test_nav_list_qss_has_selection_text_color(self, qapp, dummy_config):
        """Navigation Panel Selection Style：選取項目 QSS 應包含 color: white。"""
        pytest.importorskip("PySide6")
        from airtype.ui.settings_window import SettingsWindow

        win = SettingsWindow(config=dummy_config)
        qss = win.nav_list.styleSheet()
        assert "color: white" in qss, f"期望 QSS 包含 'color: white'，實際 QSS：{qss!r}"

    def test_nav_list_qss_has_pill_margin(self, qapp, dummy_config):
        """Navigation Panel Selection Style（pill）：QSS 應包含 margin 實現內縮。"""
        pytest.importorskip("PySide6")
        from airtype.ui.settings_window import SettingsWindow

        win = SettingsWindow(config=dummy_config)
        qss = win.nav_list.styleSheet()
        assert "margin" in qss, f"期望 QSS 包含 'margin'，實際 QSS：{qss!r}"

    def test_nav_list_qss_has_border_radius_6px(self, qapp, dummy_config):
        """Navigation Panel Selection Style（pill）：QSS 應包含 border-radius: 6px。"""
        pytest.importorskip("PySide6")
        from airtype.ui.settings_window import SettingsWindow

        win = SettingsWindow(config=dummy_config)
        qss = win.nav_list.styleSheet()
        assert "border-radius: 6px" in qss, f"期望 QSS 包含 'border-radius: 6px'，實際 QSS：{qss!r}"

    def test_nav_list_qss_has_hover_state(self, qapp, dummy_config):
        """Navigation Panel Hover State：QSS 應包含 hover 選取器。"""
        pytest.importorskip("PySide6")
        from airtype.ui.settings_window import SettingsWindow

        win = SettingsWindow(config=dummy_config)
        qss = win.nav_list.styleSheet()
        assert "hover" in qss, f"期望 QSS 包含 'hover'，實際 QSS：{qss!r}"

    def test_nav_list_qss_has_hover_rgba(self, qapp, dummy_config):
        """Navigation Panel Hover State：hover QSS 應包含半透明背景 rgba。"""
        pytest.importorskip("PySide6")
        from airtype.ui.settings_window import SettingsWindow

        win = SettingsWindow(config=dummy_config)
        qss = win.nav_list.styleSheet()
        assert "rgba(0, 0, 0, 0.06)" in qss, f"期望 QSS 包含 hover rgba，實際 QSS：{qss!r}"


# ─────────────────────────────────────────────────────────────────────────────
# fix-settings-bg-consistency：設定視窗主題背景一致性測試
# ─────────────────────────────────────────────────────────────────────────────


class TestWindowThemeBackground:
    """Settings Window Light/Dark Theme Background 與 Theme Change Response 測試。"""

    def test_content_bg_widget_exists(self, qapp, dummy_config):
        """Settings Window Light Theme Background：SettingsWindow 應有 _content_bg QWidget。"""
        pytest.importorskip("PySide6")
        from airtype.ui.settings_window import SettingsWindow

        win = SettingsWindow(config=dummy_config)
        assert hasattr(win, "_content_bg"), "SettingsWindow 應有 _content_bg 屬性"

    def test_content_bg_has_object_name(self, qapp, dummy_config):
        """Settings Window Light Theme Background：_content_bg objectName 應為 'contentBg'。"""
        pytest.importorskip("PySide6")
        from airtype.ui.settings_window import SettingsWindow

        win = SettingsWindow(config=dummy_config)
        assert win._content_bg.objectName() == "contentBg"

    def test_nav_widget_reference_exists(self, qapp, dummy_config):
        """Settings Window Light Theme Background：SettingsWindow 應有 _nav_widget 引用。"""
        pytest.importorskip("PySide6")
        from airtype.ui.settings_window import SettingsWindow

        win = SettingsWindow(config=dummy_config)
        assert hasattr(win, "_nav_widget"), "SettingsWindow 應有 _nav_widget 屬性"

    def test_apply_content_bg_light_content(self, qapp, dummy_config):
        """Settings Window Light Theme Background：淺色主題內容區 QSS 應含 #ffffff。"""
        pytest.importorskip("PySide6")
        from airtype.ui.settings_window import SettingsWindow

        win = SettingsWindow(config=dummy_config)
        win._apply_content_bg("light")
        assert "#ffffff" in win._content_bg.styleSheet()

    def test_apply_content_bg_light_nav(self, qapp, dummy_config):
        """Settings Window Light Theme Background：淺色主題導覽列 QSS 應含 #fafafa。"""
        pytest.importorskip("PySide6")
        from airtype.ui.settings_window import SettingsWindow

        win = SettingsWindow(config=dummy_config)
        win._apply_content_bg("light")
        assert "#fafafa" in win._nav_widget.styleSheet()

    def test_apply_content_bg_dark_content(self, qapp, dummy_config):
        """Settings Window Dark Theme Background：深色主題內容區 QSS 應含 #2d2d2d。"""
        pytest.importorskip("PySide6")
        from airtype.ui.settings_window import SettingsWindow

        win = SettingsWindow(config=dummy_config)
        win._apply_content_bg("dark")
        assert "#2d2d2d" in win._content_bg.styleSheet()

    def test_apply_content_bg_dark_nav(self, qapp, dummy_config):
        """Settings Window Dark Theme Background：深色主題導覽列 QSS 應含 #252525。"""
        pytest.importorskip("PySide6")
        from airtype.ui.settings_window import SettingsWindow

        win = SettingsWindow(config=dummy_config)
        win._apply_content_bg("dark")
        assert "#252525" in win._nav_widget.styleSheet()

    def test_apply_content_bg_system_same_as_light(self, qapp, dummy_config):
        """Settings Window Theme Change Response：system 主題內容區應與 light 一致（#ffffff）。"""
        pytest.importorskip("PySide6")
        from airtype.ui.settings_window import SettingsWindow

        win = SettingsWindow(config=dummy_config)
        win._apply_content_bg("system")
        assert "#ffffff" in win._content_bg.styleSheet()
        assert "#fafafa" in win._nav_widget.styleSheet()


# ─────────────────────────────────────────────────────────────────────────────
# _light_palette() 顏色驗證：確保 QLineEdit/QTableWidget 背景使用白色
# ─────────────────────────────────────────────────────────────────────────────


class TestLightPalette:
    """_light_palette() 關鍵顏色驗證。"""

    def test_light_palette_base_is_white(self):
        """_light_palette Base 顏色應為 #ffffff（QLineEdit/QTableWidget 背景）。"""
        pytest.importorskip("PySide6")
        from PySide6.QtGui import QPalette
        from airtype.ui.settings_window import _light_palette

        palette = _light_palette()
        base = palette.color(QPalette.ColorRole.Base)
        assert base.name() == "#ffffff"

    def test_light_palette_window_is_fafafa(self):
        """_light_palette Window 顏色應為 #fafafa。"""
        pytest.importorskip("PySide6")
        from PySide6.QtGui import QPalette
        from airtype.ui.settings_window import _light_palette

        palette = _light_palette()
        window = palette.color(QPalette.ColorRole.Window)
        assert window.name() == "#fafafa"

    def test_light_palette_alternate_base_is_f5f5f5(self):
        """_light_palette AlternateBase 應為 #f5f5f5（表格交替行背景）。"""
        pytest.importorskip("PySide6")
        from PySide6.QtGui import QPalette
        from airtype.ui.settings_window import _light_palette

        palette = _light_palette()
        alt = palette.color(QPalette.ColorRole.AlternateBase)
        assert alt.name() == "#f5f5f5"

    def test_light_palette_button_is_f0f0f0(self):
        """_light_palette Button 應為 #f0f0f0（表頭/按鈕背景）。"""
        pytest.importorskip("PySide6")
        from PySide6.QtGui import QPalette
        from airtype.ui.settings_window import _light_palette

        palette = _light_palette()
        btn = palette.color(QPalette.ColorRole.Button)
        assert btn.name() == "#f0f0f0"
