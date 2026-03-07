"""一般設定頁面。

提供 SettingsGeneralPage：語言、自動啟動、啟動最小化、靜音逾時、
附加空格、附加換行、通知、日誌等級等控制項。
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from airtype.config import AirtypeConfig

from airtype.utils.i18n import tr, set_language as i18n_set_language

try:
    from PySide6.QtWidgets import (
        QCheckBox,
        QComboBox,
        QFormLayout,
        QLabel,
        QSlider,
        QVBoxLayout,
        QWidget,
    )
    from PySide6.QtCore import Qt

    _PYSIDE6_AVAILABLE = True
except ImportError:
    _PYSIDE6_AVAILABLE = False


if _PYSIDE6_AVAILABLE:

    class SettingsGeneralPage(QWidget):
        """一般設定頁面。"""

        _LANGUAGES = [
            ("繁體中文", "zh_TW"),
            ("簡體中文", "zh_CN"),
            ("English", "en"),
            ("日本語", "ja"),
        ]
        _LOG_LEVELS = ["DEBUG", "INFO", "WARNING", "ERROR"]

        def __init__(
            self,
            config: "AirtypeConfig",
            schedule_save_fn: object = None,
            parent: Optional[QWidget] = None,
        ) -> None:
            super().__init__(parent)
            self._config = config
            self._schedule_save = schedule_save_fn
            self._build_ui()

        def _build_ui(self) -> None:
            outer = QVBoxLayout(self)
            outer.setContentsMargins(16, 16, 16, 16)

            self._title_label = QLabel(tr("settings.general.title"))
            self._title_label.setStyleSheet("font-size: 16px; font-weight: bold;")
            outer.addWidget(self._title_label)

            self._form = QFormLayout()
            self._form.setVerticalSpacing(10)
            outer.addLayout(self._form)

            # 語言
            self._lang_combo = QComboBox()
            for label, code in self._LANGUAGES:
                self._lang_combo.addItem(label, code)
            idx = next(
                (i for i, (_, c) in enumerate(self._LANGUAGES)
                 if c == self._config.general.language),
                0,
            )
            self._lang_combo.setCurrentIndex(idx)
            self._lang_combo.currentIndexChanged.connect(self._on_lang_changed)
            self._form.addRow(tr("settings.general.language"), self._lang_combo)

            # 自動啟動
            self._auto_start_cb = QCheckBox()
            self._auto_start_cb.setChecked(self._config.general.auto_start)
            self._auto_start_cb.stateChanged.connect(self._on_auto_start_changed)
            self._form.addRow(tr("settings.general.auto_start"), self._auto_start_cb)

            # 啟動最小化
            self._minimized_cb = QCheckBox()
            self._minimized_cb.setChecked(self._config.general.start_minimized)
            self._minimized_cb.stateChanged.connect(self._on_minimized_changed)
            self._form.addRow(tr("settings.general.start_minimized"), self._minimized_cb)

            # 靜音逾時（0.5–5.0 秒，步長 0.5）
            self._timeout_slider = QSlider(Qt.Orientation.Horizontal)
            self._timeout_slider.setMinimum(1)   # 0.5s × 2
            self._timeout_slider.setMaximum(10)  # 5.0s × 2
            self._timeout_slider.setValue(int(self._config.general.silence_timeout * 2))
            self._timeout_slider.setTickInterval(1)
            self._timeout_label = QLabel(
                tr("settings.general.timeout_sec").format(
                    self._config.general.silence_timeout
                )
            )
            self._timeout_slider.valueChanged.connect(self._on_timeout_changed)
            from PySide6.QtWidgets import QHBoxLayout
            timeout_row = QWidget()
            timeout_layout = QHBoxLayout(timeout_row)
            timeout_layout.setContentsMargins(0, 0, 0, 0)
            timeout_layout.addWidget(self._timeout_slider)
            timeout_layout.addWidget(self._timeout_label)
            self._form.addRow(tr("settings.general.silence_timeout"), timeout_row)

            # 附加空格
            self._space_cb = QCheckBox()
            self._space_cb.setChecked(self._config.general.append_space)
            self._space_cb.stateChanged.connect(self._on_space_changed)
            self._form.addRow(tr("settings.general.append_space"), self._space_cb)

            # 附加換行
            self._newline_cb = QCheckBox()
            self._newline_cb.setChecked(self._config.general.append_newline)
            self._newline_cb.stateChanged.connect(self._on_newline_changed)
            self._form.addRow(tr("settings.general.append_newline"), self._newline_cb)

            # 通知
            self._notif_cb = QCheckBox()
            self._notif_cb.setChecked(self._config.general.notifications)
            self._notif_cb.stateChanged.connect(self._on_notif_changed)
            self._form.addRow(tr("settings.general.notifications"), self._notif_cb)

            # 日誌等級
            self._log_combo = QComboBox()
            self._log_combo.addItems(self._LOG_LEVELS)
            self._log_combo.setCurrentText(self._config.general.log_level)
            self._log_combo.currentTextChanged.connect(self._on_log_changed)
            self._form.addRow(tr("settings.general.log_level"), self._log_combo)

            outer.addStretch()

        # ── 事件處理 ─────────────────────────────────────────────────────────

        def _save(self) -> None:
            if callable(self._schedule_save):
                self._schedule_save()

        def _on_lang_changed(self, index: int) -> None:
            lang_code = self._lang_combo.itemData(index)
            self._config.general.language = lang_code
            self._save()
            i18n_set_language(lang_code)

        def retranslate_ui(self, _: str = None) -> None:
            """語言切換時刷新所有標籤文字。"""
            self._title_label.setText(tr("settings.general.title"))
            self._form.labelForField(self._lang_combo).setText(tr("settings.general.language"))
            self._form.labelForField(self._auto_start_cb).setText(tr("settings.general.auto_start"))
            self._form.labelForField(self._minimized_cb).setText(tr("settings.general.start_minimized"))
            self._form.labelForField(self._timeout_slider.parent()).setText(tr("settings.general.silence_timeout"))
            self._form.labelForField(self._space_cb).setText(tr("settings.general.append_space"))
            self._form.labelForField(self._newline_cb).setText(tr("settings.general.append_newline"))
            self._form.labelForField(self._notif_cb).setText(tr("settings.general.notifications"))
            self._form.labelForField(self._log_combo).setText(tr("settings.general.log_level"))

        def _on_auto_start_changed(self, state: int) -> None:
            self._config.general.auto_start = bool(state)
            self._save()

        def _on_minimized_changed(self, state: int) -> None:
            self._config.general.start_minimized = bool(state)
            self._save()

        def _on_timeout_changed(self, value: int) -> None:
            seconds = value / 2.0
            self._config.general.silence_timeout = seconds
            self._timeout_label.setText(tr("settings.general.timeout_sec").format(seconds))
            self._save()

        def _on_space_changed(self, state: int) -> None:
            self._config.general.append_space = bool(state)
            self._save()

        def _on_newline_changed(self, state: int) -> None:
            self._config.general.append_newline = bool(state)
            self._save()

        def _on_notif_changed(self, state: int) -> None:
            self._config.general.notifications = bool(state)
            self._save()

        def _on_log_changed(self, text: str) -> None:
            self._config.general.log_level = text
            self._save()

else:

    class SettingsGeneralPage:  # type: ignore[no-redef]
        pass
