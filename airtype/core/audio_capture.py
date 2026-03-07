"""音訊擷取服務。

使用 sounddevice InputStream（callback 模式）從麥克風以
16kHz / float32 / 單聲道 / 512 樣本緩衝區擷取音訊。

功能：
- 輸入裝置列舉與執行時切換
- 3 秒 numpy 環形緩衝區（供 VAD/ASR 讀取）
- 每幀 RMS 音量計算（供波形 UI 使用）
- 透過 queue.Queue 進行執行緒安全幀資料交換
- 音訊非持久化驗證（安全性審查）
"""

from __future__ import annotations

import logging
import queue
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Union

import numpy as np
import sounddevice as sd

from airtype.config import AirtypeConfig
from airtype.ui.device_selector import list_input_devices
from airtype.utils.audio_utils import RingBuffer, compute_rms

logger = logging.getLogger(__name__)

# 音訊參數（PRD §6.1）
SAMPLE_RATE: int = 16_000       # Hz
CHANNELS: int = 1               # 單聲道
DTYPE: str = "float32"          # PCM float32
BLOCKSIZE: int = 512            # 每幀樣本數 ≈ 32ms

# 環形緩衝區：3 秒
RING_BUFFER_SIZE: int = SAMPLE_RATE * 3  # 48000 樣本

# 幀 queue 上限（約 5 秒緩衝）
FRAME_QUEUE_MAXSIZE: int = 150

# 音訊檔案副檔名（用於非持久化驗證）
_AUDIO_EXTENSIONS: frozenset[str] = frozenset(
    {".wav", ".mp3", ".pcm", ".raw", ".flac", ".ogg", ".m4a", ".opus", ".aac"}
)


@dataclass
class DeviceInfo:
    """輸入裝置資訊。"""
    index: int
    name: str


