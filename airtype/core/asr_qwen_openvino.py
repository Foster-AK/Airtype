"""Qwen3-ASR OpenVINO INT8 引擎。

使用 openvino.Core 載入 INT8 量化 OpenVINO IR 模型（3-part stateful 架構），
在 CPU 上執行批次語音辨識。

推理流程（對齊官方 qwen-asr 套件）：
  1. Qwen3ASRProcessor 建構 chat prompt 並提取 Mel 頻譜
  2. audio_encoder 將 Mel → audio_hidden
  3. thinker_embeddings 將 token IDs → text_embeddings
  4. 替換 <|audio_pad|> 位置為 audio_hidden
  5. stateful decoder 自回歸解碼（KV cache 內建）
  6. parse_asr_output 解析輸出

參考：https://github.com/QwenLM/Qwen3-ASR
符合 PRD §6.3.2（Qwen3-ASR 整合）、§6.3.5（OpenVINO INT8 路徑）。
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

logger = logging.getLogger(__name__)

# Qwen3-ASR 特殊 token ID（從 tokenizer_config.json）
_IM_END_ID = 151645
_AUDIO_PAD_ID = 151676

# 解碼上限
_MAX_DECODE_STEPS = 448

# 語言映射（Qwen3-ASR 官方語言名 → BCP-47）
_LANG_TO_BCP47: dict[str, str] = {
    "Chinese": "zh-TW",
    "English": "en",
    "Japanese": "ja",
    "Korean": "ko",
    "French": "fr",
    "German": "de",
    "Spanish": "es",
    "Italian": "it",
    "Portuguese": "pt",
    "Russian": "ru",
    "Arabic": "ar",
    "Cantonese": "zh-HK",
    "Thai": "th",
    "Vietnamese": "vi",
    "Indonesian": "id",
    "Turkish": "tr",
    "Hindi": "hi",
    "Malay": "ms",
    "Dutch": "nl",
    "Swedish": "sv",
    "Danish": "da",
    "Finnish": "fi",
    "Polish": "pl",
    "Czech": "cs",
    "Filipino": "fil",
    "Persian": "fa",
    "Greek": "el",
    "Romanian": "ro",
    "Hungarian": "hu",
    "Macedonian": "mk",
}


class QwenOpenVinoEngine:
    """Qwen3-ASR OpenVINO INT8 引擎（3-part stateful 架構）。

    使用官方 Qwen3ASRProcessor 做前後處理，OpenVINO 做推理。

    典型用法::

        engine = QwenOpenVinoEngine()
        engine.prepare("~/.airtype/models/qwen3-asr-0.6b-openvino-int8/")
        result = engine.recognize(audio)
    """

    ENGINE_ID = "qwen3-openvino"
    SUPPORTED_LANGUAGES = list(_LANG_TO_BCP47.values())

    def __init__(self) -> None:
        self._model_path: Optional[str] = None
        self._config: dict[str, Any] = {}
        self._loaded: bool = False

        # OpenVINO 編譯模型與推理請求
        self._audio_encoder = None
        self._thinker_embeddings = None
        self._decoder = None
        self._enc_request = None
        self._emb_request = None
        self._dec_request = None

        # 官方 Processor（tokenizer + feature_extractor）
        self._processor = None

        # 上下文偏移
        self._hot_words: list[HotWord] = []
        self._context_text: str = ""

    # ------------------------------------------------------------------
    # ASREngine Protocol
    # ------------------------------------------------------------------

    def load_model(self, model_path: str, config: dict[str, Any] | None = None) -> None:
        """載入 3-part OpenVINO IR 模型與官方 Processor。"""
        model_dir = Path(model_path)
        if not model_dir.exists():
            raise FileNotFoundError(
                f"模型目錄不存在：{model_path}\n"
                "請至設定頁面下載 OpenVINO 模型。"
            )

        # 驗證必要檔案
        for fname in ("audio_encoder_model.xml", "decoder_model.xml"):
            if not (model_dir / fname).exists():
                raise FileNotFoundError(f"缺少必要模型檔案：{model_dir / fname}")

        import openvino as ov

        config = config or {}
        device: str = config.get("device", "CPU")
        core = ov.Core()

        # 載入 3 個子模型
        logger.debug("載入 audio_encoder_model...")
        self._audio_encoder = core.compile_model(
            str(model_dir / "audio_encoder_model.xml"), device
        )
        self._enc_request = self._audio_encoder.create_infer_request()

        emb_xml = model_dir / "thinker_embeddings_model.xml"
        if emb_xml.exists():
            logger.debug("載入 thinker_embeddings_model...")
            self._thinker_embeddings = core.compile_model(str(emb_xml), device)
            self._emb_request = self._thinker_embeddings.create_infer_request()

        logger.debug("載入 decoder_model...")
        self._decoder = core.compile_model(
            str(model_dir / "decoder_model.xml"), device
        )
        self._dec_request = self._decoder.create_infer_request()

        # 載入官方 Qwen3ASRProcessor
        self._processor = self._load_processor(model_dir)

        self._model_path = model_path
        self._config = config
        self._loaded = True
        logger.info("QwenOpenVinoEngine 已就緒（裝置：%s）", device)

    def recognize(self, audio: np.ndarray) -> ASRResult:
        """批次辨識音訊。"""
        self._ensure_loaded()

        text, language, confidence = self._run_inference(audio)
        duration = float(len(audio)) / 16000.0

        return ASRResult(
            text=text,
            language=language,
            confidence=confidence,
            segments=[ASRSegment(text=text, start=0.0, end=duration)],
        )

    def recognize_stream(self, chunk: np.ndarray) -> PartialResult:
        """OpenVINO 批次路徑不支援串流辨識。"""
        return PartialResult(text="", is_final=False)

    def set_hot_words(self, words: list[HotWord]) -> None:
        self._hot_words = list(words)

    def set_context(self, context_text: str) -> None:
        self._context_text = context_text

    def get_supported_languages(self) -> list[str]:
        return list(self.SUPPORTED_LANGUAGES)

    def unload(self) -> None:
        self._enc_request = None
        self._emb_request = None
        self._dec_request = None
        self._audio_encoder = None
        self._thinker_embeddings = None
        self._decoder = None
        self._processor = None
        self._loaded = False
        logger.info("QwenOpenVinoEngine 已卸載")

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

    @staticmethod
    def _load_processor(model_dir: Path):
        """載入官方 Qwen3ASRProcessor（tokenizer + feature_extractor）。"""
        try:
            # 透過 qwen_asr 套件載入（會自動註冊 Qwen3ASRConfig）
            from qwen_asr.inference.qwen3_asr import Qwen3ASRProcessor  # noqa: F811
            from transformers import AutoProcessor
            proc = AutoProcessor.from_pretrained(
                str(model_dir), fix_mistral_regex=True
            )
            logger.debug("已載入 Qwen3ASRProcessor")
            return proc
        except Exception as exc:
            logger.warning("無法載入 Qwen3ASRProcessor：%s，退回手動 processor", exc)

        # fallback：分別載入 tokenizer + feature_extractor
        try:
            from transformers import AutoTokenizer, WhisperFeatureExtractor

            class _FallbackProcessor:
                """簡易 fallback processor，模擬官方 Qwen3ASRProcessor 介面。"""

                def __init__(self, tokenizer, feature_extractor, chat_template):
                    self.tokenizer = tokenizer
                    self.feature_extractor = feature_extractor
                    self._chat_template = chat_template

                def __call__(self, text=None, audio=None, **kwargs):
                    from transformers.feature_extraction_utils import BatchFeature
                    result = {}
                    if audio is not None:
                        audio_out = self.feature_extractor(
                            audio, sampling_rate=16000,
                            return_tensors="np", padding=True,
                        )
                        result["input_features"] = audio_out["input_features"]
                        result["feature_attention_mask"] = audio_out.get("attention_mask")
                    if text is not None:
                        if not isinstance(text, list):
                            text = [text]
                        tok_out = self.tokenizer(
                            text, return_tensors="np", padding=True,
                        )
                        result["input_ids"] = tok_out["input_ids"]
                        result["attention_mask"] = tok_out["attention_mask"]
                    return BatchFeature(data=result, tensor_type=kwargs.get("return_tensors"))

                def apply_chat_template(self, messages, add_generation_prompt=False, tokenize=False):
                    import json
                    if self._chat_template:
                        from jinja2 import Template
                        tmpl = Template(self._chat_template)
                        return tmpl.render(
                            messages=messages,
                            add_generation_prompt=add_generation_prompt,
                        )
                    # 硬編碼 fallback
                    parts = []
                    for m in messages:
                        role = m["role"]
                        content = m.get("content", "")
                        if isinstance(content, list):
                            text_parts = []
                            for c in content:
                                if isinstance(c, dict) and c.get("type") == "audio":
                                    text_parts.append("<|audio_start|><|audio_pad|><|audio_end|>")
                                elif isinstance(c, dict) and c.get("type") == "text":
                                    text_parts.append(c.get("text", ""))
                            content = "".join(text_parts)
                        parts.append(f"<|im_start|>{role}\n{content}<|im_end|>\n")
                    if add_generation_prompt:
                        parts.append("<|im_start|>assistant\n")
                    return "".join(parts)

                def batch_decode(self, token_ids, **kwargs):
                    return self.tokenizer.batch_decode(token_ids, **kwargs)

                def decode(self, token_ids, **kwargs):
                    return self.tokenizer.decode(token_ids, **kwargs)

            tok = AutoTokenizer.from_pretrained(str(model_dir), trust_remote_code=False)
            fe = WhisperFeatureExtractor.from_pretrained(str(model_dir))
            chat_tmpl = None
            ct_path = model_dir / "chat_template.json"
            if ct_path.exists():
                import json
                with ct_path.open("r", encoding="utf-8") as f:
                    chat_tmpl = json.load(f).get("chat_template")
            return _FallbackProcessor(tok, fe, chat_tmpl)
        except Exception as exc2:
            logger.error("Fallback processor 也載入失敗：%s", exc2)
            raise RuntimeError("無法載入任何 processor") from exc2

    def _build_text_prompt(self, context: str = "", force_language: Optional[str] = None) -> str:
        """建構 chat prompt 文字（對齊官方 _build_text_prompt）。"""
        system_text = context or ""
        if self._hot_words:
            hw = " ".join(w.word for w in self._hot_words)
            if system_text:
                system_text += f"\nKeywords: {hw}"
            else:
                system_text = f"Keywords: {hw}"

        messages = [
            {"role": "system", "content": system_text},
            {"role": "user", "content": [{"type": "audio", "audio": ""}]},
        ]
        base = self._processor.apply_chat_template(
            messages, add_generation_prompt=True, tokenize=False,
        )
        if force_language:
            base = base + f"language {force_language}<asr_text>"
        return base

    def _run_inference(self, audio: np.ndarray) -> tuple[str, str, float]:
        """完整推理管線。

        Returns:
            (text, bcp47_language, confidence) 元組。
        """
        audio = np.asarray(audio, dtype=np.float32)
        if audio.ndim > 1:
            audio = audio.mean(axis=-1)

        # 1. 提取 Mel 特徵（使用 processor 的 feature_extractor）
        fe = self._processor.feature_extractor
        mel_out = fe(
            audio, sampling_rate=16000,
            return_tensors="np", padding="do_not_pad",
        )
        mel_features = mel_out["input_features"][0]  # (n_mels, n_frames)

        # 2. Audio encoder（mel frames 需 pad 至 100 的倍數）
        n_frames = mel_features.shape[1]
        pad_to = 100
        remainder = n_frames % pad_to
        if remainder != 0:
            pad_len = pad_to - remainder
            mel_features = np.pad(
                mel_features, ((0, 0), (0, pad_len)), mode="constant",
            )
        mel_batch = mel_features[np.newaxis, :, :].astype(np.float32)
        self._enc_request.infer({"mel": mel_batch})
        audio_hidden = self._enc_request.get_output_tensor(0).data.copy()
        n_audio_tokens = audio_hidden.shape[1]
        logger.debug("Audio encoder: shape=%s", audio_hidden.shape)

        # 3. 建構 prompt 並取得 input_ids
        prompt_text = self._build_text_prompt(self._context_text)
        # 將 prompt 中的 <|audio_pad|> 擴展為正確數量
        audio_pad_str = self._processor.tokenizer.audio_token if hasattr(
            self._processor.tokenizer, "audio_token"
        ) else "<|audio_pad|>"
        expanded_prompt = prompt_text.replace(
            audio_pad_str,
            audio_pad_str * n_audio_tokens,
            1,
        )
        input_ids = self._processor.tokenizer.encode(expanded_prompt, add_special_tokens=False)

        # 4. Thinker embeddings
        if self._emb_request is None:
            raise RuntimeError("thinker_embeddings 模型未載入")
        ids_np = np.array([input_ids], dtype=np.int64)
        self._emb_request.infer({"input_ids": ids_np})
        text_embeddings = self._emb_request.get_output_tensor(0).data.copy()

        # 5. 替換 <|audio_pad|> 位置為 audio_hidden
        combined = text_embeddings.copy()
        audio_pad_positions = [i for i, tid in enumerate(input_ids) if tid == _AUDIO_PAD_ID]

        if len(audio_pad_positions) == n_audio_tokens:
            for idx, pos in enumerate(audio_pad_positions):
                combined[0, pos, :] = audio_hidden[0, idx, :]
        else:
            logger.warning(
                "audio_pad 數量 (%d) 與 audio_hidden (%d) 不符",
                len(audio_pad_positions), n_audio_tokens,
            )

        # 6. Greedy decode（stateful decoder）
        generated_ids, confidence = self._greedy_decode(combined)

        # 7. 解碼並用官方 parse_asr_output 解析
        raw_text = self._processor.tokenizer.decode(
            generated_ids, skip_special_tokens=True,
        )
        language, text = self._parse_output(raw_text)

        # 轉換語言名稱為 BCP-47
        bcp47 = _LANG_TO_BCP47.get(language, "")
        if not bcp47 and text:
            bcp47 = self._detect_language_fallback(text)

        return text, bcp47, confidence

    def _greedy_decode(
        self,
        initial_embeddings: np.ndarray,
    ) -> tuple[list[int], float]:
        """Greedy decoding（stateful decoder with internal KV cache）。

        流程：
        1. reset_state() 清空 KV cache
        2. Prefill：一次送入所有嵌入
        3. Decode：每步只送一個新 token 嵌入
        """
        self._dec_request.reset_state()

        seq_len = initial_embeddings.shape[1]
        generated: list[int] = []
        log_probs: list[float] = []

        # Prefill
        position_ids = np.arange(seq_len, dtype=np.int64).reshape(1, -1)
        self._dec_request.infer({
            "input_embeds": initial_embeddings,
            "position_ids": position_ids,
        })
        logits = self._dec_request.get_output_tensor(0).data.copy()

        last_logits = (
            logits[0, -1, :].astype(np.float64)
            if logits.ndim == 3 else logits.flatten().astype(np.float64)
        )
        next_token = int(np.argmax(last_logits))
        current_pos = seq_len

        # Autoregressive decode
        for _ in range(_MAX_DECODE_STEPS):
            if next_token == _IM_END_ID:
                break

            generated.append(next_token)

            # 信心分數
            shifted = last_logits - np.max(last_logits)
            log_prob = float(shifted[next_token] - np.log(np.sum(np.exp(shifted))))
            log_probs.append(log_prob)

            # 新 token 嵌入
            new_token_np = np.array([[next_token]], dtype=np.int64)
            self._emb_request.infer({"input_ids": new_token_np})
            new_emb = self._emb_request.get_output_tensor(0).data.copy()

            # 單步 decode（KV cache 自動累積）
            pos_ids = np.array([[current_pos]], dtype=np.int64)
            self._dec_request.infer({
                "input_embeds": new_emb,
                "position_ids": pos_ids,
            })
            logits = self._dec_request.get_output_tensor(0).data.copy()
            current_pos += 1

            last_logits = (
                logits[0, -1, :].astype(np.float64)
                if logits.ndim == 3 else logits.flatten().astype(np.float64)
            )
            next_token = int(np.argmax(last_logits))

        confidence = (
            float(np.clip(np.exp(np.mean(log_probs)), 0.0, 1.0))
            if log_probs else 0.0
        )
        return generated, confidence

    @staticmethod
    def _parse_output(raw: str) -> tuple[str, str]:
        """解析 Qwen3-ASR 輸出，優先使用官方 parse_asr_output。"""
        try:
            from qwen_asr.inference.utils import parse_asr_output
            return parse_asr_output(raw, user_language=None)
        except ImportError:
            pass

        # fallback 手動解析
        if not raw:
            return "", ""
        raw = raw.strip()
        tag = "<asr_text>"
        if tag in raw:
            meta, text = raw.split(tag, 1)
            text = text.strip()
            meta_lower = meta.lower()
            if "language none" in meta_lower:
                return "", ""
            lang = ""
            if meta_lower.startswith("language "):
                val = meta[len("language "):].strip()
                if val:
                    lang = val[0].upper() + val[1:].lower()
            return lang, text
        return "", raw

    @staticmethod
    def _detect_language_fallback(text: str) -> str:
        """簡易語言偵測 fallback。"""
        try:
            from airtype.core.asr_utils import detect_language_from_cjk_ratio
            return detect_language_from_cjk_ratio(text)
        except ImportError:
            return "zh-TW"


# ------------------------------------------------------------------
# 引擎登錄
# ------------------------------------------------------------------


def register(registry: ASREngineRegistry) -> bool:
    """若 openvino 套件可用，將 QwenOpenVinoEngine 登錄至 registry。"""
    try:
        import openvino as ov  # noqa: F401
    except ImportError:
        logger.debug("openvino 套件未安裝，跳過 '%s' 登錄", QwenOpenVinoEngine.ENGINE_ID)
        return False

    registry.register_engine(QwenOpenVinoEngine.ENGINE_ID, QwenOpenVinoEngine)
    logger.info("已登錄 ASR 引擎：%s", QwenOpenVinoEngine.ENGINE_ID)
    return True
