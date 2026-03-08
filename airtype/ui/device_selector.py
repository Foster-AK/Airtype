"""音訊裝置選擇元件。

提供：
- ``list_input_devices()``：純 Python，列舉 sounddevice 輸入裝置（不依賴 Qt）。
- ``DeviceSelector``：QComboBox 子類別，顯示裝置清單並在切換時發射 Signal。
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from airtype.config import AirtypeConfig

logger = logging.getLogger(__name__)


def list_input_devices() -> list[dict]:
    """列舉系統可用的音訊輸入裝置（去重）。

    優先回傳平台偏好 Host API 的裝置（Windows → WASAPI；macOS → CoreAudio；
    Linux → PulseAudio/ALSA）。若偏好 API 無輸入裝置，退回以名稱去重的全清單。

    Returns:
        裝置資訊字典列表，每個字典包含 ``index``（int）和 ``name``（str）。
        若 sounddevice 不可用或列舉失敗，回傳空列表。
    """
    try:
        import sys

        import sounddevice as sd

        all_devices = sd.query_devices()
        if isinstance(all_devices, dict):
            all_devices = [all_devices]

        if sys.platform == "win32":
            preferred_kw = ["wasapi"]
        elif sys.platform == "darwin":
            preferred_kw = ["core audio"]
        else:
            preferred_kw = ["pulseaudio", "alsa"]

        preferred_idx: int | None = None
        try:
            for i, api in enumerate(sd.query_hostapis()):
                if any(kw in api.get("name", "").lower() for kw in preferred_kw):
                    preferred_idx = i
                    break
        except Exception:
            pass

        candidates = [
            {"index": i, "name": d["name"], "_hostapi": d.get("hostapi")}
            for i, d in enumerate(all_devices)
            if d.get("max_input_channels", 0) > 0
        ]

        if preferred_idx is not None:
            source = [d for d in candidates if d["_hostapi"] == preferred_idx] or candidates
        else:
            source = candidates

        seen: set[str] = set()
        result: list[dict] = []
        for d in source:
            if d["name"] not in seen:
                seen.add(d["name"])
                result.append({"index": d["index"], "name": d["name"]})
        return result
    except Exception as exc:
        logger.warning("無法列舉音訊裝置：%s", exc)
        return []


# ─── Qt 元件（PySide6 可用時） ────────────────────────────────────────────────

try:
    from PySide6.QtCore import Signal
    from PySide6.QtWidgets import QComboBox, QWidget

    class DeviceSelector(QComboBox):
        """音訊裝置選擇下拉選單。

        顯示所有可用輸入裝置；第一項固定為「預設麥克風」（data = "default"）。
        切換選項時，若有 config，自動更新 ``config.voice.input_device`` 並發射
        ``device_changed`` Signal。
        """

        device_changed: Signal = Signal(object)

        def __init__(
            self,
            config: AirtypeConfig | None = None,
            parent: QWidget | None = None,
        ) -> None:
            super().__init__(parent)
            self._config = config
            self._populate()
            self.currentIndexChanged.connect(self._on_index_changed)

        def _populate(self) -> None:
            """填充裝置清單（含「預設麥克風」首項）。"""
            self.blockSignals(True)
            self.clear()
            self.addItem("預設麥克風", "default")
            for d in list_input_devices():
                self.addItem(d["name"], d["index"])
            # 恢復設定中記錄的裝置
            if self._config is not None:
                saved = self._config.voice.input_device
                for i in range(self.count()):
                    if self.itemData(i) == saved:
                        self.setCurrentIndex(i)
                        break
            self.blockSignals(False)

        def refresh(self) -> None:
            """重新掃描裝置並更新清單。"""
            self._populate()

        def _on_index_changed(self, index: int) -> None:
            device_value = self.itemData(index)
            if device_value is None:
                device_value = "default"
            if self._config is not None:
                self._config.voice.input_device = device_value
            self.device_changed.emit(device_value)

except ImportError:
    logger.debug("DeviceSelector：PySide6 不可用，使用佔位類別")

    class DeviceSelector:  # type: ignore[no-redef]
        """PySide6 不可用時的佔位類別。"""

        def __init__(self, config=None, parent=None) -> None:
            raise ImportError("DeviceSelector 需要 PySide6")
