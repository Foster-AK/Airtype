"""Qwen3-ASR PyTorch CUDA 引擎。

使用 PyTorch CUDA 以 bfloat16 精度在 NVIDIA GPU 上執行 Qwen3-ASR 批次語音辨識。
支援透過 qwen-asr 套件或 HuggingFace transformers 載入模型。
若 torch 或 CUDA 不可用，此引擎不會在登錄檔中登錄，也不產生匯入錯誤。

符合 PRD §6.3.2（Qwen3-ASR PyTorch CUDA 路徑）。
相依：06-asr-abstraction、07-numpy-preprocessor。
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
from airtype.core.processor_numpy import NumpyPreprocessor

logger = logging.getLogger(__name__)

_MAX_NEW_TOKENS: int = 448


class QwenPyTorchEngine:
    """Qwen3-ASR PyTorch CUDA bfloat16 引擎。

    實作 ASREngine Protocol，使用 PyTorch CUDA 以 bfloat16 精度推理。
    支援延遲載入；若 CUDA 不可用，此引擎不會在登錄檔中登錄。

    典型用法（延遲載入）::

        engine = QwenPyTorchEngine()
        engine.prepare("models/asr/qwen3_asr/")
        result = engine.recognize(audio)

    直接載入::

        engine = QwenPyTorchEngine()
        engine.load_model("models/asr/qwen3_asr/", {"device": "cuda"})
        result = engine.recognize(audio)
    """

    ENGINE_ID = "qwen3-pytorch-cuda"
    SUPPORTED_LANGUAGES = [
        "zh-TW", "zh-CN", "en", "ja", "ko", "fr", "de", "es", "it", "pt",
    ]

    def __init__(self) -> None:
        # 延遲載入狀態
        self._model_path: Optional[str] = None
        self._config: dict[str, Any] = {}
        self._loaded: bool = False

        # 模型與處理器（載入後設定）
        self._model = None
        self._processor = None
        self._device: str = "cuda"

        # 前處理器快取（無 processor 時退回 NumpyPreprocessor）
        self._preprocessor: Optional[NumpyPreprocessor] = None

        # 上下文偏移
        self._hot_words: list[HotWord] = []
        self._context_text: str = ""

    # ------------------------------------------------------------------
    # ASREngine Protocol 方法
    # ------------------------------------------------------------------

    def load_model(self, model_path: str, config: dict[str, Any] | None = None) -> None:
        """載入 PyTorch 模型至 GPU 記憶體（bfloat16）。

        Args:
            model_path: 模型目錄路徑（HuggingFace 格式）。
            config: 引擎設定，支援 "device"（預設 "cuda"）。

        Raises:
            FileNotFoundError: 模型目錄不存在。
            ImportError: torch 或後端套件未安裝。
            RuntimeError: CUDA 不可用。
        """
        model_dir = Path(model_path)
        if not model_dir.exists():
            raise FileNotFoundError(
                f"模型目錄不存在：{model_path}\n"
                "請執行：python scripts/download_models.py --model qwen3-asr"
            )

        import torch  # noqa: PLC0415

        if not torch.cuda.is_available():
            raise RuntimeError(
                "CUDA 不可用。QwenPyTorchEngine 需要 NVIDIA GPU 支援。"
                "請改用 qwen3-openvino 引擎（CPU 路徑）。"
            )

        config = config or {}
        self._device = config.get("device", "cuda")
        self._model, self._processor = self._load_model_and_processor(model_dir)
        self._model_path = model_path
        self._config = config
        self._loaded = True
        logger.info(
            "QwenPyTorchEngine 已就緒（裝置：%s，dtype：bfloat16）",
            self._device,
        )

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
        """PyTorch CUDA 批次路徑不支援串流辨識，回傳空部分結果。"""
        return PartialResult(text="", is_final=False)

    def set_hot_words(self, words: list[HotWord]) -> None:
        """設定熱詞列表，用於語境偏移。

        Args:
            words: HotWord 列表，含詞彙與加權分數。
        """
        self._hot_words = list(words)
        logger.debug("已設定 %d 個熱詞", len(words))

    def set_context(self, context_text: str) -> None:
        """設定語境文字，作為提示前綴。

        Args:
            context_text: 語境提示文字。
        """
        self._context_text = context_text

    def get_supported_languages(self) -> list[str]:
        """回傳此引擎支援的語言代碼清單。"""
        return list(self.SUPPORTED_LANGUAGES)

    def unload(self) -> None:
        """卸載模型並釋放 GPU 記憶體。"""
        self._model = None
        self._processor = None
        self._preprocessor = None
        self._loaded = False

        # 嘗試釋放 CUDA 快取
        try:
            import torch  # noqa: PLC0415
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except Exception:  # noqa: BLE001
            pass

        logger.info("QwenPyTorchEngine 已卸載")

    # ------------------------------------------------------------------
    # 延遲載入
    # ------------------------------------------------------------------

    def prepare(self, model_path: str, config: dict[str, Any] | None = None) -> None:
        """設定模型路徑，但不立即載入（延遲載入）。

        首次呼叫 recognize() 時才載入模型，以保持應用程式啟動速度。

        Args:
            model_path: 模型目錄路徑。
            config: 引擎設定（可選）。
        """
        self._model_path = model_path
        self._config = config or {}
        self._loaded = False
        logger.debug("QwenPyTorchEngine 已設定模型路徑：%s（延遲載入）", model_path)

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

    def _load_model_and_processor(self, model_dir: Path) -> tuple[Any, Any]:
        """載入模型與處理器。

        嘗試順序：
        1. qwen-asr 套件（若已安裝）
        2. HuggingFace transformers AutoModelForSpeechSeq2Seq

        Returns:
            (model, processor) 元組。

        Raises:
            ImportError: 無可用的模型載入後端。
        """
        import torch  # noqa: PLC0415
        dtype = torch.bfloat16

        # 嘗試 qwen-asr 套件
        try:
            import qwen_asr  # type: ignore  # noqa: PLC0415
            model = qwen_asr.load_model(str(model_dir), device=self._device, dtype=dtype)
            processor = qwen_asr.load_processor(str(model_dir))
            logger.debug("使用 qwen-asr 套件載入模型")
            return model, processor
        except ImportError:
            logger.debug("qwen-asr 套件未安裝，嘗試 transformers")

        # 退回至 transformers
        try:
            from transformers import AutoModelForSpeechSeq2Seq, AutoProcessor  # type: ignore  # noqa: PLC0415
            model = AutoModelForSpeechSeq2Seq.from_pretrained(
                str(model_dir),
                torch_dtype=dtype,
                low_cpu_mem_usage=True,
            ).to(self._device)
            model.eval()
            processor = AutoProcessor.from_pretrained(str(model_dir))
            logger.debug("使用 transformers 載入模型")
            return model, processor
        except ImportError as exc:
            raise ImportError(
                "無可用的模型載入後端。請安裝 qwen-asr 或 transformers：\n"
                "  pip install qwen-asr\n"
                "  或 pip install transformers"
            ) from exc

    def _run_inference(self, audio: np.ndarray) -> tuple[str, float]:
        """執行 CUDA bfloat16 推理，回傳 (辨識文字, 信心分數)。

        Args:
            audio: 16kHz mono PCM float32 numpy 陣列。

        Returns:
            (text, confidence) 元組。
        """
        import torch  # noqa: PLC0415

        if self._processor is not None:
            # 使用 processor 準備輸入特徵
            inputs = self._processor(
                audio,
                sampling_rate=16000,
                return_tensors="pt",
            )
            # 將浮點張量移至 GPU 並轉為 bfloat16
            processed: dict[str, Any] = {}
            for k, v in inputs.items():
                if hasattr(v, "dtype") and v.dtype.is_floating_point:
                    processed[k] = v.to(self._device, dtype=torch.bfloat16)
                elif hasattr(v, "to"):
                    processed[k] = v.to(self._device)
                else:
                    processed[k] = v

            generate_kwargs: dict[str, Any] = {"max_new_tokens": _MAX_NEW_TOKENS}
            prompt_ids = self._build_prompt_ids()
            if prompt_ids is not None:
                generate_kwargs["prompt_ids"] = prompt_ids

            with torch.inference_mode():
                output_ids = self._model.generate(**processed, **generate_kwargs)

            # 解碼輸出
            if hasattr(self._processor, "batch_decode"):
                decoded = self._processor.batch_decode(output_ids, skip_special_tokens=True)
                text = decoded[0].strip() if decoded else ""
            else:
                text = ""
        else:
            # 退回至 NumpyPreprocessor 提取 Mel 特徵
            mel_features = self._audio_to_features(audio)
            with torch.inference_mode():
                output_ids = self._model.generate(mel_features, max_new_tokens=_MAX_NEW_TOKENS)
            text = ""

        # PyTorch 路徑不直接提供 token 層級信心分數；使用保守預設值
        return text, 0.8

    def _audio_to_features(self, audio: np.ndarray) -> Any:
        """使用 NumpyPreprocessor 將音訊轉為 Mel 特徵並移至 GPU（bfloat16）。

        作為無 processor 時的退回方案。
        """
        import torch  # noqa: PLC0415
        if self._preprocessor is None:
            self._preprocessor = NumpyPreprocessor()
        mel = self._preprocessor.extract_mel_spectrogram(audio)  # (n_frames, 128)
        # mel (n_frames, 128) → (1, 128, n_frames)
        mel_tensor = torch.from_numpy(mel.T[np.newaxis, :, :]).to(
            self._device, dtype=torch.bfloat16
        )
        return mel_tensor

    def _build_prompt_text(self) -> str:
        """建構語境提示文字（熱詞 + 上下文）。

        Returns:
            合併的提示字串，無熱詞與語境時回傳空字串。
        """
        parts: list[str] = []
        if self._context_text:
            parts.append(self._context_text.strip())
        if self._hot_words:
            hw_text = " ".join(hw.word for hw in self._hot_words)
            parts.append(hw_text)
        return " ".join(parts)

    def _build_prompt_ids(self) -> Any:
        """將語境提示編碼為 token ID 張量，供 model.generate() 的 prompt_ids 參數使用。

        嘗試順序：
        1. processor.get_prompt_ids()（WhisperProcessor 標準介面）
        2. processor.tokenizer.encode()（通用 transformers tokenizer）
        3. 無法編碼時回傳 None（靜默退回，不中斷辨識）

        Returns:
            prompt_ids 張量，若無語境或編碼失敗則回傳 None。
        """
        prompt_text = self._build_prompt_text()
        if not prompt_text or self._processor is None:
            return None

        # 嘗試 WhisperProcessor 的 get_prompt_ids（最直接的介面）
        if hasattr(self._processor, "get_prompt_ids"):
            try:
                return self._processor.get_prompt_ids(prompt_text, return_tensors="pt")
            except Exception as exc:  # noqa: BLE001
                logger.debug("get_prompt_ids 失敗：%s", exc)

        # 退回至 tokenizer.encode
        tokenizer = getattr(self._processor, "tokenizer", None)
        if tokenizer is not None and hasattr(tokenizer, "encode"):
            try:
                import torch  # noqa: PLC0415
                ids = tokenizer.encode(prompt_text, return_tensors="pt")
                return ids
            except Exception as exc:  # noqa: BLE001
                logger.debug("tokenizer.encode 失敗：%s", exc)

        return None

    def _detect_language(self, text: str) -> str:
        """依文字內容偵測語言代碼（CJK 比例 > 30% → zh-TW）。"""
        return detect_language_from_cjk_ratio(text)


# ------------------------------------------------------------------
# 引擎登錄（Task 1.2 + Task 3.1）
# ------------------------------------------------------------------


def register(registry: ASREngineRegistry) -> bool:
    """若 torch 與 CUDA 可用，將 QwenPyTorchEngine 登錄至 registry。

    本函式在模組被匯入時不自動執行，需由應用程式啟動時顯式呼叫。
    若 torch 未安裝或 CUDA 不可用，靜默跳過登錄，不拋出錯誤。

    Args:
        registry: ASREngineRegistry 實例。

    Returns:
        True 若成功登錄，False 若 torch 或 CUDA 不可用。
    """
    try:
        import torch  # noqa: PLC0415
    except ImportError:
        logger.debug("torch 套件未安裝，跳過 '%s' 登錄", QwenPyTorchEngine.ENGINE_ID)
        return False

    if not torch.cuda.is_available():
        logger.debug("CUDA 不可用，跳過 '%s' 登錄", QwenPyTorchEngine.ENGINE_ID)
        return False

    registry.register_engine(QwenPyTorchEngine.ENGINE_ID, QwenPyTorchEngine)
    logger.info("已登錄 ASR 引擎：%s", QwenPyTorchEngine.ENGINE_ID)
    return True
