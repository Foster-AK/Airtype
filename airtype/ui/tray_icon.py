"""系統匣圖示與通知。

實作 QSystemTrayIcon 搭配動態狀態圖示：
- idle / listening / error 等狀態顯示不同顏色圓形圖示
- 右鍵選單：開啟設定、切換語音輸入、狀態顯示、結束
- 辨識完成時透過 showMessage 發送通知（由 general.notifications 控制）
- close_to_tray() 輔助函式：覆寫視窗的 closeEvent 以隱藏取代結束

純 Python 輔助 ``make_state_color_map`` 不依賴 Qt，可直接單元測試。
"""

from __future__ import annotations

import logging
import platform
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from airtype.config import AirtypeConfig
    from airtype.core.controller import CoreController

logger = logging.getLogger(__name__)

from airtype.utils.i18n import tr  # noqa: E402

# ─── 狀態顏色對照表 ────────────────────────────────────────────────────────────

# 各應用程式狀態對應的圖示顏色（RRGGBB）
_STATE_ICON_COLORS: dict[str, str] = {
    "IDLE":       "#64748b",  # 灰藍 — 閒置
    "ACTIVATING": "#1d4ed8",  # 藍   — 啟動中
    "LISTENING":  "#22c55e",  # 綠   — 聆聽中
    "PROCESSING": "#f59e0b",  # 琥珀 — 處理中
    "INJECTING":  "#14b8a6",  # 青綠 — 注入中
    "ERROR":      "#ef4444",  # 紅   — 錯誤
}

# 各狀態對應的 i18n key（執行期間動態翻譯，勿改為硬編碼字串）
_STATE_I18N_KEYS: dict[str, str] = {
    "IDLE":       "state.idle",
    "ACTIVATING": "state.activating",
    "LISTENING":  "state.listening",
    "PROCESSING": "state.processing",
    "INJECTING":  "state.injecting",
    "ERROR":      "state.error",
}

# 通知摘要的最大字元數
_NOTIFY_MAX_CHARS: int = 60

# 系統匣圖示尺寸（像素）
_ICON_SIZE: int = 16


# ─── 純 Python 輔助（不依賴 Qt） ───────────────────────────────────────────────


def make_state_color_map() -> dict[str, str]:
    """回傳狀態名稱 → 顏色字串（RRGGBB）的對照字典。

    此函式不依賴 PySide6，可在任何環境直接測試。

    Returns:
        複製的狀態顏色對照表。
    """
    return dict(_STATE_ICON_COLORS)


def truncate_text(text: str, max_chars: int = _NOTIFY_MAX_CHARS) -> str:
    """截短文字至指定長度，過長時附加省略號。

    Args:
        text:      原始文字。
        max_chars: 最大字元數（含省略號）。

    Returns:
        截短後的文字；若不超過長度則原樣回傳。
    """
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 1] + "…"


# ─── Qt 元件（PySide6 可用時） ─────────────────────────────────────────────────

