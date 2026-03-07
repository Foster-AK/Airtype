"""Silero VAD v5 ONNX 整合與四狀態語音活動偵測引擎。

功能：
- SileroVAD：封裝 Silero VAD v5 ONNX 模型，處理 512 樣本幀並回傳語音機率
- VadState：四狀態列舉（IDLE / SPEECH / SILENCE_COUNTING / SPEECH_ENDED）
- VadEngine：四狀態機 + 事件 callback + 可設定參數 + 背景消費執行緒

依賴：onnxruntime（CPU 推理），numpy
"""

from __future__ import annotations

import logging
import threading
import time
from enum import Enum, auto
from pathlib import Path
from typing import Callable, Optional

import numpy as np

from airtype.config import AirtypeConfig

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 常數
# ---------------------------------------------------------------------------

SAMPLE_RATE: int = 16_000
FRAME_SIZE: int = 512

# Silero VAD v5 ONNX 模型狀態張量維度（2, batch=1, 128）
_STATE_SHAPE: tuple[int, int, int] = (2, 1, 128)

# 模型預設路徑（支援 PyInstaller 打包環境）
from airtype.utils.paths import get_bundled_root

DEFAULT_MODEL_PATH: Path = get_bundled_root() / "models" / "vad" / "silero_vad_v5.onnx"


# ---------------------------------------------------------------------------
# 型別別名
# ---------------------------------------------------------------------------

StateChangeCallback = Callable[["VadState", "VadState"], None]


# ---------------------------------------------------------------------------
# VadState 列舉
# ---------------------------------------------------------------------------

class VadState(Enum):
    """VAD 四狀態列舉。

    轉換規則（依 PRD §6.2）：
    IDLE → SPEECH（speech_prob >= threshold）
    SPEECH → SILENCE_COUNTING（speech_prob < threshold）
    SILENCE_COUNTING → SPEECH（speech_prob >= threshold）
    SILENCE_COUNTING → SPEECH_ENDED（靜默持續 >= silence_timeout）
    SPEECH_ENDED → IDLE（自動重置，於下次 process_frame 開始時）
    """

    IDLE = auto()
    SPEECH = auto()
    SILENCE_COUNTING = auto()
    SPEECH_ENDED = auto()


# ---------------------------------------------------------------------------
# SileroVAD：ONNX 模型封裝
# ---------------------------------------------------------------------------

class SileroVAD:
    """封裝 Silero VAD v5 ONNX 模型，提供逐幀語音機率推理。

    每次呼叫 process_frame() 時，模型接收 512 個 float32 樣本與
    LSTM 隱藏狀態，回傳語音機率 [0, 1] 並更新隱藏狀態。

    Args:
        model_path: silero_vad_v5.onnx 模型檔案路徑。
    """

    def __init__(self, model_path: Path = DEFAULT_MODEL_PATH) -> None:
        if not model_path.exists():
            raise FileNotFoundError(
                f"Silero VAD v5 模型檔案不存在：{model_path}\n"
                "請執行 python models/vad/download_model.py 下載模型。"
            )

        import onnxruntime as ort  # 延遲匯入，避免未安裝時影響整個模組

        self._session = ort.InferenceSession(
            str(model_path),
            providers=["CPUExecutionProvider"],
        )

        # 查詢模型輸入名稱（Silero VAD v5：input, state, sr）
        input_names = [inp.name for inp in self._session.get_inputs()]
        self._input_name = "input"
        self._state_name = "state" if "state" in input_names else "h"
        self._sr_name = "sr"

        # 初始化 LSTM 狀態張量
        self._state = np.zeros(_STATE_SHAPE, dtype=np.float32)

        logger.info("Silero VAD v5 模型已載入：%s", model_path)

    def reset_states(self) -> None:
        """重置 LSTM 狀態張量（每次新語音段開始前呼叫）。"""
        self._state = np.zeros(_STATE_SHAPE, dtype=np.float32)

    def process_frame(self, frame: np.ndarray) -> float:
        """處理 512 樣本音訊幀，回傳語音機率 [0.0, 1.0]。

        Args:
            frame: 形狀 (512,) 的 float32 一維陣列。

        Returns:
            語音機率，介於 0.0 到 1.0 之間。
        """
        audio = frame.reshape(1, -1).astype(np.float32)
        sr = np.array(SAMPLE_RATE, dtype=np.int64)

        ort_inputs = {
            self._input_name: audio,
            self._state_name: self._state,
            self._sr_name: sr,
        }

        outputs = self._session.run(None, ort_inputs)
        # output shape: (1, 1) → 取出純量
        speech_prob: float = float(outputs[0].flatten()[0])
        self._state = outputs[1]

        return speech_prob


# ---------------------------------------------------------------------------
# VadEngine：四狀態機 + callback + 消費執行緒
# ---------------------------------------------------------------------------