class AudioCaptureService:
    """sounddevice 音訊擷取服務。

    使用 InputStream callback 模式，callback 在 PortAudio 背景執行緒中
    執行，因此 callback 內僅進行 numpy 複製、RMS 計算與 queue put。

    Args:
        config: Airtype 設定物件；讀取 config.voice.input_device
    """

    def __init__(self, config: AirtypeConfig) -> None:
        self._config = config
        self._stream: Optional[sd.InputStream] = None
        self._ring_buffer = RingBuffer(RING_BUFFER_SIZE)
        self._frame_queue: queue.Queue[np.ndarray] = queue.Queue(
            maxsize=FRAME_QUEUE_MAXSIZE
        )
        self._rms: float = 0.0
        self._rms_lock = threading.Lock()
        self._is_capturing: bool = False

    # ------------------------------------------------------------------
    # 公開屬性
    # ------------------------------------------------------------------

    @property
    def rms(self) -> float:
        """目前幀的 RMS 音量（執行緒安全讀取）。"""
        with self._rms_lock:
            return self._rms

    @property
    def is_capturing(self) -> bool:
        """是否正在擷取音訊。"""
        return self._is_capturing

    @property
    def ring_buffer(self) -> RingBuffer:
        """音訊環形緩衝區（供 VAD/ASR 直接讀取）。"""
        return self._ring_buffer

    # ------------------------------------------------------------------
    # 裝置管理
    # ------------------------------------------------------------------

    def list_devices(self) -> list[DeviceInfo]:
        """列舉所有可用音訊輸入裝置（去重）。

        Returns:
            DeviceInfo 清單，優先使用平台偏好 Host API（WASAPI/CoreAudio/ALSA）。
            若無裝置或列舉失敗，回傳空清單並記錄警告。
        """
        result = [DeviceInfo(index=d["index"], name=d["name"]) for d in list_input_devices()]
        if not result:
            logger.warning("未找到任何音訊輸入裝置")
        return result

    # ------------------------------------------------------------------
    # 擷取控制
    # ------------------------------------------------------------------

    def start(self, device: Union[int, str, None] = None) -> None:
        """開始音訊擷取。

        Args:
            device: 裝置索引（int）、裝置名稱（str）、
                    "default" 或 None（使用系統預設）。
                    若省略，從 config.voice.input_device 讀取。

        Raises:
            sounddevice.PortAudioError: 裝置不可用或串流開啟失敗
        """
        if device is None:
            device = self._config.voice.input_device

        # sounddevice 使用 None 代表預設裝置
        sd_device: Union[int, str, None] = None if device == "default" else device

        self._stop_stream()

        try:
            self._stream = sd.InputStream(
                device=sd_device,
                samplerate=SAMPLE_RATE,
                channels=CHANNELS,
                dtype=DTYPE,
                blocksize=BLOCKSIZE,
                callback=self._callback,
            )
            self._stream.start()
            self._is_capturing = True
            logger.info(
                "音訊擷取已啟動：裝置=%s, 取樣率=%d Hz, 幀大小=%d 樣本",
                device,
                SAMPLE_RATE,
                BLOCKSIZE,
            )
        except Exception as exc:
            self._stream = None
            logger.error("音訊串流啟動失敗：%s", exc)
            raise

    def stop(self) -> None:
        """停止音訊擷取並釋放裝置。"""
        self._stop_stream()
        logger.info("音訊擷取已停止")

    def set_device(self, device_index: Union[int, str]) -> None:
        """執行時切換輸入裝置。

        若正在擷取，停止目前串流並在新裝置上重新啟動。
        切換在 200ms 內完成（符合 spec 需求）。

        Args:
            device_index: 新裝置索引或裝置名稱
        """
        was_capturing = self._is_capturing
        self._stop_stream()

        # 更新設定
        self._config.voice.input_device = str(device_index)

        if was_capturing:
            self.start(device=device_index)
            logger.info("已切換至裝置：%s", device_index)

    # ------------------------------------------------------------------
    # 消費者介面
    # ------------------------------------------------------------------

    def get_frame(self, timeout: float = 0.05) -> Optional[np.ndarray]:
        """從 queue 取出下一個音訊幀（FIFO）。

        Args:
            timeout: 等待逾時秒數（預設 50ms）

        Returns:
            一維 float32 陣列（512 樣本），或逾時時回傳 None。
        """
        try:
            return self._frame_queue.get(timeout=timeout)
        except queue.Empty:
            return None

    # ------------------------------------------------------------------
    # 內部實作
    # ------------------------------------------------------------------

    def _stop_stream(self) -> None:
        """停止並關閉目前串流（若有）。"""
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception as exc:
                logger.warning("關閉音訊串流時發生錯誤：%s", exc)
            finally:
                self._stream = None
                self._is_capturing = False

    def _callback(
        self,
        indata: np.ndarray,
        frames: int,
        time_info: object,
        status: sd.CallbackFlags,
    ) -> None:
        """sounddevice InputStream callback（在 PortAudio 執行緒中執行）。

        此函式必須輕量、非阻塞。僅執行：
        1. 複製音訊幀（避免 sounddevice 重用 indata buffer）
        2. 寫入環形緩衝區
        3. 計算 RMS
        4. 將幀放入 queue

        Args:
            indata: 形狀 (frames, channels) 的 float32 陣列
            frames: 本次 callback 的樣本數
            time_info: PortAudio 時間資訊（未使用）
            status: 串流狀態旗標
        """
        if status:
            logger.warning("音訊 callback 狀態：%s", status)

        # 取出單聲道並複製（重要：indata 在 callback 返回後可能被重用）
        audio_frame: np.ndarray = indata[:, 0].copy()

        # 寫入環形緩衝區
        self._ring_buffer.write(audio_frame)

        # 計算 RMS（供 UI 波形顯示）
        rms_value = compute_rms(audio_frame)
        with self._rms_lock:
            self._rms = rms_value

        # 非阻塞放入幀 queue；若滿則丟棄最舊幀
        try:
            self._frame_queue.put_nowait(audio_frame)
        except queue.Full:
            try:
                self._frame_queue.get_nowait()
                self._frame_queue.put_nowait(audio_frame)
            except queue.Empty:
                pass


# ---------------------------------------------------------------------------
# 安全性：音訊非持久化驗證
# ---------------------------------------------------------------------------

def verify_no_audio_files(directory: Path) -> bool:
    """驗證目錄中不存在任何持久化音訊檔案。

    在完整辨識週期後呼叫，確認音訊資料未被寫入磁碟。

    Args:
        directory: 要掃描的目錄（通常為 ~/.airtype/）。

    Returns:
        True 表示目錄中無音訊檔案（符合安全要求）；
        False 表示發現音訊檔案（安全性違規）。
    """
    if not directory.exists():
        return True

    found: list[Path] = []
    for ext in _AUDIO_EXTENSIONS:
        found.extend(directory.rglob(f"*{ext}"))

    if found:
        logger.warning(
            "安全性警告：發現持久化音訊檔案（音訊非持久化需求違規）：%s",
            [str(f) for f in found],
        )
        return False

    return True
