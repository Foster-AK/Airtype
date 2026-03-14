"""Qwen3-ASR MLX 引擎單元測試。

使用 mock mlx_qwen3_asr 的單元測試（載入、推理流程、延遲載入）。
"""
from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

import numpy as np
import pytest


# ── Mock 工廠 ─────────────────────────────────────────────────────────────────


def _make_mock_transcription_result(text="測試文字", language="Chinese"):
    """建立 mock TranscriptionResult。"""
    result = MagicMock()
    result.text = text
    result.language = language
    result.segments = None
    result.chunks = None
    result.speaker_segments = None
    return result


def _make_mock_mlx_qwen3_asr():
    """建立完整的 mock mlx_qwen3_asr 模組。"""
    mock_mod = MagicMock()
    mock_session = MagicMock()
    mock_session.transcribe.return_value = _make_mock_transcription_result()
    mock_mod.Session.return_value = mock_session
    return mock_mod


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def engine():
    """建立未載入的 QwenMlxEngine 實例。"""
    from airtype.core.asr_qwen_mlx import QwenMlxEngine
    return QwenMlxEngine()


# ── 引擎登錄 ──────────────────────────────────────────────────────────────────


class TestEngineRegistration:
    """驗證引擎登錄需求。"""

    def test_register_succeeds_when_mlx_available(self):
        """mlx_qwen3_asr 可用時 register() 應回傳 True。"""
        from airtype.core.asr_engine import ASREngineRegistry
        from airtype.core.asr_qwen_mlx import register

        mock_mlx = MagicMock()
        registry = ASREngineRegistry()
        with patch.dict(sys.modules, {"mlx_qwen3_asr": mock_mlx}):
            result = register(registry)
        assert result is True
        assert "qwen3-mlx" in registry.registered_ids

    def test_register_fails_when_mlx_not_installed(self):
        """mlx_qwen3_asr 未安裝時 register() 應回傳 False。"""
        from airtype.core.asr_engine import ASREngineRegistry
        from airtype.core.asr_qwen_mlx import register

        registry = ASREngineRegistry()
        with patch.dict(sys.modules, {"mlx_qwen3_asr": None}):
            result = register(registry)
        assert result is False
        assert "qwen3-mlx" not in registry.registered_ids

    def test_engine_id_is_correct(self):
        """ENGINE_ID 應為 'qwen3-mlx'。"""
        from airtype.core.asr_qwen_mlx import QwenMlxEngine
        assert QwenMlxEngine.ENGINE_ID == "qwen3-mlx"


# ── Protocol 一致性 ──────────────────────────────────────────────────────────


class TestProtocolConformance:
    """QwenMlxEngine 符合 ASREngine Protocol。"""

    def test_conforms_to_protocol(self, engine):
        from airtype.core.asr_engine import ASREngine
        assert isinstance(engine, ASREngine)


# ── 模型載入 ──────────────────────────────────────────────────────────────────


class TestModelLoading:
    """驗證模型載入需求。"""

    def test_initial_state_not_loaded(self, engine):
        """初始狀態 _loaded 應為 False。"""
        assert not engine._loaded

    def test_load_model_creates_session(self, engine):
        """load_model() 應建立 Session。"""
        mock_mlx = _make_mock_mlx_qwen3_asr()
        with patch.dict(sys.modules, {"mlx_qwen3_asr": mock_mlx}):
            engine.load_model("Qwen/Qwen3-ASR-0.6B", {})
        assert engine._loaded
        assert engine._session is not None
        mock_mlx.Session.assert_called_once_with(model="Qwen/Qwen3-ASR-0.6B")

    def test_load_model_sets_loaded_flag(self, engine):
        """成功載入後 _loaded 應為 True。"""
        mock_mlx = _make_mock_mlx_qwen3_asr()
        with patch.dict(sys.modules, {"mlx_qwen3_asr": mock_mlx}):
            engine.load_model("Qwen/Qwen3-ASR-0.6B", {})
        assert engine._loaded


# ── 延遲載入 ──────────────────────────────────────────────────────────────────


class TestLazyLoading:
    """驗證延遲載入需求。"""

    def test_prepare_does_not_load_model(self, engine):
        """prepare() 後 _loaded 應仍為 False。"""
        engine.prepare("Qwen/Qwen3-ASR-0.6B")
        assert not engine._loaded

    def test_recognize_triggers_lazy_load(self, engine):
        """首次呼叫 recognize() 應自動載入模型。"""
        mock_mlx = _make_mock_mlx_qwen3_asr()
        engine.prepare("Qwen/Qwen3-ASR-0.6B")
        audio = np.zeros(16000, dtype=np.float32)
        with patch.dict(sys.modules, {"mlx_qwen3_asr": mock_mlx}):
            engine.recognize(audio)
        assert engine._loaded

    def test_recognize_without_prepare_raises_runtime_error(self, engine):
        """未呼叫 prepare() 或 load_model() 時 recognize() 應拋出 RuntimeError。"""
        audio = np.zeros(16000, dtype=np.float32)
        with pytest.raises(RuntimeError, match="模型路徑"):
            engine.recognize(audio)


# ── 辨識 ──────────────────────────────────────────────────────────────────────


