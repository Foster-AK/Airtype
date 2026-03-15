"""Qwen3-ASR MLX 引擎單元測試。

使用 mock 避免實際 MLX 依賴，覆蓋所有 spec 情境：
  - MLX Model Loading
  - Batch Speech Recognition
  - Context Text Biasing
  - Lazy Model Loading
  - Model Unloading
  - Hot Words Property
  - Supported Languages
  - Engine Registration
"""
from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

import numpy as np
import pytest


# ---------------------------------------------------------------------------
# Mock MLX 模組（測試環境不需要真正的 mlx / mlx_qwen3_asr）
# ---------------------------------------------------------------------------


def _make_mock_mlx_modules():
    """建立 mock mlx 與 mlx_qwen3_asr 模組。"""
    mock_mlx = MagicMock()
    mock_mlx_qwen3_asr = MagicMock()

    # mock Session 實例
    mock_session = MagicMock()
    mock_session.transcribe.return_value = "你好世界"
    mock_mlx_qwen3_asr.Session.return_value = mock_session

    return mock_mlx, mock_mlx_qwen3_asr, mock_session


@pytest.fixture
def mock_mlx_env():
    """注入 mock mlx 模組至 sys.modules。"""
    mock_mlx, mock_mlx_qwen3_asr, mock_session = _make_mock_mlx_modules()
    with patch.dict(sys.modules, {
        "mlx": mock_mlx,
        "mlx_qwen3_asr": mock_mlx_qwen3_asr,
    }):
        # 重新載入模組以使用 mock
        if "airtype.core.asr_qwen_mlx" in sys.modules:
            del sys.modules["airtype.core.asr_qwen_mlx"]
        from airtype.core.asr_qwen_mlx import MLXQwen3ASREngine
        yield {
            "engine_cls": MLXQwen3ASREngine,
            "mock_mlx": mock_mlx,
            "mock_mlx_qwen3_asr": mock_mlx_qwen3_asr,
            "mock_session": mock_session,
        }


# ---------------------------------------------------------------------------
# MLX Model Loading
# ---------------------------------------------------------------------------


class TestMLXModelLoading:
    """MLX Model Loading spec 情境。"""

    def test_load_model_from_hf_id(self, mock_mlx_env):
        """load_model 接受 HuggingFace ID，建立 Session 並就緒。"""
        engine = mock_mlx_env["engine_cls"]()
        engine.load_model("Qwen/Qwen3-ASR-0.6B", {})
        mock_mlx_env["mock_mlx_qwen3_asr"].Session.assert_called_once()

    def test_load_model_from_local_path(self, mock_mlx_env):
        """load_model 接受本地路徑。"""
        engine = mock_mlx_env["engine_cls"]()
        engine.load_model("~/.airtype/models/qwen3-asr-0.6b-mlx/", {})
        mock_mlx_env["mock_mlx_qwen3_asr"].Session.assert_called_once()

    def test_load_model_missing_path_raises(self, mock_mlx_env):
        """模型路徑不存在且非有效 HF ID 時應拋出例外。"""
        mock_mlx_env["mock_mlx_qwen3_asr"].Session.side_effect = FileNotFoundError(
            "model not found"
        )
        engine = mock_mlx_env["engine_cls"]()
        with pytest.raises(FileNotFoundError):
            engine.load_model("/nonexistent/path", {})


# ---------------------------------------------------------------------------
# Batch Speech Recognition
# ---------------------------------------------------------------------------


