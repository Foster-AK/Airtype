"""系統匣圖示單元測試。

涵蓋：
- 任務 1.1/1.2：SystemTrayIcon 建立、選單操作
- 任務 2.1：notify() 通知發送
- 任務 2.2：close_to_tray() 關閉至系統匣行為

純 Python 測試（make_state_color_map、truncate_text）不依賴 PySide6，
可在任何環境執行。Qt 元件測試在 PySide6 可用時執行。
"""

from __future__ import annotations

import sys

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
def dummy_config():
    """建立預設 AirtypeConfig。"""
    from airtype.config import AirtypeConfig

    return AirtypeConfig()


@pytest.fixture()
def dummy_config_no_notify():
    """建立關閉通知的 AirtypeConfig。"""
    from airtype.config import AirtypeConfig

    cfg = AirtypeConfig()
    cfg.general.notifications = False
    return cfg


# ─────────────────────────────────────────────────────────────────────────────
# 純 Python 測試（不需 Qt）
# ─────────────────────────────────────────────────────────────────────────────


class TestMakeStateColorMap:
    """測試 make_state_color_map 純 Python 輔助函式。"""

    def test_returns_dict(self):
        from airtype.ui.tray_icon import make_state_color_map

        result = make_state_color_map()
        assert isinstance(result, dict)

    def test_has_all_states(self):
        from airtype.ui.tray_icon import make_state_color_map

        result = make_state_color_map()
        for state in ("IDLE", "ACTIVATING", "LISTENING", "PROCESSING", "INJECTING", "ERROR"):
            assert state in result

    def test_colors_are_strings(self):
        from airtype.ui.tray_icon import make_state_color_map

        result = make_state_color_map()
        for color in result.values():
            assert isinstance(color, str)
            assert color.startswith("#")

    def test_is_copy(self):
        from airtype.ui.tray_icon import make_state_color_map

        m1 = make_state_color_map()
        m2 = make_state_color_map()
        m1["IDLE"] = "#000000"
        assert m2["IDLE"] != "#000000"


class TestTruncateText:
    """測試 truncate_text 文字截短函式。"""

    def test_short_text_unchanged(self):
        from airtype.ui.tray_icon import truncate_text

        text = "短文字"
        assert truncate_text(text) == text

    def test_exact_length_unchanged(self):
        from airtype.ui.tray_icon import truncate_text

        text = "a" * 60
        assert truncate_text(text, max_chars=60) == text

    def test_long_text_truncated(self):
        from airtype.ui.tray_icon import truncate_text

        text = "a" * 100
        result = truncate_text(text, max_chars=60)
        assert len(result) == 60
        assert result.endswith("…")

    def test_custom_max_chars(self):
        from airtype.ui.tray_icon import truncate_text

        text = "hello world"
        result = truncate_text(text, max_chars=7)
        assert len(result) == 7

    def test_empty_string(self):
        from airtype.ui.tray_icon import truncate_text

        assert truncate_text("") == ""


# ─────────────────────────────────────────────────────────────────────────────
# Qt 元件測試（需要 PySide6 + QApplication）
# ─────────────────────────────────────────────────────────────────────────────


class TestSystemTrayIconCreate:
    """SystemTrayIcon 建立測試。"""

    def test_import(self):
        pytest.importorskip("PySide6")
        from airtype.ui.tray_icon import SystemTrayIcon  # noqa: F401

    def test_create_without_config(self, qapp):
        from airtype.ui.tray_icon import SystemTrayIcon

        tray = SystemTrayIcon()
        assert tray is not None
        tray.hide()

    def test_create_with_config(self, qapp, dummy_config):
        from airtype.ui.tray_icon import SystemTrayIcon

        tray = SystemTrayIcon(config=dummy_config)
        assert tray is not None
        tray.hide()

    def test_has_context_menu(self, qapp):
        from airtype.ui.tray_icon import SystemTrayIcon

        tray = SystemTrayIcon()
        assert tray.contextMenu() is not None
        tray.hide()


class TestSystemTrayIconMenu:
    """右鍵選單操作測試。"""

    def test_menu_has_settings_action(self, qapp):
        from airtype.ui.tray_icon import SystemTrayIcon

        tray = SystemTrayIcon()
        menu = tray.contextMenu()
        texts = [a.text() for a in menu.actions()]
        assert any("設定" in t for t in texts)
        tray.hide()

    def test_menu_has_toggle_action(self, qapp):
        from airtype.ui.tray_icon import SystemTrayIcon

        tray = SystemTrayIcon()
        menu = tray.contextMenu()
        texts = [a.text() for a in menu.actions()]
        assert any("語音" in t for t in texts)
        tray.hide()

    def test_menu_has_quit_action(self, qapp):
        from airtype.ui.tray_icon import SystemTrayIcon

        tray = SystemTrayIcon()
        menu = tray.contextMenu()
        texts = [a.text() for a in menu.actions()]
        assert "結束" in texts
        tray.hide()

    def test_menu_has_status_action_disabled(self, qapp):
        from airtype.ui.tray_icon import SystemTrayIcon

        tray = SystemTrayIcon()
        # 狀態顯示項目應為 disabled（不可點擊）
        menu = tray.contextMenu()
        disabled_actions = [a for a in menu.actions() if not a.isEnabled()]
        assert len(disabled_actions) >= 1
        tray.hide()

    def test_open_settings_signal_emitted(self, qapp):
        from airtype.ui.tray_icon import SystemTrayIcon

        tray = SystemTrayIcon()
        received = []
        tray.open_settings_requested.connect(lambda: received.append(True))

        # 直接觸發 signal（不需要真正點擊選單）
        tray.open_settings_requested.emit()
        assert received == [True]
        tray.hide()

    def test_toggle_voice_signal_emitted(self, qapp):
        from airtype.ui.tray_icon import SystemTrayIcon

        tray = SystemTrayIcon()
        received = []
        tray.toggle_voice_requested.connect(lambda: received.append(True))

        tray.toggle_voice_requested.emit()
        assert received == [True]
        tray.hide()


