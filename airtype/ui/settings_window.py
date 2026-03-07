"""設定視窗框架。

實作分頁式設定視窗（720×520 px）：
- 左側 QListWidget 導覽
- 右側 QStackedWidget 內容區域（7 個分頁）
- 所有 widget 變更透過 500ms 防抖動計時器自動儲存至 config

分頁索引常數（PAGE_*）可供外部引用以程式化切換分頁。
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from airtype.config import AirtypeConfig
    from airtype.core.dictionary import DictionaryEngine

logger = logging.getLogger(__name__)

from airtype.utils.i18n import tr, get_manager  # noqa: E402

# 分頁索引常數
PAGE_GENERAL: int = 0
PAGE_VOICE: int = 1
PAGE_MODELS: int = 2
PAGE_APPEARANCE: int = 3
PAGE_SHORTCUTS: int = 4
PAGE_LLM: int = 5
PAGE_DICTIONARY: int = 6
PAGE_ABOUT: int = 7

_NAV_I18N_KEYS: list[str] = [
    "settings.nav.general",
    "settings.nav.voice",
    "settings.nav.models",
    "settings.nav.appearance",
    "settings.nav.shortcuts",
    "settings.nav.llm",
    "settings.nav.dictionary",
    "settings.nav.about",
]

WINDOW_WIDTH: int = 720
WINDOW_HEIGHT: int = 520
DEBOUNCE_MS: int = 500

try:
    from PySide6.QtWidgets import (
        QApplication,
        QHBoxLayout,
        QLabel,
        QListWidget,
        QListWidgetItem,
        QSizePolicy,
        QStackedWidget,
        QVBoxLayout,
        QWidget,
    )
    from PySide6.QtCore import Qt, QTimer
    from PySide6.QtGui import QColor, QPalette

    _NAV_BG_LIGHT = "#fafafa"
    _NAV_BG_DARK = "#252525"
    _CONTENT_BG_LIGHT = "#ffffff"
    _CONTENT_BG_DARK = "#2d2d2d"

    _PYSIDE6_AVAILABLE = True
except ImportError:
    _PYSIDE6_AVAILABLE = False


def _dark_palette() -> "QPalette":
    """回傳深色 QPalette。"""
    palette = QPalette()
    _c = QColor
    palette.setColor(QPalette.ColorRole.Window,          _c(30, 30, 30))
    palette.setColor(QPalette.ColorRole.WindowText,      _c(220, 220, 220))
    palette.setColor(QPalette.ColorRole.Base,            _c(45, 45, 45))
    palette.setColor(QPalette.ColorRole.AlternateBase,   _c(55, 55, 55))
    palette.setColor(QPalette.ColorRole.ToolTipBase,     _c(30, 30, 30))
    palette.setColor(QPalette.ColorRole.ToolTipText,     _c(220, 220, 220))
    palette.setColor(QPalette.ColorRole.Text,            _c(220, 220, 220))
    palette.setColor(QPalette.ColorRole.Button,          _c(53, 53, 53))
    palette.setColor(QPalette.ColorRole.ButtonText,      _c(220, 220, 220))
    palette.setColor(QPalette.ColorRole.BrightText,      _c(255, 80, 80))
    palette.setColor(QPalette.ColorRole.Link,            _c(42, 130, 218))
    palette.setColor(QPalette.ColorRole.Highlight,       _c(42, 130, 218))
    palette.setColor(QPalette.ColorRole.HighlightedText, _c(0, 0, 0))
    return palette


# ── App 層主題樣式表（覆蓋所有子元件，未來新增頁面自動繼承）──────────────────

_LIGHT_STYLESHEET = """
QLineEdit, QTextEdit, QPlainTextEdit, QSpinBox, QDoubleSpinBox {
    background-color: #ffffff;
    border: 1px solid #d8d8d8;
    border-radius: 4px;
}
QComboBox {
    background-color: #ffffff;
    border: 1px solid #d8d8d8;
    border-radius: 4px;
}
QComboBox QAbstractItemView {
    background-color: #ffffff;
    selection-background-color: #0a84ff;
    selection-color: white;
}
QTableWidget, QTableView, QListView, QTreeView {
    background-color: #ffffff;
    alternate-background-color: #f5f5f5;
    gridline-color: #e0e0e0;
}
QHeaderView::section {
    background-color: #f0f0f0;
    border: none;
    border-right: 1px solid #d8d8d8;
    border-bottom: 1px solid #d8d8d8;
    padding: 4px 8px;
    color: #1a1a1a;
}
QGroupBox {
    background-color: transparent;
    border: 1px solid #d8d8d8;
    border-radius: 4px;
    margin-top: 8px;
    padding-top: 4px;
}
QGroupBox::title {
    color: #1a1a1a;
    subcontrol-origin: margin;
    left: 8px;
    padding: 0 4px;
}
QScrollArea, QScrollArea > QWidget > QWidget { background-color: transparent; }
"""

_DARK_STYLESHEET = """
QLineEdit, QTextEdit, QPlainTextEdit, QSpinBox, QDoubleSpinBox {
    background-color: #3a3a3a;
    border: 1px solid #555;
    border-radius: 4px;
    color: #dcdcdc;
}
QComboBox {
    background-color: #3a3a3a;
    border: 1px solid #555;
    border-radius: 4px;
    color: #dcdcdc;
}
QComboBox QAbstractItemView {
    background-color: #3a3a3a;
    selection-background-color: #2a82da;
    selection-color: white;
}
QTableWidget, QTableView, QListView, QTreeView {
    background-color: #2d2d2d;
    alternate-background-color: #383838;
    gridline-color: #444;
}
QHeaderView::section {
    background-color: #353535;
    border: none;
    border-right: 1px solid #444;
    border-bottom: 1px solid #444;
    padding: 4px 8px;
    color: #dcdcdc;
}
QGroupBox {
    background-color: transparent;
    border: 1px solid #444;
    border-radius: 4px;
    margin-top: 8px;
    padding-top: 4px;
}
QGroupBox::title {
    color: #dcdcdc;
    subcontrol-origin: margin;
    left: 8px;
    padding: 0 4px;
}
QScrollArea, QScrollArea > QWidget > QWidget { background-color: transparent; }
"""


def _light_palette() -> "QPalette":
    """回傳明亮 QPalette，覆蓋 Windows 11 系統預設暖米色。

    明確設定 Base（輸入框背景）、AlternateBase（表格交替行）、
    Button（表頭/按鈕背景）等顏色，確保所有子元件視覺一致。
    """
    palette = QPalette()
    _c = QColor
    palette.setColor(QPalette.ColorRole.Window,          _c(250, 250, 250))   # #fafafa
    palette.setColor(QPalette.ColorRole.WindowText,      _c(26, 26, 26))      # #1a1a1a
    palette.setColor(QPalette.ColorRole.Base,            _c(255, 255, 255))   # #ffffff — QLineEdit/QTableWidget 背景
    palette.setColor(QPalette.ColorRole.AlternateBase,   _c(245, 245, 245))   # #f5f5f5 — 表格交替行
    palette.setColor(QPalette.ColorRole.ToolTipBase,     _c(255, 255, 255))
    palette.setColor(QPalette.ColorRole.ToolTipText,     _c(26, 26, 26))
    palette.setColor(QPalette.ColorRole.Text,            _c(26, 26, 26))
    palette.setColor(QPalette.ColorRole.Button,          _c(240, 240, 240))   # #f0f0f0 — 表頭/按鈕背景
    palette.setColor(QPalette.ColorRole.ButtonText,      _c(26, 26, 26))
    palette.setColor(QPalette.ColorRole.BrightText,      _c(255, 80, 80))
    palette.setColor(QPalette.ColorRole.Link,            _c(10, 132, 255))    # #0a84ff
    palette.setColor(QPalette.ColorRole.Highlight,       _c(10, 132, 255))
    palette.setColor(QPalette.ColorRole.HighlightedText, _c(255, 255, 255))
    return palette


def apply_theme(theme: str) -> None:
    """依主題名稱套用 QPalette 至整個 QApplication。

    Args:
        theme: 'dark' / 'light' / 'system'
    """
    if not _PYSIDE6_AVAILABLE:
        return
    app = QApplication.instance()
    if app is None:
        return
    if theme == "dark":
        app.setPalette(_dark_palette())
        app.setStyleSheet(_DARK_STYLESHEET)
    else:
        # 'light' 與 'system' 均套用明亮 Palette + Stylesheet，
        # 覆蓋 Windows 11 standardPalette 的暖米色系統預設；
        # 未來新增任何頁面/元件均自動繼承此主題色
        app.setPalette(_light_palette())
        app.setStyleSheet(_LIGHT_STYLESHEET)


if _PYSIDE6_AVAILABLE:

    class SettingsWindow(QWidget):
        """設定視窗。

        左側 QListWidget 導覽 + 右側 QStackedWidget 內容區域。
        所有子頁面的 widget 變更均透過 500ms 防抖動計時器觸發 config 儲存。
        """

        def __init__(
            self,
            config: "AirtypeConfig",
            dictionary_engine: Optional["DictionaryEngine"] = None,
            parent: Optional[QWidget] = None,
        ) -> None:
            super().__init__(parent)
            self._config = config
            self._dictionary_engine = dictionary_engine
            self._build_timer()
            self._build_ui()
            self.setWindowTitle(tr("settings.window.title"))
            self.resize(WINDOW_WIDTH, WINDOW_HEIGHT)
            # 套用儲存的主題
            apply_theme(config.appearance.theme)
            # 套用明確背景色，覆蓋 OS 系統預設 window palette
            self._apply_content_bg(config.appearance.theme)

        # ── 主題背景 ─────────────────────────────────────────────────────────

        def _apply_content_bg(self, theme: str) -> None:
            """依主題更新導覽列與內容區的明確背景色。

            覆蓋 OS 系統預設 window palette，確保導覽列與內容區顏色一致。
            """
            if theme == "dark":
                self._content_bg.setStyleSheet(
                    f"#contentBg {{ background-color: {_CONTENT_BG_DARK}; }}"
                )
                self._nav_widget.setStyleSheet(
                    f"background-color: {_NAV_BG_DARK}; border-right: 1px solid #444;"
                )
            else:  # "light" 或 "system"
                self._content_bg.setStyleSheet(
                    f"#contentBg {{ background-color: {_CONTENT_BG_LIGHT}; }}"
                )
                self._nav_widget.setStyleSheet(
                    f"background-color: {_NAV_BG_LIGHT}; border-right: 1px solid #e0e0e0;"
                )

        # ── 防抖動計時器 ─────────────────────────────────────────────────────

        def _build_timer(self) -> None:
            self._save_timer = QTimer(self)
            self._save_timer.setInterval(DEBOUNCE_MS)
            self._save_timer.setSingleShot(True)
            self._save_timer.timeout.connect(self._do_save)

        def schedule_save(self) -> None:
            """啟動（或重設）防抖動計時器，500ms 後觸發實際儲存。"""
            self._save_timer.start()

        def _do_save(self) -> None:
            """執行實際 config 儲存。"""
            try:
                self._config.save()
                logger.debug("設定已自動儲存")
            except Exception as exc:
                logger.error("自動儲存設定失敗：%s", exc)

        # ── UI 建構 ──────────────────────────────────────────────────────────

        def _build_ui(self) -> None:
            root = QHBoxLayout(self)
            root.setContentsMargins(0, 0, 0, 0)
            root.setSpacing(0)

            # 右側內容（須先建立，供 _build_nav connect 使用）
            self.stacked = QStackedWidget()

            # 以明確背景色容器包裝 stacked，避免繼承系統暖米色
            self._content_bg = QWidget()
            self._content_bg.setObjectName("contentBg")
            content_layout = QVBoxLayout(self._content_bg)
            content_layout.setContentsMargins(0, 0, 0, 0)
            content_layout.setSpacing(0)
            content_layout.addWidget(self.stacked)

            # 左側導覽
            nav_panel = self._build_nav()
            root.addWidget(nav_panel)

            self._add_pages()
            root.addWidget(self._content_bg, stretch=1)

        def _build_nav(self) -> QWidget:
            nav_widget = QWidget()
            self._nav_widget = nav_widget  # 儲存引用，供 _apply_content_bg 使用
            nav_widget.setFixedWidth(160)
            layout = QVBoxLayout(nav_widget)
            layout.setContentsMargins(0, 8, 0, 8)
            layout.setSpacing(0)

            self.nav_list = QListWidget()
            self.nav_list.setFrameShape(QListWidget.Shape.NoFrame)
            self.nav_list.setStyleSheet(
                "QListWidget { background: transparent; outline: 0; border: none; }"
                "QListWidget::item { padding: 10px 16px; margin: 2px 8px; border-radius: 6px; }"
                "QListWidget::item:hover:!selected { background: rgba(0, 0, 0, 0.06); }"
                "QListWidget::item:selected { background: #0a84ff; color: white; }"
            )

            for name in [tr(k) for k in _NAV_I18N_KEYS]:
                item = QListWidgetItem(name)
                item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                self.nav_list.addItem(item)

            self.nav_list.setCurrentRow(PAGE_GENERAL)
            self.nav_list.currentRowChanged.connect(self.stacked.setCurrentIndex)

            layout.addWidget(self.nav_list)
            return nav_widget

        def _add_pages(self) -> None:
            """建立並加入 8 個設定頁面。"""
            from airtype.ui.settings_general import SettingsGeneralPage
            from airtype.ui.settings_voice import SettingsVoicePage
            from airtype.ui.settings_models import SettingsModelsPage
            from airtype.ui.settings_appearance import SettingsAppearancePage
            from airtype.ui.settings_shortcuts import SettingsShortcutsPage
            from airtype.ui.settings_llm import SettingsLlmPage
            from airtype.ui.settings_dictionary import SettingsDictionaryPage
            from airtype.ui.settings_about import SettingsAboutPage

            save_fn = self.schedule_save

            self._page_general = SettingsGeneralPage(self._config, save_fn)
            self._page_voice = SettingsVoicePage(self._config, save_fn)
            self._page_models = SettingsModelsPage(self._config, save_fn)
            self._page_appearance = SettingsAppearancePage(self._config, save_fn)
            self._page_shortcuts = SettingsShortcutsPage(self._config, save_fn)
            self._page_llm = SettingsLlmPage(self._config, save_fn)
            self._page_dictionary = SettingsDictionaryPage(
                self._config, save_fn, self._dictionary_engine
            )
            self._page_about = SettingsAboutPage(self._config)

            for page in (
                self._page_general,
                self._page_voice,
                self._page_models,
                self._page_appearance,
                self._page_shortcuts,
                self._page_llm,
                self._page_dictionary,
                self._page_about,
            ):
                self.stacked.addWidget(page)

            # 連接模型管理 Signal → 跨頁面刷新
            if hasattr(self._page_models, "model_downloaded"):
                self._page_models.model_downloaded.connect(self._on_model_state_changed)
            if hasattr(self._page_models, "model_deleted"):
                self._page_models.model_deleted.connect(self._on_model_state_changed)

            # 連接 language_changed → 所有頁面 retranslate_ui + 視窗自身
            i18n_manager = get_manager()
            i18n_manager.language_changed.connect(self.retranslate_ui)
            for page in (
                self._page_general,
                self._page_voice,
                self._page_models,
                self._page_appearance,
                self._page_shortcuts,
                self._page_llm,
                self._page_dictionary,
                self._page_about,
            ):
                if hasattr(page, "retranslate_ui"):
                    i18n_manager.language_changed.connect(page.retranslate_ui)

        def _on_model_state_changed(self, model_id: str) -> None:
            """模型下載/刪除後通知語音頁與 LLM 頁刷新下拉選單。"""
            if hasattr(self._page_voice, "refresh_asr_combo"):
                self._page_voice.refresh_asr_combo()
            if hasattr(self._page_llm, "refresh_llm_combo"):
                self._page_llm.refresh_llm_combo()

        # ── 公開方法 ─────────────────────────────────────────────────────────

        def retranslate_ui(self, _: str = None) -> None:
            """語言切換時刷新導覽清單與視窗標題。"""
            self.setWindowTitle(tr("settings.window.title"))
            for i, key in enumerate(_NAV_I18N_KEYS):
                item = self.nav_list.item(i)
                if item is not None:
                    item.setText(tr(key))

        def show_page(self, page_index: int) -> None:
            """程式化切換至指定分頁。"""
            self.nav_list.setCurrentRow(page_index)

        def connect_overlay(self, overlay) -> None:
            """連接浮動膠囊疊層至設定視窗，使外觀變更即時生效。

            連接以下 Signals：
            - theme_changed   → 即時套用 QPalette
            - opacity_changed → 即時更新膠囊背景不透明度
            - position_changed → 即時移動膠囊位置

            Args:
                overlay: CapsuleOverlay 實例。
            """
            page = self._page_appearance

            # 主題切換 → 套用 QPalette + 更新視窗背景色
            if hasattr(page, "theme_changed"):
                page.theme_changed.connect(apply_theme)
                page.theme_changed.connect(self._apply_content_bg)

            # 不透明度變更 → 更新膠囊背景透明度
            if hasattr(page, "opacity_changed"):
                page.opacity_changed.connect(
                    lambda op: overlay._capsule_body.set_background(
                        overlay._bg_color, op
                    )
                )

            # 膠囊位置變更 → 移動 overlay
            if hasattr(page, "position_changed"):
                if hasattr(overlay, "refresh_position"):
                    page.position_changed.connect(lambda _: overlay.refresh_position())

            # 音波樣式變更 → 即時切換繪製模式
            if hasattr(page, "waveform_style_changed"):
                page.waveform_style_changed.connect(
                    lambda style: overlay._waveform.set_style(style)
                )

            # 波形顏色變更 → 即時更新波形顏色
            if hasattr(page, "waveform_color_changed"):
                page.waveform_color_changed.connect(
                    lambda color: overlay._waveform.set_color(color)
                )

            # 狀態文字顯示切換 → 即時更新（非 IDLE 時才有效果）
            if hasattr(page, "status_text_changed"):
                def _on_status_text(show: bool, ov=overlay):
                    ov._status_label.setVisible(
                        show and ov._current_state != "IDLE"
                    )
                    ov.adjustSize()
                page.status_text_changed.connect(_on_status_text)

            # 即時預覽切換 → 立即隱藏/顯示預覽
            if hasattr(page, "realtime_preview_changed"):
                def _on_preview_toggle(show: bool, ov=overlay):
                    if not show:
                        ov.clear_preview()
                page.realtime_preview_changed.connect(_on_preview_toggle)

        def connect_rms_feed(self, signal) -> None:
            """連接外部 RMS 訊號至語音頁面音量表。

            Args:
                signal: 發射 float（0.0–1.0）的 Qt Signal。
            """
            if hasattr(self._page_voice, "set_rms_feed"):
                self._page_voice.set_rms_feed(signal)

else:

    class SettingsWindow:  # type: ignore[no-redef]
        pass
