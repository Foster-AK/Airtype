"""Qwen3-ASR 共用邏輯。

提供 Qwen3-ASR 引擎（OpenVINO / ONNX Runtime）共用的常數、
Processor 載入、Prompt 建構與輸出解析函式。
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Optional

import numpy as np

from airtype.core.asr_engine import HotWord

logger = logging.getLogger(__name__)

# Qwen3-ASR 特殊 token ID（從 tokenizer_config.json）
IM_END_ID = 151645
AUDIO_PAD_ID = 151676

# 解碼上限
MAX_DECODE_STEPS = 448

# 語言映射（Qwen3-ASR 官方語言名 → BCP-47）
LANG_TO_BCP47: dict[str, str] = {
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


# ---------------------------------------------------------------------------
# Processor 建構
# ---------------------------------------------------------------------------


def build_numpy_processor(model_dir: Path):
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

    # ── Mel 濾波器組（從 precomputed mel_filters.npy）──
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


def load_processor(model_dir: Path):
    """載入 Qwen3-ASR Processor（3 層 fallback）。

    優先順序：
    1. qwen_asr 套件 → Qwen3ASRProcessor
    2. transformers → AutoTokenizer + WhisperFeatureExtractor
    3. 純 numpy + tokenizers（PyInstaller 相容）
    """
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
        logger.warning("Fallback processor (transformers) 也載入失敗：%s，退回純 numpy processor", exc2)

    # fallback 3：純 numpy + tokenizers（不依賴 torch/transformers，PyInstaller 相容）
    try:
        return build_numpy_processor(model_dir)
    except Exception as exc3:
        logger.error("純 numpy processor 也載入失敗：%s", exc3)
        raise RuntimeError("無法載入任何 processor") from exc3


# ---------------------------------------------------------------------------
# Prompt 建構與輸出解析
# ---------------------------------------------------------------------------


def build_text_prompt(
    processor,
    hot_words: list[HotWord],
    context_text: str = "",
    force_language: Optional[str] = None,
) -> str:
    """建構 Qwen3-ASR chat prompt 文字。"""
    system_text = context_text or ""
    if hot_words:
        hw = " ".join(w.word for w in hot_words)
        if system_text:
            system_text += f"\nKeywords: {hw}"
        else:
            system_text = f"Keywords: {hw}"

    messages = [
        {"role": "system", "content": system_text},
        {"role": "user", "content": [{"type": "audio", "audio": ""}]},
    ]
    base = processor.apply_chat_template(
        messages, add_generation_prompt=True, tokenize=False,
    )
    if force_language:
        base = base + f"language {force_language}<asr_text>"
    return base


def parse_output(raw: str) -> tuple[str, str]:
    """解析 Qwen3-ASR 輸出，優先使用官方 parse_asr_output。

    Returns:
        (language, text) 元組。
    """
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


def detect_language_fallback(text: str) -> str:
    """簡易語言偵測 fallback。"""
    try:
        from airtype.core.asr_utils import detect_language_from_cjk_ratio
        return detect_language_from_cjk_ratio(text)
    except ImportError:
        return "zh-TW"