class TestSystemTrayIconUpdateState:
    """狀態更新測試。"""

    def test_update_state_idle(self, qapp):
        from airtype.ui.tray_icon import SystemTrayIcon

        tray = SystemTrayIcon()
        tray.update_state("IDLE")  # 不應拋出例外
        tray.hide()

    def test_update_state_listening(self, qapp):
        from airtype.ui.tray_icon import SystemTrayIcon

        tray = SystemTrayIcon()
        tray.update_state("LISTENING")
        tray.hide()

    def test_update_state_error(self, qapp):
        from airtype.ui.tray_icon import SystemTrayIcon

        tray = SystemTrayIcon()
        tray.update_state("ERROR")
        tray.hide()

    def test_update_state_unknown_no_error(self, qapp):
        from airtype.ui.tray_icon import SystemTrayIcon

        tray = SystemTrayIcon()
        tray.update_state("UNKNOWN_STATE")  # 不應拋出例外
        tray.hide()

    def test_update_state_changes_tooltip(self, qapp):
        from airtype.ui.tray_icon import SystemTrayIcon

        tray = SystemTrayIcon()
        tray.update_state("LISTENING")
        assert "聆聽中" in tray.toolTip()
        tray.hide()

    def test_update_state_updates_menu_status(self, qapp):
        from airtype.ui.tray_icon import SystemTrayIcon

        tray = SystemTrayIcon()
        tray.update_state("PROCESSING")
        # 選單中狀態說明文字應包含「處理中」
        menu = tray.contextMenu()
        disabled_actions = [a for a in menu.actions() if not a.isEnabled()]
        assert any("處理中" in a.text() for a in disabled_actions)
        tray.hide()


class TestSystemTrayIconNotify:
    """通知（showMessage）測試。"""

    def test_notify_enabled_calls_show_message(self, qapp, dummy_config, monkeypatch):
        from airtype.ui.tray_icon import SystemTrayIcon

        tray = SystemTrayIcon(config=dummy_config)
        calls = []
        monkeypatch.setattr(
            tray,
            "showMessage",
            lambda title, msg, icon=None, msecs=0: calls.append(msg),
        )
        tray.notify("測試辨識文字")
        assert len(calls) == 1
        assert "測試辨識文字" in calls[0]
        tray.hide()

    def test_notify_disabled_does_not_call_show_message(
        self, qapp, dummy_config_no_notify, monkeypatch
    ):
        from airtype.ui.tray_icon import SystemTrayIcon

        tray = SystemTrayIcon(config=dummy_config_no_notify)
        calls = []
        monkeypatch.setattr(
            tray,
            "showMessage",
            lambda *args, **kwargs: calls.append(args),
        )
        tray.notify("不應顯示的文字")
        assert len(calls) == 0
        tray.hide()

    def test_notify_long_text_truncated(self, qapp, dummy_config, monkeypatch):
        from airtype.ui.tray_icon import SystemTrayIcon, _NOTIFY_MAX_CHARS

        tray = SystemTrayIcon(config=dummy_config)
        calls = []
        monkeypatch.setattr(
            tray,
            "showMessage",
            lambda title, msg, icon=None, msecs=0: calls.append(msg),
        )
        long_text = "測" * 200
        tray.notify(long_text)
        assert len(calls) == 1
        assert len(calls[0]) <= _NOTIFY_MAX_CHARS
        tray.hide()

    def test_notify_no_config_shows_message(self, qapp, monkeypatch):
        from airtype.ui.tray_icon import SystemTrayIcon

        tray = SystemTrayIcon(config=None)  # 無設定時預設顯示
        calls = []
        monkeypatch.setattr(
            tray,
            "showMessage",
            lambda title, msg, icon=None, msecs=0: calls.append(msg),
        )
        tray.notify("無設定時的通知")
        assert len(calls) == 1
        tray.hide()


class TestConnectController:
    """連接 CoreController 測試。"""

    def test_connect_pure_python_controller(self, qapp):
        from airtype.core.controller import CoreController, AppState
        from airtype.ui.tray_icon import SystemTrayIcon

        controller = CoreController()
        tray = SystemTrayIcon()

        tray.connect_controller(controller)

        # 透過回呼驗證：觸發狀態變更後 tray 狀態應更新
        controller._emit_state_changed(AppState.LISTENING)
        assert tray._current_state == "LISTENING"
        tray.hide()


class TestCloseToTray:
    """close_to_tray 行為測試。"""

    def test_close_event_hides_window(self, qapp):
        from PySide6.QtWidgets import QWidget

        from airtype.ui.tray_icon import close_to_tray

        window = QWidget()
        window.show()
        assert window.isVisible()

        close_to_tray(window)

        # 模擬關閉事件
        from PySide6.QtGui import QCloseEvent

        event = QCloseEvent()
        window.closeEvent(event)

        assert event.isAccepted() is False  # 事件被攔截（ignore）
        assert not window.isVisible()       # 視窗已隱藏

    def test_close_event_does_not_quit(self, qapp):
        from PySide6.QtWidgets import QWidget

        from airtype.ui.tray_icon import close_to_tray

        window = QWidget()
        close_to_tray(window)

        from PySide6.QtGui import QCloseEvent

        event = QCloseEvent()
        # 不應拋出例外，也不應真正退出
        window.closeEvent(event)
        assert not event.isAccepted()
