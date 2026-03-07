"""浮動膠囊疊層視窗。

實作不搶焦點的浮動膠囊 QWidget：
- 無邊框、透明背景、置頂（Qt.Tool + WA_ShowWithoutActivating）
- 含 7 條音波動畫（WaveformWidget）、狀態文字、裝置選擇器（DeviceSelector）
- 滑入動畫 200ms（slide-up + fade-in）、滑出動畫 150ms（slide-down + fade-out）
- 拖曳重新定位，釋放後自動儲存位置至設定
- 連接 CoreController.state_changed 以驅動顏色與狀態文字

純 Python 輔助函式 ``parse_pill_position`` 不依賴 PySide6，可直接單元測試。
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from airtype.config import AirtypeConfig
    from airtype.core.controller import CoreController

logger = logging.getLogger(__name__)

from airtype.utils.i18n import tr  # noqa: E402

# ─── 常數 ────────────────────────────────────────────────────────────────────

CAPSULE_WIDTH: int = 220
CAPSULE_HEIGHT: int = 48
SLIDE_IN_MS: int = 200
SLIDE_OUT_MS: int = 150
SLIDE_OFFSET: int = 20  # 滑入/滑出的垂直像素偏移

# 狀態名稱 → 背景色（RRGGBB，不含透明度）
STATE_COLORS: dict[str, str] = {
    "IDLE":       "#1e293b",  # 深藍灰
    "ACTIVATING": "#1d4ed8",  # 藍
    "LISTENING":  "#15803d",  # 綠
    "PROCESSING": "#b45309",  # 琥珀
    "INJECTING":  "#0f766e",  # 青綠
    "ERROR":      "#b91c1c",  # 紅
}

STATE_I18N_KEYS: dict[str, str] = {
    "IDLE":       "state.idle",
    "ACTIVATING": "state.activating",
    "LISTENING":  "state.listening",
    "PROCESSING": "state.processing",
    "INJECTING":  "state.injecting",
    "ERROR":      "state.error",
}

# 向後相容別名（供外部引用）
STATE_LABELS: dict[str, str] = STATE_I18N_KEYS


# ─── 純 Python 輔助（不依賴 Qt） ──────────────────────────────────────────────


def parse_pill_position(
    position_str: str,
    screen_width: int,
    screen_height: int,
    capsule_w: int = CAPSULE_WIDTH,
    capsule_h: int = CAPSULE_HEIGHT,
) -> tuple[int, int]:
    """將 pill_position 設定字串解析為 (x, y) 螢幕座標。

    Args:
        position_str:  ``"center"`` 或 ``"x,y"`` 格式字串。
        screen_width:  螢幕可用寬度（像素）。
        screen_height: 螢幕可用高度（像素）。
        capsule_w:     膠囊寬度（像素）。
        capsule_h:     膠囊高度（像素）。

    Returns:
        (x, y) 整數座標元組；無效字串回傳居中底部位置。
    """
    if position_str == "center":
        return _center_pos(screen_width, screen_height, capsule_w, capsule_h)

    try:
        parts = position_str.split(",")
        if len(parts) == 2:
            return int(parts[0].strip()), int(parts[1].strip())
    except (ValueError, AttributeError):
        pass

    return _center_pos(screen_width, screen_height, capsule_w, capsule_h)


def _center_pos(sw: int, sh: int, cw: int, ch: int) -> tuple[int, int]:
    return (sw - cw) // 2, sh - ch - 80


# ─── Qt 元件（PySide6 可用時） ────────────────────────────────────────────────

try:
    from PySide6.QtCore import (
        QEasingCurve,
        QPoint,
        QPropertyAnimation,
        QRect,
        QSize,
        Qt,
    )
    from PySide6.QtGui import QBrush, QColor, QIcon, QPainter, QPainterPath, QPixmap
    from PySide6.QtWidgets import (
        QFrame,
        QGraphicsOpacityEffect,
        QHBoxLayout,
        QLabel,
        QMenu,
        QToolButton,
        QVBoxLayout,
        QWidget,
    )

    from airtype.ui.device_selector import DeviceSelector
    from airtype.ui.waveform_widget import WaveformWidget

    class CapsuleBody(QWidget):
        """膠囊主體元件：負責圓角背景繪製（48px 固定高度）。

        從 CapsuleOverlay 分離出來，使圓角背景不覆蓋下方狀態文字。
        """

        BODY_HEIGHT: int = 48

        def __init__(self, parent: QWidget | None = None) -> None:
            super().__init__(parent)
            self.setFixedHeight(self.BODY_HEIGHT)
            self._bg_color: QColor = QColor(STATE_COLORS["IDLE"])
            self._opacity: float = 0.92
            self._drag_pos: Optional[QPoint] = None

        def set_background(self, color: QColor, opacity: float) -> None:
            """更新背景色與透明度。"""
            self._bg_color = color
            self._opacity = opacity
            self.update()

        def paintEvent(self, event) -> None:  # noqa: N802
            painter = QPainter(self)
            painter.setRenderHint(QPainter.Antialiasing)

            path = QPainterPath()
            radius = self.height() / 2.0
            path.addRoundedRect(
                0.0, 0.0, float(self.width()), float(self.height()),
                radius, radius,
            )

            bg = QColor(self._bg_color)
            bg.setAlpha(max(0, min(255, int(self._opacity * 255))))
            painter.fillPath(path, QBrush(bg))
            painter.end()

        def mousePressEvent(self, event) -> None:  # noqa: N802
            if event.button() == Qt.LeftButton:
                self._drag_pos = (
                    event.globalPosition().toPoint() - self.parent().frameGeometry().topLeft()
                    if self.parent()
                    else event.globalPosition().toPoint()
                )
                event.accept()

        def mouseMoveEvent(self, event) -> None:  # noqa: N802
            if event.buttons() == Qt.LeftButton and self._drag_pos is not None:
                if self.parent():
                    self.parent().move(
                        event.globalPosition().toPoint() - self._drag_pos
                    )
                event.accept()

        def mouseReleaseEvent(self, event) -> None:  # noqa: N802
            if event.button() == Qt.LeftButton and self._drag_pos is not None:
                self._drag_pos = None
                if self.parent() and hasattr(self.parent(), "_save_position"):
                    self.parent()._save_position()
                event.accept()

    class CapsuleOverlay(QWidget):
        """浮動膠囊疊層。

        使用方式::

            overlay = CapsuleOverlay(config=cfg)
            overlay.connect_controller(controller)
            overlay.show_animated()   # 滑入顯示
            overlay.update_rms(rms)   # 更新音波
            overlay.hide_animated()   # 滑出隱藏
        """

        def __init__(
            self,
            config: AirtypeConfig | None = None,
            parent: QWidget | None = None,
        ) -> None:
            flags = (
                Qt.Tool
                | Qt.FramelessWindowHint
                | Qt.WindowStaysOnTopHint
            )
            super().__init__(parent, flags)
            self._config = config
            self._drag_pos: Optional[QPoint] = None
            self._bg_color: QColor = QColor(STATE_COLORS["IDLE"])
            self._current_state: str = "IDLE"
            self._controller = None

            # 不搶焦點
            self.setAttribute(Qt.WA_ShowWithoutActivating)
            # 允許透明背景（需配合 paintEvent 圓角繪製）
            self.setAttribute(Qt.WA_TranslucentBackground)

            self.setFixedWidth(CAPSULE_WIDTH)

            self._fade_anim: Optional[QPropertyAnimation] = None

            self._setup_ui()
            self._setup_animations()
            self._restore_position()

        # ── 平台特定：不搶焦點 ────────────────────────────────────────────

        def _apply_no_activate(self) -> None:
            """在 Windows 上為視窗加入 WS_EX_NOACTIVATE 擴充樣式。

            此樣式確保點擊膠囊按鈕時不會搶走使用者原本的焦點視窗，
            與螢幕小鍵盤、浮動工具列採用相同機制。
            """
            import sys
            if sys.platform != "win32":
                return
            try:
                import ctypes
                GWL_EXSTYLE = -20
                WS_EX_NOACTIVATE = 0x08000000
                hwnd = int(self.winId())
                style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
                ctypes.windll.user32.SetWindowLongW(
                    hwnd, GWL_EXSTYLE, style | WS_EX_NOACTIVATE
                )
            except Exception:
                logger.debug("無法設定 WS_EX_NOACTIVATE", exc_info=True)

        # ── UI 配置 ────────────────────────────────────────────────────────

        def _setup_ui(self) -> None:
            from PySide6.QtWidgets import QVBoxLayout

            # 外層：垂直 layout，包含 CapsuleBody + 下方狀態文字
            outer = QVBoxLayout(self)
            outer.setContentsMargins(0, 0, 0, 0)
            outer.setSpacing(2)

            # ── CapsuleBody：膠囊主體（圓角背景 + 音波 + 控制按鈕）──
            self._capsule_body = CapsuleBody(self)
            body_layout = QHBoxLayout(self._capsule_body)
            body_layout.setContentsMargins(12, 8, 8, 8)
            body_layout.setSpacing(6)

            _wf_style = self._config.appearance.waveform_style if self._config else "bars"
            self._waveform = WaveformWidget(self._capsule_body, style=_wf_style)
            body_layout.addWidget(self._waveform, 1)  # stretch=1：填滿可用空間

            # 垂直分隔線（1x24px，半透明白色）
            from PySide6.QtWidgets import QFrame
            self._separator = QFrame(self._capsule_body)
            self._separator.setFrameShape(QFrame.VLine)
            self._separator.setFrameShadow(QFrame.Plain)
            self._separator.setFixedSize(1, 24)
            self._separator.setStyleSheet("color: rgba(255, 255, 255, 0.3);")
            body_layout.addWidget(self._separator)

            # 麥克風切換按鈕（32x32，QPainter 自繪圖示）
            self._mic_button = QToolButton(self._capsule_body)
            self._mic_button.setFixedSize(32, 32)
            self._mic_button.setStyleSheet(
                "QToolButton { background: transparent; border: none; }"
                "QToolButton:hover { background: rgba(255,255,255,0.15); border-radius: 6px; }"
            )
            self._mic_button.setIcon(self._make_mic_icon())
            self._mic_button.setIconSize(QSize(20, 20))
            self._mic_button.clicked.connect(self._on_mic_button_clicked)
            body_layout.addWidget(self._mic_button)

            # 裝置下拉箭頭按鈕（20x32，QMenu）
            self._device_button = QToolButton(self._capsule_body)
            self._device_button.setFixedSize(20, 32)
            self._device_button.setArrowType(Qt.DownArrow)
            self._device_button.setPopupMode(QToolButton.InstantPopup)
            self._device_button.setStyleSheet(
                "QToolButton { background: transparent; border: none; color: white; }"
                "QToolButton:hover { background: rgba(255,255,255,0.15); border-radius: 4px; }"
                "QToolButton::menu-indicator { image: none; }"
            )
            self._device_menu = self._build_device_menu()
            self._device_button.setMenu(self._device_menu)
            body_layout.addWidget(self._device_button)

            outer.addWidget(self._capsule_body)

            # ── 從 config 套用初始外觀 ──
            if self._config is not None:
                pill_opacity = self._config.appearance.pill_opacity
                self._capsule_body.set_background(self._bg_color, pill_opacity)
                self._waveform.set_color(self._config.appearance.waveform_color)

            # ── 即時辨識預覽（膠囊下方，串流模式用）──
            self._preview_label = QLabel("", self)
            self._preview_label.setAlignment(Qt.AlignCenter)
            self._preview_label.setWordWrap(True)
            self._preview_label.setMaximumWidth(CAPSULE_WIDTH)
            self._preview_label.setStyleSheet(
                "color: #e2e8f0; font-size: 12px;"
                " background: rgba(0, 0, 0, 0.65);"
                " border-radius: 8px; padding: 4px 10px;"
            )
            self._preview_label.setVisible(False)
            outer.addWidget(self._preview_label)

            # ── 狀態文字（膠囊下方，IDLE 時隱藏）──
            self._status_label = QLabel(tr("state.idle"), self)
            self._status_label.setAlignment(Qt.AlignCenter)
            self._status_label.setStyleSheet(
                "color: white; font-size: 11px;"
                " background: rgba(0, 0, 0, 0.55);"
                " border-radius: 6px; padding: 2px 8px;"
            )
            self._status_label.setVisible(False)
            outer.addWidget(self._status_label)

        # ── 麥克風按鈕圖示 ───────────────────────────────────────────────

        def _build_device_menu(self) -> QMenu:
            """建立音訊裝置選單（第一項為預設麥克風）。"""
            from airtype.ui.device_selector import list_input_devices

            menu = QMenu(self)
            menu.setStyleSheet(
                "QMenu { background: #1e293b; color: white; border: 1px solid #334155; }"
                "QMenu::item:selected { background: #334155; }"
            )
            default_action = menu.addAction("預設麥克風")
            default_action.setData("default")
            default_action.triggered.connect(
                lambda: self._on_device_selected("default")
            )
            for dev in list_input_devices():
                action = menu.addAction(dev["name"])
                action.setData(dev["name"])
                action.triggered.connect(
                    lambda checked=False, name=dev["name"]: self._on_device_selected(name)
                )
            return menu

        def _on_device_selected(self, device_name: str) -> None:
            """裝置選單選擇後更新 config。"""
            if self._config is not None:
                self._config.voice.input_device = device_name

        def _make_mic_icon(self) -> QIcon:
            """用 QPainter 繪製麥克風圖示（白色輪廓）。"""
            px = QPixmap(20, 20)
            px.fill(Qt.transparent)
            p = QPainter(px)
            p.setRenderHint(QPainter.Antialiasing)
            p.setPen(QColor("white"))
            p.setBrush(QColor("white"))
            # 麥克風膠囊體
            p.drawRoundedRect(7, 2, 6, 10, 3, 3)
            # 底座弧線（簡化為半圓 arc）
            p.setBrush(Qt.NoBrush)
            from PySide6.QtCore import QRectF
            p.drawArc(QRectF(3, 8, 14, 8), 0, -180 * 16)
            # 支架
            p.drawLine(10, 16, 10, 19)
            p.drawLine(7, 19, 13, 19)
            p.end()
            return QIcon(px)

        def _make_stop_icon(self) -> QIcon:
            """用 QPainter 繪製停止圖示（白色方塊）。"""
            px = QPixmap(20, 20)
            px.fill(Qt.transparent)
            p = QPainter(px)
            p.setRenderHint(QPainter.Antialiasing)
            p.setPen(Qt.NoPen)
            p.setBrush(QColor("white"))
            p.drawRoundedRect(4, 4, 12, 12, 2, 2)
            p.end()
            return QIcon(px)

        def _on_mic_button_clicked(self) -> None:
            """點擊麥克風/停止按鈕：依目前狀態呼叫 controller 方法。"""
            if self._controller is None:
                return
            if self._current_state == "IDLE":
                self._controller.request_start()
            else:
                self._controller.request_stop()

        # ── 動畫 ──────────────────────────────────────────────────────────

        def _setup_animations(self) -> None:
            # 滑入位置動畫（200ms，OutCubic 緩動）
            self._slide_in = QPropertyAnimation(self, b"pos")
            self._slide_in.setDuration(SLIDE_IN_MS)
            self._slide_in.setEasingCurve(QEasingCurve.OutCubic)

            # 滑出位置動畫（150ms，InCubic 緩動）
            self._slide_out = QPropertyAnimation(self, b"pos")
            self._slide_out.setDuration(SLIDE_OUT_MS)
            self._slide_out.setEasingCurve(QEasingCurve.InCubic)
            self._slide_out.finished.connect(self._on_slide_out_done)

        # ── 位置管理 ──────────────────────────────────────────────────────

        def _get_target_pos(self) -> QPoint:
            """依設定或預設取得目標顯示座標。"""
            pos_str = "center"
            if self._config is not None:
                pos_str = self._config.appearance.pill_position

            screen = self.screen()
            if screen is not None:
                geo = screen.availableGeometry()
                x, y = parse_pill_position(
                    pos_str, geo.width(), geo.height(),
                    CAPSULE_WIDTH, CAPSULE_HEIGHT,
                )
                return QPoint(geo.x() + x, geo.y() + y)
            # 無法取得螢幕資訊（測試環境）
            return QPoint(0, 0)

        def _restore_position(self) -> None:
            """依設定恢復位置（不顯示視窗）。"""
            self.move(self._get_target_pos())

        def _save_position(self) -> None:
            """將目前位置儲存至設定。"""
            if self._config is None:
                return
            pos = self.pos()
            self._config.appearance.pill_position = f"{pos.x()},{pos.y()}"
            try:
                self._config.save()
            except Exception as exc:
                logger.warning("儲存膠囊位置失敗：%s", exc)

        # ── 顯示/隱藏動畫 ─────────────────────────────────────────────────

        def _clear_fade_anim(self) -> None:
            """停止並清除目前的 fade 動畫與 graphics effect（防護用）。"""
            if self._fade_anim is not None:
                self._fade_anim.stop()
                self._fade_anim.deleteLater()
                self._fade_anim = None
            self.setGraphicsEffect(None)

        def show_animated(self) -> None:
            """以滑入動畫（slide-up + fade-in，200ms）顯示膠囊。"""
            self._clear_fade_anim()

            target = self._get_target_pos()
            start = QPoint(target.x(), target.y() + SLIDE_OFFSET)

            fade_effect = QGraphicsOpacityEffect(self)
            fade_effect.setOpacity(0.0)
            self.setGraphicsEffect(fade_effect)

            self._fade_anim = QPropertyAnimation(fade_effect, b"opacity")
            self._fade_anim.setDuration(SLIDE_IN_MS)
            self._fade_anim.setStartValue(0.0)
            self._fade_anim.setEndValue(1.0)
            self._fade_anim.finished.connect(self._on_fade_in_done)

            self._slide_in.setStartValue(start)
            self._slide_in.setEndValue(target)

            super().show()
            self._apply_no_activate()
            self._slide_in.start()
            self._fade_anim.start()

        def hide_animated(self) -> None:
            """以滑出動畫（slide-down + fade-out，150ms）隱藏膠囊。"""
            if not self.isVisible():
                return
            self._clear_fade_anim()

            current = self.pos()
            end = QPoint(current.x(), current.y() + SLIDE_OFFSET)

            fade_effect = QGraphicsOpacityEffect(self)
            fade_effect.setOpacity(1.0)
            self.setGraphicsEffect(fade_effect)

            self._fade_anim = QPropertyAnimation(fade_effect, b"opacity")
            self._fade_anim.setDuration(SLIDE_OUT_MS)
            self._fade_anim.setStartValue(1.0)
            self._fade_anim.setEndValue(0.0)

            self._slide_out.setStartValue(current)
            self._slide_out.setEndValue(end)

            self._slide_out.start()
            self._fade_anim.start()

        def _on_fade_in_done(self) -> None:
            """淡入動畫結束後移除 graphics effect，恢復正常渲染路徑。"""
            self.setGraphicsEffect(None)
            if self._fade_anim is not None:
                self._fade_anim.deleteLater()
                self._fade_anim = None

        def _on_slide_out_done(self) -> None:
            """滑出動畫結束後真正隱藏視窗，並移除 graphics effect。"""
            super().hide()
            self.setGraphicsEffect(None)
            if self._fade_anim is not None:
                self._fade_anim.deleteLater()
                self._fade_anim = None

        # ── 狀態驅動 UI ──────────────────────────────────────────────────

        def set_state(self, state_name: str) -> None:
            """依 AppState 名稱更新背景色與狀態文字。

            Args:
                state_name: ``AppState`` 列舉的 ``.name``，例如 ``"LISTENING"``。
                            未知的狀態名稱退回 IDLE 色系。
            """
            self._current_state = state_name
            # 回到 IDLE 時清除預覽
            if state_name == "IDLE":
                self.clear_preview()
            color_hex = STATE_COLORS.get(state_name, STATE_COLORS["IDLE"])
            self._bg_color = QColor(color_hex)

            # 更新 CapsuleBody 背景色
            pill_opacity = (
                self._config.appearance.pill_opacity
                if self._config is not None
                else 0.92
            )
            self._capsule_body.set_background(self._bg_color, pill_opacity)

            i18n_key = STATE_I18N_KEYS.get(state_name, "state.idle")
            self._status_label.setText(tr(i18n_key))
            # Status Label Below Capsule：IDLE 時隱藏；非 IDLE 依 config 決定
            show = state_name != "IDLE"
            if show and self._config is not None:
                show = self._config.appearance.show_status_text
            self._status_label.setVisible(show)
            self.adjustSize()

            # 麥克風按鈕圖示切換（IDLE=麥克風圖示，其他=停止圖示）
            if state_name == "IDLE":
                self._mic_button.setIcon(self._make_mic_icon())
            else:
                self._mic_button.setIcon(self._make_stop_icon())

            # 同步音波樣式（從 config 即時讀取，設定變更後下次狀態切換生效）
            if self._config is not None:
                self._waveform.set_style(self._config.appearance.waveform_style)
            # 同步音波顏色（從 config 讀取使用者設定）
            if self._config is not None:
                waveform_color = self._config.appearance.waveform_color
            else:
                waveform_color = "#60a5fa"
            self._waveform.set_color(waveform_color)
            # 狀態驅動音波動畫：LISTENING / PROCESSING 時啟動，其餘停止
            self._waveform.set_active(state_name in ("LISTENING", "PROCESSING"))
            self.update()

        def connect_controller(self, controller: CoreController) -> None:
            """連接至 CoreController 的 state_changed Signal/回呼。

            支援兩種模式：
            - PySide6 版本：透過 Qt Signal 自動跨執行緒安全。
            - 純 Python 版本：透過 connect_state_changed 回呼。
            """
            self._controller = controller
            # Qt Signal 版本（執行緒安全，跨執行緒自動切換）
            if hasattr(controller, "state_changed"):
                try:
                    controller.state_changed.connect(
                        lambda state: self.set_state(state.name)
                    )
                    # 連接串流部分結果信號
                    if hasattr(controller, "partial_result"):
                        controller.partial_result.connect(self.update_preview)
                    logger.debug("CapsuleOverlay：已連接 Qt Signal state_changed")
                    return
                except Exception as exc:
                    logger.debug("連接 Qt Signal 失敗，退回回呼模式：%s", exc)

            # 純 Python 回呼版本（測試用）
            controller.connect_state_changed(
                lambda state: self.set_state(state.name)
            )
            controller.connect_partial_result(self.update_preview)
            logger.debug("CapsuleOverlay：已連接回呼版 state_changed")

        # ── 即時預覽 ──────────────────────────────────────────────────────

        def update_preview(self, text: str, is_final: bool) -> None:
            """更新即時辨識預覽文字。

            Args:
                text: 部分或最終辨識文字。
                is_final: True 時清除預覽（最終結果由 controller 處理注入）。
            """
            if is_final:
                self._preview_label.setVisible(False)
                self._preview_label.setText("")
                self.adjustSize()
                return

            show_preview = (
                self._config is not None
                and self._config.appearance.show_realtime_preview
                and self._config.voice.recognition_mode == "stream"
            )
            if show_preview and text:
                self._preview_label.setText(text)
                self._preview_label.setVisible(True)
                self.adjustSize()

        def clear_preview(self) -> None:
            """清除預覽文字（狀態回到 IDLE 時呼叫）。"""
            self._preview_label.setVisible(False)
            self._preview_label.setText("")
            self.adjustSize()

        # ── 音波更新 ──────────────────────────────────────────────────────

        def update_rms(self, rms: float) -> None:
            """更新音波 RMS 值（由 AudioCaptureService 定期呼叫）。"""
            self._waveform.update_rms(rms)

        def refresh_position(self) -> None:
            """依設定重新計算並移動至正確位置。"""
            self.move(self._get_target_pos())

except ImportError:
    logger.debug("CapsuleOverlay：PySide6 不可用，使用佔位類別")

    class CapsuleOverlay:  # type: ignore[no-redef]
        """PySide6 不可用時的佔位類別。"""

        def __init__(self, config=None, parent=None) -> None:
            raise ImportError("CapsuleOverlay 需要 PySide6")
