"""TextInjector 單元測試與整合測試。

涵蓋：
  - 剪貼簿備份 / 還原往返（需求：Clipboard Backup、Clipboard Restore）
  - 注入時序（需求：Injection Timing）
  - 跨平台貼上模擬（需求：Cross-Platform Paste Simulation）
  - 整合注入（需求：Text Injection via Paste）
"""

from __future__ import annotations

import os
import sys
import time
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# 輔助夾具
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_config():
    cfg = MagicMock()
    cfg.general.clipboard_restore_delay_ms = 150
    return cfg


@pytest.fixture
def injector(mock_config):
    from airtype.core.text_injector import TextInjector

    return TextInjector(mock_config)


@pytest.fixture
def injector_with_focus(mock_config):
    from airtype.core.hotkey import FocusManager
    from airtype.core.text_injector import TextInjector

    focus_mgr = MagicMock(spec=FocusManager)
    return TextInjector(mock_config, focus_manager=focus_mgr), focus_mgr


# ---------------------------------------------------------------------------
# 3.1 剪貼簿備份 / 還原往返測試
# ---------------------------------------------------------------------------


def test_clipboard_backup_restore_roundtrip(injector):
    """備份 → 覆寫 → 還原 → 原始值應完整返回。"""
    import pyperclip

    original = "original clipboard content 原始剪貼簿"
    pyperclip.copy(original)

    injector._backup_clipboard()
    pyperclip.copy("overwritten 覆寫")
    injector._restore_clipboard()

    assert pyperclip.paste() == original


def test_clipboard_backup_empty(injector):
    """空剪貼簿備份值應為空字串。"""
    import pyperclip

    pyperclip.copy("")
    injector._backup_clipboard()

    assert injector._backup == ""


def test_clipboard_backup_non_text_treated_as_empty(injector):
    """pyperclip 擲出例外時，備份值應退為空字串。"""
    with patch("pyperclip.paste", side_effect=Exception("非文字剪貼簿")):
        injector._backup_clipboard()

    assert injector._backup == ""


def test_clipboard_restore_writes_backup(injector):
    """_restore_clipboard() 應將 _backup 內容寫回剪貼簿。"""
    import pyperclip

    injector._backup = "restore me 請還原"
    pyperclip.copy("other")
    injector._restore_clipboard()

    assert pyperclip.paste() == "restore me 請還原"


def test_inject_restores_empty_clipboard(injector):
    """Restore Empty Clipboard After Injection：原始剪貼簿為空時，注入後剪貼簿應還原為空字串。"""
    import pyperclip

    pyperclip.copy("")
    with (patch("pyautogui.hotkey"), patch("time.sleep")):
        injector.inject("some text 注入文字")

    assert pyperclip.paste() == ""


# ---------------------------------------------------------------------------
# 3.2 注入時序測試
# ---------------------------------------------------------------------------


def test_inject_timing_under_300ms(injector_with_focus):
    """完整注入週期（sleep 已 mock）的純函式呼叫開銷應遠低於 300ms。"""
    injector, focus_mgr = injector_with_focus

    with (
        patch("pyperclip.paste", return_value="old"),
        patch("pyperclip.copy"),
        patch("pyautogui.hotkey"),
        patch("time.sleep"),
    ):
        start = time.perf_counter()
        injector.inject("測試文字")
        elapsed_ms = (time.perf_counter() - start) * 1000

    assert elapsed_ms < 300, f"注入耗時 {elapsed_ms:.1f}ms，超過 300ms 限制"


def test_inject_calls_focus_restore_before_paste(injector_with_focus):
    """inject() 應在模擬貼上前呼叫 FocusManager.restore_focus()。"""
    injector, focus_mgr = injector_with_focus

    call_order: list[str] = []
    focus_mgr.restore_focus.side_effect = lambda: call_order.append("restore_focus")

    with (
        patch("pyperclip.paste", return_value=""),
        patch("pyperclip.copy"),
        patch(
            "pyautogui.hotkey",
            side_effect=lambda *a: call_order.append("paste"),
        ),
        patch("time.sleep"),
    ):
        injector.inject("hello")

    assert "restore_focus" in call_order
    assert "paste" in call_order
    assert call_order.index("restore_focus") < call_order.index("paste")