class TestBatchSpeechRecognition:
    """Batch Speech Recognition spec 情境。"""

    def test_recognize_returns_asr_result(self, mock_mlx_env):
        """recognize() 應回傳包含文字、語言、信心分數的 ASRResult。"""
        from airtype.core.asr_engine import ASRResult

        engine = mock_mlx_env["engine_cls"]()
        engine.load_model("Qwen/Qwen3-ASR-0.6B", {})
        audio = np.zeros(16000 * 5, dtype=np.float32)  # 5 秒
        result = engine.recognize(audio)

        assert isinstance(result, ASRResult)
        assert isinstance(result.text, str)
        assert isinstance(result.language, str)
        assert isinstance(result.confidence, float)

    def test_recognize_mandarin_detects_chinese(self, mock_mlx_env):
        """辨識中文語音時 language 應為 zh-TW，confidence > 0.5。"""
        mock_mlx_env["mock_session"].transcribe.return_value = "你好世界這是測試"
        engine = mock_mlx_env["engine_cls"]()
        engine.load_model("Qwen/Qwen3-ASR-0.6B", {})
        audio = np.zeros(16000 * 5, dtype=np.float32)
        result = engine.recognize(audio)
        assert result.language == "zh-TW"
        assert result.confidence > 0.5

    def test_recognize_english_detects_en(self, mock_mlx_env):
        """辨識英文語音時 language 應為 en，confidence > 0.5。"""
        mock_mlx_env["mock_session"].transcribe.return_value = "Hello world this is a test"
        engine = mock_mlx_env["engine_cls"]()
        engine.load_model("Qwen/Qwen3-ASR-0.6B", {})
        audio = np.zeros(16000 * 5, dtype=np.float32)
        result = engine.recognize(audio)
        assert result.language == "en"
        assert result.confidence > 0.5

    def test_recognize_passes_audio_to_session(self, mock_mlx_env):
        """recognize() 應將音訊傳遞至 Session.transcribe()。"""
        engine = mock_mlx_env["engine_cls"]()
        engine.load_model("Qwen/Qwen3-ASR-0.6B", {})
        audio = np.random.randn(16000 * 3).astype(np.float32)
        engine.recognize(audio)
        mock_mlx_env["mock_session"].transcribe.assert_called()

    def test_recognize_empty_audio(self, mock_mlx_env):
        """空音訊輸入應回傳空文字與 confidence=0.0。"""
        mock_mlx_env["mock_session"].transcribe.return_value = ""
        engine = mock_mlx_env["engine_cls"]()
        engine.load_model("Qwen/Qwen3-ASR-0.6B", {})
        audio = np.array([], dtype=np.float32)
        result = engine.recognize(audio)
        assert result.text == ""
        assert result.confidence == 0.0

    def test_confidence_varies_with_text_density(self, mock_mlx_env):
        """信心分數應依文字密度變化，非固定值。"""
        engine = mock_mlx_env["engine_cls"]()
        engine.load_model("Qwen/Qwen3-ASR-0.6B", {})

        # 正常密度（5 秒音訊、8 個字）→ 正常信心
        mock_mlx_env["mock_session"].transcribe.return_value = "你好世界這是測試"
        audio_normal = np.zeros(16000 * 5, dtype=np.float32)
        r_normal = engine.recognize(audio_normal)

        # 極少文字（5 秒音訊、1 個字）→ 較低信心
        mock_mlx_env["mock_session"].transcribe.return_value = "a"
        audio_sparse = np.zeros(16000 * 5, dtype=np.float32)
        r_sparse = engine.recognize(audio_sparse)

        assert r_normal.confidence >= r_sparse.confidence


# ---------------------------------------------------------------------------
# Context Text Biasing
# ---------------------------------------------------------------------------


class TestContextTextBiasing:
    """Context Text Biasing spec 情境。"""

    def test_set_context_passes_to_transcribe(self, mock_mlx_env):
        """set_context() 後 recognize() 應將 context 傳入 transcribe。"""
        engine = mock_mlx_env["engine_cls"]()
        engine.load_model("Qwen/Qwen3-ASR-0.6B", {})
        engine.set_context("PostgreSQL 鼎新")
        audio = np.zeros(16000, dtype=np.float32)
        engine.recognize(audio)
        call_kwargs = mock_mlx_env["mock_session"].transcribe.call_args
        # context 應出現在呼叫參數中
        assert "context" in call_kwargs.kwargs or (
            len(call_kwargs.args) > 1 and call_kwargs.args[1] is not None
        )

    def test_clear_context(self, mock_mlx_env):
        """set_context("") 應清除 context。"""
        engine = mock_mlx_env["engine_cls"]()
        engine.load_model("Qwen/Qwen3-ASR-0.6B", {})
        engine.set_context("some context")
        engine.set_context("")
        audio = np.zeros(16000, dtype=np.float32)
        engine.recognize(audio)
        # 驗證無 context 或 context 為空字串
        call_kwargs = mock_mlx_env["mock_session"].transcribe.call_args
        ctx_value = call_kwargs.kwargs.get("context", "")
        assert ctx_value == "" or ctx_value is None


# ---------------------------------------------------------------------------
# Lazy Model Loading
# ---------------------------------------------------------------------------


