"""音波動畫元件。

以 QPainter 繪製 7 條音波動畫條，由音訊 RMS 資料驅動。
動畫使用正弦波疊加達到自然效果，目標 ≥30 FPS。

`compute_bar_heights` 為純計算函式，不依賴 PySide6，可在單元測試中直接呼叫。
"""

from __future__ import annotations

import logging
import math
import random
import time

logger = logging.getLogger(__name__)

# ─── 常數 ────────────────────────────────────────────────────────────────────

BAR_COUNT: int = 7
BAR_MIN_HEIGHT: int = 2
ANIMATION_INTERVAL_MS: int = 33  # ≈30 FPS


# ─── 純 Python 計算（不依賴 Qt） ─────────────────────────────────────────────


def compute_bar_heights(
    rms: float,
    time_sec: float,
    bar_count: int = BAR_COUNT,
    max_height: int = 40,
) -> list[int]:
    """從 RMS 值計算音波條高度（純計算，不依賴 Qt）。

    Args:
        rms:       0.0–1.0 的 RMS 音量值；0.0 時所有條為最小高度。
        time_sec:  動畫時間（秒），驅動正弦波相位。
        bar_count: 音波條數量（預設 7）。
        max_height:最大高度（像素）。

    Returns:
        每條音波條的高度列表（像素），保證 ≥ BAR_MIN_HEIGHT 且 ≤ max_height。
    """
    rms = max(0.0, min(1.0, float(rms)))
    heights: list[int] = []
    for i in range(bar_count):
        # 每條使用不同頻率，視覺上呈現自然起伏
        freq = 1.0 + i * 0.3
        phase = 2 * math.pi * time_sec * freq + i * math.pi / bar_count
        sin_modulation = 0.5 + 0.5 * math.sin(phase)  # 0.0–1.0

        # RMS 驅動主振幅，正弦波負責動畫調變
        amplitude = rms * sin_modulation
        # 輕微隨機擾動（僅在有音訊時加入，靜音時完全平整）
        if rms > 0.0:
            amplitude += random.uniform(-0.03, 0.03) * rms
        amplitude = max(0.0, min(1.0, amplitude))

        # 映射至像素高度
        height = max(
            BAR_MIN_HEIGHT,
            int(amplitude * (max_height - BAR_MIN_HEIGHT)) + BAR_MIN_HEIGHT,
        )
        heights.append(height)
    return heights


# ─── Qt 元件（PySide6 可用時） ────────────────────────────────────────────────

