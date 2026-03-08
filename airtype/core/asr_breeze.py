"""Breeze-ASR-25 引擎。

使用 HuggingFace Transformers（優先，官方推薦）或 faster-whisper（CTranslate2 後端）
載入 Breeze-ASR-25 模型，提供最佳化的臺灣華語辨識與中英語碼轉換支援。
若兩套件均不可用，此引擎不會在登錄檔中登錄，也不產生匯入錯誤。

符合 PRD §6.3.3（Breeze-ASR-25）。
相依：06-asr-abstraction。
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Optional

import numpy as np

from airtype.core.asr_engine import (
    ASREngineRegistry,
    ASRResult,
    ASRSegment,
    HotWord,
    PartialResult,
)
from airtype.core.asr_utils import detect_language_from_cjk_ratio

logger = logging.getLogger(__name__)

_DEFAULT_LANGUAGE = None   # None → 自動偵測語言（支援語碼轉換）
_DEFAULT_BEAM_SIZE = 5
_DEFAULT_COMPUTE_TYPE = "float16"


class BreezeAsrEngine:
    """Breeze-ASR-25 引擎。

    實作 ASREngine Protocol，使用 transformers（優先，官方推薦）或 faster-whisper
    推理 Breeze-ASR-25 模型。支援臺灣華語辨識與中英語碼轉換。
    Whisper 架構為批次辨識；`recognize_stream()` 回傳空 PartialResult。
    """

    ENGINE_ID = "breeze-asr-25"
    SUPPORTED_LANGUAGES = ["zh-TW", "zh-CN", "en"]

    def __init__(self) -> None:
        # 延遲載入狀態
        self._model_path: Optional[str] = None
        self._config: dict[str, Any] = {}
        self._loaded: bool = False

        # 後端模型（載入後設定）
        self._model = None           # faster-whisper WhisperModel 或 transformers pipeline
        self._backend: Optional[str] = None  # "faster-whisper" 或 "transformers"

        # 上下文偏移
        self._hot_words: list[HotWord] = []
        self._context_text: str = ""

    # ------------------------------------------------------------------
    # ASREngine Protocol 方法
    # ------------------------------------------------------------------

    def load_model(self, model_path: str, config: dict[str, Any] | None = None) -> None:
        """載入 Breeze-ASR-25 模型。

        嘗試順序：faster-whisper（CTranslate2）→ transformers pipeline。

        Args:
            model_path: 模型目錄路徑（CTranslate2 格式或 HuggingFace 格式）。
            config: 引擎設定，支援 "compute_type"（預設 "float16"）、
                    "device"（預設 "auto"）、"beam_size"（預設 5）。

        Raises:
            FileNotFoundError: 模型目錄不存在。
            ImportError: faster-whisper 與 transformers 均未安裝。
        """
        model_dir = Path(model_path)
        if not model_dir.exists():
            raise FileNotFoundError(
                f"模型目錄不存在：{model_path}\n"
                "請執行：python scripts/download_models.py --model breeze-asr-25"
            )

        config = config or {}
        self._config = config

        self._model, self._backend = self._load_backend(model_dir, config)
        self._model_path = model_path
        self._loaded = True
        logger.info("BreezeAsrEngine 已就緒（後端：%s）", self._backend)

    def recognize(self, audio: np.ndarray) -> ASRResult:
        """批次辨識音訊，回傳完整結果。

        首次呼叫時若模型尚未載入，自動觸發延遲載入。

        Args:
            audio: 16kHz mono PCM float32 numpy 陣列。

        Returns:
            ASRResult 含辨識文字、語言代碼、信心分數與時間段。

        Raises:
            RuntimeError: 未設定模型路徑。
        """
        self._ensure_loaded()

        text, confidence = self._run_inference(audio)
        language = self._detect_language(text)
        duration = float(len(audio)) / 16000.0

        return ASRResult(
            text=text,
            language=language,
            confidence=confidence,
            segments=[ASRSegment(text=text, start=0.0, end=duration)],
        )

    def recognize_stream(self, chunk: np.ndarray) -> PartialResult:
        """Whisper 架構不支援串流辨識，回傳空部分結果。

        若需串流，可搭配 VAD 將長音訊切段後使用 recognize() 批次辨識。
        """
        return PartialResult(text="", is_final=False)

    @property
    def supports_hot_words(self) -> bool:
        """Breeze-ASR 不支援原生熱詞偏置。"""
        return False

    def set_hot_words(self, words: list[HotWord]) -> None:
        """設定熱詞列表（儲存供提示注入）。

        Args:
            words: HotWord 列表，含詞彙與加權分數。
        """
        self._hot_words = list(words)
        logger.debug("已設定 %d 個熱詞", len(words))

    def set_context(self, context_text: str) -> None:
        """設定語境文字，作為 initial_prompt 注入。

        Args:
            context_text: 語境提示文字。
        """
        self._context_text = context_text

    def get_supported_languages(self) -> list[str]:
        """回傳此引擎支援的語言代碼清單。"""
        return list(self.SUPPORTED_LANGUAGES)

    def unload(self) -> None:
        """卸載模型並釋放記憶體資源。"""
        self._model = None
        self._backend = None
        self._loaded = False
        logger.info("BreezeAsrEngine 已卸載")

    # ------------------------------------------------------------------
    # 延遲載入
    # ------------------------------------------------------------------

    def prepare(self, model_path: str, config: dict[str, Any] | None = None) -> None:
        """設定模型路徑，但不立即載入（延遲載入）。

        Args:
            model_path: 模型目錄路徑。
            config: 引擎設定（可選）。
        """
        self._model_path = model_path
        self._config = config or {}
        self._loaded = False
        logger.debug("BreezeAsrEngine 已設定模型路徑：%s（延遲載入）", model_path)

    # ------------------------------------------------------------------
    # 內部輔助方法
    # ------------------------------------------------------------------

    def _ensure_loaded(self) -> None:
        """若模型尚未載入則觸發延遲載入。"""
        if self._loaded:
            return
        if self._model_path is None:
            raise RuntimeError(
                "引擎未設定模型路徑。"
                "請先呼叫 prepare(model_path) 或 load_model(model_path, config)。"
            )
        self.load_model(self._model_path, self._config)

    def _load_backend(
        self, model_dir: Path, config: dict[str, Any]
    ) -> tuple[Any, str]:
        """嘗試載入 transformers（官方推薦），退回至 faster-whisper。

        Returns:
            (model, backend_name) 元組。

        Raises:
            ImportError: 兩套件均未安裝。
        """
        # 嘗試 transformers（官方推薦，WhisperForConditionalGeneration）
        try:
            from transformers import (  # type: ignore  # noqa: PLC0415
                AutomaticSpeechRecognitionPipeline,
                WhisperForConditionalGeneration,
                WhisperProcessor,
            )
            import torch  # noqa: PLC0415

            device = "cpu"
            torch_dtype = torch.float32
            if torch.cuda.is_available():
                device = "cuda"
                torch_dtype = torch.float16
                logger.debug("偵測到 CUDA，使用 GPU 推理")

            processor = WhisperProcessor.from_pretrained(str(model_dir))
            model = WhisperForConditionalGeneration.from_pretrained(
                str(model_dir), torch_dtype=torch_dtype,
            ).to(device).eval()

            pipe = AutomaticSpeechRecognitionPipeline(
                model=model,
                tokenizer=processor.tokenizer,
                feature_extractor=processor.feature_extractor,
                chunk_length_s=0,
                device=device,
                torch_dtype=torch_dtype,
            )
            logger.debug("使用 transformers 載入 Breeze-ASR-25（裝置：%s）", device)
            return pipe, "transformers"
        except ImportError:
            logger.debug("transformers 或 torch 未安裝，嘗試 faster-whisper")

        # 退回至 faster-whisper（CTranslate2）
        try:
            from faster_whisper import WhisperModel  # type: ignore  # noqa: PLC0415
            device = config.get("device", "auto")
            compute_type = config.get("compute_type", _DEFAULT_COMPUTE_TYPE)
            model = WhisperModel(
                str(model_dir),
                device=device,
                compute_type=compute_type,
            )
            logger.debug("使用 faster-whisper 載入 Breeze-ASR-25（裝置：%s）", device)
            return model, "faster-whisper"
        except ImportError as exc:
            raise ImportError(
                "無可用的 Breeze-ASR-25 後端。請安裝 transformers + torch 或 faster-whisper：\n"
                "  pip install transformers torch\n"
                "  或 pip install faster-whisper"
            ) from exc

    def _run_inference(self, audio: np.ndarray) -> tuple[str, float]:
        """依後端分派推理，回傳 (辨識文字, 信心分數)。"""
        if self._backend == "faster-whisper":
            return self._run_faster_whisper(audio)
        return self._run_transformers(audio)

    def _run_faster_whisper(self, audio: np.ndarray) -> tuple[str, float]:
        """使用 faster-whisper 推理，回傳 (text, confidence)。

        initial_prompt 注入語境文字與熱詞以偏移辨識結果。
        """
        initial_prompt = self._build_initial_prompt()
        transcribe_kwargs: dict[str, Any] = {
            "language": _DEFAULT_LANGUAGE,
            "beam_size": self._config.get("beam_size", _DEFAULT_BEAM_SIZE),
        }
        if initial_prompt:
            transcribe_kwargs["initial_prompt"] = initial_prompt

        segments, _info = self._model.transcribe(audio, **transcribe_kwargs)

        parts: list[str] = []
        for segment in segments:
            parts.append(segment.text)

        text = "".join(parts).strip()
        # faster-whisper 不直接提供整體信心分數；使用保守預設值
        return text, 0.85

    def _run_transformers(self, audio: np.ndarray) -> tuple[str, float]:
        """使用 transformers pipeline 推理，回傳 (text, confidence)。

        AutomaticSpeechRecognitionPipeline 接受 dict(array, sampling_rate)
        或直接 np.ndarray（預設 16kHz）。
        """
        inputs: dict[str, Any] = {
            "raw": audio,
            "sampling_rate": 16000,
        }
        result = self._model(inputs, return_timestamps=True)
        if isinstance(result, dict):
            text = str(result.get("text", "")).strip()
        else:
            text = str(result).strip()
        return text, 0.85

    def _build_initial_prompt(self) -> str:
        """建構 initial_prompt（語境 + 熱詞）。"""
        parts: list[str] = []
        if self._context_text:
            parts.append(self._context_text.strip())
        if self._hot_words:
            hw_text = " ".join(hw.word for hw in self._hot_words)
            parts.append(hw_text)
        return " ".join(parts)

    def _detect_language(self, text: str) -> str:
        """依文字內容偵測語言代碼（CJK 比例 > 30% → zh-TW）。"""
        return detect_language_from_cjk_ratio(text)


# ------------------------------------------------------------------
# 引擎登錄（Task 1.3）
# ------------------------------------------------------------------


def register(registry: ASREngineRegistry) -> bool:
    """若 transformers 或 faster-whisper 可用，將 BreezeAsrEngine 登錄至 registry。

    本函式在模組被匯入時不自動執行，需由應用程式啟動時顯式呼叫。
    若兩套件均未安裝，靜默跳過登錄，不拋出錯誤。

    Args:
        registry: ASREngineRegistry 實例。

    Returns:
        True 若成功登錄，False 若兩套件均不可用。
    """
    # 檢查 transformers（官方推薦）
    try:
        import transformers  # noqa: F401, PLC0415
        registry.register_engine(BreezeAsrEngine.ENGINE_ID, BreezeAsrEngine)
        logger.info("已登錄 ASR 引擎：%s（後端：transformers）", BreezeAsrEngine.ENGINE_ID)
        return True
    except ImportError:
        pass

    # 退回至 faster-whisper
    try:
        import faster_whisper  # noqa: F401, PLC0415
        registry.register_engine(BreezeAsrEngine.ENGINE_ID, BreezeAsrEngine)
        logger.info("已登錄 ASR 引擎：%s（後端：faster-whisper）", BreezeAsrEngine.ENGINE_ID)
        return True
    except ImportError:
        pass

    logger.debug(
        "transformers 與 faster-whisper 均未安裝，跳過 '%s' 登錄",
        BreezeAsrEngine.ENGINE_ID,
    )
    return False
