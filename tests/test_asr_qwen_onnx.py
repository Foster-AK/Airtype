"""Qwen3-ASR ONNX Runtime 引擎單元測試。

使用 mock onnxruntime 的單元測試（載入、推理流程、延遲載入）。
整合測試（載入真實 ONNX 模型，模型不可用時跳過）。

模型結構（社群 andrewleech/qwen3-asr-onnx 匯出）：
  - encoder.onnx / encoder.int8.onnx
  - embed_tokens.bin + config.json
  - decoder_init.onnx / decoder_init.int8.onnx
  - decoder_step.onnx / decoder_step.int8.onnx
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest


# ── 模型目錄路徑（整合測試用）────────────────────────────────────────────────

_ONNX_MODEL_DIR = Path("models/asr/qwen3_asr_onnx_int8")
_HAS_REAL_MODEL = _ONNX_MODEL_DIR.exists() and any(_ONNX_MODEL_DIR.glob("*.onnx"))

# ── 常數 ──────────────────────────────────────────────────────────────────────

_VOCAB_SIZE = 152000  # 需大於 EOS token ID 151645
_HIDDEN_DIM = 512
_NUM_LAYERS = 2
_KV_HEADS = 4
_HEAD_DIM = 64


# ── Mock 工廠 ─────────────────────────────────────────────────────────────────


def _logits(winning_token: int) -> np.ndarray:
    """建立一個 logits 陣列，讓指定 token 獲勝。"""
    arr = np.zeros((1, 1, _VOCAB_SIZE), dtype=np.float32)
    arr[0, 0, winning_token] = 10.0
    return arr


def _make_mock_ort(*, decoder_tokens: int = 0) -> MagicMock:
    """建立完整的 mock onnxruntime 模組。

    Args:
        decoder_tokens: decoder 在輸出 EOS 前先生成的 token 數量。

    Returns:
        可注入 sys.modules["onnxruntime"] 的 MagicMock。
    """
    mock_ort = MagicMock()

    # ── encoder session ──
    # 輸出 audio_features [1, n_audio_tokens, hidden_dim]
    enc_output = np.random.rand(1, 10, _HIDDEN_DIM).astype(np.float32)
    mock_enc_session = MagicMock()
    mock_enc_session.run.return_value = [enc_output]

    # ── decoder_init session（prefill）──
    # 輸出：logits, present_keys, present_values
    eos_logits = _logits(151645)
    present_keys = np.zeros((_NUM_LAYERS, 1, _KV_HEADS, 10, _HEAD_DIM), dtype=np.float32)
    present_values = np.zeros((_NUM_LAYERS, 1, _KV_HEADS, 10, _HEAD_DIM), dtype=np.float32)

    mock_dec_init_session = MagicMock()

    if decoder_tokens == 0:
        mock_dec_init_session.run.return_value = [eos_logits, present_keys, present_values]
    else:
        # prefill 回傳第一個非 EOS token
        init_logits = _logits(100)
        mock_dec_init_session.run.return_value = [init_logits, present_keys, present_values]

    # ── decoder_step session（自回歸）──
    mock_dec_step_session = MagicMock()

    if decoder_tokens > 0:
        _step_idx = [0]

        def _step_run(*args, **kwargs):
            idx = _step_idx[0]
            _step_idx[0] += 1
            pk = np.zeros((_NUM_LAYERS, 1, _KV_HEADS, 10 + idx + 1, _HEAD_DIM), dtype=np.float32)
            pv = np.zeros((_NUM_LAYERS, 1, _KV_HEADS, 10 + idx + 1, _HEAD_DIM), dtype=np.float32)
            if idx < decoder_tokens - 1:
                return [_logits(101 + idx), pk, pv]
            return [eos_logits, pk, pv]

        mock_dec_step_session.run.side_effect = _step_run
    else:
        mock_dec_step_session.run.return_value = [eos_logits, present_keys, present_values]

    # ── InferenceSession factory ──
    # load_model 按順序建立：encoder, decoder_init, decoder_step
    _session_idx = [0]
    sessions = [mock_enc_session, mock_dec_init_session, mock_dec_step_session]

    def _make_session(*args, **kwargs):
        idx = min(_session_idx[0], len(sessions) - 1)
        _session_idx[0] += 1
        return sessions[idx]

    mock_ort.InferenceSession.side_effect = _make_session
    mock_ort.get_available_providers.return_value = ["CPUExecutionProvider"]

    return mock_ort


def _create_embed_tokens_bin(model_dir: Path) -> None:
    """在模型目錄中建立 embed_tokens.bin 和 config.json。"""
    embed = np.random.rand(_VOCAB_SIZE, _HIDDEN_DIM).astype(np.float32)
    embed.tofile(str(model_dir / "embed_tokens.bin"))
    config = {"embed_tokens_shape": [_VOCAB_SIZE, _HIDDEN_DIM]}
    with (model_dir / "config.json").open("w") as f:
        json.dump(config, f)


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def engine():
    """建立未載入的 QwenOnnxEngine 實例。"""
    from airtype.core.asr_qwen_onnx import QwenOnnxEngine
    return QwenOnnxEngine()


@pytest.fixture
def model_dir(tmp_path):
    """建立含假 ONNX 檔案和 embed_tokens 的臨時模型目錄。"""
    for name in (
        "encoder.onnx",
        "decoder_init.onnx",
        "decoder_step.onnx",
    ):
        (tmp_path / name).write_bytes(b"<placeholder>")
    _create_embed_tokens_bin(tmp_path)
    return tmp_path


@pytest.fixture
def model_dir_int8(tmp_path):
    """建立含 INT8 變體 ONNX 檔案的臨時模型目錄。"""
    for name in (
        "encoder.int8.onnx",
        "decoder_init.int8.onnx",
        "decoder_step.int8.onnx",
    ):
        (tmp_path / name).write_bytes(b"<placeholder>")
    _create_embed_tokens_bin(tmp_path)
    return tmp_path


@pytest.fixture
def encoder_only_dir(tmp_path):
    """僅含 encoder ONNX 的目錄（無 decoder）。"""
    (tmp_path / "encoder.onnx").write_bytes(b"<placeholder>")
    return tmp_path


# ── Protocol 一致性 ──────────────────────────────────────────────────────────


class TestProtocolConformance:
    """QwenOnnxEngine 符合 ASREngine Protocol。"""

    def test_conforms_to_protocol(self, engine):
        from airtype.core.asr_engine import ASREngine
        assert isinstance(engine, ASREngine)


# ── 模型載入 ──────────────────────────────────────────────────────────────────


class TestModelLoading:
    """驗證 ONNX 模型載入需求。"""

    def test_initial_state_not_loaded(self, engine):
        assert not engine._loaded

    def test_load_missing_directory_raises_file_not_found(self, engine):
        with pytest.raises(FileNotFoundError, match="不存在"):
            engine.load_model("/nonexistent/model/path", {})

    def test_load_empty_directory_raises_file_not_found(self, engine, tmp_path):
        with pytest.raises(FileNotFoundError):
            engine.load_model(str(tmp_path), {})

    def test_load_model_sets_loaded_flag(self, engine, model_dir):
        mock_ort = _make_mock_ort()
        with patch.dict(sys.modules, {"onnxruntime": mock_ort}):
            with patch.object(type(engine), "_load_processor", return_value=MagicMock()):
                engine.load_model(str(model_dir), {})
        assert engine._loaded

    def test_load_model_creates_sessions(self, engine, model_dir):
        mock_ort = _make_mock_ort()
        with patch.dict(sys.modules, {"onnxruntime": mock_ort}):
            with patch.object(type(engine), "_load_processor", return_value=MagicMock()):
                engine.load_model(str(model_dir), {})
        assert engine._enc_session is not None
        assert engine._dec_init_session is not None
        assert engine._dec_step_session is not None

    def test_load_model_loads_embed_tokens(self, engine, model_dir):
        mock_ort = _make_mock_ort()
        with patch.dict(sys.modules, {"onnxruntime": mock_ort}):
            with patch.object(type(engine), "_load_processor", return_value=MagicMock()):
                engine.load_model(str(model_dir), {})
        assert engine._embed_tokens is not None
        assert engine._embed_tokens.shape == (_VOCAB_SIZE, _HIDDEN_DIM)

    def test_load_model_prefers_int8(self, engine, model_dir_int8):
        """INT8 變體優先於 FP32。"""
        mock_ort = _make_mock_ort()
        with patch.dict(sys.modules, {"onnxruntime": mock_ort}):
            with patch.object(type(engine), "_load_processor", return_value=MagicMock()):
                engine.load_model(str(model_dir_int8), {})
        assert engine._loaded

    def test_load_missing_embed_tokens_raises(self, engine, tmp_path):
        """缺少 embed_tokens.bin 應拋出 FileNotFoundError。"""
        for name in ("encoder.onnx", "decoder_init.onnx", "decoder_step.onnx"):
            (tmp_path / name).write_bytes(b"<placeholder>")
        with pytest.raises(FileNotFoundError, match="embed_tokens"):
            engine.load_model(str(tmp_path), {})


# ── 延遲載入 ──────────────────────────────────────────────────────────────────


class TestLazyLoading:
    """驗證延遲載入模型需求。"""

    def test_prepare_does_not_load_model(self, engine, model_dir):
        engine.prepare(str(model_dir))
        assert not engine._loaded

    def test_recognize_without_prepare_raises_runtime_error(self, engine):
        audio = np.zeros(16000, dtype=np.float32)
        with pytest.raises(RuntimeError, match="模型路徑"):
            engine.recognize(audio)


# ── 批次辨識 ──────────────────────────────────────────────────────────────────


class TestBatchRecognition:
    """驗證批次語音辨識需求。"""

    def _recognize_with_mock(self, engine, model_dir, audio):
        mock_ort = _make_mock_ort()
        with patch.dict(sys.modules, {"onnxruntime": mock_ort}):
            with patch.object(type(engine), "_load_processor") as mock_proc:
                proc = MagicMock()
                proc.feature_extractor.return_value = {
                    "input_features": np.zeros((1, 128, 100), dtype=np.float32)
                }
                proc.tokenizer.audio_token = "<|audio_pad|>"
                proc.tokenizer.encode.return_value = [1, 2, 3]
                proc.tokenizer.decode.return_value = "language Chinese<asr_text>你好"
                proc.apply_chat_template.return_value = "<|im_start|>system\n<|im_end|>\n<|im_start|>user\n<|audio_start|><|audio_pad|><|audio_end|><|im_end|>\n<|im_start|>assistant\n"
                mock_proc.return_value = proc
                engine.load_model(str(model_dir), {})
                return engine.recognize(audio)

    def test_recognize_returns_asr_result(self, engine, model_dir):
        from airtype.core.asr_engine import ASRResult
        audio = np.zeros(16000, dtype=np.float32)
        result = self._recognize_with_mock(engine, model_dir, audio)
        assert isinstance(result, ASRResult)

    def test_recognize_result_has_text(self, engine, model_dir):
        audio = np.zeros(16000, dtype=np.float32)
        result = self._recognize_with_mock(engine, model_dir, audio)
        assert isinstance(result.text, str)

    def test_recognize_result_confidence_in_range(self, engine, model_dir):
        audio = np.zeros(16000, dtype=np.float32)
        result = self._recognize_with_mock(engine, model_dir, audio)
        assert 0.0 <= result.confidence <= 1.0

    def test_recognize_result_has_segments(self, engine, model_dir):
        audio = np.zeros(16000 * 3, dtype=np.float32)
        result = self._recognize_with_mock(engine, model_dir, audio)
        assert len(result.segments) >= 1


# ── 上下文偏移 ──────────────────────────────────────────────────────────────


class TestContextBiasing:
    """驗證透過提示注入實現上下文偏移需求。"""

    def test_set_hot_words_stores_list(self, engine):
        from airtype.core.asr_engine import HotWord
        words = [HotWord(word="PostgreSQL", weight=8), HotWord(word="鼎新", weight=6)]
        engine.set_hot_words(words)
        assert engine._hot_words == words

    def test_set_context_stores_text(self, engine):
        engine.set_context("今天天氣很好")
        assert engine._context_text == "今天天氣很好"

    def test_hot_words_cleared_by_new_set(self, engine):
        from airtype.core.asr_engine import HotWord
        engine.set_hot_words([HotWord(word="A", weight=5)])
        engine.set_hot_words([HotWord(word="B", weight=3)])
        assert len(engine._hot_words) == 1
        assert engine._hot_words[0].word == "B"


# ── 卸載 ──────────────────────────────────────────────────────────────────────


class TestUnload:
    """驗證引擎卸載行為。"""

    def test_unload_clears_loaded_flag(self, engine, model_dir):
        mock_ort = _make_mock_ort()
        with patch.dict(sys.modules, {"onnxruntime": mock_ort}):
            with patch.object(type(engine), "_load_processor", return_value=MagicMock()):
                engine.load_model(str(model_dir), {})
        assert engine._loaded
        engine.unload()
        assert not engine._loaded

    def test_unload_clears_session_references(self, engine, model_dir):
        mock_ort = _make_mock_ort()
        with patch.dict(sys.modules, {"onnxruntime": mock_ort}):
            with patch.object(type(engine), "_load_processor", return_value=MagicMock()):
                engine.load_model(str(model_dir), {})
        engine.unload()
        assert engine._enc_session is None
        assert engine._dec_init_session is None
        assert engine._dec_step_session is None
        assert engine._embed_tokens is None


# ── 其他 Protocol 方法 ──────────────────────────────────────────────────────


class TestOtherProtocolMethods:
    """驗證其餘 ASREngine Protocol 方法。"""

    def test_recognize_stream_returns_partial_result(self, engine):
        from airtype.core.asr_engine import PartialResult
        chunk = np.zeros(1024, dtype=np.float32)
        result = engine.recognize_stream(chunk)
        assert isinstance(result, PartialResult)
        assert not result.is_final

    def test_get_supported_languages_returns_list(self, engine):
        langs = engine.get_supported_languages()
        assert isinstance(langs, list)
        assert all(isinstance(lang, str) for lang in langs)

    def test_get_supported_languages_includes_chinese(self, engine):
        langs = engine.get_supported_languages()
        assert any("zh" in lang for lang in langs)

    def test_get_supported_languages_returns_copy(self, engine):
        langs1 = engine.get_supported_languages()
        langs2 = engine.get_supported_languages()
        assert langs1 is not langs2


# ── 引擎登錄 ──────────────────────────────────────────────────────────────────


class TestEngineRegistration:
    """驗證引擎登錄需求：onnxruntime 可用時自動登錄為 'qwen3-onnx'。"""

    def test_register_succeeds_when_onnxruntime_available(self):
        from airtype.core.asr_engine import ASREngineRegistry
        from airtype.core.asr_qwen_onnx import register

        mock_ort = MagicMock()
        registry = ASREngineRegistry()
        with patch.dict(sys.modules, {"onnxruntime": mock_ort}):
            result = register(registry)
        assert result is True
        assert "qwen3-onnx" in registry.registered_ids

    def test_register_fails_when_onnxruntime_not_installed(self):
        from airtype.core.asr_engine import ASREngineRegistry
        from airtype.core.asr_qwen_onnx import register

        registry = ASREngineRegistry()
        with patch.dict(sys.modules, {"onnxruntime": None}):
            result = register(registry)
        assert result is False
        assert "qwen3-onnx" not in registry.registered_ids

    def test_engine_id_is_correct(self):
        from airtype.core.asr_qwen_onnx import QwenOnnxEngine
        assert QwenOnnxEngine.ENGINE_ID == "qwen3-onnx"


# ── 整合測試（模型不可用時跳過）──────────────────────────────────────────────


@pytest.mark.skipif(
    not _HAS_REAL_MODEL,
    reason="Qwen3-ASR ONNX 模型不可用（跳過整合測試）",
)
class TestIntegration:
    """整合測試 — 載入真實 ONNX 模型並辨識測試音訊。"""

    @pytest.fixture(scope="class")
    def loaded_engine(self):
        from airtype.core.asr_qwen_onnx import QwenOnnxEngine

        engine = QwenOnnxEngine()
        engine.load_model(str(_ONNX_MODEL_DIR))
        yield engine
        engine.unload()

    def test_recognize_silent_audio_returns_asr_result(self, loaded_engine):
        from airtype.core.asr_engine import ASRResult

        audio = np.zeros(16000 * 3, dtype=np.float32)
        result = loaded_engine.recognize(audio)
        assert isinstance(result, ASRResult)
        assert isinstance(result.text, str)
        assert 0.0 <= result.confidence <= 1.0

    def test_recognize_returns_valid_language_code(self, loaded_engine):
        audio = np.zeros(16000, dtype=np.float32)
        result = loaded_engine.recognize(audio)
        assert isinstance(result.language, str)
        assert len(result.language) >= 2

    def test_lazy_load_then_recognize(self):
        from airtype.core.asr_engine import ASRResult
        from airtype.core.asr_qwen_onnx import QwenOnnxEngine

        engine = QwenOnnxEngine()
        engine.prepare(str(_ONNX_MODEL_DIR))
        assert not engine._loaded

        audio = np.zeros(16000, dtype=np.float32)
        result = engine.recognize(audio)
        assert engine._loaded
        assert isinstance(result, ASRResult)
        engine.unload()
