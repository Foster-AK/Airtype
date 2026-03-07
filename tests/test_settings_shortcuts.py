"""快捷鍵錄製器單元測試（TDD）。

涵蓋：
- 任務 2.4：ShortcutRecorderWidget 按鍵擷取
- 衝突偵測邏輯
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


# ─────────────────────────────────────────────────────────────────────────────
# 純 Python 輔助函式測試（不依賴 PySide6）
# ─────────────────────────────────────────────────────────────────────────────


class TestKeyComboFormatting:
    """按鍵組合格式化輔助函式測試。"""

    def test_format_single_key(self):
        """單個按鍵應回傳其名稱。"""
        from airtype.ui.settings_shortcuts import format_key_combo

        assert format_key_combo([], "a") == "a"

    def test_format_ctrl_shift_space(self):
        """Ctrl+Shift+Space 應正確格式化。"""
        from airtype.ui.settings_shortcuts import format_key_combo

        result = format_key_combo(["ctrl", "shift"], "space")
        assert result == "ctrl+shift+space"

    def test_format_modifiers_sorted(self):
        """修飾鍵應依固定順序排列（ctrl < shift < alt）。"""
        from airtype.ui.settings_shortcuts import format_key_combo

        result = format_key_combo(["alt", "ctrl"], "x")
        assert result == "ctrl+alt+x"

    def test_format_empty_key_raises(self):
        """按鍵為空字串應引發 ValueError。"""
        from airtype.ui.settings_shortcuts import format_key_combo

        with pytest.raises(ValueError):
            format_key_combo([], "")


class TestConflictDetection:
    """快捷鍵衝突偵測測試。"""

    def test_no_conflict_with_empty_shortcuts(self):
        """空的快捷鍵字典不應有衝突。"""
        from airtype.ui.settings_shortcuts import detect_conflict

        result = detect_conflict("ctrl+shift+space", {}, ignore_key=None)
        assert result is None

    def test_detect_conflict_with_existing(self):
        """與現有快捷鍵相同應回傳衝突的按鍵名稱。"""
        from airtype.ui.settings_shortcuts import detect_conflict

        shortcuts = {"toggle_voice": "ctrl+shift+space", "cancel": "escape"}
        result = detect_conflict("ctrl+shift+space", shortcuts, ignore_key="cancel")
        assert result == "toggle_voice"

    def test_no_conflict_when_ignoring_same_key(self):
        """更新同一快捷鍵本身不應視為衝突。"""
        from airtype.ui.settings_shortcuts import detect_conflict

        shortcuts = {"toggle_voice": "ctrl+shift+space"}
        result = detect_conflict("ctrl+shift+space", shortcuts, ignore_key="toggle_voice")
        assert result is None

    def test_different_combo_no_conflict(self):
        """不同按鍵組合不應有衝突。"""
        from airtype.ui.settings_shortcuts import detect_conflict

        shortcuts = {"toggle_voice": "ctrl+shift+space"}
        result = detect_conflict("ctrl+alt+v", shortcuts, ignore_key=None)
        assert result is None


# ─────────────────────────────────────────────────────────────────────────────
# Qt 元件測試（需要 PySide6）
# ─────────────────────────────────────────────────────────────────────────────


class TestShortcutRecorderWidget:
    """ShortcutRecorderWidget Qt 元件測試。"""

    def test_widget_importable(self):
        """ShortcutRecorderWidget 應可匯入。"""
        from airtype.ui.settings_shortcuts import ShortcutRecorderWidget

    def test_widget_initial_state(self, qapp):
        """錄製器初始狀態應為非錄製中。"""
        pytest.importorskip("PySide6")
        from airtype.ui.settings_shortcuts import ShortcutRecorderWidget

        widget = ShortcutRecorderWidget(current_combo="ctrl+shift+space")
        assert widget.is_recording is False

    def test_widget_initial_display(self, qapp):
        """錄製器應顯示初始按鍵組合。"""
        pytest.importorskip("PySide6")
        from airtype.ui.settings_shortcuts import ShortcutRecorderWidget

        widget = ShortcutRecorderWidget(current_combo="ctrl+shift+space")
        assert widget.current_combo == "ctrl+shift+space"

    def test_start_recording(self, qapp):
        """start_recording() 後 is_recording 應為 True。"""
        pytest.importorskip("PySide6")
        from airtype.ui.settings_shortcuts import ShortcutRecorderWidget

        widget = ShortcutRecorderWidget(current_combo="ctrl+shift+space")
        widget.start_recording()
        assert widget.is_recording is True

    def test_stop_recording(self, qapp):
        """stop_recording() 後 is_recording 應為 False。"""
        pytest.importorskip("PySide6")
        from airtype.ui.settings_shortcuts import ShortcutRecorderWidget

        widget = ShortcutRecorderWidget(current_combo="ctrl+shift+space")
        widget.start_recording()
        widget.stop_recording()
        assert widget.is_recording is False