class TestRecognition:
    """驗證語音辨識需求。"""

    def _recognize_with_mock(self, engine, audio, text="測試", language="Chinese"):
        mock_mlx = _make_mock_mlx_qwen3_asr()
        mock_mlx.Session.return_value.transcribe.return_value = (
            _make_mock_transcription_result(text=text, language=language)
        )
        with patch.dict(sys.modules, {"mlx_qwen3_asr": mock_mlx}):
            engine.load_model("Qwen/Qwen3-ASR-0.6B", {})
            return engine.recognize(audio)

    def test_recognize_returns_asr_result(self, engine):
        """recognize() 應回傳 ASRResult 實例。"""
        from airtype.core.asr_engine import ASRResult
        audio = np.zeros(16000, dtype=np.float32)
        result = self._recognize_with_mock(engine, audio)
        assert isinstance(result, ASRResult)

    def test_recognize_result_has_text(self, engine):
        """ASRResult.text 應為正確的辨識文字。"""
        audio = np.zeros(16000, dtype=np.float32)
        result = self._recognize_with_mock(engine, audio, text="你好世界")
        assert result.text == "你好世界"

    def test_recognize_result_has_language(self, engine):
        """ASRResult.language 應為字串。"""
        audio = np.zeros(16000, dtype=np.float32)
        result = self._recognize_with_mock(engine, audio, language="Chinese")
        assert isinstance(result.language, str)
        assert result.language == "Chinese"

    def test_recognize_result_confidence_in_range(self, engine):
        """ASRResult.confidence 應在 0.0–1.0 範圍內。"""
        audio = np.zeros(16000, dtype=np.float32)
        result = self._recognize_with_mock(engine, audio)
        assert 0.0 <= result.confidence <= 1.0

    def test_recognize_result_has_segments(self, engine):
        """ASRResult.segments 應包含至少一個時間段。"""
        audio = np.zeros(16000 * 3, dtype=np.float32)
        result = self._recognize_with_mock(engine, audio)
        assert len(result.segments) >= 1

    def test_recognize_segment_end_matches_duration(self, engine):
        """時間段 end 應等於音訊長度（秒）。"""
        duration = 3.0
        audio = np.zeros(int(16000 * duration), dtype=np.float32)
        result = self._recognize_with_mock(engine, audio)
        assert result.segments[0].end == pytest.approx(duration)

    def test_recognize_passes_context(self, engine):
        """recognize() 應將 context 傳遞給 session.transcribe()。"""
        mock_mlx = _make_mock_mlx_qwen3_asr()
        with patch.dict(sys.modules, {"mlx_qwen3_asr": mock_mlx}):
            engine.load_model("Qwen/Qwen3-ASR-0.6B", {})
            engine.set_context("今天天氣很好")
            audio = np.zeros(16000, dtype=np.float32)
            engine.recognize(audio)
        # 驗證 transcribe 被呼叫時有 context 參數
        call_kwargs = mock_mlx.Session.return_value.transcribe.call_args
        assert call_kwargs.kwargs.get("context") == "今天天氣很好"

    def test_recognize_passes_hot_words_as_context(self, engine):
        """recognize() 應將熱詞組合到 context 中。"""
        from airtype.core.asr_engine import HotWord
        mock_mlx = _make_mock_mlx_qwen3_asr()
        with patch.dict(sys.modules, {"mlx_qwen3_asr": mock_mlx}):
            engine.load_model("Qwen/Qwen3-ASR-0.6B", {})
            engine.set_hot_words([HotWord(word="PostgreSQL", weight=8)])
            audio = np.zeros(16000, dtype=np.float32)
            engine.recognize(audio)
        call_kwargs = mock_mlx.Session.return_value.transcribe.call_args
        assert "PostgreSQL" in call_kwargs.kwargs.get("context", "")


# ── 串流 ──────────────────────────────────────────────────────────────────────


class TestStreamRecognition:
    """驗證串流辨識行為。"""

    def test_recognize_stream_returns_partial_result(self, engine):
        """recognize_stream() 應回傳空的 PartialResult。"""
        from airtype.core.asr_engine import PartialResult
        chunk = np.zeros(1024, dtype=np.float32)
        result = engine.recognize_stream(chunk)
        assert isinstance(result, PartialResult)
        assert not result.is_final


# ── 卸載 ──────────────────────────────────────────────────────────────────────


class TestUnload:
    """驗證引擎卸載行為。"""

    def test_unload_clears_loaded_flag(self, engine):
        """unload() 後 _loaded 應為 False。"""
        mock_mlx = _make_mock_mlx_qwen3_asr()
        with patch.dict(sys.modules, {"mlx_qwen3_asr": mock_mlx}):
            engine.load_model("Qwen/Qwen3-ASR-0.6B", {})
        assert engine._loaded
        engine.unload()
        assert not engine._loaded

    def test_unload_clears_session(self, engine):
        """unload() 後 _session 應為 None。"""
        mock_mlx = _make_mock_mlx_qwen3_asr()
        with patch.dict(sys.modules, {"mlx_qwen3_asr": mock_mlx}):
            engine.load_model("Qwen/Qwen3-ASR-0.6B", {})
        engine.unload()
        assert engine._session is None


# ── 其他 Protocol 方法 ──────────────────────────────────────────────────────


class TestOtherProtocolMethods:
    """驗證其餘 ASREngine Protocol 方法。"""

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

    def test_set_context_stores_text(self, engine):
        engine.set_context("今天天氣很好")
        assert engine._context_text == "今天天氣很好"

    def test_set_hot_words_stores_list(self, engine):
        from airtype.core.asr_engine import HotWord
        words = [HotWord(word="PostgreSQL", weight=8)]
        engine.set_hot_words(words)
        assert engine._hot_words == words
