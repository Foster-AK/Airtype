"""音訊擷取服務。

使用 sounddevice InputStream（callback 模式）從麥克風以
16kHz / float32 / 單聲道 / 512 樣本緩衝區擷取音訊。

功能：
- 輸入裝置列舉與執行時切換
- 3 秒 numpy 環形緩衝區（供 VAD/ASR 讀取）
- 每幀 RMS 音量計算（供波形 UI 使用）
- 以 collections.deque 進行無競態幀資料交換（取代 queue.Queue）
- 音訊非持久化驗證（安全性審查）
"""

from __future__ import annotations

import logging
import sys
import time
import threading
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Union

import numpy as np
import sounddevice as sd

from airtype.config import AirtypeConfig
from airtype.ui.device_selector import list_input_devices
from airtype.utils.audio_utils import RingBuffer, build_wasapi_extra_settings, compute_rms

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
        # deque(maxlen=N) 在 append 時若滿則自動丟棄最舊元素，
        # CPython 的 GIL 保證 append/popleft 各自的原子性，無 TOCTOU 問題。
        self._frame_queue: deque[np.ndarray] = deque(maxlen=FRAME_QUEUE_MAXSIZE)
        # _rms 是純 Python float，在 CPython 中單次賦值受 GIL 保護，不需額外 Lock。
        self._rms: float = 0.0
        self._is_capturing: bool = False

    # ------------------------------------------------------------------
    # 公開屬性
    # ------------------------------------------------------------------

    @property
    def rms(self) -> float:
        """目前幀的 RMS 音量。CPython GIL 保證 float 賦值的原子性。"""
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
    # 平台特定設定
    # ------------------------------------------------------------------

    @staticmethod
    def _build_extra_settings():
        """建立平台特定的 InputStream extra_settings（委派至 audio_utils）。"""
        return build_wasapi_extra_settings()

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
        extra_settings = self._build_extra_settings()

        try:
            self._stream = sd.InputStream(
                device=sd_device,
                samplerate=SAMPLE_RATE,
                channels=CHANNELS,
                dtype=DTYPE,
                blocksize=BLOCKSIZE,
                callback=self._callback,
                extra_settings=extra_settings,
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
            # 若以 int index 開啟失敗，fallback 至系統預設裝置
            if isinstance(sd_device, int):
                logger.warning(
                    "裝置 index %d 無效（%s），退回系統預設裝置",
                    sd_device,
                    exc,
                )
                try:
                    self._stream = sd.InputStream(
                        device=None,
                        samplerate=SAMPLE_RATE,
                        channels=CHANNELS,
                        dtype=DTYPE,
                        blocksize=BLOCKSIZE,
                        callback=self._callback,
                        extra_settings=extra_settings,
                    )
                    self._stream.start()
                    self._is_capturing = True
                    logger.info(
                        "音訊擷取已啟動（fallback 預設裝置）：取樣率=%d Hz, 幀大小=%d 樣本",
                        SAMPLE_RATE,
                        BLOCKSIZE,
                    )
                    return
                except Exception as fallback_exc:
                    self._stream = None
                    logger.error("Fallback 預設裝置也啟動失敗：%s", fallback_exc)
                    raise
            logger.error("音訊串流啟動失敗：%s", exc)
            raise

    def stop(self) -> None:
        """停止音訊擷取並釋放裝置。"""
        self._stop_stream()
        logger.info("音訊擷取已停止")

    def __enter__(self) -> "AudioCaptureService":
        """支援 with 語句；回傳 self（start 由呼叫端負責）。"""
        return self

    def __exit__(self, *_) -> None:
        """離開 with 區塊時自動停止串流，防止資源洩漏。"""
        self.stop()

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
        self._config.voice.input_device = device_index

        if was_capturing:
            self.start(device=device_index)
            logger.info("已切換至裝置：%s", device_index)

    # ------------------------------------------------------------------
    # 消費者介面
    # ------------------------------------------------------------------

    def get_frame(self, timeout: float = 0.05) -> Optional[np.ndarray]:
        """從幀緩衝取出最舊的音訊幀（FIFO）。

        以短輪詢取代 Condition variable；輪詢間隔 1ms，最多等待 timeout 秒。

        Args:
            timeout: 等待逾時秒數（預設 50ms）

        Returns:
            一維 float32 陣列（512 樣本），或逾時時回傳 None。
        """
        deadline = time.monotonic() + timeout
        while True:
            try:
                return self._frame_queue.popleft()
            except IndexError:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return None
                time.sleep(min(0.001, remaining))

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

        # 計算 RMS（供 UI 波形顯示）；CPython float 賦值受 GIL 保護，無需 Lock。
        self._rms = compute_rms(audio_frame)

        # deque(maxlen=N).append 在緩衝區滿時自動丟棄最舊幀，無 TOCTOU 問題。
        self._frame_queue.append(audio_frame)


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
