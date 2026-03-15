"""Qwen3-ASR ONNX Runtime 引擎。

使用 onnxruntime.InferenceSession 載入社群 ONNX 模型（4-part 架構），
在 CPU 上執行批次語音辨識，全平台通用（Windows、macOS、Linux）。

模型結構（對齊 andrewleech/qwen3-asr-onnx 社群匯出）：
  - encoder.onnx / encoder.int8.onnx — 輸入 mel [1,128,T]，輸出 audio_features
  - embed_tokens.bin — 純 numpy 嵌入矩陣 [vocab_size, hidden_dim]
  - decoder_init.onnx / decoder_init.int8.onnx — prefill，輸出 logits + present KV
  - decoder_step.onnx / decoder_step.int8.onnx — 自回歸步驟，接收 past KV

推理流程：
  1. Processor 建構 chat prompt 並提取 Mel 頻譜
  2. encoder 將 Mel → audio_features
  3. embed_tokens numpy 查表取得 text_embeddings
  4. 替換 <|audio_pad|> 位置為 audio_features
  5. decoder_init prefill → logits + present KV
  6. decoder_step 自回歸解碼（顯式 KV cache I/O）
  7. parse_asr_output 解析輸出

參考：https://huggingface.co/andrewleech/qwen3-asr-0.6b-onnx
符合 PRD §6.3.2（Qwen3-ASR 整合）。
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

# Qwen3-ASR 特殊 token ID（從 tokenizer_config.json / prompt.py）
_ENDOFTEXT_ID = 151643
_IM_END_ID = 151645
_AUDIO_START_ID = 151669
_AUDIO_END_ID = 151670
_AUDIO_PAD_ID = 151676
_ASR_TEXT_ID = 151704
_EOS_IDS = frozenset({_ENDOFTEXT_ID, _IM_END_ID})

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


def _build_numpy_processor(model_dir: Path):
    """建構不依賴 torch/transformers 的純 numpy processor（PyInstaller 相容）。

    使用 tokenizers（Rust BPE）做分詞，numpy 做 Whisper 相容 Mel 頻譜提取。
    """
    import json as _json

    from tokenizers import Tokenizer as _HFTokenizer
    from tokenizers import models as _tok_models

    # ── Tokenizer ────────────────────────────────────────────────────────
    vocab_path = model_dir / "vocab.json"
    merges_path = model_dir / "merges.txt"
    if not vocab_path.exists() or not merges_path.exists():
        raise FileNotFoundError(f"缺少 vocab.json 或 merges.txt：{model_dir}")

    raw_tok = _HFTokenizer(_tok_models.BPE.from_file(str(vocab_path), str(merges_path)))

    # 設定 byte-level pre-tokenizer 和 decoder（與 transformers GPT2 tokenizer 一致）
    from tokenizers import pre_tokenizers as _pre_tok, decoders as _decoders
    raw_tok.pre_tokenizer = _pre_tok.ByteLevel(add_prefix_space=False)
    raw_tok.decoder = _decoders.ByteLevel()

    # 從 tokenizer_config.json 載入 added_tokens（特殊 token）
    tc_path = model_dir / "tokenizer_config.json"
    if tc_path.exists():
        with tc_path.open("r", encoding="utf-8") as f:
            tc = _json.load(f)
        added_tokens = tc.get("added_tokens_decoder", {})
        from tokenizers import AddedToken as _AddedToken
        for _tid_str, info in sorted(added_tokens.items(), key=lambda x: int(x[0])):
            raw_tok.add_special_tokens([_AddedToken(
                content=info["content"],
                single_word=info.get("single_word", False),
                lstrip=info.get("lstrip", False),
                rstrip=info.get("rstrip", False),
                normalized=info.get("normalized", False),
                special=info.get("special", True),
            )])

    # ── Mel 濾波器組（從 NumpyPreprocessor 共用的 precomputed mel_filters.npy）──
    from airtype.utils.paths import get_bundled_root
    mel_path = get_bundled_root() / "models" / "precomputed" / "mel_filters.npy"
    if not mel_path.exists():
        raise FileNotFoundError(f"mel_filters.npy not found: {mel_path}")
    mel_filters = np.load(mel_path)  # (n_mels, n_fft//2+1)

    # Whisper 參數
    _n_fft = 400
    _hop = 160
    _n = np.arange(_n_fft, dtype=np.float32)
    _window = (0.5 * (1.0 - np.cos(2.0 * np.pi * _n / _n_fft))).astype(np.float32)

    # ── chat_template ────────────────────────────────────────────────────
    chat_tmpl = None
    ct_path = model_dir / "chat_template.json"
    if ct_path.exists():
        with ct_path.open("r", encoding="utf-8") as f:
            chat_tmpl = _json.load(f).get("chat_template")

    class _NumpyFeatureExtractor:
        """WhisperFeatureExtractor 相容的純 numpy Mel 頻譜提取器。"""

        def __call__(self, audio, sampling_rate=16000, return_tensors="np", padding="do_not_pad"):
            waveform = np.asarray(audio, dtype=np.float32)
            if waveform.ndim == 1:
                waveform = waveform[np.newaxis, :]

            log_spec_batch = []
            for wav in waveform:
                # 反射填充
                pad = _n_fft // 2
                wav_padded = np.pad(wav, (pad, pad), mode="reflect")

                # STFT → 功率頻譜
                num_frames = 1 + (len(wav_padded) - _n_fft) // _hop
                frames = np.lib.stride_tricks.as_strided(
                    wav_padded,
                    shape=(num_frames, _n_fft),
                    strides=(wav_padded.strides[0] * _hop, wav_padded.strides[0]),
                ).copy()
                frames *= _window
                fft_out = np.fft.rfft(frames, n=_n_fft)
                magnitudes = np.abs(fft_out) ** 2  # (num_frames, n_fft//2+1)

                # Mel 濾波
                mel_spec = mel_filters @ magnitudes.T  # (n_mels, num_frames)

                # log10 → Whisper 正規化
                log_mel = np.log10(np.maximum(mel_spec, 1e-10))
                log_mel = log_mel[:, :-1]  # 移除最後一幀（與 WhisperFeatureExtractor 一致）
                log_mel = np.maximum(log_mel, log_mel.max() - 8.0)
                log_mel = (log_mel + 4.0) / 4.0
                log_spec_batch.append(log_mel)

            return {"input_features": np.array(log_spec_batch, dtype=np.float32)}

    class _TokenizerWrapper:
        """包裝 tokenizers.Tokenizer，提供與 transformers tokenizer 相容的介面。"""

        def __init__(self, tok):
            self._tok = tok
            self.audio_token = "<|audio_pad|>"

        def encode(self, text, add_special_tokens=False):
            return self._tok.encode(text, add_special_tokens=add_special_tokens).ids

        def decode(self, ids, **kwargs):
            skip = kwargs.get("skip_special_tokens", False)
            return self._tok.decode(ids, skip_special_tokens=skip)

        def batch_decode(self, ids_batch, **kwargs):
            return [self.decode(ids, **kwargs) for ids in ids_batch]

    class _NumpyProcessor:
        """不依賴 torch/transformers 的 Qwen3-ASR processor。"""

        def __init__(self, tok_wrapper, fe, tmpl):
            self.tokenizer = tok_wrapper
            self.feature_extractor = fe
            self._chat_template = tmpl

        def apply_chat_template(self, messages, add_generation_prompt=False, tokenize=False):
            if self._chat_template:
                try:
                    from jinja2 import Template
                    tmpl = Template(self._chat_template)
                    return tmpl.render(
                        messages=messages,
                        add_generation_prompt=add_generation_prompt,
                    )
                except ImportError:
                    pass
            # 硬編碼 fallback（Qwen chat format）
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

        def decode(self, token_ids, **kwargs):
            return self.tokenizer.decode(token_ids, **kwargs)

        def batch_decode(self, token_ids, **kwargs):
            return self.tokenizer.batch_decode(token_ids, **kwargs)

    proc = _NumpyProcessor(
        _TokenizerWrapper(raw_tok),
        _NumpyFeatureExtractor(),
        chat_tmpl,
    )
    logger.info("已載入純 numpy processor（PyInstaller 相容模式）")
    return proc


class QwenOnnxEngine:
    """Qwen3-ASR ONNX Runtime 引擎（4-part 架構，顯式 KV cache）。

    使用社群 ONNX 匯出模型（andrewleech/qwen3-asr-onnx）做推理，全平台通用。
    模型包含 encoder.onnx、embed_tokens.bin、decoder_init.onnx、decoder_step.onnx。

    典型用法::

        engine = QwenOnnxEngine()
        engine.prepare("~/.airtype/models/qwen3-asr-0.6b-onnx-int8/")
        result = engine.recognize(audio)
    """

    ENGINE_ID = "qwen3-onnx"
    SUPPORTED_LANGUAGES = list(_LANG_TO_BCP47.values())

    def __init__(self) -> None:
        self._model_path: Optional[str] = None
        self._config: dict[str, Any] = {}
        self._loaded: bool = False

        # ONNX Runtime sessions
        self._enc_session = None   # encoder.onnx
        self._dec_init_session = None  # decoder_init.onnx（prefill）
        self._dec_step_session = None  # decoder_step.onnx（自回歸）

        # 嵌入矩陣（純 numpy，從 embed_tokens.bin 載入）
        self._embed_tokens: np.ndarray | None = None  # [vocab_size, hidden_dim]

        # Processor（tokenizer + feature_extractor）
        self._processor = None

        # 上下文偏移
        self._hot_words: list[HotWord] = []
        self._context_text: str = ""

    # ------------------------------------------------------------------
    # ASREngine Protocol
    # ------------------------------------------------------------------

    def load_model(self, model_path: str, config: dict[str, Any] | None = None) -> None:
        """載入 4-part ONNX 模型與 Processor。

        模型檔案結構（社群 andrewleech/qwen3-asr-onnx 匯出）：
          - encoder.onnx 或 encoder.int8.onnx
          - embed_tokens.bin + config.json（嵌入矩陣形狀）
          - decoder_init.onnx 或 decoder_init.int8.onnx
          - decoder_step.onnx 或 decoder_step.int8.onnx
        """
        import json as _json

        import onnxruntime as ort

        model_dir = Path(model_path)
        if not model_dir.exists():
            raise FileNotFoundError(
                f"模型目錄不存在：{model_path}\n"
                "請至設定頁面下載 ONNX 模型。"
            )

        # 偵測 INT8 或 FP32 變體
        def _find_onnx(base_name: str) -> Path:
            """優先載入 INT8 版本，fallback FP32。"""
            int8 = model_dir / f"{base_name}.int8.onnx"
            fp32 = model_dir / f"{base_name}.onnx"
            if int8.exists():
                return int8
            if fp32.exists():
                return fp32
            raise FileNotFoundError(
                f"缺少必要模型檔案：{fp32} 或 {int8}"
            )

        encoder_path = _find_onnx("encoder")
        dec_init_path = _find_onnx("decoder_init")
        dec_step_path = _find_onnx("decoder_step")

        # 驗證 embed_tokens.bin
        embed_bin_path = model_dir / "embed_tokens.bin"
        if not embed_bin_path.exists():
            raise FileNotFoundError(f"缺少嵌入矩陣檔案：{embed_bin_path}")

        config = config or {}

        # 選擇 Execution Provider（macOS 可用 CoreML 加速）
        providers = []
        available = ort.get_available_providers()
        if "CoreMLExecutionProvider" in available:
            providers.append("CoreMLExecutionProvider")
        providers.append("CPUExecutionProvider")

        # 載入 encoder
        logger.debug("載入 %s...", encoder_path.name)
        self._enc_session = ort.InferenceSession(
            str(encoder_path), providers=providers,
        )

        # 載入 embed_tokens（純 numpy 嵌入矩陣）
        config_path = model_dir / "config.json"
        if config_path.exists():
            with config_path.open("r", encoding="utf-8") as f:
                model_config = _json.load(f)
            embed_shape = model_config.get("embed_tokens_shape")
        else:
            embed_shape = None

        logger.debug("載入 embed_tokens.bin...")
        raw_embed = np.fromfile(str(embed_bin_path), dtype=np.float32)
        if embed_shape:
            self._embed_tokens = raw_embed.reshape(embed_shape)
        else:
            # fallback：假設 Qwen3-ASR 0.6B 的 vocab=151936, hidden=1024
            vocab_size = 151936
            hidden_dim = len(raw_embed) // vocab_size
            self._embed_tokens = raw_embed.reshape(vocab_size, hidden_dim)
        logger.debug("embed_tokens shape=%s", self._embed_tokens.shape)

        # 載入 decoder_init（prefill）
        logger.debug("載入 %s...", dec_init_path.name)
        self._dec_init_session = ort.InferenceSession(
            str(dec_init_path), providers=providers,
        )

        # 載入 decoder_step（自回歸）
        logger.debug("載入 %s...", dec_step_path.name)
        self._dec_step_session = ort.InferenceSession(
            str(dec_step_path), providers=providers,
        )

        # 載入 Processor
        self._processor = self._load_processor(model_dir)

        self._model_path = model_path
        self._config = config
        self._loaded = True
        logger.info(
            "QwenOnnxEngine 已就緒（providers=%s, embed=%s）",
            providers, self._embed_tokens.shape,
        )

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
        """ONNX 批次路徑不支援串流辨識。"""
        return PartialResult(text="", is_final=False)

    @property
    def supports_hot_words(self) -> bool:
        """Qwen3-ASR ONNX 不支援原生熱詞偏置。"""
        return False

    def set_hot_words(self, words: list[HotWord]) -> None:
        self._hot_words = list(words)

    def set_context(self, context_text: str) -> None:
        self._context_text = context_text

    def get_supported_languages(self) -> list[str]:
        return list(self.SUPPORTED_LANGUAGES)

    def unload(self) -> None:
        self._enc_session = None
        self._dec_init_session = None
        self._dec_step_session = None
        self._embed_tokens = None
        self._processor = None
        self._loaded = False
        logger.info("QwenOnnxEngine 已卸載")

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
        """載入 Qwen3ASRProcessor（tokenizer + feature_extractor）。"""
        try:
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
            logger.warning("Fallback processor (transformers) 也載入失敗：%s，退回純 numpy processor", exc2)

        # fallback 3：純 numpy + tokenizers（不依賴 torch/transformers，PyInstaller 相容）
        try:
            return _build_numpy_processor(model_dir)
        except Exception as exc3:
            logger.error("純 numpy processor 也載入失敗：%s", exc3)
            raise RuntimeError("無法載入任何 processor") from exc3

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
        [audio_features] = self._enc_session.run(
            ["audio_features"], {"mel": mel_batch},
        )
        n_audio_tokens = audio_features.shape[1]
        logger.debug("Audio encoder: shape=%s", audio_features.shape)

        # 3. 建構 prompt 並取得 input_ids
        prompt_text = self._build_text_prompt(self._context_text)
        audio_pad_str = self._processor.tokenizer.audio_token if hasattr(
            self._processor.tokenizer, "audio_token"
        ) else "<|audio_pad|>"
        expanded_prompt = prompt_text.replace(
            audio_pad_str,
            audio_pad_str * n_audio_tokens,
            1,
        )
        input_ids = self._processor.tokenizer.encode(expanded_prompt, add_special_tokens=False)

        # 4. embed_tokens 查表（純 numpy，不需 ONNX session）
        if self._embed_tokens is None:
            raise RuntimeError("embed_tokens 嵌入矩陣未載入")
        ids_np = np.array(input_ids, dtype=np.int64)
        text_embeddings = self._embed_tokens[ids_np]  # (seq_len, hidden_dim)
        text_embeddings = text_embeddings[np.newaxis, :, :]  # (1, seq_len, hidden_dim)

        # 5. 替換 <|audio_pad|> 位置為 audio_features
        combined = text_embeddings.copy()
        audio_pad_positions = [i for i, tid in enumerate(input_ids) if tid == _AUDIO_PAD_ID]

        if len(audio_pad_positions) == n_audio_tokens:
            for idx, pos in enumerate(audio_pad_positions):
                combined[0, pos, :] = audio_features[0, idx, :]
        else:
            logger.warning(
                "audio_pad 數量 (%d) 與 audio_features (%d) 不符",
                len(audio_pad_positions), n_audio_tokens,
            )

        # 6. Greedy decode
        generated_ids, confidence = self._greedy_decode(combined)

        # 7. 解碼並解析輸出
        raw_text = self._processor.tokenizer.decode(
            generated_ids, skip_special_tokens=False,
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
        """Greedy decoding（decoder_init + decoder_step，顯式 KV cache）。

        流程：
        1. decoder_init：送入所有嵌入做 prefill，取得 logits + present KV
        2. decoder_step：每步送一個新 token 嵌入 + past KV，取得 logits + present KV
        """
        seq_len = initial_embeddings.shape[1]
        generated: list[int] = []
        log_probs: list[float] = []

        # Prefill（decoder_init）
        position_ids = np.arange(seq_len, dtype=np.int64).reshape(1, -1)
        logits, present_keys, present_values = self._dec_init_session.run(
            ["logits", "present_keys", "present_values"],
            {
                "input_embeds": initial_embeddings.astype(np.float32),
                "position_ids": position_ids,
            },
        )

        last_logits = (
            logits[0, -1, :].astype(np.float64)
            if logits.ndim == 3 else logits.flatten().astype(np.float64)
        )
        next_token = int(np.argmax(last_logits))
        current_pos = seq_len

        # Autoregressive decode（decoder_step）
        for _ in range(_MAX_DECODE_STEPS):
            if next_token in _EOS_IDS:
                break

            generated.append(next_token)

            # 信心分數
            shifted = last_logits - np.max(last_logits)
            log_prob = float(shifted[next_token] - np.log(np.sum(np.exp(shifted))))
            log_probs.append(log_prob)

            # 新 token 嵌入（numpy 查表）
            token_embed = self._embed_tokens[next_token]  # (hidden_dim,)
            token_embed = token_embed[np.newaxis, np.newaxis, :]  # (1, 1, hidden_dim)

            # 單步 decode
            step_pos = np.array([[current_pos]], dtype=np.int64)
            logits, present_keys, present_values = self._dec_step_session.run(
                ["logits", "present_keys", "present_values"],
                {
                    "input_embeds": token_embed.astype(np.float32),
                    "position_ids": step_pos,
                    "past_keys": present_keys,
                    "past_values": present_values,
                },
            )
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
        except Exception:
            # PyInstaller frozen 環境可能拋出 KeyError 而非 ImportError
            pass

        # fallback 手動解析
        if not raw:
            return "", ""
        raw = raw.strip()
        tag = "<asr_text>"
        if tag in raw:
            meta, text = raw.split(tag, 1)
            # 清除殘留特殊 token（skip_special_tokens=False 時會出現）
            for st in ("<|im_end|>", "<|im_start|>", "<|endoftext|>"):
                text = text.replace(st, "")
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
        # 沒有 <asr_text> 標記時，嘗試移除 "language Xxx" 前綴
        import re
        m = re.match(r"language\s+\w+\s*(.*)", raw, re.DOTALL)
        if m:
            return "", m.group(1).strip()
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
    """若 onnxruntime 套件可用，將 QwenOnnxEngine 登錄至 registry。"""
    try:
        import onnxruntime as ort  # noqa: F401
    except ImportError:
        logger.debug("onnxruntime 套件未安裝，跳過 '%s' 登錄", QwenOnnxEngine.ENGINE_ID)
        return False

    registry.register_engine(QwenOnnxEngine.ENGINE_ID, QwenOnnxEngine)
    logger.info("已登錄 ASR 引擎：%s", QwenOnnxEngine.ENGINE_ID)
    return True