class VadEngine:
    """四狀態 VAD 狀態機，整合 SileroVAD ONNX 模型推理。

    使用方式：
    1. 以 on_state_change() 註冊 callback
    2. 手動呼叫 process_frame() 處理幀，或
    3. 呼叫 start_consuming(audio_service) 開啟背景消費執行緒

    Args:
        config: AirtypeConfig 設定物件，讀取 general.silence_timeout。
        vad_model: SileroVAD 實例（可注入 mock 供測試使用）。
                   若為 None，首次呼叫 process_frame 時自動建立。
    """

    def __init__(
        self,
        config: AirtypeConfig,
        vad_model: Optional[SileroVAD] = None,
    ) -> None:
        self._config = config
        self._vad_model = vad_model  # 可注入 mock 供測試
        self._state: VadState = VadState.IDLE
        self._callbacks: list[StateChangeCallback] = []
        self._silence_start: Optional[float] = None
        self._running: bool = False
        self._thread: Optional[threading.Thread] = None

        # 可設定參數（從設定讀取）
        self.speech_threshold: float = 0.5

        _timeout = config.general.silence_timeout
        if not (0.5 <= _timeout <= 5.0):
            logger.warning(
                "silence_timeout %.2f 超出有效範圍 [0.5, 5.0]，已截斷至範圍內", _timeout
            )
            _timeout = max(0.5, min(5.0, _timeout))
        self.silence_timeout: float = _timeout

    # ------------------------------------------------------------------
    # 公開屬性
    # ------------------------------------------------------------------

    @property
    def state(self) -> VadState:
        """目前 VAD 狀態。"""
        return self._state

    # ------------------------------------------------------------------
    # Callback 註冊
    # ------------------------------------------------------------------

    def on_state_change(self, callback: StateChangeCallback) -> None:
        """註冊狀態轉換事件 callback。

        Args:
            callback: 函式 (previous: VadState, current: VadState) → None
        """
        self._callbacks.append(callback)

    # ------------------------------------------------------------------
    # 幀處理（核心邏輯）
    # ------------------------------------------------------------------

    def process_frame(self, frame: np.ndarray) -> float:
        """處理 512 樣本音訊幀，更新狀態機，回傳語音機率。

        若 vad_model 尚未初始化，自動載入 SileroVAD 模型。

        Args:
            frame: 形狀 (512,) 的 float32 一維陣列。

        Returns:
            語音機率，介於 0.0 到 1.0 之間。
        """
        if self._vad_model is None:
            self._vad_model = SileroVAD()

        speech_prob = self._vad_model.process_frame(frame)
        self._update_state(speech_prob)
        return speech_prob

    # ------------------------------------------------------------------
    # 背景消費執行緒（整合 AudioCaptureService）
    # ------------------------------------------------------------------

    def start_consuming(self, audio_service) -> None:
        """在背景 daemon 執行緒中持續消費 AudioCaptureService 的幀 queue。

        從 audio_service.get_frame() 取出幀並呼叫 process_frame()。
        呼叫 stop_consuming() 停止。

        Args:
            audio_service: AudioCaptureService 實例（或具有 get_frame() 方法的物件）。
        """
        if self._running:
            logger.warning("VadEngine 消費執行緒已在執行中")
            return

        self._running = True
        self._thread = threading.Thread(
            target=self._consume_loop,
            args=(audio_service,),
            daemon=True,
            name="vad-consumer",
        )
        self._thread.start()
        logger.info("VadEngine 消費執行緒已啟動")

    def stop_consuming(self) -> None:
        """停止背景消費執行緒（最多等待 2 秒）。"""
        self._running = False
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        logger.info("VadEngine 消費執行緒已停止")

    # ------------------------------------------------------------------
    # 內部實作
    # ------------------------------------------------------------------

    def _update_state(self, speech_prob: float) -> None:
        """依語音機率更新狀態機。"""
        now = time.monotonic()

        # SPEECH_ENDED：自動重置至 IDLE，再處理本幀
        if self._state == VadState.SPEECH_ENDED:
            self._state = VadState.IDLE
            self._silence_start = None
            if self._vad_model is not None:
                self._vad_model.reset_states()

        if self._state == VadState.IDLE:
            if speech_prob >= self.speech_threshold:
                self._transition(VadState.SPEECH)

        elif self._state == VadState.SPEECH:
            if speech_prob < self.speech_threshold:
                self._silence_start = now
                self._transition(VadState.SILENCE_COUNTING)

        elif self._state == VadState.SILENCE_COUNTING:
            if speech_prob >= self.speech_threshold:
                self._silence_start = None
                self._transition(VadState.SPEECH)
            elif (
                self._silence_start is not None
                and (now - self._silence_start) >= self.silence_timeout
            ):
                self._transition(VadState.SPEECH_ENDED)

    def _transition(self, new_state: VadState) -> None:
        """執行狀態轉換並通知所有 callback。"""
        prev = self._state
        self._state = new_state
        logger.debug("VAD 狀態轉換：%s → %s", prev.name, new_state.name)

        for cb in self._callbacks:
            try:
                cb(prev, new_state)
            except Exception as exc:
                logger.warning("VAD callback 拋出例外（已忽略）：%s", exc)

    def _consume_loop(self, audio_service) -> None:
        """背景執行緒：持續從 audio_service 取幀並處理。"""
        while self._running:
            frame = audio_service.get_frame(timeout=0.05)
            if frame is not None:
                try:
                    self.process_frame(frame)
                except Exception as exc:
                    logger.error("VadEngine 處理幀時發生錯誤：%s", exc)