def test_inject_without_focus_manager_does_not_raise(injector):
    """無 FocusManager 時 inject() 應正常執行不拋例外。"""
    with (
        patch("pyperclip.paste", return_value=""),
        patch("pyperclip.copy"),
        patch("pyautogui.hotkey"),
        patch("time.sleep"),
    ):
        injector.inject("no focus manager")  # 不應拋出例外


def test_inject_sleep_calls(injector_with_focus):
    """inject() 應各 sleep 一次：50ms 焦點穩定、restore delay。"""
    injector, _ = injector_with_focus

    with (
        patch("pyperclip.paste", return_value=""),
        patch("pyperclip.copy"),
        patch("pyautogui.hotkey"),
        patch("time.sleep") as mock_sleep,
    ):
        injector.inject("text")

    sleep_args = [c.args[0] for c in mock_sleep.call_args_list]
    assert pytest.approx(0.050, abs=0.001) in sleep_args  # 焦點穩定 50ms
    assert pytest.approx(0.150, abs=0.001) in sleep_args  # restore delay 150ms


# ---------------------------------------------------------------------------
# 跨平台貼上模擬測試
# ---------------------------------------------------------------------------


def test_simulate_paste_windows():
    """Windows 平台應使用 Ctrl+V。"""
    from airtype.core.text_injector import TextInjector

    cfg = MagicMock()
    cfg.general.clipboard_restore_delay_ms = 0
    injector = TextInjector(cfg)

    with (
        patch.object(sys, "platform", "win32"),
        patch("pyperclip.paste", return_value=""),
        patch("pyperclip.copy"),
        patch("pyautogui.hotkey") as mock_hotkey,
        patch("time.sleep"),
    ):
        injector.inject("test")

    mock_hotkey.assert_called_once_with("ctrl", "v")


def test_simulate_paste_macos():
    """macOS 平台應使用 Cmd+V。"""
    from airtype.core.text_injector import TextInjector

    cfg = MagicMock()
    cfg.general.clipboard_restore_delay_ms = 0
    injector = TextInjector(cfg)

    with (
        patch.object(sys, "platform", "darwin"),
        patch("pyperclip.paste", return_value=""),
        patch("pyperclip.copy"),
        patch("pyautogui.hotkey") as mock_hotkey,
        patch("time.sleep"),
    ):
        injector.inject("test")

    mock_hotkey.assert_called_once_with("command", "v")


def test_simulate_paste_linux():
    """Linux 平台應使用 Ctrl+V。"""
    from airtype.core.text_injector import TextInjector

    cfg = MagicMock()
    cfg.general.clipboard_restore_delay_ms = 0
    injector = TextInjector(cfg)

    with (
        patch.object(sys, "platform", "linux"),
        patch("pyperclip.paste", return_value=""),
        patch("pyperclip.copy"),
        patch("pyautogui.hotkey") as mock_hotkey,
        patch("time.sleep"),
    ):
        injector.inject("test")

    mock_hotkey.assert_called_once_with("ctrl", "v")


# ---------------------------------------------------------------------------
# 3.3 整合測試（需要 PySide6，且非 CI headless）
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    "CI" in os.environ or "GITHUB_ACTIONS" in os.environ,
    reason="整合測試需要顯示伺服器，跳過 CI/CD headless 環境",
)
def test_integration_inject_to_qlineedit():
    """整合測試：注入文字至 QLineEdit 並驗證文字到達。

    pyautogui.hotkey 被 mock 為直接呼叫 QLineEdit.paste()，
    驗證完整注入流程（剪貼簿寫入 → 貼上 → 還原）的端對端行為。
    """
    pytest.importorskip("PySide6", reason="需要 PySide6")

    from PySide6.QtWidgets import QApplication, QLineEdit

    from airtype.core.text_injector import TextInjector

    app = QApplication.instance() or QApplication([])

    field = QLineEdit()
    field.show()
    app.processEvents()

    cfg = MagicMock()
    cfg.general.clipboard_restore_delay_ms = 0
    injector = TextInjector(cfg)

    test_text = "整合測試文字 Integration"

    def fake_paste(*args):
        field.paste()
        app.processEvents()

    with (
        patch("pyautogui.hotkey", side_effect=fake_paste),
        patch("time.sleep"),
    ):
        injector.inject(test_text)

    assert field.text() == test_text

    field.close()
