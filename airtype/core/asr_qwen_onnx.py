"""Qwen3-ASR ONNX Runtime 引擎（支援 Apple Silicon）。

使用 onnxruntime 載入 ONNX 量化模型（3-part 架構），
在 CPU 與 Apple Silicon CoreML 上執行批次語音辨識。

推理流程同 OpenVINO 引擎，但 KV cache 採手動管理：
  1. Processor 建構 chat prompt 並提取 Mel 頻譜
  2. audio_encoder 將 Mel → audio_hidden
  3. thinker_embeddings 將 token IDs → text_embeddings
  4. 替換 <|audio_pad|> 位置為 audio_hidden
  5. decoder 自回歸解碼（手動傳遞 past_key_values）
  6. parse_output 解析輸出
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
from airtype.core.asr_qwen_common import (
    AUDIO_PAD_ID,
    IM_END_ID,
    LANG_TO_BCP47,
    MAX_DECODE_STEPS,
    build_text_prompt,
    detect_language_fallback,
    load_processor,
    parse_output,
)

logger = logging.getLogger(__name__)


def _get_providers() -> list[str]:
    """取得可用的 ONNX Runtime Execution Providers（Apple Silicon 優先 CoreML）。"""
    import onnxruntime as ort

    available = set(ort.get_available_providers())
    providers: list[str] = []
    if "CoreMLExecutionProvider" in available:
        providers.append("CoreMLExecutionProvider")
    providers.append("CPUExecutionProvider")
    return providers


class QwenOnnxEngine:
    """Qwen3-ASR ONNX Runtime 引擎（3-part 架構，手動 KV cache）。

    典型用法::

        engine = QwenOnnxEngine()
        engine.prepare("~/.airtype/models/qwen3-asr-0.6b-onnx/")
        result = engine.recognize(audio)
    """

    ENGINE_ID = "qwen3-onnx"
    SUPPORTED_LANGUAGES = list(LANG_TO_BCP47.values())

    def __init__(self) -> None:
        self._model_path: Optional[str] = None
        self._config: dict[str, Any] = {}
        self._loaded: bool = False

        # ONNX Runtime Sessions
        self._enc_session = None   # audio_encoder
        self._emb_session = None   # thinker_embeddings
        self._dec_session = None   # decoder

        # Processor（tokenizer + feature_extractor）
        self._processor = None

        # KV cache I/O 名稱（從模型動態發現）
        self._kv_input_names: list[str] = []
        self._kv_output_names: list[str] = []

        # 上下文偏移
        self._hot_words: list[HotWord] = []
        self._context_text: str = ""

    # ------------------------------------------------------------------
    # ASREngine Protocol
    # ------------------------------------------------------------------

    def load_model(self, model_path: str, config: dict[str, Any] | None = None) -> None:
        """載入 3-part ONNX 模型與 Processor。"""
        model_dir = Path(model_path)
        if not model_dir.exists():
            raise FileNotFoundError(
                f"模型目錄不存在：{model_path}\n"
                "請至設定頁面下載 ONNX 模型。"
            )

        # 驗證必要檔案
        for fname in ("audio_encoder.onnx", "decoder_model.onnx"):
            if not (model_dir / fname).exists():
                raise FileNotFoundError(f"缺少必要模型檔案：{model_dir / fname}")

        import onnxruntime as ort

        config = config or {}
        providers = _get_providers()
        sess_opts = ort.SessionOptions()
        sess_opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL

        # 載入 3 個子模型
        logger.debug("載入 audio_encoder.onnx...")
        self._enc_session = ort.InferenceSession(
            str(model_dir / "audio_encoder.onnx"),
            sess_options=sess_opts,
            providers=providers,
        )

        emb_path = model_dir / "thinker_embeddings.onnx"
        if emb_path.exists():
            logger.debug("載入 thinker_embeddings.onnx...")
            self._emb_session = ort.InferenceSession(
                str(emb_path),
                sess_options=sess_opts,
                providers=providers,
            )

        logger.debug("載入 decoder_model.onnx...")
        self._dec_session = ort.InferenceSession(
            str(model_dir / "decoder_model.onnx"),
            sess_options=sess_opts,
            providers=providers,
        )

        # 動態發現 KV cache I/O 名稱
        self._discover_kv_cache_names()

        # 載入 Processor
        self._processor = load_processor(model_dir)

        self._model_path = model_path
        self._config = config
        self._loaded = True
        logger.info("QwenOnnxEngine 已就緒（providers：%s）", providers)

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
        return False

    def set_hot_words(self, words: list[HotWord]) -> None:
        self._hot_words = list(words)

    def set_context(self, context_text: str) -> None:
        self._context_text = context_text

    def get_supported_languages(self) -> list[str]:
        return list(self.SUPPORTED_LANGUAGES)

    def unload(self) -> None:
        self._enc_session = None
        self._emb_session = None
        self._dec_session = None
        self._processor = None
        self._kv_input_names = []
        self._kv_output_names = []
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

    def _discover_kv_cache_names(self) -> None:
        """從 decoder session 動態發現 KV cache 的 input/output 名稱。"""
        if self._dec_session is None:
            return

        self._kv_input_names = [
            inp.name for inp in self._dec_session.get_inputs()
            if inp.name.startswith("past_key_values")
        ]
        self._kv_output_names = [
            out.name for out in self._dec_session.get_outputs()
            if out.name.startswith("present")
        ]
        logger.debug(
            "KV cache I/O：%d inputs, %d outputs",
            len(self._kv_input_names), len(self._kv_output_names),
        )

    def _run_inference(self, audio: np.ndarray) -> tuple[str, str, float]:
        """完整推理管線。

        Returns:
            (text, bcp47_language, confidence) 元組。
        """
        audio = np.asarray(audio, dtype=np.float32)
        if audio.ndim > 1:
            audio = audio.mean(axis=-1)

        # 1. 提取 Mel 特徵
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

        enc_input_name = self._enc_session.get_inputs()[0].name
        enc_output_name = self._enc_session.get_outputs()[0].name
        audio_hidden = self._enc_session.run(
            [enc_output_name], {enc_input_name: mel_batch},
        )[0]
        n_audio_tokens = audio_hidden.shape[1]
        logger.debug("Audio encoder: shape=%s", audio_hidden.shape)

        # 3. 建構 prompt 並取得 input_ids
        prompt_text = build_text_prompt(
            self._processor, self._hot_words, self._context_text,
        )
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
        if self._emb_session is None:
            raise RuntimeError("thinker_embeddings 模型未載入")
        ids_np = np.array([input_ids], dtype=np.int64)
        emb_input_name = self._emb_session.get_inputs()[0].name
        emb_output_name = self._emb_session.get_outputs()[0].name
        text_embeddings = self._emb_session.run(
            [emb_output_name], {emb_input_name: ids_np},
        )[0]

        # 5. 替換 <|audio_pad|> 位置為 audio_hidden
        combined = text_embeddings.copy()
        audio_pad_positions = [i for i, tid in enumerate(input_ids) if tid == AUDIO_PAD_ID]

        if len(audio_pad_positions) == n_audio_tokens:
            for idx, pos in enumerate(audio_pad_positions):
                combined[0, pos, :] = audio_hidden[0, idx, :]
        else:
            logger.warning(
                "audio_pad 數量 (%d) 與 audio_hidden (%d) 不符",
                len(audio_pad_positions), n_audio_tokens,
            )

        # 6. Greedy decode（手動 KV cache）
        generated_ids, confidence = self._greedy_decode(combined)

        # 7. 解碼並解析
        raw_text = self._processor.tokenizer.decode(
            generated_ids, skip_special_tokens=False,
        )
        language, text = parse_output(raw_text)

        bcp47 = LANG_TO_BCP47.get(language, "")
        if not bcp47 and text:
            bcp47 = detect_language_fallback(text)

        return text, bcp47, confidence

    def _greedy_decode(
        self,
        initial_embeddings: np.ndarray,
    ) -> tuple[list[int], float]:
        """Greedy decoding（手動 KV cache 管理）。

        流程：
        1. Prefill：一次送入所有嵌入，past_key_values 為空
        2. Decode：每步只送一個新 token 嵌入，傳遞累積的 KV cache
        """
        seq_len = initial_embeddings.shape[1]
        generated: list[int] = []
        log_probs: list[float] = []

        # Prefill
        position_ids = np.arange(seq_len, dtype=np.int64).reshape(1, -1)
        feeds: dict[str, np.ndarray] = {
            "input_embeds": initial_embeddings,
            "position_ids": position_ids,
        }

        # 為 KV cache inputs 提供空張量（prefill 階段無歷史 KV）
        if self._kv_input_names:
            kv_cache = self._make_empty_kv_cache()
            feeds.update(kv_cache)

        output_names = [out.name for out in self._dec_session.get_outputs()]
        outputs = self._dec_session.run(output_names, feeds)
        output_dict = dict(zip(output_names, outputs))

        logits = output_dict["logits"]
        last_logits = (
            logits[0, -1, :].astype(np.float64)
            if logits.ndim == 3 else logits.flatten().astype(np.float64)
        )
        next_token = int(np.argmax(last_logits))
        current_pos = seq_len

        # 收集 present KV（給下一步用）
        past_kv = self._extract_present_kv(output_dict)

        # Autoregressive decode
        for _ in range(MAX_DECODE_STEPS):
            if next_token == IM_END_ID:
                break

            generated.append(next_token)

            # 信心分數
            shifted = last_logits - np.max(last_logits)
            log_prob = float(shifted[next_token] - np.log(np.sum(np.exp(shifted))))
            log_probs.append(log_prob)

            # 新 token 嵌入
            new_token_np = np.array([[next_token]], dtype=np.int64)
            emb_input_name = self._emb_session.get_inputs()[0].name
            emb_output_name = self._emb_session.get_outputs()[0].name
            new_emb = self._emb_session.run(
                [emb_output_name], {emb_input_name: new_token_np},
            )[0]

            # 單步 decode（傳遞 KV cache）
            pos_ids = np.array([[current_pos]], dtype=np.int64)
            feeds = {
                "input_embeds": new_emb,
                "position_ids": pos_ids,
            }
            if past_kv:
                feeds.update(past_kv)

            outputs = self._dec_session.run(output_names, feeds)
            output_dict = dict(zip(output_names, outputs))

            logits = output_dict["logits"]
            current_pos += 1

            last_logits = (
                logits[0, -1, :].astype(np.float64)
                if logits.ndim == 3 else logits.flatten().astype(np.float64)
            )
            next_token = int(np.argmax(last_logits))

            # 更新 KV cache
            past_kv = self._extract_present_kv(output_dict)

        confidence = (
            float(np.clip(np.exp(np.mean(log_probs)), 0.0, 1.0))
            if log_probs else 0.0
        )
        return generated, confidence

    def _make_empty_kv_cache(self) -> dict[str, np.ndarray]:
        """建構空的 KV cache 張量（prefill 階段使用）。

        透過 decoder session 的 input metadata 取得維度資訊，
        建構 past_seq_len=0 的空張量。
        """
        cache: dict[str, np.ndarray] = {}
        for inp in self._dec_session.get_inputs():
            if not inp.name.startswith("past_key_values"):
                continue
            shape = inp.shape  # e.g. ['batch', 'num_heads', 'past_seq_len', 'head_dim']
            # 替換動態維度為具體值
            concrete_shape = []
            for dim in shape:
                if isinstance(dim, int):
                    concrete_shape.append(dim)
                elif dim in ("batch", "batch_size"):
                    concrete_shape.append(1)
                elif "seq" in str(dim) or "past" in str(dim):
                    concrete_shape.append(0)  # 空序列
                else:
                    concrete_shape.append(1)
            # 判斷 dtype
            dtype = np.float32
            if inp.type and "float16" in inp.type:
                dtype = np.float16
            cache[inp.name] = np.zeros(concrete_shape, dtype=dtype)
        return cache

    def _extract_present_kv(self, output_dict: dict[str, np.ndarray]) -> dict[str, np.ndarray]:
        """從 decoder 輸出中提取 present KV，轉為下一步的 past_key_values 輸入。"""
        past_kv: dict[str, np.ndarray] = {}
        # present.{i}.key → past_key_values.{i}.key
        for out_name in self._kv_output_names:
            in_name = out_name.replace("present", "past_key_values", 1)
            if in_name in [n for n in self._kv_input_names]:
                past_kv[in_name] = output_dict[out_name]
        return past_kv


# ------------------------------------------------------------------
# 引擎登錄
# ------------------------------------------------------------------


def register(registry: ASREngineRegistry) -> bool:
    """若 onnxruntime 可用，將 QwenOnnxEngine 登錄至 registry。"""
    try:
        import onnxruntime as ort  # noqa: F401
    except ImportError:
        logger.debug("onnxruntime 套件未安裝，跳過 '%s' 登錄", QwenOnnxEngine.ENGINE_ID)
        return False

    registry.register_engine(QwenOnnxEngine.ENGINE_ID, QwenOnnxEngine)
    logger.info("已登錄 ASR 引擎：%s", QwenOnnxEngine.ENGINE_ID)
    return True