try:
    from PySide6.QtCore import Signal as _Signal
    from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
    from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

    def _make_circle_icon(color_hex: str, size: int = _ICON_SIZE) -> QIcon:
        """以指定顏色繪製填充圓形 QIcon。

        Args:
            color_hex: 十六進位顏色字串（例如 ``"#22c55e"``）。
            size:      圖示邊長（像素）。

        Returns:
            填充圓形 QIcon 物件。
        """
        pixmap = QPixmap(size, size)
        pixmap.fill(QColor(0, 0, 0, 0))  # 透明背景

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setBrush(QColor(color_hex))
        painter.setPen(QColor(0, 0, 0, 0))  # 無邊框
        painter.drawEllipse(1, 1, size - 2, size - 2)
        painter.end()

        return QIcon(pixmap)

    class SystemTrayIcon(QSystemTrayIcon):
        """動態狀態系統匣圖示。

        使用方式::

            tray = SystemTrayIcon(config=cfg)
            tray.show()
            tray.connect_controller(controller)
            # 辨識完成後
            tray.notify("辨識文字")
            # 更新狀態
            tray.update_state("LISTENING")
        """

        # Qt Signals（供外部連接，例如設定面板、主視窗）
        open_settings_requested = _Signal()
        toggle_voice_requested = _Signal()

        def __init__(
            self,
            config: AirtypeConfig | None = None,
            parent=None,
        ) -> None:
            """
            Args:
                config: :class:`airtype.config.AirtypeConfig` 實例（可選）。
                parent: Qt parent 物件（可選）。
            """
            super().__init__(parent)
            self._config = config
            self._current_state: str = "IDLE"

            # Linux SNI 可用性檢查（StatusNotifierItem 協定）
            if not QSystemTrayIcon.isSystemTrayAvailable():
                if platform.system() == "Linux":
                    logger.warning(
                        "系統匣不可用（Linux 可能缺少 StatusNotifierItem/SNI 支援）。"
                        "請確認桌面環境支援系統匣（如安裝 libappindicator 或 snixembed）。"
                    )
                else:
                    logger.warning("系統匣不可用於此系統。")

            # 預先建立所有狀態圖示
            self._icons: dict[str, QIcon] = {
                state: _make_circle_icon(color)
                for state, color in _STATE_ICON_COLORS.items()
            }

            self.setIcon(self._icons["IDLE"])
            self.setToolTip(tr("tray.tooltip_prefix") + tr("state.idle"))

            self._setup_menu()

        # ── 選單建立 ───────────────────────────────────────────────────────

        def _setup_menu(self) -> None:
            """建立右鍵選單。"""
            menu = QMenu()

            # 狀態顯示（不可點擊的說明文字）
            self._status_action = menu.addAction(
                tr("tray.status_prefix") + tr("state.idle")
            )
            self._status_action.setEnabled(False)

            menu.addSeparator()

            # 開啟設定
            settings_action = menu.addAction(tr("tray.menu.open_settings"))
            settings_action.triggered.connect(self.open_settings_requested)

            # 切換語音輸入
            self._toggle_action = menu.addAction(tr("tray.menu.toggle_voice"))
            self._toggle_action.triggered.connect(self.toggle_voice_requested)

            menu.addSeparator()

            # 結束應用程式
            quit_action = menu.addAction(tr("tray.menu.quit"))
            quit_action.triggered.connect(QApplication.quit)

            self.setContextMenu(menu)

        # ── 狀態更新 ───────────────────────────────────────────────────────

        def update_state(self, state_name: str) -> None:
            """依應用程式狀態名稱更新圖示與選單說明。

            Args:
                state_name: ``AppState`` 列舉的 ``.name``，例如 ``"LISTENING"``。
                            未知狀態退回 IDLE 圖示。
            """
            self._current_state = state_name
            icon = self._icons.get(state_name, self._icons["IDLE"])
            label = tr(_STATE_I18N_KEYS.get(state_name, "state.idle"))

            self.setIcon(icon)
            self.setToolTip(tr("tray.tooltip_prefix") + label)
            self._status_action.setText(tr("tray.status_prefix") + label)
            logger.debug("SystemTrayIcon 狀態更新：%s", state_name)

        def connect_controller(self, controller: CoreController) -> None:
            """連接至 CoreController 的 state_changed Signal 或回呼。

            支援兩種模式：
            - PySide6 版本：透過 Qt Signal 自動跨執行緒安全。
            - 純 Python 版本：透過 connect_state_changed 回呼。

            Args:
                controller: :class:`airtype.core.controller.CoreController` 實例。
            """
            if hasattr(controller, "state_changed"):
                try:
                    controller.state_changed.connect(
                        lambda state: self.update_state(state.name)
                    )
                    logger.debug("SystemTrayIcon：已連接 Qt Signal state_changed")
                    return
                except Exception as exc:
                    logger.debug("連接 Qt Signal 失敗，退回回呼模式：%s", exc)

            controller.connect_state_changed(
                lambda state: self.update_state(state.name)
            )
            logger.debug("SystemTrayIcon：已連接回呼版 state_changed")

        # ── 通知 ──────────────────────────────────────────────────────────

        def notify(self, text: str) -> None:
            """辨識完成後顯示系統通知。

            僅在設定 ``general.notifications`` 啟用時顯示。

            Args:
                text: 辨識並注入的文字內容。
            """
            if self._config is not None and not self._config.general.notifications:
                return

            summary = truncate_text(text)
            self.showMessage(
                "Airtype",
                summary,
                QSystemTrayIcon.MessageIcon.Information,
                3000,  # 顯示 3 秒
            )
            logger.debug("系統通知已發送，文字長度：%d", len(text))

    PYSIDE6_AVAILABLE = True
    logger.debug("SystemTrayIcon：已載入 PySide6 版本")

except ImportError:
    PYSIDE6_AVAILABLE = False
    logger.debug("SystemTrayIcon：PySide6 不可用，使用佔位類別")

    class SystemTrayIcon:  # type: ignore[no-redef]
        """PySide6 不可用時的佔位類別。"""

        def __init__(self, config=None, parent=None) -> None:
            raise ImportError("SystemTrayIcon 需要 PySide6")


# ─── 關閉至系統匣輔助函式 ─────────────────────────────────────────────────────


def close_to_tray(window, tray_icon: "SystemTrayIcon | None" = None) -> None:
    """覆寫視窗的 closeEvent，使關閉視窗時隱藏而非退出應用程式。

    只有系統匣選單的「結束」才真正退出應用程式。

    Args:
        window:     要套用此行為的 QWidget 或 QMainWindow 實例。
        tray_icon:  （可選）:class:`SystemTrayIcon` 實例，用於在視窗隱藏時
                    顯示「已最小化至系統匣」提示（僅顯示一次）。

    範例::

        main_window = MyMainWindow()
        tray = SystemTrayIcon(config=cfg)
        close_to_tray(main_window, tray_icon=tray)
        main_window.show()
    """
    _hinted: list[bool] = [False]  # 用 list 以便閉包修改

    def _close_event(event) -> None:
        event.ignore()
        window.hide()
        if tray_icon is not None and not _hinted[0]:
            _hinted[0] = True
            try:
                tray_icon.showMessage(
                    tr("app.name"),
                    tr("tray.notify.minimized"),
                    QSystemTrayIcon.MessageIcon.Information,  # type: ignore[name-defined]
                    4000,
                )
            except Exception:
                pass  # PySide6 不可用時靜默忽略
        logger.debug("視窗已隱藏至系統匣")

    window.closeEvent = _close_event