try:
    from PySide6.QtCore import Qt, QTimer
    from PySide6.QtGui import QBrush, QColor, QPainter, QPainterPath, QPen
    from PySide6.QtWidgets import QSizePolicy, QWidget

    class WaveformWidget(QWidget):
        """7 條音波動畫元件（QPainter 渲染，≥30 FPS）。

        呼叫 ``update_rms(rms)`` 以更新音量驅動動畫。
        顏色可透過 ``set_color(hex_str)`` 設定。
        樣式可透過 ``set_style(style)`` 切換（``"bars"`` / ``"wave"`` / ``"dots"``）。
        """

        _VALID_STYLES = {"bars", "wave", "dots"}

        def __init__(self, parent: QWidget | None = None, *, style: str = "bars") -> None:
            super().__init__(parent)
            self._rms: float = 0.0
            self._start_time: float = time.monotonic()
            self._bar_heights: list[int] = [BAR_MIN_HEIGHT] * BAR_COUNT
            self._color: QColor = QColor("#60a5fa")
            self._style: str = style if style in self._VALID_STYLES else "bars"

            self.setMinimumWidth(80)
            self.setFixedHeight(32)
            self.setSizePolicy(
                QSizePolicy.Expanding,
                QSizePolicy.Fixed,
            )
            self.setAttribute(Qt.WA_TransparentForMouseEvents)

            self._timer = QTimer(self)
            self._timer.setInterval(ANIMATION_INTERVAL_MS)
            self._timer.timeout.connect(self._animate)
            self._timer.start()

        def set_color(self, color: str) -> None:
            """設定音波條顏色（十六進位色碼）。"""
            self._color = QColor(color)

        def set_style(self, style: str) -> None:
            """切換繪製樣式（``"bars"`` / ``"wave"`` / ``"dots"``）。"""
            if style in self._VALID_STYLES:
                self._style = style
                self.update()

        def set_active(self, active: bool) -> None:
            """啟動或暫停動畫計時器。

            閒置（非錄音）時應傳入 ``False`` 以停止計時器，
            減少不必要的重繪（降低閒置 CPU 用量）。
            開始錄音時傳入 ``True`` 恢復動畫。

            Args:
                active: True 啟動計時器，False 暫停計時器。
            """
            if active:
                self._timer.start()
            else:
                self._timer.stop()

        def update_rms(self, rms: float) -> None:
            """更新 RMS 音量值（0.0–1.0）；超出範圍自動截斷。"""
            self._rms = max(0.0, min(1.0, float(rms)))

        def _animate(self) -> None:
            """定時更新動畫幀並觸發重繪。"""
            elapsed = time.monotonic() - self._start_time
            self._bar_heights = compute_bar_heights(
                self._rms, elapsed, BAR_COUNT, self.height() - 4
            )
            self.update()

        def paintEvent(self, event) -> None:  # noqa: N802
            painter = QPainter(self)
            painter.setRenderHint(QPainter.Antialiasing)

            w = self.width()
            h = self.height()

            if self._style == "wave":
                self._paint_wave(painter, w, h)
            elif self._style == "dots":
                self._paint_dots(painter, w, h)
            else:
                self._paint_bars(painter, w, h)

            painter.end()

        def _paint_bars(self, painter: QPainter, w: int, h: int) -> None:
            painter.setPen(Qt.NoPen)
            painter.setBrush(QBrush(self._color))
            bar_w = max(2, (w - BAR_COUNT - 1) // BAR_COUNT)
            gap = max(1, (w - BAR_COUNT * bar_w) // (BAR_COUNT + 1))
            for i, bar_h in enumerate(self._bar_heights):
                x = gap + i * (bar_w + gap)
                y = (h - bar_h) // 2
                painter.drawRoundedRect(x, y, bar_w, bar_h, 1, 1)

        def _paint_wave(self, painter: QPainter, w: int, h: int) -> None:
            pen = QPen(self._color, 2.5)
            pen.setCapStyle(Qt.RoundCap)
            pen.setJoinStyle(Qt.RoundJoin)
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)

            n = len(self._bar_heights)
            if n < 2:
                return
            max_h = h - 4
            gap = w / (n + 1)
            # 計算各控制點的 y 座標（中心線偏移）
            points: list[tuple[float, float]] = []
            for i, bar_h in enumerate(self._bar_heights):
                x = gap * (i + 1)
                ratio = min(bar_h, max_h) / max_h if max_h > 0 else 0
                y = h / 2 - (ratio - 0.5) * (h - 4)
                points.append((x, y))

            path = QPainterPath()
            path.moveTo(points[0][0], points[0][1])
            for i in range(1, n):
                mid_x = (points[i - 1][0] + points[i][0]) / 2
                path.quadTo(points[i - 1][0], points[i - 1][1], mid_x, (points[i - 1][1] + points[i][1]) / 2)
            path.lineTo(points[-1][0], points[-1][1])
            painter.drawPath(path)

        def _paint_dots(self, painter: QPainter, w: int, h: int) -> None:
            painter.setPen(Qt.NoPen)
            painter.setBrush(QBrush(self._color))
            n = len(self._bar_heights)
            max_h = h - 4
            gap = w / (n + 1)
            for i, bar_h in enumerate(self._bar_heights):
                x = gap * (i + 1)
                ratio = min(bar_h, max_h) / max_h if max_h > 0 else 0
                radius = max(2.0, ratio * (h / 2 - 1))
                painter.drawEllipse(int(x - radius), int(h / 2 - radius), int(radius * 2), int(radius * 2))

except ImportError:
    logger.debug("WaveformWidget：PySide6 不可用，使用佔位類別")

    class WaveformWidget:  # type: ignore[no-redef]
        """PySide6 不可用時的佔位類別。"""

        def __init__(self, parent=None, *, style: str = "bars") -> None:
            raise ImportError("WaveformWidget 需要 PySide6")
