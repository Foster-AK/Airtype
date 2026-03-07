"""Qwen3-ASR OpenVINO INT8 引擎單元測試。

Task 3.1：使用 mock OpenVINO 的單元測試（載入、推理流程、延遲載入）。
Task 3.2：整合測試（載入真實 INT8 模型，模型不可用時跳過）。
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest


# ── 模型目錄路徑（整合測試用）────────────────────────────────────────────────

_INT8_MODEL_DIR = Path("models/asr/qwen3_asr_int8")
_HAS_REAL_MODEL = _INT8_MODEL_DIR.exists() and any(_INT8_MODEL_DIR.glob("*.xml"))


# ── Mock 工廠 ─────────────────────────────────────────────────────────────────


def _make_mock_ov(*, has_decoder: bool = True, decoder_tokens: int = 0) -> MagicMock:
    """建立完整的 mock openvino 模組，包含 encoder / decoder 模型。

    Args:
        has_decoder: 若為 True，compile_model side_effect 依序回傳 encoder 與 decoder；
                     若為 False，始終回傳 encoder mock。
        decoder_tokens: decoder 在輸出 EOS 前先生成的 token 數量（預設 0，立即 EOS）。
                        大於 0 時可用於驗證信心分數計算路徑。

    Returns:
        可注入 sys.modules["openvino"] 的 MagicMock。
    """
    mock_ov = MagicMock()

    # ── encoder ──
    enc_output_data = np.random.rand(1, 10, 512).astype(np.float32)
    mock_enc_tensor = MagicMock()
    mock_enc_tensor.data = enc_output_data
    mock_enc_request = MagicMock()
    mock_enc_request.get_output_tensor.return_value = mock_enc_tensor

    mock_enc_input = MagicMock()
    mock_enc_input.any_name = "input_features"
    mock_enc_model = MagicMock()
    mock_enc_model.input.return_value = mock_enc_input
    mock_enc_model.create_infer_request.return_value = mock_enc_request

    # ── decoder ──
    # 建立 decoder_tokens 個非 EOS token 的 logits，接著輸出 EOS
    def _logits(winning_token: int) -> np.ndarray:
        arr = np.zeros((1, 1, 1000), dtype=np.float32)
        arr[0, 0, winning_token] = 10.0
        return arr

    # 序列：[non-EOS token 100, 101, ...] 接 EOS(=2)
    tensor_sequence = []
    for i in range(decoder_tokens):
        t = MagicMock()
        t.data = _logits(100 + i)  # token IDs 100+ 都是普通 token
        tensor_sequence.append(t)
    eos_tensor = MagicMock()
    eos_tensor.data = _logits(2)  # EOS
    tensor_sequence.append(eos_tensor)

    mock_dec_request = MagicMock()
    if decoder_tokens == 0:
        # 快速路徑：固定回傳 EOS
        mock_dec_request.get_output_tensor.return_value = eos_tensor
    else:
        # 依序回傳 non-EOS，最後 EOS；超出序列後繼續回傳 EOS
        _call_idx = [0]

        def _get_tensor(*_args, **_kwargs):
            idx = min(_call_idx[0], len(tensor_sequence) - 1)
            _call_idx[0] += 1
            return tensor_sequence[idx]

        mock_dec_request.get_output_tensor.side_effect = _get_tensor

    mock_dec_input_ids = MagicMock()
    mock_dec_input_ids.any_name = "input_ids"
    mock_dec_enc_hidden = MagicMock()
    mock_dec_enc_hidden.any_name = "encoder_hidden_states"
    mock_dec_model = MagicMock()
    mock_dec_model.inputs = [mock_dec_input_ids, mock_dec_enc_hidden]
    mock_dec_model.create_infer_request.return_value = mock_dec_request

    # ── Core ──
    mock_core = MagicMock()
    if has_decoder:
        mock_core.compile_model.side_effect = [mock_enc_model, mock_dec_model]
    else:
        mock_core.compile_model.return_value = mock_enc_model

    mock_ov.Core.return_value = mock_core
    return mock_ov


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def engine():
    """建立未載入的 QwenOpenVinoEngine 實例。"""
    from airtype.core.asr_qwen_openvino import QwenOpenVinoEngine
    return QwenOpenVinoEngine()


@pytest.fixture
def model_dir(tmp_path):
    """建立含假 OpenVINO IR 檔案的臨時模型目錄（encoder + decoder）。"""
    for name in (
        "openvino_encoder_model.xml",
        "openvino_encoder_model.bin",
        "openvino_decoder_with_past_model.xml",
        "openvino_decoder_with_past_model.bin",
    ):
        (tmp_path / name).write_text("<placeholder>")
    return tmp_path


@pytest.fixture
def encoder_only_dir(tmp_path):
    """僅含 encoder XML 的目錄（無 decoder）。"""
    (tmp_path / "openvino_encoder_model.xml").write_text("<placeholder>")
    (tmp_path / "openvino_encoder_model.bin").write_text("<placeholder>")
    return tmp_path


# ── Task 3.1a ── ASREngine Protocol 一致性 ────────────────────────────────────


class TestProtocolConformance:
    """QwenOpenVinoEngine 符合 ASREngine Protocol。"""

    def test_conforms_to_protocol(self, engine):
        from airtype.core.asr_engine import ASREngine
        assert isinstance(engine, ASREngine)


# ── Task 3.1b ── 模型載入（OpenVINO INT8 Model Loading 需求）─────────────────


class TestModelLoading:
    """驗證 OpenVINO INT8 模型載入需求。"""

    def test_initial_state_not_loaded(self, engine):
        """初始狀態 _loaded 應為 False。"""
        assert not engine._loaded

    def test_load_missing_directory_raises_file_not_found(self, engine):
        """模型目錄不存在時應拋出含路徑說明的 FileNotFoundError。"""
        with pytest.raises(FileNotFoundError, match="不存在"):
            engine.load_model("/nonexistent/model/path", {})

    def test_load_empty_directory_raises_file_not_found(self, engine, tmp_path):
        """目錄存在但無 XML 模型時應拋出 FileNotFoundError。"""
        with pytest.raises(FileNotFoundError):
            engine.load_model(str(tmp_path), {})

    def test_load_model_sets_loaded_flag(self, engine, model_dir):
        """成功載入後 _loaded 應為 True。"""
        mock_ov = _make_mock_ov()
        with patch.dict(sys.modules, {"openvino": mock_ov}):
            engine.load_model(str(model_dir), {})
        assert engine._loaded

    def test_load_model_default_device_is_cpu(self, engine, model_dir):
        """未指定 device 時 compile_model 第二個引數應為 'CPU'。"""
        mock_ov = _make_mock_ov()
        with patch.dict(sys.modules, {"openvino": mock_ov}):
            engine.load_model(str(model_dir), {})
        first_call = mock_ov.Core.return_value.compile_model.call_args_list[0]
        assert first_call.args[1] == "CPU"

    def test_load_model_custom_device(self, engine, model_dir):
        """config['device'] 應傳遞至 compile_model。"""
        mock_ov = _make_mock_ov()
        with patch.dict(sys.modules, {"openvino": mock_ov}):
            engine.load_model(str(model_dir), {"device": "GPU"})
        first_call = mock_ov.Core.return_value.compile_model.call_args_list[0]
        assert first_call.args[1] == "GPU"

    def test_load_model_with_decoder(self, engine, model_dir):
        """有 decoder XML 時 _decoder 應不為 None。"""
        mock_ov = _make_mock_ov(has_decoder=True)
        with patch.dict(sys.modules, {"openvino": mock_ov}):
            engine.load_model(str(model_dir), {})
        assert engine._decoder is not None

    def test_load_model_encoder_only(self, engine, encoder_only_dir):
        """無 decoder XML 時 _decoder 應為 None，但仍正常載入。"""
        mock_ov = _make_mock_ov(has_decoder=False)
        with patch.dict(sys.modules, {"openvino": mock_ov}):
            engine.load_model(str(encoder_only_dir), {})
        assert engine._loaded
        assert engine._decoder is None


# ── Task 3.1c ── 延遲載入（Lazy Model Loading 需求）──────────────────────────


class TestLazyLoading:
    """驗證延遲載入模型需求。"""

    def test_prepare_does_not_load_model(self, engine, model_dir):
        """prepare() 後 _loaded 應仍為 False（尚未載入）。"""
        engine.prepare(str(model_dir))
        assert not engine._loaded

    def test_recognize_triggers_lazy_load(self, engine, model_dir):
        """首次呼叫 recognize() 應自動載入模型（_loaded 變 True）。"""
        mock_ov = _make_mock_ov()
        engine.prepare(str(model_dir))
        audio = np.zeros(16000, dtype=np.float32)
        with patch.dict(sys.modules, {"openvino": mock_ov}):
            with patch("airtype.core.asr_qwen_openvino.NumpyPreprocessor") as MockPrep:
                MockPrep.return_value.extract_mel_spectrogram.return_value = (
                    np.zeros((100, 128), dtype=np.float32)
                )
                engine.recognize(audio)
        assert engine._loaded

    def test_recognize_does_not_reload_on_second_call(self, engine, model_dir):
        """第二次 recognize() 不應重新建立 Core（即不重新載入模型）。"""
        mock_ov = _make_mock_ov()
        engine.prepare(str(model_dir))
        audio = np.zeros(16000, dtype=np.float32)
        with patch.dict(sys.modules, {"openvino": mock_ov}):
            with patch("airtype.core.asr_qwen_openvino.NumpyPreprocessor") as MockPrep:
                MockPrep.return_value.extract_mel_spectrogram.return_value = (
                    np.zeros((100, 128), dtype=np.float32)
                )
                engine.recognize(audio)
                core_calls_after_first = mock_ov.Core.call_count
                engine.recognize(audio)
        # 第二次不應再建立 Core
        assert mock_ov.Core.call_count == core_calls_after_first

    def test_recognize_without_prepare_raises_runtime_error(self, engine):
        """未呼叫 prepare() 或 load_model() 時 recognize() 應拋出 RuntimeError。"""
        audio = np.zeros(16000, dtype=np.float32)
        with pytest.raises(RuntimeError, match="模型路徑"):
            engine.recognize(audio)


# ── Task 3.1d ── 批次辨識（Batch Speech Recognition 需求）────────────────────


class TestBatchRecognition:
    """驗證批次語音辨識需求。"""

    def _recognize_with_mock(self, engine, model_dir, audio):
        mock_ov = _make_mock_ov()
        with patch.dict(sys.modules, {"openvino": mock_ov}):
            with patch("airtype.core.asr_qwen_openvino.NumpyPreprocessor") as MockPrep:
                MockPrep.return_value.extract_mel_spectrogram.return_value = (
                    np.zeros((100, 128), dtype=np.float32)
                )
                engine.load_model(str(model_dir), {})
                return engine.recognize(audio)

    def test_recognize_returns_asr_result(self, engine, model_dir):
        """recognize() 應回傳 ASRResult 實例。"""
        from airtype.core.asr_engine import ASRResult
        audio = np.zeros(16000, dtype=np.float32)
        result = self._recognize_with_mock(engine, model_dir, audio)
        assert isinstance(result, ASRResult)

    def test_recognize_result_has_text(self, engine, model_dir):
        """ASRResult.text 應為字串。"""
        audio = np.zeros(16000, dtype=np.float32)
        result = self._recognize_with_mock(engine, model_dir, audio)
        assert isinstance(result.text, str)

    def test_recognize_result_has_language(self, engine, model_dir):
        """ASRResult.language 應為非空字串。"""
        audio = np.zeros(16000, dtype=np.float32)
        result = self._recognize_with_mock(engine, model_dir, audio)
        assert isinstance(result.language, str)
        assert len(result.language) >= 2

    def test_recognize_result_confidence_in_range(self, engine, model_dir):
        """ASRResult.confidence 應在 0.0–1.0 範圍內。"""
        audio = np.zeros(16000, dtype=np.float32)
        result = self._recognize_with_mock(engine, model_dir, audio)
        assert 0.0 <= result.confidence <= 1.0

    def test_recognize_result_has_segments(self, engine, model_dir):
        """ASRResult.segments 應包含至少一個時間段。"""
        audio = np.zeros(16000 * 3, dtype=np.float32)
        result = self._recognize_with_mock(engine, model_dir, audio)
        assert len(result.segments) >= 1

    def test_recognize_segment_end_matches_duration(self, engine, model_dir):
        """時間段 end 應等於音訊長度（秒）。"""
        duration = 3.0
        audio = np.zeros(int(16000 * duration), dtype=np.float32)
        result = self._recognize_with_mock(engine, model_dir, audio)
        assert result.segments[0].end == pytest.approx(duration)

    def test_recognize_confidence_nonzero_when_decoder_generates_tokens(
        self, engine, model_dir
    ):
        """decoder 生成至少一個 token 時，信心分數應 > 0.0。

        這驗證 greedy_decode 中的 log-prob 累積與信心計算路徑確實有效。
        spec.md 要求 Mandarin 辨識信心 > 0.5 需真實模型才能完整驗證（整合測試），
        此處驗證計算路徑不會讓信心永遠為 0。
        """
        # decoder_tokens=2 → 生成 token 100, 101 後遇 EOS
        mock_ov = _make_mock_ov(decoder_tokens=2)
        audio = np.zeros(16000, dtype=np.float32)
        with patch.dict(sys.modules, {"openvino": mock_ov}):
            with patch("airtype.core.asr_qwen_openvino.NumpyPreprocessor") as MockPrep:
                MockPrep.return_value.extract_mel_spectrogram.return_value = (
                    np.zeros((100, 128), dtype=np.float32)
                )
                engine.load_model(str(model_dir), {})
                result = engine.recognize(audio)
        assert result.confidence > 0.0, (
            "生成 token 後信心分數應 > 0.0；"
            "若為 0.0 表示 log-prob 累積路徑未正確執行"
        )


# ── Task 3.1e ── 上下文偏移（Context Biasing 需求）──────────────────────────


class TestContextBiasing:
    """驗證透過提示注入實現上下文偏移需求。"""

    def test_set_hot_words_stores_list(self, engine):
        """set_hot_words() 應儲存熱詞列表。"""
        from airtype.core.asr_engine import HotWord
        words = [HotWord(word="PostgreSQL", weight=8), HotWord(word="鼎新", weight=6)]
        engine.set_hot_words(words)
        assert engine._hot_words == words

    def test_set_context_stores_text(self, engine):
        """set_context() 應儲存語境文字。"""
        engine.set_context("今天天氣很好")
        assert engine._context_text == "今天天氣很好"

    def test_build_prompt_tokens_empty_when_no_context(self, engine):
        """無熱詞與語境時 _build_prompt_tokens() 應回傳空列表。"""
        tokens = engine._build_prompt_tokens()
        assert tokens == []

    def test_build_prompt_tokens_returns_list(self, engine):
        """有熱詞時 _build_prompt_tokens() 應回傳 list（tokenizer 為 None 時回傳空列表）。"""
        from airtype.core.asr_engine import HotWord
        engine.set_hot_words([HotWord(word="PostgreSQL", weight=8)])
        engine._tokenizer = None
        tokens = engine._build_prompt_tokens()
        assert isinstance(tokens, list)

    def test_hot_words_cleared_by_new_set(self, engine):
        """再次 set_hot_words() 應完全取代舊列表。"""
        from airtype.core.asr_engine import HotWord
        engine.set_hot_words([HotWord(word="A", weight=5)])
        engine.set_hot_words([HotWord(word="B", weight=3)])
        assert len(engine._hot_words) == 1
        assert engine._hot_words[0].word == "B"


# ── Task 3.1f ── 卸載（Unload 需求）──────────────────────────────────────────


class TestUnload:
    """驗證引擎卸載行為。"""

    def test_unload_clears_loaded_flag(self, engine, model_dir):
        """unload() 後 _loaded 應為 False。"""
        mock_ov = _make_mock_ov()
        with patch.dict(sys.modules, {"openvino": mock_ov}):
            engine.load_model(str(model_dir), {})
        assert engine._loaded
        engine.unload()
        assert not engine._loaded

    def test_unload_clears_encoder_reference(self, engine, model_dir):
        """unload() 後 _encoder 應為 None。"""
        mock_ov = _make_mock_ov()
        with patch.dict(sys.modules, {"openvino": mock_ov}):
            engine.load_model(str(model_dir), {})
        engine.unload()
        assert engine._encoder is None

    def test_unload_clears_decoder_reference(self, engine, model_dir):
        """unload() 後 _decoder 應為 None。"""
        mock_ov = _make_mock_ov()
        with patch.dict(sys.modules, {"openvino": mock_ov}):
            engine.load_model(str(model_dir), {})
        engine.unload()
        assert engine._decoder is None


# ── Task 3.1g ── 其他 Protocol 方法 ──────────────────────────────────────────


class TestOtherProtocolMethods:
    """驗證其餘 ASREngine Protocol 方法。"""

    def test_recognize_stream_returns_partial_result(self, engine):
        """recognize_stream() 應回傳 PartialResult（OpenVINO 不支援串流）。"""
        from airtype.core.asr_engine import PartialResult
        chunk = np.zeros(1024, dtype=np.float32)
        result = engine.recognize_stream(chunk)
        assert isinstance(result, PartialResult)
        assert not result.is_final

    def test_get_supported_languages_returns_list(self, engine):
        """get_supported_languages() 應回傳字串列表。"""
        langs = engine.get_supported_languages()
        assert isinstance(langs, list)
        assert all(isinstance(lang, str) for lang in langs)

    def test_get_supported_languages_includes_chinese(self, engine):
        """支援語言清單應包含中文代碼。"""
        langs = engine.get_supported_languages()
        assert any("zh" in lang for lang in langs)

    def test_get_supported_languages_returns_copy(self, engine):
        """get_supported_languages() 應回傳新列表（不洩漏內部狀態）。"""
        langs1 = engine.get_supported_languages()
        langs2 = engine.get_supported_languages()
        assert langs1 is not langs2


# ── Task 2.1 ── 引擎登錄（Engine Registration 需求）─────────────────────────


class TestEngineRegistration:
    """驗證引擎登錄需求：openvino 可用時自動登錄為 'qwen3-openvino'。"""

    def test_register_succeeds_when_openvino_available(self):
        """openvino 可用時 register() 應回傳 True 並登錄 'qwen3-openvino'。"""
        from airtype.core.asr_engine import ASREngineRegistry
        from airtype.core.asr_qwen_openvino import register

        mock_ov = MagicMock()
        registry = ASREngineRegistry()
        with patch.dict(sys.modules, {"openvino": mock_ov}):
            result = register(registry)
        assert result is True
        assert "qwen3-openvino" in registry.registered_ids

    def test_register_fails_when_openvino_not_installed(self):
        """openvino 未安裝時 register() 應回傳 False，不登錄。"""
        from airtype.core.asr_engine import ASREngineRegistry
        from airtype.core.asr_qwen_openvino import register

        registry = ASREngineRegistry()
        # None in sys.modules 會讓 import openvino 拋出 ImportError
        with patch.dict(sys.modules, {"openvino": None}):
            result = register(registry)
        assert result is False
        assert "qwen3-openvino" not in registry.registered_ids

    def test_engine_id_is_correct(self):
        """ENGINE_ID 應為 'qwen3-openvino'。"""
        from airtype.core.asr_qwen_openvino import QwenOpenVinoEngine
        assert QwenOpenVinoEngine.ENGINE_ID == "qwen3-openvino"


# ── Task 3.2 ── 整合測試（模型不可用時跳過）──────────────────────────────────


@pytest.mark.skipif(
    not _HAS_REAL_MODEL,
    reason="Qwen3-ASR INT8 模型不可用（跳過整合測試，模型路徑：models/asr/qwen3_asr_int8）",
)
class TestIntegration:
    """Task 3.2：整合測試 — 載入真實 INT8 模型並辨識測試音訊。"""

    @pytest.fixture(scope="class")
    def loaded_engine(self):
        """載入真實 INT8 模型的引擎（class 範圍，只載入一次）。"""
        from airtype.core.asr_qwen_openvino import QwenOpenVinoEngine

        engine = QwenOpenVinoEngine()
        engine.load_model(str(_INT8_MODEL_DIR))
        yield engine
        engine.unload()

    def test_recognize_silent_audio_returns_asr_result(self, loaded_engine):
        """靜音音訊辨識應回傳 ASRResult 而不崩潰。"""
        from airtype.core.asr_engine import ASRResult

        audio = np.zeros(16000 * 3, dtype=np.float32)  # 3 秒靜音
        result = loaded_engine.recognize(audio)
        assert isinstance(result, ASRResult)
        assert isinstance(result.text, str)
        assert 0.0 <= result.confidence <= 1.0

    def test_recognize_returns_valid_language_code(self, loaded_engine):
        """辨識結果 language 應為有效語言代碼字串。"""
        audio = np.zeros(16000, dtype=np.float32)
        result = loaded_engine.recognize(audio)
        assert isinstance(result.language, str)
        assert len(result.language) >= 2

    def test_recognize_returns_at_least_one_segment(self, loaded_engine):
        """辨識結果應包含至少一個時間段。"""
        audio = np.zeros(16000 * 5, dtype=np.float32)
        result = loaded_engine.recognize(audio)
        assert len(result.segments) >= 1

    def test_lazy_load_then_recognize(self):
        """prepare() + recognize() 流程應正確觸發延遲載入。"""
        from airtype.core.asr_engine import ASRResult
        from airtype.core.asr_qwen_openvino import QwenOpenVinoEngine

        engine = QwenOpenVinoEngine()
        engine.prepare(str(_INT8_MODEL_DIR))
        assert not engine._loaded

        audio = np.zeros(16000, dtype=np.float32)
        result = engine.recognize(audio)
        assert engine._loaded
        assert isinstance(result, ASRResult)
        engine.unload()

    def test_hot_words_do_not_crash_recognize(self, loaded_engine):
        """設定熱詞後辨識不應崩潰。"""
        from airtype.core.asr_engine import HotWord

        loaded_engine.set_hot_words([
            HotWord(word="PostgreSQL", weight=8),
            HotWord(word="鼎新", weight=6),
        ])
        audio = np.zeros(16000 * 2, dtype=np.float32)
        result = loaded_engine.recognize(audio)
        assert result is not None
        loaded_engine.set_hot_words([])  # 清除
