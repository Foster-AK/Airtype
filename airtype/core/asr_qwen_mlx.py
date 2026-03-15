"""Qwen3-ASR MLX 引擎。

使用 mlx-qwen3-asr 套件的 Session API 在 macOS Apple Silicon 上
執行 Qwen3-ASR 0.6B 語音辨識。MLX 透過 Apple 統一記憶體架構
進行推理，延遲僅 0.11–0.46 秒。

推理流程：
  1. Session 載入 HuggingFace safetensors 模型
  2. Session.transcribe() 接收 (np.ndarray, sample_rate) 並內建
     Mel 特徵提取、encoder-decoder 推理
  3. 回傳辨識文字

符合 specs/asr-qwen-mlx/spec.md。
相依：06-asr-abstraction（ASREngine Protocol）。
"""
from __future__ import annotations

import logging
from typing import Any, Optional

import numpy as np

from airtype.core.asr_engine import (
    ASREngineRegistry,
    ASRResult,
    ASRSegment,
    HotWord,
    PartialResult,
)

logger = logging.getLogger(__name__)

# 支援語言（Qwen3-ASR 多語言能力）
_SUPPORTED_LANGUAGES = ["zh-TW", "zh-CN", "en", "ja", "ko"]


class MLXQwen3ASREngine:
    """Qwen3-ASR MLX 推理引擎（macOS Apple Silicon 專用）。

    封裝 mlx-qwen3-asr 的 Session API，支援批次辨識、
    context text biasing、延遲載入與模型卸載。

    典型用法::

        engine = MLXQwen3ASREngine()
        engine.prepare("Qwen/Qwen3-ASR-0.6B")
        result = engine.recognize(audio)
    """

    ENGINE_ID = "qwen3-mlx"

    def __init__(self) -> None:
        self._model_path: Optional[str] = None
        self._config: dict[str, Any] = {}
        self._loaded: bool = False
        self._session = None  # mlx_qwen3_asr.Session
        self._context_text: str = ""
        self._hot_words: list[HotWord] = []

    # ------------------------------------------------------------------
    # ASREngine Protocol
    # ------------------------------------------------------------------

    def load_model(self, model_path: str, config: dict[str, Any] | None = None) -> None:
        """載入 Qwen3-ASR MLX 模型。

        Args:
            model_path: HuggingFace 模型 ID（如 "Qwen/Qwen3-ASR-0.6B"）
                        或本地模型目錄路徑。
            config: 引擎特定設定（目前未使用）。
        """
        from mlx_qwen3_asr import Session

        self._session = Session(model_path)
        self._model_path = model_path
        self._config = config or {}
        self._loaded = True
        logger.info("MLXQwen3ASREngine 已載入模型：%s", model_path)

    def recognize(self, audio: np.ndarray) -> ASRResult:
        """批次辨識音訊。

        Args:
            audio: 16kHz mono PCM float32 numpy 陣列。

        Returns:
            ASRResult 含文字、語言、信心分數與時間段。
        """
        self._ensure_loaded()

        audio = np.asarray(audio, dtype=np.float32)

        # 空音訊處理
        if audio.size == 0:
            return ASRResult(text="", language="", confidence=0.0)

        # 透過 Session.transcribe() 進行推理
        kwargs: dict[str, Any] = {}
        if self._context_text:
            kwargs["context"] = self._context_text

        text = self._session.transcribe(audio, sample_rate=16000, **kwargs)

        # 處理回傳值
        if not text or not text.strip():
            return ASRResult(text="", language="", confidence=0.0)

        text = text.strip()
        duration = float(len(audio)) / 16000.0
        language = self._detect_language(text)
        confidence = self._estimate_confidence(text, audio)

        return ASRResult(
            text=text,
            language=language,
            confidence=confidence,
            segments=[ASRSegment(text=text, start=0.0, end=duration)],
        )

    def recognize_stream(self, chunk: np.ndarray) -> PartialResult:
        """MLX 批次路徑不支援串流辨識。"""
        return PartialResult(text="", is_final=False)

    @property
    def supports_hot_words(self) -> bool:
        """MLX 引擎不支援原生熱詞偏置（使用 context text biasing）。"""
        return False

    def set_hot_words(self, words: list[HotWord]) -> None:
        self._hot_words = list(words)

    def set_context(self, context_text: str) -> None:
        self._context_text = context_text

    def get_supported_languages(self) -> list[str]:
        return list(_SUPPORTED_LANGUAGES)

    def unload(self) -> None:
        """卸載模型並釋放記憶體。"""
        self._session = None
        self._loaded = False
        logger.info("MLXQwen3ASREngine 已卸載")

    def prepare(self, model_path: str, config: dict[str, Any] | None = None) -> None:
        """設定模型路徑（延遲載入）。"""
        self._model_path = model_path
        self._config = config or {}
        self._loaded = False

    # ------------------------------------------------------------------
    # 內部方法
    # ------------------------------------------------------------------

    @staticmethod
    def _detect_language(text: str) -> str:
        """依辨識文字推測語言代碼。

        mlx-qwen3-asr Session.transcribe() 僅回傳文字，不含語言 metadata，
        因此使用 CJK 字元比例作為語言偵測的後備方案。
        """
        from airtype.core.asr_utils import detect_language_from_cjk_ratio

        return detect_language_from_cjk_ratio(text)

    @staticmethod
    def _estimate_confidence(text: str, audio: np.ndarray) -> float:
        """估算辨識信心分數。

        mlx-qwen3-asr Session.transcribe() 不回傳信心分數，
        使用啟發式估算：依文字長度與音訊時長的比值判斷合理性。
        空結果回傳 0.0；正常結果依文字密度給予 0.7–0.95 之間的分數。
        """
        if not text:
            return 0.0
        duration_sec = len(audio) / 16000.0
        if duration_sec <= 0:
            return 0.0
        # 每秒合理字元數約 2–8（中文）或 5–20（英文）
        chars_per_sec = len(text) / duration_sec
        if chars_per_sec < 0.5:
            return 0.5  # 文字極少，可能辨識不佳
        if chars_per_sec > 30:
            return 0.6  # 文字過多，可能有幻覺
        return 0.85  # 正常範圍

    def _ensure_loaded(self) -> None:
        """確保模型已載入，若未載入則觸發載入。"""
        if self._loaded:
            return
        if self._model_path is None:
            raise RuntimeError("引擎未設定模型路徑。請先呼叫 prepare() 或 load_model()。")
        self.load_model(self._model_path, self._config)


# ------------------------------------------------------------------
# 引擎登錄
# ------------------------------------------------------------------


def register(registry: ASREngineRegistry) -> bool:
    """若 mlx 套件可用，將 MLXQwen3ASREngine 登錄至 registry。"""
    try:
        import mlx  # noqa: F401
    except ImportError:
        logger.debug("mlx 套件未安裝，跳過 '%s' 登錄", MLXQwen3ASREngine.ENGINE_ID)
        return False

    registry.register_engine(MLXQwen3ASREngine.ENGINE_ID, MLXQwen3ASREngine)
    logger.info("已登錄 ASR 引擎：%s", MLXQwen3ASREngine.ENGINE_ID)
    return True
