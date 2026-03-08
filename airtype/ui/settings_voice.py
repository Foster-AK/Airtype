"""語音/ASR 設定頁面。

提供 SettingsVoicePage：輸入裝置下拉選單（動態）、重新整理按鈕、
音量滑桿與音量表、降噪切換、ASR 模型選擇、辨識語言、辨識模式、串流預覽。
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from airtype.config import AirtypeConfig

logger = logging.getLogger(__name__)

from airtype.ui.device_selector import list_input_devices
from airtype.utils.i18n import tr  # noqa: E402

try:
    from PySide6.QtWidgets import (
        QCheckBox,
        QComboBox,
        QFormLayout,
        QHBoxLayout,
        QLabel,
        QPushButton,
        QProgressBar,
        QRadioButton,
        QButtonGroup,
        QSlider,
        QVBoxLayout,
        QWidget,
    )
    from PySide6.QtCore import Qt, QThread, Signal, Slot

    _PYSIDE6_AVAILABLE = True
except ImportError:
    _PYSIDE6_AVAILABLE = False


if _PYSIDE6_AVAILABLE:

    # ── 麥克風測試背景執行緒 ──────────────────────────────────────────────────

    class _MicTestWorker(QThread):
        """背景執行緒：錄製 3 秒麥克風音訊並即時發射 RMS 值，結束後播放錄音。

        Signals:
            rms_update(float): 每 ~100ms 發射一次 RMS 值（0.0–1.0）。
            finished(): 錄製與播放均已完成。
            error(str): 發生例外時發射錯誤訊息。
        """

        rms_update = Signal(float)
        finished = Signal()
        error = Signal(str)

        _DURATION_S: float = 3.0
        _SAMPLERATE: int = 16_000

        def __init__(self, device: "str | int", parent=None) -> None:
            super().__init__(parent)
            self._device = device

        def run(self) -> None:
            try:
                import sys

                import numpy as np
                import sounddevice as sd

                recorded: list = []
                device_arg = None if self._device == "default" else self._device

                # Windows WASAPI: 啟用 auto_convert 讓 OS 處理取樣率轉換
                extra_settings = None
                if sys.platform == "win32":
                    try:
                        extra_settings = sd.WasapiSettings(auto_convert=True)
                    except Exception:
                        pass

                def _callback(indata, frames, time, status):
                    chunk = indata[:, 0]
                    rms = float(np.sqrt(np.mean(chunk ** 2)))
                    # 放大 4 倍讓音量表在正常說話時能有感反應（約 0–1 範圍）
                    self.rms_update.emit(min(rms * 4.0, 1.0))
                    recorded.append(chunk.copy())

                with sd.InputStream(
                    samplerate=self._SAMPLERATE,
                    channels=1,
                    dtype="float32",
                    callback=_callback,
                    device=device_arg,
                    extra_settings=extra_settings,
                ):
                    sd.sleep(int(self._DURATION_S * 1000))

                # 播放錄音
                if recorded:
                    audio = np.concatenate(recorded)
                    sd.play(audio, samplerate=self._SAMPLERATE, device=device_arg)
                    sd.wait()

                self.rms_update.emit(0.0)
                self.finished.emit()

            except Exception as exc:
                logger.debug("麥克風測試失敗：%s", exc)
                self.error.emit(str(exc))

    _LANGUAGES = [
        ("繁體中文", "zh-TW"),
        ("簡體中文", "zh-CN"),
        ("English", "en"),
        ("日本語", "ja"),
        ("自動偵測", "auto"),
    ]

    class SettingsVoicePage(QWidget):
        """語音/ASR 設定頁面。"""

        device_changed = Signal(object)

        def __init__(
            self,
            config: "AirtypeConfig",
            schedule_save_fn: object = None,
            parent: Optional[QWidget] = None,
        ) -> None:
            super().__init__(parent)
            self._config = config
            self._schedule_save = schedule_save_fn
            self._asr_manifest_entries: list[dict] = []
            self._recommended_asr_model: Optional[str] = None
            self._init_model_manager()
            self._build_ui()
            self._refresh_devices()

        def _init_model_manager(self) -> None:
            """初始化 ModelManager 並取得 ASR 模型清單與硬體建議。"""
            try:
                from airtype.utils.model_manager import ModelManager
                from airtype.utils.hardware_detect import HardwareDetector, recommend_inference_path
                mgr = ModelManager()
                self._asr_manifest_entries = mgr.list_models_by_category("asr")
                self._model_manager = mgr
                caps = HardwareDetector().assess()
                path = recommend_inference_path(caps)
                self._recommended_asr_model = path.model
                logger.debug("硬體偵測完成，ASR 建議模型：%s", self._recommended_asr_model)
            except Exception as exc:  # noqa: BLE001
                logger.debug(
                    "初始化 ModelManager 或硬體偵測失敗，下拉選單將無建議標記：%s",
                    exc,
                )
                self._model_manager = None

        def _build_ui(self) -> None:
            outer = QVBoxLayout(self)
            outer.setContentsMargins(16, 16, 16, 16)

            self._title_label = QLabel(tr("settings.voice.title"))
            self._title_label.setStyleSheet("font-size: 16px; font-weight: bold;")
            outer.addWidget(self._title_label)

            self._form = QFormLayout()
            self._form.setVerticalSpacing(10)
            outer.addLayout(self._form)

            # 輸入裝置 + 重新整理
            self._device_row = QWidget()
            device_layout = QHBoxLayout(self._device_row)
            device_layout.setContentsMargins(0, 0, 0, 0)
            self._device_combo = QComboBox()
            self._device_combo.setSizeAdjustPolicy(
                QComboBox.SizeAdjustPolicy.AdjustToContents
            )
            self._device_combo.currentTextChanged.connect(self._on_device_changed)
            device_layout.addWidget(self._device_combo)
            self._refresh_btn = QPushButton(tr("settings.voice.refresh_btn"))
            self._refresh_btn.setFixedWidth(80)
            self._refresh_btn.clicked.connect(self._refresh_devices)
            device_layout.addWidget(self._refresh_btn)
            self._form.addRow(tr("settings.voice.input_device"), self._device_row)

            # 音量表 + 測試麥克風按鈕
            self._vol_row = QWidget()
            vol_layout = QHBoxLayout(self._vol_row)
            vol_layout.setContentsMargins(0, 0, 0, 0)

            self._vol_bar = QProgressBar()
            self._vol_bar.setRange(0, 100)
            self._vol_bar.setValue(0)
            self._vol_bar.setTextVisible(False)
            self._vol_bar.setFixedHeight(10)
            vol_layout.addWidget(self._vol_bar)

            self._test_btn = QPushButton(tr("settings.voice.test_mic_btn"))
            self._test_btn.setFixedWidth(100)
            self._test_btn.clicked.connect(self._on_test_clicked)
            vol_layout.addWidget(self._test_btn)

            self._test_status = QLabel("")
            self._test_status.setStyleSheet("color: #666; font-size: 11px;")
            vol_layout.addWidget(self._test_status)

            self._form.addRow(tr("settings.voice.volume"), self._vol_row)
            self._mic_worker: "_MicTestWorker | None" = None

            # 降噪
            self._noise_cb = QCheckBox()
            self._noise_cb.setChecked(self._config.voice.noise_reduction)
            self._noise_cb.stateChanged.connect(self._on_noise_changed)
            self._form.addRow(tr("settings.voice.noise_reduction"), self._noise_cb)

            # ASR 模型（manifest 驅動，只列已下載模型）
            self._asr_combo = QComboBox()
            self._asr_no_model_label = QLabel(tr("settings.voice.no_model_hint"))
            self._asr_no_model_label.setStyleSheet("color: #888; font-size: 11px;")
            self._asr_no_model_label.setWordWrap(True)
            self._populate_asr_combo()
            self._asr_combo.currentIndexChanged.connect(self._on_asr_changed)
            self._form.addRow(tr("settings.voice.asr_model"), self._asr_combo)
            self._form.addRow("", self._asr_no_model_label)

            # 辨識語言
            self._lang_combo = QComboBox()
            for label, code in _LANGUAGES:
                self._lang_combo.addItem(label, code)
            lang_idx = next(
                (i for i, (_, c) in enumerate(_LANGUAGES)
                 if c == self._config.voice.asr_language),
                0,
            )
            self._lang_combo.setCurrentIndex(lang_idx)
            self._lang_combo.currentIndexChanged.connect(self._on_lang_changed)
            self._form.addRow(tr("settings.voice.asr_language"), self._lang_combo)

            # 辨識模式（Batch / Stream）
            self._mode_row = QWidget()
            mode_layout = QHBoxLayout(self._mode_row)
            mode_layout.setContentsMargins(0, 0, 0, 0)
            self._mode_group = QButtonGroup(self)
            self._batch_rb = QRadioButton(tr("settings.voice.mode.batch"))
            self._stream_rb = QRadioButton(tr("settings.voice.mode.stream"))
            self._mode_group.addButton(self._batch_rb, 0)
            self._mode_group.addButton(self._stream_rb, 1)
            if self._config.voice.recognition_mode == "stream":
                self._stream_rb.setChecked(True)
            else:
                self._batch_rb.setChecked(True)
            mode_layout.addWidget(self._batch_rb)
            mode_layout.addWidget(self._stream_rb)
            self._mode_group.idClicked.connect(self._on_mode_changed)
            self._form.addRow(tr("settings.voice.recognition_mode"), self._mode_row)

            # 串流模式警語（當引擎不支援真實串流時顯示）
            self._stream_warning = QLabel(tr("settings.voice.stream_warning"))
            self._stream_warning.setWordWrap(True)
            self._stream_warning.setStyleSheet(
                "color: #f59e0b; font-size: 11px; padding: 2px 0;"
            )
            self._form.addRow("", self._stream_warning)
            self._update_stream_warning()

            outer.addStretch()

        # ── ASR 模型下拉 ──────────────────────────────────────────────────────

        def _populate_asr_combo(self) -> None:
            """依 manifest 動態填充 ASR 模型下拉選單（只列已下載模型）。

            - 只顯示已下載的 ASR 模型
            - 硬體建議項目標示「（建議）」
            - 無已下載模型時顯示 placeholder 並 disable
            """
            self._asr_combo.blockSignals(True)
            self._asr_combo.clear()

            selected_id = self._config.voice.asr_model
            select_idx = 0
            downloaded_entries = []

            for entry in self._asr_manifest_entries:
                model_id = entry.get("id", "")
                is_downloaded = (
                    self._model_manager is not None
                    and self._model_manager.is_downloaded(model_id)
                )
                if is_downloaded:
                    downloaded_entries.append(entry)

            if not downloaded_entries:
                self._asr_combo.addItem(tr("settings.voice.no_downloaded_models"), None)
                self._asr_combo.setEnabled(False)
                self._asr_no_model_label.setVisible(True)
            else:
                self._asr_combo.setEnabled(True)
                self._asr_no_model_label.setVisible(False)
                for i, entry in enumerate(downloaded_entries):
                    model_id = entry.get("id", "")
                    description = entry.get("description", model_id)
                    recommended_mark = (
                        tr("settings.voice.model.recommended_mark")
                        if model_id == self._recommended_asr_model else ""
                    )
                    label = f"{description}{recommended_mark}"
                    self._asr_combo.addItem(label, model_id)
                    if model_id == selected_id:
                        select_idx = i

                self._asr_combo.setCurrentIndex(select_idx)

            self._asr_combo.blockSignals(False)

        def refresh_asr_combo(self) -> None:
            """重建 ASR 模型下拉選單（模型下載/刪除後呼叫以刷新清單）。"""
            self._populate_asr_combo()

        # ── 裝置列舉 ─────────────────────────────────────────────────────────

        def _refresh_devices(self) -> None:
            """列舉可用輸入裝置並填充下拉選單（去重）。"""
            self._device_combo.blockSignals(True)
            self._device_combo.clear()
            self._device_combo.addItem(tr("settings.voice.device.default"), "default")
            for d in list_input_devices():
                self._device_combo.addItem(d["name"], d["index"])

            # 還原設定值
            current = self._config.voice.input_device
            for i in range(self._device_combo.count()):
                if self._device_combo.itemData(i) == current:
                    self._device_combo.setCurrentIndex(i)
                    break
            self._device_combo.blockSignals(False)

        # ── 事件處理 ─────────────────────────────────────────────────────────

        def _save(self) -> None:
            if callable(self._schedule_save):
                self._schedule_save()

        def retranslate_ui(self, _: str = None) -> None:
            """語言切換時刷新所有標籤文字。"""
            self._title_label.setText(tr("settings.voice.title"))
            self._refresh_btn.setText(tr("settings.voice.refresh_btn"))
            self._form.labelForField(self._device_row).setText(tr("settings.voice.input_device"))
            self._form.labelForField(self._vol_row).setText(tr("settings.voice.volume"))
            self._form.labelForField(self._noise_cb).setText(tr("settings.voice.noise_reduction"))
            self._form.labelForField(self._asr_combo).setText(tr("settings.voice.asr_model"))
            self._asr_no_model_label.setText(tr("settings.voice.no_model_hint"))
            self._form.labelForField(self._lang_combo).setText(tr("settings.voice.asr_language"))
            self._form.labelForField(self._mode_row).setText(tr("settings.voice.recognition_mode"))
            self._batch_rb.setText(tr("settings.voice.mode.batch"))
            self._stream_rb.setText(tr("settings.voice.mode.stream"))
            self._stream_warning.setText(tr("settings.voice.stream_warning"))

        def _on_device_changed(self, _text: str) -> None:
            device_value = self._device_combo.currentData()
            if device_value is None:
                device_value = "default"
            self._config.voice.input_device = device_value
            self._save()
            self.device_changed.emit(device_value)

        def _on_noise_changed(self, state: int) -> None:
            self._config.voice.noise_reduction = bool(state)
            self._save()

        def _on_asr_changed(self, index: int) -> None:
            data = self._asr_combo.itemData(index)
            if data is not None:
                self._config.voice.asr_model = data
                self._update_stream_warning()
                self._save()

        def _on_lang_changed(self, index: int) -> None:
            self._config.voice.asr_language = self._lang_combo.itemData(index)
            self._save()

        def _on_mode_changed(self, button_id: int) -> None:
            self._config.voice.recognition_mode = "stream" if button_id == 1 else "batch"
            self._update_stream_warning()
            self._save()

        # ── 串流警語 ──────────────────────────────────────────────────────────

        def _get_current_inference_engine(self) -> str:
            """取得目前選取 ASR 模型的 inference_engine 值。"""
            model_id = self._config.voice.asr_model
            for entry in self._asr_manifest_entries:
                if entry.get("id") == model_id:
                    return entry.get("inference_engine", "")
            return ""

        def _update_stream_warning(self) -> None:
            """根據辨識模式與引擎能力，顯示或隱藏串流警語。"""
            from airtype.core.asr_engine import STREAMING_CAPABLE_ENGINES

            is_stream = self._config.voice.recognition_mode == "stream"
            engine = self._get_current_inference_engine()
            show = is_stream and engine not in STREAMING_CAPABLE_ENGINES
            self._stream_warning.setVisible(show)

        # ── 麥克風測試 ────────────────────────────────────────────────────────

        def _on_test_clicked(self) -> None:
            """啟動或停止麥克風測試（錄製 3 秒後播放回放）。"""
            if self._mic_worker is not None and self._mic_worker.isRunning():
                self._mic_worker.requestInterruption()
                self._mic_worker.wait(500)
                self._reset_test_ui()
                return

            device = self._config.voice.input_device
            self._mic_worker = _MicTestWorker(device, self)
            self._mic_worker.rms_update.connect(self.update_volume)
            self._mic_worker.finished.connect(self._on_test_done)
            self._mic_worker.error.connect(self._on_test_error)

            self._test_btn.setText(tr("settings.voice.test_stop_btn"))
            self._test_status.setText(tr("settings.voice.test_recording_status"))
            self._mic_worker.start()

        @Slot()
        def _on_test_done(self) -> None:
            self._test_status.setText(tr("settings.voice.test_done_status"))
            self._reset_test_ui()

        @Slot(str)
        def _on_test_error(self, msg: str) -> None:
            self._test_status.setText(tr("settings.voice.test_error_status").format(msg))
            self._reset_test_ui()

        def _reset_test_ui(self) -> None:
            self._test_btn.setText(tr("settings.voice.test_mic_btn"))
            self.update_volume(0.0)

        # ── 音量表更新（由外部呼叫 / 麥克風測試）────────────────────────────

        def update_volume(self, level: float) -> None:
            """更新音量表顯示（level: 0.0–1.0）。"""
            self._vol_bar.setValue(int(level * 100))

        def set_rms_feed(self, signal) -> None:
            """連接外部 RMS 訊號至音量表（如主音訊擷取服務）。

            Args:
                signal: 可呼叫的 Signal 物件，發射 float 值（0.0–1.0）。
                         傳入 None 不做任何事。
            """
            if signal is not None:
                signal.connect(self.update_volume)

else:

    class SettingsVoicePage:  # type: ignore[no-redef]
        pass
