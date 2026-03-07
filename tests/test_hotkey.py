"""快捷鍵與焦點管理測試。

涵蓋：
- parse_key_combo 按鍵組合解析（單元測試）
- FocusManager 各平台實作（mock 平台 API）
- HotkeyManager 切換狀態機與 Escape 取消（整合測試，mock pynput）
"""

from __future__ import annotations

import sys
from unittest.mock import MagicMock, call, patch

import pytest

from airtype.core.hotkey import (
    HotkeyManager,
    HotkeyState,
    parse_key_combo,
)
from airtype.utils.platform_utils import (
    LinuxFocusManager,
    MacOSFocusManager,
    WindowsFocusManager,
    create_focus_manager,
)


# ===========================================================================
# 4.1 parse_key_combo 單元測試
# ===========================================================================


class TestParseKeyCombo:
    """驗證按鍵組合字串解析（任務 4.1）。"""

    def test_ctrl_shift_space(self):
        assert parse_key_combo("ctrl+shift+space") == "<ctrl>+<shift>+<space>"

    def test_ctrl_alt_r(self):
        assert parse_key_combo("ctrl+alt+r") == "<ctrl>+<alt>+r"

    def test_alt_f1(self):
        assert parse_key_combo("alt+f1") == "<alt>+<f1>"

    def test_ctrl_shift_s(self):
        assert parse_key_combo("ctrl+shift+s") == "<ctrl>+<shift>+s"

    def test_cmd_alias(self):
        assert parse_key_combo("cmd+space") == "<cmd>+<space>"

    def test_super_alias(self):
        assert parse_key_combo("super+space") == "<cmd>+<space>"

    def test_escape_special_key(self):
        assert parse_key_combo("escape") == "<esc>"

    def test_esc_alias(self):
        assert parse_key_combo("esc") == "<esc>"

    def test_single_letter(self):
        assert parse_key_combo("r") == "r"

    def test_digit_key(self):
        assert parse_key_combo("ctrl+1") == "<ctrl>+1"

    def test_invalid_empty_string(self):
        with pytest.raises(ValueError, match="無效的按鍵組合"):
            parse_key_combo("")

    def test_invalid_unknown_key(self):
        with pytest.raises(ValueError, match="無法辨識的按鍵"):
            parse_key_combo("ctrl+unknownkey123")

    def test_case_insensitive(self):
        assert parse_key_combo("Ctrl+Shift+Space") == "<ctrl>+<shift>+<space>"

    def test_whitespace_trimmed(self):
        assert parse_key_combo("ctrl + shift + space") == "<ctrl>+<shift>+<space>"


# ===========================================================================
# 4.2 FocusManager 單元測試（mock 平台呼叫）
# ===========================================================================


class TestWindowsFocusManager:
    """驗證 WindowsFocusManager（mock ctypes）。

    ctypes 在方法內部匯入，因此以 patch.dict(sys.modules) 攔截。
    """

    def test_record_stores_hwnd(self):
        mgr = WindowsFocusManager()
        mock_ctypes = MagicMock()
        mock_ctypes.windll.user32.GetForegroundWindow.return_value = 42

        with patch.dict("sys.modules", {"ctypes": mock_ctypes}):
            mgr.record()

        assert mgr._hwnd == 42

    def test_restore_calls_set_foreground_window(self):
        mgr = WindowsFocusManager()
        mgr._hwnd = 99

        mock_ctypes = MagicMock()
        user32 = mock_ctypes.windll.user32
        user32.IsWindow.return_value = True
        user32.GetForegroundWindow.return_value = 10
        user32.GetWindowThreadProcessId.side_effect = lambda hwnd, _: (
            1001 if hwnd == 10 else 2002
        )

        with patch.dict("sys.modules", {"ctypes": mock_ctypes}):
            mgr.restore()

        user32.SetForegroundWindow.assert_called_once_with(99)

    def test_restore_without_record_logs_warning(self, caplog):
        import logging

        mgr = WindowsFocusManager()
        with caplog.at_level(logging.WARNING, logger="airtype.utils.platform_utils"):
            mgr.restore()
        assert "尚未記錄視窗" in caplog.text

    def test_restore_closed_window_logs_warning(self, caplog):
        import logging

        mgr = WindowsFocusManager()
        mgr._hwnd = 999

        mock_ctypes = MagicMock()
        mock_ctypes.windll.user32.IsWindow.return_value = False

        with patch.dict("sys.modules", {"ctypes": mock_ctypes}):
            with caplog.at_level(logging.WARNING, logger="airtype.utils.platform_utils"):
                mgr.restore()

        assert "已不存在" in caplog.text


