"""外觀設定頁面。

提供 SettingsAppearancePage：主題（亮色/暗色/系統）、膠囊位置、
縮放比例（80–150%）、不透明度（50–100%）、波形樣式、波形顏色、
顯示狀態文字、顯示即時預覽。
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from airtype.config import AirtypeConfig

from airtype.utils.i18n import tr

try:
    from PySide6.QtWidgets import (
        QCheckBox,
        QColorDialog,
        QComboBox,
        QFormLayout,
        QHBoxLayout,
        QLabel,
        QPushButton,
        QSlider,
        QVBoxLayout,
        QWidget,
    )
    from PySide6.QtCore import Qt, Signal
    from PySide6.QtGui import QColor

    _PYSIDE6_AVAILABLE = True
except ImportError:
    _PYSIDE6_AVAILABLE = False


if _PYSIDE6_AVAILABLE:

    _THEME_CODES = [("settings.appearance.theme.system", "system"),
                    ("settings.appearance.theme.light", "light"),
                    ("settings.appearance.theme.dark", "dark")]
    _POSITION_CODES = [
        ("settings.appearance.position.center", "center"),
        ("settings.appearance.position.left", "left"),
        ("settings.appearance.position.right", "right"),
        ("settings.appearance.position.top_left", "top-left"),
        ("settings.appearance.position.top_right", "top-right"),
    ]
    _WAVEFORM_STYLE_CODES = [
        ("settings.appearance.waveform.bars", "bars"),
        ("settings.appearance.waveform.wave", "wave"),
        ("settings.appearance.waveform.dots", "dots"),
    ]

    class SettingsAppearancePage(QWidget):
        """外觀設定頁面。"""

        # 即時通知訊號（供 SettingsWindow.connect_overlay 連接）
        theme_changed = Signal(str)      # 主題名稱：'light' / 'dark' / 'system'
        opacity_changed = Signal(float)  # pill_opacity：0.50–1.00
        position_changed = Signal(str)   # pill_position 字串
        waveform_style_changed = Signal(str)  # 'bars' / 'wave' / 'dots'
        waveform_color_changed = Signal(str)  # hex color e.g. '#ff0000'
        status_text_changed = Signal(bool)  # show_status_text
        realtime_preview_changed = Signal(bool)  # show_realtime_preview

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

            self._title_label = QLabel(tr("settings.appearance.title"))
            self._title_label.setStyleSheet("font-size: 16px; font-weight: bold;")
            outer.addWidget(self._title_label)

            self._form = QFormLayout()
            self._form.setVerticalSpacing(10)
            outer.addLayout(self._form)

            # 主題
            self._theme_combo = QComboBox()
            for label, code in [(tr(k), c) for k, c in _THEME_CODES]:
                self._theme_combo.addItem(label, code)
            idx = next(
                (i for i, (_, c) in enumerate(_THEME_CODES)
                 if c == self._config.appearance.theme),
                0,
            )
            self._theme_combo.setCurrentIndex(idx)
            self._theme_combo.currentIndexChanged.connect(self._on_theme_changed)
            self._form.addRow(tr("settings.appearance.theme"), self._theme_combo)

            # 膠囊位置
            self._pos_combo = QComboBox()
            for label, code in [(tr(k), c) for k, c in _POSITION_CODES]:
                self._pos_combo.addItem(label, code)
            pos_idx = next(
                (i for i, (_, c) in enumerate(_POSITION_CODES)
                 if c == self._config.appearance.pill_position),
                0,
            )
            self._pos_combo.setCurrentIndex(pos_idx)
            self._pos_combo.currentIndexChanged.connect(self._on_pos_changed)
            self._form.addRow(tr("settings.appearance.pill_position"), self._pos_combo)

            # 縮放比例（80–150%，步長 5，存 0.80–1.50）
            self._scale_slider = QSlider(Qt.Orientation.Horizontal)
            self._scale_slider.setMinimum(16)  # 80% / 5
            self._scale_slider.setMaximum(30)  # 150% / 5
            scale_val = int(round(self._config.appearance.pill_scale * 20))
            self._scale_slider.setValue(scale_val)
            self._scale_label = QLabel(f"{int(self._config.appearance.pill_scale * 100)}%")
            self._scale_slider.valueChanged.connect(self._on_scale_changed)
            self._scale_row = QWidget()
            scale_layout = QHBoxLayout(self._scale_row)
            scale_layout.setContentsMargins(0, 0, 0, 0)
            scale_layout.addWidget(self._scale_slider)
            scale_layout.addWidget(self._scale_label)
            self._form.addRow(tr("settings.appearance.pill_scale"), self._scale_row)

            # 不透明度（50–100%，步長 1，存 0.50–1.00）
            self._opacity_slider = QSlider(Qt.Orientation.Horizontal)
            self._opacity_slider.setMinimum(50)
            self._opacity_slider.setMaximum(100)
            self._opacity_slider.setValue(int(self._config.appearance.pill_opacity * 100))
            self._opacity_label = QLabel(
                f"{int(self._config.appearance.pill_opacity * 100)}%"
            )
            self._opacity_slider.valueChanged.connect(self._on_opacity_changed)
            self._opacity_row = QWidget()
            opacity_layout = QHBoxLayout(self._opacity_row)
            opacity_layout.setContentsMargins(0, 0, 0, 0)
            opacity_layout.addWidget(self._opacity_slider)
            opacity_layout.addWidget(self._opacity_label)
            self._form.addRow(tr("settings.appearance.pill_opacity"), self._opacity_row)

            # 波形樣式
            self._wave_combo = QComboBox()
            for label, code in [(tr(k), c) for k, c in _WAVEFORM_STYLE_CODES]:
                self._wave_combo.addItem(label, code)
            wave_idx = next(
                (i for i, (_, c) in enumerate(_WAVEFORM_STYLE_CODES)
                 if c == self._config.appearance.waveform_style),
                0,
            )
            self._wave_combo.setCurrentIndex(wave_idx)
            self._wave_combo.currentIndexChanged.connect(self._on_wave_style_changed)
            self._form.addRow(tr("settings.appearance.waveform_style"), self._wave_combo)

            # 波形顏色
            self._color_row = QWidget()
            color_layout = QHBoxLayout(self._color_row)
            color_layout.setContentsMargins(0, 0, 0, 0)
            self._color_preview = QLabel()
            self._color_preview.setFixedSize(40, 24)
            self._color_preview.setStyleSheet(
                f"background-color: {self._config.appearance.waveform_color}; border: 1px solid #999;"
            )
            color_layout.addWidget(self._color_preview)
            self._color_btn = QPushButton(tr("settings.appearance.color_btn"))
            self._color_btn.setFixedWidth(90)
            self._color_btn.clicked.connect(self._on_color_pick)
            color_layout.addWidget(self._color_btn)
            color_layout.addStretch()
            self._form.addRow(tr("settings.appearance.waveform_color"), self._color_row)

            # 顯示狀態文字
            self._status_text_cb = QCheckBox()
            self._status_text_cb.setChecked(self._config.appearance.show_status_text)
            self._status_text_cb.stateChanged.connect(self._on_status_text_changed)
            self._form.addRow(tr("settings.appearance.show_status_text"), self._status_text_cb)

            # 顯示即時預覽（僅串流模式顯示）
            self._realtime_cb = QCheckBox()
            self._realtime_cb.setChecked(self._config.appearance.show_realtime_preview)
            self._realtime_cb.stateChanged.connect(self._on_realtime_changed)
            self._form.addRow(tr("settings.appearance.show_realtime_preview"), self._realtime_cb)
            is_stream = self._config.voice.recognition_mode == "stream"
            self._realtime_cb.setVisible(is_stream)
            self._form.labelForField(self._realtime_cb).setVisible(is_stream)

            outer.addStretch()

        # ── 事件處理 ─────────────────────────────────────────────────────────

        def _save(self) -> None:
            if callable(self._schedule_save):
                self._schedule_save()

        def retranslate_ui(self, _: str = None) -> None:
            """語言切換時刷新所有標籤文字。"""
            self._title_label.setText(tr("settings.appearance.title"))
            self._form.labelForField(self._theme_combo).setText(tr("settings.appearance.theme"))
            self._form.labelForField(self._pos_combo).setText(tr("settings.appearance.pill_position"))
            self._form.labelForField(self._scale_row).setText(tr("settings.appearance.pill_scale"))
            self._form.labelForField(self._opacity_row).setText(tr("settings.appearance.pill_opacity"))
            self._form.labelForField(self._wave_combo).setText(tr("settings.appearance.waveform_style"))
            self._form.labelForField(self._color_row).setText(tr("settings.appearance.waveform_color"))
            self._form.labelForField(self._status_text_cb).setText(tr("settings.appearance.show_status_text"))
            self._form.labelForField(self._realtime_cb).setText(tr("settings.appearance.show_realtime_preview"))
            self._color_btn.setText(tr("settings.appearance.color_btn"))
            for i, (k, _) in enumerate(_THEME_CODES):
                self._theme_combo.setItemText(i, tr(k))
            for i, (k, _) in enumerate(_POSITION_CODES):
                self._pos_combo.setItemText(i, tr(k))
            for i, (k, _) in enumerate(_WAVEFORM_STYLE_CODES):
                self._wave_combo.setItemText(i, tr(k))

        def _on_theme_changed(self, index: int) -> None:
            theme = self._theme_combo.itemData(index)
            self._config.appearance.theme = theme
            self._save()
            self.theme_changed.emit(theme)

        def _on_pos_changed(self, index: int) -> None:
            pos = self._pos_combo.itemData(index)
            self._config.appearance.pill_position = pos
            self._save()
            self.position_changed.emit(pos)

        def _on_scale_changed(self, value: int) -> None:
            scale = value / 20.0
            self._config.appearance.pill_scale = scale
            self._scale_label.setText(f"{int(scale * 100)}%")
            self._save()

        def _on_opacity_changed(self, value: int) -> None:
            opacity = value / 100.0
            self._config.appearance.pill_opacity = opacity
            self._opacity_label.setText(f"{value}%")
            self._save()
            self.opacity_changed.emit(opacity)

        def _on_wave_style_changed(self, index: int) -> None:
            style = self._wave_combo.itemData(index)
            self._config.appearance.waveform_style = style
            self._save()
            self.waveform_style_changed.emit(style)

        def _on_color_pick(self) -> None:
            current = QColor(self._config.appearance.waveform_color)
            color = QColorDialog.getColor(current, self, tr("settings.appearance.color_dialog_title"))
            if color.isValid():
                hex_color = color.name()
                self._config.appearance.waveform_color = hex_color
                self._color_preview.setStyleSheet(
                    f"background-color: {hex_color}; border: 1px solid #999;"
                )
                self._save()
                self.waveform_color_changed.emit(hex_color)

        def _on_status_text_changed(self, state: int) -> None:
            self._config.appearance.show_status_text = bool(state)
            self._save()
            self.status_text_changed.emit(bool(state))

        def _on_realtime_changed(self, state: int) -> None:
            self._config.appearance.show_realtime_preview = bool(state)
            self._save()
            self.realtime_preview_changed.emit(bool(state))

else:

    class SettingsAppearancePage:  # type: ignore[no-redef]
        pass