class TestLazyModelLoading:
    """Lazy Model Loading spec 情境。"""

    def test_prepare_does_not_load(self, mock_mlx_env):
        """prepare() 後不應立即載入模型。"""
        engine = mock_mlx_env["engine_cls"]()
        engine.prepare("Qwen/Qwen3-ASR-0.6B")
        mock_mlx_env["mock_mlx_qwen3_asr"].Session.assert_not_called()

    def test_first_recognize_triggers_load(self, mock_mlx_env):
        """首次 recognize() 應觸發模型載入。"""
        engine = mock_mlx_env["engine_cls"]()
        engine.prepare("Qwen/Qwen3-ASR-0.6B")
        audio = np.zeros(16000, dtype=np.float32)
        engine.recognize(audio)
        mock_mlx_env["mock_mlx_qwen3_asr"].Session.assert_called_once()

    def test_subsequent_recognize_no_reload(self, mock_mlx_env):
        """後續 recognize() 不應重複載入模型。"""
        engine = mock_mlx_env["engine_cls"]()
        engine.prepare("Qwen/Qwen3-ASR-0.6B")
        audio = np.zeros(16000, dtype=np.float32)
        engine.recognize(audio)
        engine.recognize(audio)
        mock_mlx_env["mock_mlx_qwen3_asr"].Session.assert_called_once()


# ---------------------------------------------------------------------------
# Model Unloading
# ---------------------------------------------------------------------------


class TestModelUnloading:
    """Model Unloading spec 情境。"""

    def test_unload_releases_session(self, mock_mlx_env):
        """unload() 後 Session 引用應為 None。"""
        engine = mock_mlx_env["engine_cls"]()
        engine.load_model("Qwen/Qwen3-ASR-0.6B", {})
        engine.unload()
        assert engine._session is None

    def test_recognize_after_unload_with_prepare(self, mock_mlx_env):
        """unload() + prepare() 後再 recognize() 應重新載入。"""
        engine = mock_mlx_env["engine_cls"]()
        engine.prepare("Qwen/Qwen3-ASR-0.6B")
        audio = np.zeros(16000, dtype=np.float32)
        engine.recognize(audio)  # 第一次載入
        engine.unload()
        engine.recognize(audio)  # 應重新載入
        assert mock_mlx_env["mock_mlx_qwen3_asr"].Session.call_count == 2


# ---------------------------------------------------------------------------
# Hot Words Property
# ---------------------------------------------------------------------------


class TestHotWordsProperty:
    """Hot Words Property spec 情境。"""

    def test_supports_hot_words_is_false(self, mock_mlx_env):
        """supports_hot_words 應回傳 False。"""
        engine = mock_mlx_env["engine_cls"]()
        assert engine.supports_hot_words is False


# ---------------------------------------------------------------------------
# Supported Languages
# ---------------------------------------------------------------------------


class TestSupportedLanguages:
    """Supported Languages spec 情境。"""

    def test_supported_languages_contains_required(self, mock_mlx_env):
        """get_supported_languages() 應包含 zh-TW, zh-CN, en, ja, ko。"""
        engine = mock_mlx_env["engine_cls"]()
        langs = engine.get_supported_languages()
        for required in ["zh-TW", "zh-CN", "en", "ja", "ko"]:
            assert required in langs


# ---------------------------------------------------------------------------
# Engine Registration
# ---------------------------------------------------------------------------


class TestEngineRegistration:
    """Engine Registration spec 情境。"""

    def test_register_with_mlx_available(self, mock_mlx_env):
        """mlx 可用時 register() 應回傳 True 且 registry 含 qwen3-mlx。"""
        from airtype.core.asr_engine import ASREngineRegistry
        from airtype.core.asr_qwen_mlx import register

        registry = ASREngineRegistry()
        result = register(registry)
        assert result is True
        assert "qwen3-mlx" in registry.registered_ids

    def test_register_without_mlx_returns_false(self):
        """mlx 不可用時 register() 應回傳 False。"""
        # 確保 mlx 不在 sys.modules 中
        with patch.dict(sys.modules, {"mlx": None}):
            if "airtype.core.asr_qwen_mlx" in sys.modules:
                del sys.modules["airtype.core.asr_qwen_mlx"]
            # 模擬 import mlx 失敗
            import importlib
            with patch("builtins.__import__", side_effect=lambda name, *args, **kwargs: (
                (_ for _ in ()).throw(ImportError("No module named 'mlx'"))
                if name == "mlx" else importlib.__import__(name, *args, **kwargs)
            )):
                from airtype.core.asr_engine import ASREngineRegistry
                # 需要直接測試 register 函式中的 import 檢查
                # 由於模組載入問題，直接建立一個簡單測試
                from airtype.core import asr_qwen_mlx
                importlib.reload(asr_qwen_mlx)
                registry = ASREngineRegistry()
                result = asr_qwen_mlx.register(registry)
                assert result is False
