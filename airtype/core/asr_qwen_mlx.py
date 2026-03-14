"""Qwen3-ASR MLX 引擎（Apple Silicon 專用）。

使用 mlx-qwen3-asr 套件在 Apple Silicon 上進行高效能語音辨識。
MLX 框架原生支援 Metal GPU 加速，效能優於 ONNX Runtime + CoreML。

參考：https://github.com/moona3k/mlx-qwen3-asr
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

# 支援語言（與 Qwen3-ASR 官方一致）
_SUPPORTED_LANGUAGES = [
    "zh-TW", "en", "ja", "ko", "fr", "de", "es", "it", "pt", "ru",
    "ar", "zh-HK", "th", "vi", "id", "tr", "hi", "ms", "nl", "sv",
    "da", "fi", "pl", "cs", "fil", "fa", "el", "ro", "hu", "mk",
]


class QwenMlxEngine:
    """Qwen3-ASR MLX 引擎（Apple Silicon 原生推理）。

    使用 mlx-qwen3-asr 套件的 Session API 進行語音辨識。

    典型用法::

        engine = QwenMlxEngine()
        engine.prepare("Qwen/Qwen3-ASR-0.6B")
        result = engine.recognize(audio)
    """

    ENGINE_ID = "qwen3-mlx"
    SUPPORTED_LANGUAGES = _SUPPORTED_LANGUAGES

    def __init__(self) -> None:
        self._model_path: Optional[str] = None
        self._config: dict[str, Any] = {}
        self._loaded: bool = False
        self._session = None

        # 上下文偏移
        self._hot_words: list[HotWord] = []
        self._context_text: str = ""

    # ------------------------------------------------------------------
    # ASREngine Protocol
    # ------------------------------------------------------------------

    def load_model(self, model_path: str, config: dict[str, Any] | None = None) -> None:
        """載入 MLX 模型。

        Args:
            model_path: HuggingFace 模型 ID（如 "Qwen/Qwen3-ASR-0.6B"）或本地路徑。
            config: 可選配置（目前支援 "dtype"）。
        """
        from mlx_qwen3_asr import Session

        config = config or {}
        self._session = Session(model=model_path)
        self._model_path = model_path
        self._config = config
        self._loaded = True
        logger.info("QwenMlxEngine 已就緒（模型：%s）", model_path)

    def recognize(self, audio: np.ndarray) -> ASRResult:
        """批次辨識音訊。"""
        self._ensure_loaded()

        audio = np.asarray(audio, dtype=np.float32)
        if audio.ndim > 1:
            audio = audio.mean(axis=-1)

        duration = float(len(audio)) / 16000.0

        # 組合上下文
        context = self._build_context()

        result = self._session.transcribe(audio, context=context)

        # 轉換語言格式
        language = result.language or ""

        return ASRResult(
            text=result.text,
            language=language,
            confidence=1.0,  # mlx-qwen3-asr 不提供信心分數
            segments=[ASRSegment(text=result.text, start=0.0, end=duration)],
        )

    def recognize_stream(self, chunk: np.ndarray) -> PartialResult:
        """MLX 批次路徑不支援串流辨識。"""
        return PartialResult(text="", is_final=False)

    @property
    def supports_hot_words(self) -> bool:
        return False

    def set_hot_words(self, words: list[HotWord]) -> None:
        self._hot_words = list(words)

    def set_context(self, context_text: str) -> None:
        self._context_text = context_text

    def get_supported_languages(self) -> list[str]:
        return list(self.SUPPORTED_LANGUAGES)

    def unload(self) -> None:
        self._session = None
        self._loaded = False
        logger.info("QwenMlxEngine 已卸載")

    def prepare(self, model_path: str, config: dict[str, Any] | None = None) -> None:
        """設定模型路徑（延遲載入）。"""
        self._model_path = model_path
        self._config = config or {}
        self._loaded = False

    # ------------------------------------------------------------------
    # 內部方法
    # ------------------------------------------------------------------

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        if self._model_path is None:
            raise RuntimeError("引擎未設定模型路徑。請先呼叫 prepare() 或 load_model()。")
        self.load_model(self._model_path, self._config)

    def _build_context(self) -> str:
        """組合上下文字串（語境 + 熱詞）。"""
        parts = []
        if self._context_text:
            parts.append(self._context_text)
        if self._hot_words:
            hw = " ".join(w.word for w in self._hot_words)
            parts.append(hw)
        return " ".join(parts) if parts else ""


# ------------------------------------------------------------------
# 引擎登錄
# ------------------------------------------------------------------


def register(registry: ASREngineRegistry) -> bool:
    """若 mlx_qwen3_asr 套件可用，將 QwenMlxEngine 登錄至 registry。"""
    try:
        import mlx_qwen3_asr  # noqa: F401
    except ImportError:
        logger.debug("mlx_qwen3_asr 套件未安裝，跳過 '%s' 登錄", QwenMlxEngine.ENGINE_ID)
        return False

    registry.register_engine(QwenMlxEngine.ENGINE_ID, QwenMlxEngine)
    logger.info("已登錄 ASR 引擎：%s", QwenMlxEngine.ENGINE_ID)
    return True
