"""快捷鍵設定頁面。

提供 ShortcutRecorderWidget（透過 keyPressEvent 擷取按鍵組合）
以及快捷鍵設定頁面 SettingsShortcutsPage。

純 Python 輔助函式（format_key_combo、detect_conflict）不依賴 PySide6，
可直接單元測試。
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from airtype.config import AirtypeConfig

from airtype.utils.i18n import tr  # noqa: E402

# 修飾鍵排序優先順序（越小越靠前）
_MODIFIER_ORDER = {"ctrl": 0, "shift": 1, "alt": 2, "meta": 3}


# ---------------------------------------------------------------------------
# 純 Python 輔助函式
# ---------------------------------------------------------------------------


def format_key_combo(modifiers: list[str], key: str) -> str:
    """將修飾鍵列表與主鍵格式化為標準字串（如 ctrl+shift+space）。

    Args:
        modifiers: 修飾鍵名稱列表（不分大小寫）。
        key: 主鍵名稱（不可為空）。

    Returns:
        格式化後的按鍵組合字串。

    Raises:
        ValueError: key 為空字串時引發。
    """
    if not key:
        raise ValueError("key 不可為空字串")

    # 正規化為小寫並排序
    sorted_mods = sorted(
        (m.lower() for m in modifiers),
        key=lambda m: _MODIFIER_ORDER.get(m, 99),
    )
    parts = sorted_mods + [key.lower()]
    return "+".join(parts)


def detect_conflict(
    combo: str,
    shortcuts: dict[str, str],
    ignore_key: Optional[str],
) -> Optional[str]:
    """偵測按鍵組合是否與現有快捷鍵衝突。

    Args:
        combo: 要檢查的按鍵組合字串。
        shortcuts: 現有快捷鍵字典 {key_name: combo}。
        ignore_key: 忽略此快捷鍵名稱（用於更新同一快捷鍵）。

    Returns:
        衝突的快捷鍵名稱，無衝突時回傳 None。
    """
    for key_name, existing_combo in shortcuts.items():
        if key_name == ignore_key:
            continue
        if existing_combo == combo:
            return key_name
    return None


# ---------------------------------------------------------------------------
# Qt 元件（需要 PySide6）
# ---------------------------------------------------------------------------

try:
    from PySide6.QtCore import Qt, Signal
    from PySide6.QtGui import QKeyEvent
    from PySide6.QtWidgets import (
        QFrame,
        QHBoxLayout,
        QLabel,
        QMessageBox,
        QPushButton,
        QScrollArea,
        QSizePolicy,
        QVBoxLayout,
        QWidget,
    )

    _PYSIDE6_AVAILABLE = True
except ImportError:
    _PYSIDE6_AVAILABLE = False


if _PYSIDE6_AVAILABLE:

    class ShortcutRecorderWidget(QWidget):
        """按鍵組合錄製元件。

        透過覆寫 keyPressEvent 擷取按鍵組合，即時顯示已擷取的組合，
        並對現有快捷鍵進行衝突驗證。

        Signals:
            combo_changed(str): 新的按鍵組合已確認時發射。
        """

        combo_changed = Signal(str)

        def __init__(
            self,
            current_combo: str = "",
            parent: Optional[QWidget] = None,
        ) -> None:
            super().__init__(parent)
            self._current_combo = current_combo
            self._is_recording = False

            self._build_ui()

        # ── 屬性 ─────────────────────────────────────────────────────────────

        @property
        def current_combo(self) -> str:
            return self._current_combo

        @property
        def is_recording(self) -> bool:
            return self._is_recording

        # ── 公開方法 ─────────────────────────────────────────────────────────

        def start_recording(self) -> None:
            """進入錄製模式。"""
            self._is_recording = True
            self._combo_label.setText(tr("settings.shortcuts.recorder.recording"))
            self._record_btn.setText(tr("settings.shortcuts.recorder.cancel_btn"))
            self.setFocus()

        def stop_recording(self) -> None:
            """離開錄製模式。"""
            self._is_recording = False
            self._combo_label.setText(
                self._current_combo or tr("settings.shortcuts.recorder.not_set")
            )
            self._record_btn.setText(tr("settings.shortcuts.recorder.record_btn"))

        # ── UI 建構 ──────────────────────────────────────────────────────────

        def _build_ui(self) -> None:
            layout = QHBoxLayout(self)
            layout.setContentsMargins(0, 0, 0, 0)

            self._combo_label = QLabel(
                self._current_combo or tr("settings.shortcuts.recorder.not_set")
            )
            self._combo_label.setMinimumWidth(160)
            self._combo_label.setStyleSheet(
                "border: 1px solid #ccc; border-radius: 4px; padding: 2px 6px;"
            )
            layout.addWidget(self._combo_label)

            self._record_btn = QPushButton(tr("settings.shortcuts.recorder.record_btn"))
            self._record_btn.setFixedWidth(60)
            self._record_btn.clicked.connect(self._on_record_clicked)
            layout.addWidget(self._record_btn)

        def _on_record_clicked(self) -> None:
            if self._is_recording:
                self.stop_recording()
            else:
                self.start_recording()

        # ── 按鍵事件擷取 ─────────────────────────────────────────────────────

        def keyPressEvent(self, event: QKeyEvent) -> None:
            if not self._is_recording:
                super().keyPressEvent(event)
                return

            key = event.key()
            modifiers = event.modifiers()

            # 純修飾鍵按下時不結束錄製
            modifier_keys = {
                Qt.Key.Key_Control,
                Qt.Key.Key_Shift,
                Qt.Key.Key_Alt,
                Qt.Key.Key_Meta,
            }
            if key in modifier_keys:
                return

            # Escape 取消錄製
            if key == Qt.Key.Key_Escape:
                self.stop_recording()
                return

            # 組合修飾鍵
            mod_parts: list[str] = []
            if modifiers & Qt.KeyboardModifier.ControlModifier:
                mod_parts.append("ctrl")
            if modifiers & Qt.KeyboardModifier.ShiftModifier:
                mod_parts.append("shift")
            if modifiers & Qt.KeyboardModifier.AltModifier:
                mod_parts.append("alt")
            if modifiers & Qt.KeyboardModifier.MetaModifier:
                mod_parts.append("meta")

            # 主鍵名稱
            key_text = event.text().strip()
            if not key_text:
                key_text = self._qt_key_to_name(key)

            new_combo = format_key_combo(mod_parts, key_text)
            self._current_combo = new_combo
            self.stop_recording()
            self.combo_changed.emit(new_combo)

        @staticmethod
        def _qt_key_to_name(key: int) -> str:
            """將 Qt.Key 轉換為可讀名稱。"""
            _KEY_NAMES: dict[int, str] = {
                Qt.Key.Key_Space: "space",
                Qt.Key.Key_Return: "return",
                Qt.Key.Key_Enter: "enter",
                Qt.Key.Key_Backspace: "backspace",
                Qt.Key.Key_Tab: "tab",
                Qt.Key.Key_Delete: "delete",
                Qt.Key.Key_Home: "home",
                Qt.Key.Key_End: "end",
                Qt.Key.Key_PageUp: "pageup",
                Qt.Key.Key_PageDown: "pagedown",
                Qt.Key.Key_Up: "up",
                Qt.Key.Key_Down: "down",
                Qt.Key.Key_Left: "left",
                Qt.Key.Key_Right: "right",
                Qt.Key.Key_F1: "f1",
                Qt.Key.Key_F2: "f2",
                Qt.Key.Key_F3: "f3",
                Qt.Key.Key_F4: "f4",
                Qt.Key.Key_F5: "f5",
                Qt.Key.Key_F6: "f6",
                Qt.Key.Key_F7: "f7",
                Qt.Key.Key_F8: "f8",
                Qt.Key.Key_F9: "f9",
                Qt.Key.Key_F10: "f10",
                Qt.Key.Key_F11: "f11",
                Qt.Key.Key_F12: "f12",
            }
            return _KEY_NAMES.get(key, f"key{key}")

    # ── 頁面 ─────────────────────────────────────────────────────────────────

    class SettingsShortcutsPage(QWidget):
        """快捷鍵設定頁面。

        列出所有可設定的快捷鍵及其目前按鍵組合，
        每個快捷鍵均有錄製按鈕可透過按鍵事件擷取新組合。
        """

        shortcuts_changed = Signal()

        # 快捷鍵顯示名稱對應
        _SHORTCUT_I18N_KEYS: dict[str, str] = {
            "toggle_voice": "settings.shortcuts.shortcut.toggle_voice",
            "cancel": "settings.shortcuts.shortcut.cancel",
            "open_settings": "settings.shortcuts.shortcut.open_settings",
            "switch_language": "settings.shortcuts.shortcut.switch_language",
            "switch_dictionary": "settings.shortcuts.shortcut.switch_dictionary",
            "toggle_polish": "settings.shortcuts.shortcut.toggle_polish",
        }

        def __init__(
            self,
            config: "AirtypeConfig",
            schedule_save_fn: object = None,
            parent: Optional[QWidget] = None,
        ) -> None:
            super().__init__(parent)
            self._config = config
            self._schedule_save = schedule_save_fn
            self._recorders: dict[str, ShortcutRecorderWidget] = {}
            self._row_labels: dict[str, "QLabel"] = {}
            self._build_ui()

        def _build_ui(self) -> None:
            outer = QVBoxLayout(self)
            outer.setContentsMargins(16, 16, 16, 16)

            self._title_label = QLabel(tr("settings.shortcuts.title"))
            self._title_label.setStyleSheet("font-size: 16px; font-weight: bold;")
            outer.addWidget(self._title_label)

            self._hint_label = QLabel(tr("settings.shortcuts.hint"))
            self._hint_label.setStyleSheet("color: #666; font-size: 12px;")
            outer.addWidget(self._hint_label)

            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setFrameShape(QFrame.Shape.NoFrame)
            outer.addWidget(scroll)

            container = QWidget()
            scroll.setWidget(container)
            grid = QVBoxLayout(container)
            grid.setSpacing(8)

            shortcuts = self._config.shortcuts
            for key_name, i18n_key in self._SHORTCUT_I18N_KEYS.items():
                label_text = tr(i18n_key)
                current = getattr(shortcuts, key_name, "")
                row = self._make_row(key_name, label_text, current)
                grid.addWidget(row)

            grid.addStretch()

        def _make_row(self, key_name: str, label_text: str, current_combo: str) -> QFrame:
            frame = QFrame()
            frame.setFrameShape(QFrame.Shape.StyledPanel)
            layout = QHBoxLayout(frame)
            layout.setContentsMargins(8, 4, 8, 4)

            label = QLabel(label_text)
            label.setMinimumWidth(140)
            label.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred)
            layout.addWidget(label)
            self._row_labels[key_name] = label

            recorder = ShortcutRecorderWidget(current_combo=current_combo)
            recorder.combo_changed.connect(
                lambda combo, kn=key_name: self._on_combo_changed(kn, combo)
            )
            self._recorders[key_name] = recorder
            layout.addWidget(recorder)
            layout.addStretch()

            return frame

        def retranslate_ui(self, _: str = None) -> None:
            """語言切換時刷新所有標籤文字。"""
            self._title_label.setText(tr("settings.shortcuts.title"))
            self._hint_label.setText(tr("settings.shortcuts.hint"))
            for key_name, i18n_key in self._SHORTCUT_I18N_KEYS.items():
                if key_name in self._row_labels:
                    self._row_labels[key_name].setText(tr(i18n_key))

        def _on_combo_changed(self, key_name: str, new_combo: str) -> None:
            """按鍵組合變更時更新 config 並觸發自動儲存。"""
            # 衝突偵測
            shortcuts_dict = {
                k: getattr(self._config.shortcuts, k)
                for k in self._config.shortcuts.__dataclass_fields__
            }
            conflict = detect_conflict(new_combo, shortcuts_dict, ignore_key=key_name)
            if conflict:
                conflict_label = tr(self._SHORTCUT_I18N_KEYS.get(conflict, conflict))
                reply = QMessageBox.question(
                    self,
                    tr("settings.shortcuts.conflict_title"),
                    tr("settings.shortcuts.conflict_msg").format(new_combo, conflict_label),
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                )
                if reply != QMessageBox.StandardButton.Yes:
                    # 還原顯示
                    self._recorders[key_name].stop_recording()
                    return
                # 清除衝突的快捷鍵
                setattr(self._config.shortcuts, conflict, "")

            setattr(self._config.shortcuts, key_name, new_combo)
            if callable(self._schedule_save):
                self._schedule_save()
            self.shortcuts_changed.emit()

else:
    # PySide6 不可用時提供佔位符
    class ShortcutRecorderWidget:  # type: ignore[no-redef]
        def __init__(self, current_combo: str = "", parent=None) -> None:
            self._current_combo = current_combo
            self._is_recording = False

        @property
        def current_combo(self) -> str:
            return self._current_combo

        @property
        def is_recording(self) -> bool:
            return self._is_recording

        def start_recording(self) -> None:
            self._is_recording = True

        def stop_recording(self) -> None:
            self._is_recording = False

    class SettingsShortcutsPage:  # type: ignore[no-redef]
        pass