class TestMacOSFocusManager:
    """驗證 MacOSFocusManager（mock subprocess）。"""

    def test_record_stores_app_name(self):
        mgr = MacOSFocusManager()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "Visual Studio Code\n"

        with patch("airtype.utils.platform_utils.subprocess.run", return_value=mock_result):
            mgr.record()

        assert mgr._app_name == "Visual Studio Code"

    def test_restore_calls_osascript_activate(self):
        mgr = MacOSFocusManager()
        mgr._app_name = "Visual Studio Code"

        mock_result = MagicMock()
        mock_result.returncode = 0

        with patch("airtype.utils.platform_utils.subprocess.run", return_value=mock_result) as mock_run:
            mgr.restore()

        args = mock_run.call_args[0][0]
        assert "osascript" in args
        assert "Visual Studio Code" in " ".join(args)

    def test_restore_without_record_logs_warning(self, caplog):
        import logging

        mgr = MacOSFocusManager()
        with caplog.at_level(logging.WARNING, logger="airtype.utils.platform_utils"):
            mgr.restore()
        assert "尚未記錄應用程式" in caplog.text

    def test_restore_failed_logs_warning(self, caplog):
        import logging

        mgr = MacOSFocusManager()
        mgr._app_name = "ClosedApp"

        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "Application not found"

        with patch("airtype.utils.platform_utils.subprocess.run", return_value=mock_result):
            with caplog.at_level(logging.WARNING, logger="airtype.utils.platform_utils"):
                mgr.restore()

        assert "還原焦點失敗" in caplog.text


class TestLinuxFocusManager:
    """驗證 LinuxFocusManager（mock subprocess）。"""

    def test_record_stores_window_id(self):
        mgr = LinuxFocusManager()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "12345678\n"

        with patch("airtype.utils.platform_utils.subprocess.run", return_value=mock_result):
            mgr.record()

        assert mgr._window_id == "12345678"

    def test_restore_calls_xdotool_windowactivate(self):
        mgr = LinuxFocusManager()
        mgr._window_id = "12345678"

        mock_result = MagicMock()
        mock_result.returncode = 0

        with patch("airtype.utils.platform_utils.subprocess.run", return_value=mock_result) as mock_run:
            mgr.restore()

        args = mock_run.call_args[0][0]
        assert "xdotool" in args
        assert "windowactivate" in args
        assert "12345678" in args

    def test_restore_without_record_logs_warning(self, caplog):
        import logging

        mgr = LinuxFocusManager()
        with caplog.at_level(logging.WARNING, logger="airtype.utils.platform_utils"):
            mgr.restore()
        assert "尚未記錄視窗 ID" in caplog.text

    def test_restore_closed_window_logs_warning(self, caplog):
        import logging

        mgr = LinuxFocusManager()
        mgr._window_id = "99999"

        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "No such window"

        with patch("airtype.utils.platform_utils.subprocess.run", return_value=mock_result):
            with caplog.at_level(logging.WARNING, logger="airtype.utils.platform_utils"):
                mgr.restore()

        assert "還原焦點失敗" in caplog.text


class TestCreateFocusManager:
    """驗證工廠函式依平台回傳正確實作。"""

    def test_factory_windows(self):
        with patch.object(sys, "platform", "win32"):
            mgr = create_focus_manager()
        assert isinstance(mgr, WindowsFocusManager)

    def test_factory_macos(self):
        with patch.object(sys, "platform", "darwin"):
            mgr = create_focus_manager()
        assert isinstance(mgr, MacOSFocusManager)

    def test_factory_linux(self):
        with patch.object(sys, "platform", "linux"):
            mgr = create_focus_manager()
        assert isinstance(mgr, LinuxFocusManager)

    def test_factory_unsupported_raises(self):
        with patch.object(sys, "platform", "freebsd"):
            with pytest.raises(NotImplementedError):
                create_focus_manager()


# ===========================================================================
# 4.3 HotkeyManager 整合測試（mock pynput）
# ===========================================================================


class _MockShortcutsConfig:
    toggle_voice = "ctrl+shift+space"
    cancel = "escape"


class TestHotkeyManagerToggle:
    """驗證切換狀態轉換（任務 4.3）。"""

    def _make_manager(self):
        """建立 HotkeyManager，mock pynput 模組。"""
        mock_pynput = MagicMock()
        mock_keyboard = MagicMock()
        mock_pynput.keyboard = mock_keyboard
        mock_keyboard.GlobalHotKeys.return_value = MagicMock()
        mock_keyboard.Listener.return_value = MagicMock()
        # Key.esc mock
        mock_keyboard.Key.esc = "ESC_SENTINEL"

        with patch.dict("sys.modules", {"pynput": mock_pynput, "pynput.keyboard": mock_keyboard}):
            mgr = HotkeyManager(_MockShortcutsConfig())
            mgr.start()

        return mgr, mock_keyboard

    def test_initial_state_inactive(self):
        mgr = HotkeyManager(_MockShortcutsConfig())
        assert mgr.state == HotkeyState.INACTIVE

    def test_first_toggle_activates(self):
        mgr = HotkeyManager(_MockShortcutsConfig())
        started = []
        mgr.on_start(lambda: started.append(True))

        mgr._handle_toggle()

        assert mgr.state == HotkeyState.ACTIVE
        assert len(started) == 1

    def test_second_toggle_deactivates(self):
        mgr = HotkeyManager(_MockShortcutsConfig())
        stopped = []
        mgr.on_stop(lambda: stopped.append(True))

        mgr._handle_toggle()  # INACTIVE → ACTIVE
        mgr._handle_toggle()  # ACTIVE → INACTIVE

        assert mgr.state == HotkeyState.INACTIVE
        assert len(stopped) == 1

    def test_escape_cancels_when_active(self):
        mgr = HotkeyManager(_MockShortcutsConfig())
        cancelled = []
        mgr.on_cancel(lambda: cancelled.append(True))

        mgr._handle_toggle()  # INACTIVE → ACTIVE

        # 使用獨立 sentinel 物件作為 Key.esc 替代，patch sys.modules 攔截
        esc_sentinel = object()
        mock_kb = MagicMock()
        mock_kb.Key.esc = esc_sentinel

        with patch.dict("sys.modules", {"pynput.keyboard": mock_kb}):
            mgr._handle_key_press(esc_sentinel)

        assert mgr.state == HotkeyState.INACTIVE
        assert len(cancelled) == 1

    def test_escape_noop_when_inactive(self):
        mgr = HotkeyManager(_MockShortcutsConfig())
        cancelled = []
        mgr.on_cancel(lambda: cancelled.append(True))

        # state 為 INACTIVE，按 Escape 為 no-op
        esc_sentinel = object()
        mock_kb = MagicMock()
        mock_kb.Key.esc = esc_sentinel

        with patch.dict("sys.modules", {"pynput.keyboard": mock_kb}):
            mgr._handle_key_press(esc_sentinel)

        assert mgr.state == HotkeyState.INACTIVE
        assert len(cancelled) == 0

    def test_start_registers_hotkey_with_pynput(self):
        """驗證 start() 以正確組合向 GlobalHotKeys 註冊。"""
        mock_pynput_kb = MagicMock()
        mock_global_hotkeys = MagicMock()
        mock_pynput_kb.GlobalHotKeys.return_value = mock_global_hotkeys
        mock_pynput_kb.Listener.return_value = MagicMock()

        with patch.dict("sys.modules", {"pynput": MagicMock(keyboard=mock_pynput_kb), "pynput.keyboard": mock_pynput_kb}):
            mgr = HotkeyManager(_MockShortcutsConfig())
            with patch("airtype.core.hotkey._check_platform_support"):
                mgr.start()

        # 確認以正確按鍵組合呼叫 GlobalHotKeys
        call_kwargs = mock_pynput_kb.GlobalHotKeys.call_args
        hotkey_dict = call_kwargs[0][0]
        assert "<ctrl>+<shift>+<space>" in hotkey_dict

    def test_stop_resets_state(self):
        mgr = HotkeyManager(_MockShortcutsConfig())
        mgr._handle_toggle()  # INACTIVE → ACTIVE
        assert mgr.state == HotkeyState.ACTIVE

        # mock listeners
        mgr._hotkey_listener = MagicMock()
        mgr._escape_listener = MagicMock()
        mgr.stop()

        assert mgr.state == HotkeyState.INACTIVE
        mgr._hotkey_listener = None  # already cleared by stop()

    def test_multiple_toggle_cycles(self):
        """驗證多次切換的完整狀態轉換序列。"""
        mgr = HotkeyManager(_MockShortcutsConfig())
        events = []
        mgr.on_start(lambda: events.append("start"))
        mgr.on_stop(lambda: events.append("stop"))

        mgr._handle_toggle()  # → ACTIVE
        mgr._handle_toggle()  # → INACTIVE
        mgr._handle_toggle()  # → ACTIVE
        mgr._handle_toggle()  # → INACTIVE

        assert events == ["start", "stop", "start", "stop"]
        assert mgr.state == HotkeyState.INACTIVE

    def test_reset_state_from_active(self):
        """reset_state() 應將 ACTIVE 重置為 INACTIVE，不觸發任何 callback。"""
        mgr = HotkeyManager(_MockShortcutsConfig())
        events = []
        mgr.on_stop(lambda: events.append("stop"))

        mgr._handle_toggle()  # → ACTIVE
        assert mgr.state == HotkeyState.ACTIVE

        mgr.reset_state()  # 強制重置，不觸發 callback
        assert mgr.state == HotkeyState.INACTIVE
        assert events == []  # on_stop 不應被呼叫

    def test_reset_state_from_inactive_is_noop(self):
        """reset_state() 在 INACTIVE 狀態下呼叫應為 idempotent。"""
        mgr = HotkeyManager(_MockShortcutsConfig())
        assert mgr.state == HotkeyState.INACTIVE
        mgr.reset_state()
        assert mgr.state == HotkeyState.INACTIVE

    def test_after_reset_next_toggle_triggers_start(self):
        """reset_state() 後再次按快捷鍵應觸發 on_start（不是 on_stop）。"""
        mgr = HotkeyManager(_MockShortcutsConfig())
        events = []
        mgr.on_start(lambda: events.append("start"))
        mgr.on_stop(lambda: events.append("stop"))

        mgr._handle_toggle()  # → ACTIVE（呼叫 on_start）
        mgr.reset_state()     # 強制回 INACTIVE
        mgr._handle_toggle()  # → ACTIVE again（應再次呼叫 on_start）

        assert events == ["start", "start"]
