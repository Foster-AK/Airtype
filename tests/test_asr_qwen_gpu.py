"""Qwen3-ASR GPU 引擎單元測試與整合測試。

Task 4.1：使用 mock torch/CUDA 的單元測試（測試套件缺失時的優雅降級）。
Task 4.2：整合測試（GPU 辨識，無 GPU/chatllm 可用時跳過）。
"""
from __future__ import annotations

import json
import sys
import wave
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest


# ── 可用性旗標（整合測試用）─────────────────────────────────────────────────

def _cuda_available() -> bool:
    try:
        import torch  # noqa: PLC0415
        return torch.cuda.is_available()
    except ImportError:
        return False


def _chatllm_available() -> bool:
    from airtype.core.asr_qwen_vulkan import _is_chatllm_available  # noqa: PLC0415
    return _is_chatllm_available()


_HAS_CUDA = _cuda_available()
_HAS_CHATLLM = _chatllm_available()

# 整合測試模型路徑
_PYTORCH_MODEL_DIR = Path("models/asr/qwen3_asr")
_GGUF_MODEL_FILE = Path("models/asr/qwen3_asr_q8.gguf")

_HAS_PYTORCH_MODEL = _PYTORCH_MODEL_DIR.exists()
_HAS_GGUF_MODEL = _GGUF_MODEL_FILE.exists()


# ════════════════════════════════════════════════════════════════════════════
# Task 4.1a — PyTorch CUDA 引擎單元測試
# ════════════════════════════════════════════════════════════════════════════


class TestPyTorchProtocolConformance:
    """QwenPyTorchEngine 符合 ASREngine Protocol。"""

    def test_conforms_to_protocol(self):
        from airtype.core.asr_engine import ASREngine
        from airtype.core.asr_qwen_pytorch import QwenPyTorchEngine

        engine = QwenPyTorchEngine()
        assert isinstance(engine, ASREngine)


class TestPyTorchEngineId:
    """ENGINE_ID 正確性。"""

    def test_engine_id_is_correct(self):
        from airtype.core.asr_qwen_pytorch import QwenPyTorchEngine

        assert QwenPyTorchEngine.ENGINE_ID == "qwen3-pytorch-cuda"


class TestPyTorchGracefulDegradation:
    """可選依賴缺失時優雅降級——Task 4.1（torch 套件缺失）。"""

    def test_import_module_without_torch_does_not_raise(self):
        """匯入 asr_qwen_pytorch 模組時不需要 torch，不應產生 ImportError。

        驗證模組頂層不做 `import torch`，確保在純 CPU 環境下可安全匯入。
        """
        # 模組已被 Python 快取，此測試確認模組層級不依賴 torch
        import airtype.core.asr_qwen_pytorch  # noqa: F401, PLC0415
        # 若到達此處即表示模組匯入無誤

    def test_register_returns_false_when_torch_missing(self):
        """torch 未安裝時 register() 應回傳 False，不登錄引擎。"""
        from airtype.core.asr_engine import ASREngineRegistry
        from airtype.core.asr_qwen_pytorch import register

        registry = ASREngineRegistry()
        with patch.dict(sys.modules, {"torch": None}):
            result = register(registry)

        assert result is False
        assert "qwen3-pytorch-cuda" not in registry.registered_ids

    def test_register_returns_false_when_cuda_not_available(self):
        """torch 存在但 CUDA 不可用時 register() 應回傳 False。"""
        from airtype.core.asr_engine import ASREngineRegistry
        from airtype.core.asr_qwen_pytorch import register

        mock_torch = MagicMock()
        mock_torch.cuda.is_available.return_value = False

        registry = ASREngineRegistry()
        with patch.dict(sys.modules, {"torch": mock_torch}):
            result = register(registry)

        assert result is False
        assert "qwen3-pytorch-cuda" not in registry.registered_ids

    def test_register_returns_true_when_cuda_available(self):
        """torch 存在且 CUDA 可用時 register() 應回傳 True 並登錄引擎。"""
        from airtype.core.asr_engine import ASREngineRegistry
        from airtype.core.asr_qwen_pytorch import register

        mock_torch = MagicMock()
        mock_torch.cuda.is_available.return_value = True

        registry = ASREngineRegistry()
        with patch.dict(sys.modules, {"torch": mock_torch}):
            result = register(registry)

        assert result is True
        assert "qwen3-pytorch-cuda" in registry.registered_ids


class TestPyTorchInitialState:
    """QwenPyTorchEngine 初始狀態。"""

    def test_initial_not_loaded(self):
        from airtype.core.asr_qwen_pytorch import QwenPyTorchEngine

        engine = QwenPyTorchEngine()
        assert not engine._loaded

    def test_prepare_does_not_load(self, tmp_path):
        from airtype.core.asr_qwen_pytorch import QwenPyTorchEngine

        engine = QwenPyTorchEngine()
        engine.prepare(str(tmp_path))
        assert not engine._loaded

    def test_recognize_without_prepare_raises_runtime_error(self):
        from airtype.core.asr_qwen_pytorch import QwenPyTorchEngine

        engine = QwenPyTorchEngine()
        with pytest.raises(RuntimeError, match="模型路徑"):
            engine.recognize(np.zeros(16000, dtype=np.float32))


class TestPyTorchLoadModel:
    """QwenPyTorchEngine.load_model 行為。"""

    def test_load_missing_directory_raises_file_not_found(self):
        from airtype.core.asr_qwen_pytorch import QwenPyTorchEngine

        engine = QwenPyTorchEngine()
        with pytest.raises(FileNotFoundError, match="不存在"):
            engine.load_model("/nonexistent/model/path", {})

    def test_load_raises_runtime_error_when_cuda_not_available(self, tmp_path):
        from airtype.core.asr_qwen_pytorch import QwenPyTorchEngine

        engine = QwenPyTorchEngine()
        mock_torch = MagicMock()
        mock_torch.cuda.is_available.return_value = False

        with patch.dict(sys.modules, {"torch": mock_torch}):
            with pytest.raises(RuntimeError, match="CUDA"):
                engine.load_model(str(tmp_path), {})


class TestPyTorchProtocolMethods:
    """ASREngine Protocol 其他方法。"""

    def test_recognize_stream_returns_partial_result(self):
        from airtype.core.asr_engine import PartialResult
        from airtype.core.asr_qwen_pytorch import QwenPyTorchEngine

        engine = QwenPyTorchEngine()
        result = engine.recognize_stream(np.zeros(1024, dtype=np.float32))
        assert isinstance(result, PartialResult)
        assert not result.is_final

    def test_set_hot_words_stores_list(self):
        from airtype.core.asr_engine import HotWord
        from airtype.core.asr_qwen_pytorch import QwenPyTorchEngine

        engine = QwenPyTorchEngine()
        words = [HotWord(word="PostgreSQL", weight=8)]
        engine.set_hot_words(words)
        assert engine._hot_words == words

    def test_set_context_stores_text(self):
        from airtype.core.asr_qwen_pytorch import QwenPyTorchEngine

        engine = QwenPyTorchEngine()
        engine.set_context("今天天氣很好")
        assert engine._context_text == "今天天氣很好"

    def test_get_supported_languages_returns_list(self):
        from airtype.core.asr_qwen_pytorch import QwenPyTorchEngine

        engine = QwenPyTorchEngine()
        langs = engine.get_supported_languages()
        assert isinstance(langs, list)
        assert all(isinstance(lang, str) for lang in langs)

    def test_get_supported_languages_includes_chinese(self):
        from airtype.core.asr_qwen_pytorch import QwenPyTorchEngine

        engine = QwenPyTorchEngine()
        langs = engine.get_supported_languages()
        assert any("zh" in lang for lang in langs)

    def test_get_supported_languages_returns_copy(self):
        from airtype.core.asr_qwen_pytorch import QwenPyTorchEngine

        engine = QwenPyTorchEngine()
        assert engine.get_supported_languages() is not engine.get_supported_languages()

    def test_unload_clears_loaded_flag(self):
        from airtype.core.asr_qwen_pytorch import QwenPyTorchEngine

        engine = QwenPyTorchEngine()
        engine._loaded = True
        engine._model = MagicMock()
        engine.unload()
        assert not engine._loaded
        assert engine._model is None


class TestPyTorchPromptInjection:
    """_build_prompt_text() 與 _build_prompt_ids() 語境注入邏輯。"""

    def test_build_prompt_text_empty_when_no_context(self):
        from airtype.core.asr_qwen_pytorch import QwenPyTorchEngine

        engine = QwenPyTorchEngine()
        assert engine._build_prompt_text() == ""

    def test_build_prompt_text_includes_context(self):
        from airtype.core.asr_qwen_pytorch import QwenPyTorchEngine

        engine = QwenPyTorchEngine()
        engine.set_context("語境文字")
        assert "語境文字" in engine._build_prompt_text()

    def test_build_prompt_text_includes_hot_words(self):
        from airtype.core.asr_engine import HotWord
        from airtype.core.asr_qwen_pytorch import QwenPyTorchEngine

        engine = QwenPyTorchEngine()
        engine.set_hot_words([HotWord(word="PostgreSQL", weight=8)])
        assert "PostgreSQL" in engine._build_prompt_text()

    def test_build_prompt_text_combines_both(self):
        from airtype.core.asr_engine import HotWord
        from airtype.core.asr_qwen_pytorch import QwenPyTorchEngine

        engine = QwenPyTorchEngine()
        engine.set_context("今天天氣")
        engine.set_hot_words([HotWord(word="鼎新", weight=5)])
        text = engine._build_prompt_text()
        assert "今天天氣" in text
        assert "鼎新" in text

    def test_build_prompt_ids_returns_none_when_no_context(self):
        from airtype.core.asr_qwen_pytorch import QwenPyTorchEngine

        engine = QwenPyTorchEngine()
        engine._processor = None
        assert engine._build_prompt_ids() is None

    def test_build_prompt_ids_returns_none_when_no_processor(self):
        from airtype.core.asr_engine import HotWord
        from airtype.core.asr_qwen_pytorch import QwenPyTorchEngine

        engine = QwenPyTorchEngine()
        engine.set_context("test context")
        engine._processor = None
        assert engine._build_prompt_ids() is None

    def test_build_prompt_ids_uses_get_prompt_ids_when_available(self):
        """若 processor 有 get_prompt_ids()，應優先使用（WhisperProcessor 介面）。"""
        from airtype.core.asr_qwen_pytorch import QwenPyTorchEngine

        engine = QwenPyTorchEngine()
        engine.set_context("語境測試")

        mock_processor = MagicMock()
        expected_ids = MagicMock()
        mock_processor.get_prompt_ids.return_value = expected_ids
        engine._processor = mock_processor

        result = engine._build_prompt_ids()

        mock_processor.get_prompt_ids.assert_called_once_with("語境測試", return_tensors="pt")
        assert result is expected_ids

    def test_build_prompt_ids_falls_back_to_tokenizer_encode(self):
        """get_prompt_ids 失敗時退回至 tokenizer.encode。"""
        from airtype.core.asr_qwen_pytorch import QwenPyTorchEngine

        engine = QwenPyTorchEngine()
        engine.set_context("語境測試")

        mock_processor = MagicMock()
        # get_prompt_ids 存在但拋出例外，觸發退回至 tokenizer.encode
        mock_processor.get_prompt_ids.side_effect = ValueError("不支援的呼叫方式")

        mock_tokenizer = MagicMock()
        expected_ids = MagicMock()
        mock_tokenizer.encode.return_value = expected_ids
        mock_processor.tokenizer = mock_tokenizer
        engine._processor = mock_processor

        mock_torch = MagicMock()
        with patch.dict(sys.modules, {"torch": mock_torch}):
            result = engine._build_prompt_ids()

        mock_tokenizer.encode.assert_called_once()
        assert result is expected_ids

    def test_build_prompt_ids_returns_none_on_exception(self):
        """get_prompt_ids 拋出例外時應靜默退回 None。"""
        from airtype.core.asr_qwen_pytorch import QwenPyTorchEngine

        engine = QwenPyTorchEngine()
        engine.set_context("語境測試")

        mock_processor = MagicMock()
        mock_processor.get_prompt_ids.side_effect = ValueError("不支援的格式")
        # tokenizer.encode 也失敗
        mock_processor.tokenizer = MagicMock()
        del mock_processor.tokenizer.encode  # 無 encode 屬性
        engine._processor = mock_processor

        # 不應拋出例外
        result = engine._build_prompt_ids()
        assert result is None


class TestPyTorchRecognizeWithMock:
    """使用 mock model 驗證 recognize() 流程。"""

    def _make_loaded_engine(self):
        """建立已載入狀態的 QwenPyTorchEngine（完全 mock）。"""
        from airtype.core.asr_qwen_pytorch import QwenPyTorchEngine

        engine = QwenPyTorchEngine()
        engine._loaded = True

        # mock processor
        mock_processor = MagicMock()
        mock_processor.return_value = {"input_features": MagicMock(
            dtype=MagicMock(is_floating_point=True),
            to=MagicMock(return_value=MagicMock()),
            items=MagicMock(return_value=[
                ("input_features", MagicMock(
                    dtype=MagicMock(is_floating_point=True),
                    to=MagicMock(return_value=MagicMock()),
                ))
            ]),
        )}
        mock_processor.batch_decode.return_value = ["測試辨識文字"]

        # mock model
        mock_model = MagicMock()
        mock_model.generate.return_value = MagicMock()

        engine._processor = mock_processor
        engine._model = mock_model
        return engine

    def test_recognize_returns_asr_result(self):
        from airtype.core.asr_engine import ASRResult
        from airtype.core.asr_qwen_pytorch import QwenPyTorchEngine

        engine = QwenPyTorchEngine()
        engine._loaded = True
        engine._model = MagicMock()
        engine._model.generate.return_value = MagicMock()
        # 使用無 processor 路徑（退回 NumpyPreprocessor）
        engine._processor = None

        audio = np.zeros(16000, dtype=np.float32)

        mock_torch = MagicMock()
        mock_torch.inference_mode.return_value.__enter__ = lambda s: None
        mock_torch.inference_mode.return_value.__exit__ = lambda s, *a: None
        mock_torch.bfloat16 = "bfloat16"
        mock_torch.from_numpy.return_value.to.return_value = MagicMock()

        with patch.dict(sys.modules, {"torch": mock_torch}):
            with patch("airtype.core.asr_qwen_pytorch.NumpyPreprocessor") as MockPrep:
                MockPrep.return_value.extract_mel_spectrogram.return_value = (
                    np.zeros((100, 128), dtype=np.float32)
                )
                result = engine.recognize(audio)

        assert isinstance(result, ASRResult)

    def test_recognize_result_confidence_is_0_8(self):
        """PyTorch 路徑固定回傳 0.8 信心分數。"""
        from airtype.core.asr_qwen_pytorch import QwenPyTorchEngine

        engine = QwenPyTorchEngine()
        engine._loaded = True
        engine._model = MagicMock()
        engine._model.generate.return_value = MagicMock()
        engine._processor = None

        audio = np.zeros(16000, dtype=np.float32)

        mock_torch = MagicMock()
        mock_torch.inference_mode.return_value.__enter__ = lambda s: None
        mock_torch.inference_mode.return_value.__exit__ = lambda s, *a: None
        mock_torch.bfloat16 = "bfloat16"
        mock_torch.from_numpy.return_value.to.return_value = MagicMock()

        with patch.dict(sys.modules, {"torch": mock_torch}):
            with patch("airtype.core.asr_qwen_pytorch.NumpyPreprocessor") as MockPrep:
                MockPrep.return_value.extract_mel_spectrogram.return_value = (
                    np.zeros((100, 128), dtype=np.float32)
                )
                result = engine.recognize(audio)

        assert result.confidence == pytest.approx(0.8)

    def test_recognize_result_has_segment(self):
        """辨識結果應包含至少一個時間段。"""
        from airtype.core.asr_qwen_pytorch import QwenPyTorchEngine

        engine = QwenPyTorchEngine()
        engine._loaded = True
        engine._model = MagicMock()
        engine._model.generate.return_value = MagicMock()
        engine._processor = None

        audio = np.zeros(32000, dtype=np.float32)  # 2 秒

        mock_torch = MagicMock()
        mock_torch.inference_mode.return_value.__enter__ = lambda s: None
        mock_torch.inference_mode.return_value.__exit__ = lambda s, *a: None
        mock_torch.bfloat16 = "bfloat16"
        mock_torch.from_numpy.return_value.to.return_value = MagicMock()

        with patch.dict(sys.modules, {"torch": mock_torch}):
            with patch("airtype.core.asr_qwen_pytorch.NumpyPreprocessor") as MockPrep:
                MockPrep.return_value.extract_mel_spectrogram.return_value = (
                    np.zeros((200, 128), dtype=np.float32)
                )
                result = engine.recognize(audio)

        assert len(result.segments) >= 1
        assert result.segments[0].end == pytest.approx(2.0)


# ════════════════════════════════════════════════════════════════════════════
# Task 4.1b — Vulkan 引擎單元測試
# ════════════════════════════════════════════════════════════════════════════


class TestVulkanProtocolConformance:
    """QwenVulkanEngine 符合 ASREngine Protocol。"""

    def test_conforms_to_protocol(self):
        from airtype.core.asr_engine import ASREngine
        from airtype.core.asr_qwen_vulkan import QwenVulkanEngine

        engine = QwenVulkanEngine()
        assert isinstance(engine, ASREngine)


class TestVulkanEngineId:
    """ENGINE_ID 正確性。"""

    def test_engine_id_is_correct(self):
        from airtype.core.asr_qwen_vulkan import QwenVulkanEngine

        assert QwenVulkanEngine.ENGINE_ID == "qwen3-vulkan"


class TestVulkanGracefulDegradation:
    """chatllm.cpp 不可用時優雅降級——Task 4.1（可選依賴缺失）。"""

    def test_import_module_does_not_require_chatllm(self):
        """匯入 asr_qwen_vulkan 模組不需要 chatllm.cpp，不應產生 ImportError。"""
        import airtype.core.asr_qwen_vulkan  # noqa: F401, PLC0415

    def test_register_returns_false_when_chatllm_not_available(self):
        """chatllm.cpp 不可用時 register() 應回傳 False，不登錄引擎。"""
        from airtype.core.asr_engine import ASREngineRegistry
        from airtype.core.asr_qwen_vulkan import register

        registry = ASREngineRegistry()
        with patch("airtype.core.asr_qwen_vulkan._is_chatllm_available", return_value=False):
            result = register(registry)

        assert result is False
        assert "qwen3-vulkan" not in registry.registered_ids

    def test_register_returns_true_when_chatllm_available(self):
        """chatllm.cpp 可用時 register() 應回傳 True 並登錄引擎。"""
        from airtype.core.asr_engine import ASREngineRegistry
        from airtype.core.asr_qwen_vulkan import register

        registry = ASREngineRegistry()
        with patch("airtype.core.asr_qwen_vulkan._is_chatllm_available", return_value=True):
            result = register(registry)

        assert result is True
        assert "qwen3-vulkan" in registry.registered_ids


class TestVulkanInitialState:
    """QwenVulkanEngine 初始狀態。"""

    def test_initial_not_loaded(self):
        from airtype.core.asr_qwen_vulkan import QwenVulkanEngine

        engine = QwenVulkanEngine()
        assert not engine._loaded

    def test_prepare_does_not_load(self, tmp_path):
        from airtype.core.asr_qwen_vulkan import QwenVulkanEngine

        engine = QwenVulkanEngine()
        engine.prepare(str(tmp_path / "model.gguf"))
        assert not engine._loaded

    def test_recognize_without_prepare_raises_runtime_error(self):
        from airtype.core.asr_qwen_vulkan import QwenVulkanEngine

        engine = QwenVulkanEngine()
        with pytest.raises(RuntimeError, match="模型路徑"):
            engine.recognize(np.zeros(16000, dtype=np.float32))


class TestVulkanLoadModel:
    """QwenVulkanEngine.load_model 行為。"""

    def test_load_missing_model_raises_file_not_found(self):
        from airtype.core.asr_qwen_vulkan import QwenVulkanEngine

        engine = QwenVulkanEngine()
        with pytest.raises(FileNotFoundError, match="GGUF"):
            engine.load_model("/nonexistent/model.gguf", {})

    def test_load_raises_file_not_found_when_binary_missing(self, tmp_path):
        from airtype.core.asr_qwen_vulkan import QwenVulkanEngine

        # 建立假 GGUF 檔案
        model_file = tmp_path / "model.gguf"
        model_file.write_bytes(b"\x47\x47\x55\x46")  # GGUF magic bytes

        engine = QwenVulkanEngine()
        with patch("airtype.core.asr_qwen_vulkan._find_chatllm_binary", return_value=None):
            with pytest.raises(FileNotFoundError, match="chatllm"):
                engine.load_model(str(model_file), {})

    def test_load_model_sets_loaded_flag(self, tmp_path):
        from airtype.core.asr_qwen_vulkan import QwenVulkanEngine

        model_file = tmp_path / "model.gguf"
        model_file.write_bytes(b"\x00\x01\x02\x03")

        engine = QwenVulkanEngine()
        mock_binary = tmp_path / "chatllm"
        with patch("airtype.core.asr_qwen_vulkan._find_chatllm_binary", return_value=mock_binary):
            engine.load_model(str(model_file), {})

        assert engine._loaded


class TestVulkanProtocolMethods:
    """ASREngine Protocol 其他方法。"""

    def test_recognize_stream_returns_partial_result(self):
        from airtype.core.asr_engine import PartialResult
        from airtype.core.asr_qwen_vulkan import QwenVulkanEngine

        engine = QwenVulkanEngine()
        result = engine.recognize_stream(np.zeros(1024, dtype=np.float32))
        assert isinstance(result, PartialResult)
        assert not result.is_final

    def test_set_hot_words_stores_list(self):
        from airtype.core.asr_engine import HotWord
        from airtype.core.asr_qwen_vulkan import QwenVulkanEngine

        engine = QwenVulkanEngine()
        words = [HotWord(word="鼎新", weight=6)]
        engine.set_hot_words(words)
        assert engine._hot_words == words

    def test_set_context_stores_text(self):
        from airtype.core.asr_qwen_vulkan import QwenVulkanEngine

        engine = QwenVulkanEngine()
        engine.set_context("今天天氣很好")
        assert engine._context_text == "今天天氣很好"

    def test_get_supported_languages_returns_list_with_chinese(self):
        from airtype.core.asr_qwen_vulkan import QwenVulkanEngine

        engine = QwenVulkanEngine()
        langs = engine.get_supported_languages()
        assert isinstance(langs, list)
        assert any("zh" in lang for lang in langs)

    def test_get_supported_languages_returns_copy(self):
        from airtype.core.asr_qwen_vulkan import QwenVulkanEngine

        engine = QwenVulkanEngine()
        assert engine.get_supported_languages() is not engine.get_supported_languages()

    def test_unload_clears_loaded_flag(self):
        from airtype.core.asr_qwen_vulkan import QwenVulkanEngine

        engine = QwenVulkanEngine()
        engine._loaded = True
        engine._binary = Path("/fake/chatllm")
        engine.unload()
        assert not engine._loaded
        assert engine._binary is None


class TestVulkanParseOutput:
    """_parse_output 解析邏輯。"""

    def test_parse_json_with_text_key(self):
        from airtype.core.asr_qwen_vulkan import QwenVulkanEngine

        engine = QwenVulkanEngine()
        result = engine._parse_output(json.dumps({"text": "你好世界"}))
        assert result == "你好世界"

    def test_parse_json_with_transcription_key(self):
        from airtype.core.asr_qwen_vulkan import QwenVulkanEngine

        engine = QwenVulkanEngine()
        result = engine._parse_output(json.dumps({"transcription": "Hello world"}))
        assert result == "Hello world"

    def test_parse_plain_text_fallback(self):
        from airtype.core.asr_qwen_vulkan import QwenVulkanEngine

        engine = QwenVulkanEngine()
        result = engine._parse_output("純文字輸出")
        assert result == "純文字輸出"

    def test_parse_empty_output_returns_empty(self):
        from airtype.core.asr_qwen_vulkan import QwenVulkanEngine

        engine = QwenVulkanEngine()
        assert engine._parse_output("") == ""
        assert engine._parse_output("   ") == ""


class TestVulkanBuildPrompt:
    """_build_prompt 提示建構邏輯。"""

    def test_empty_when_no_hot_words_or_context(self):
        from airtype.core.asr_qwen_vulkan import QwenVulkanEngine

        engine = QwenVulkanEngine()
        assert engine._build_prompt() == ""

    def test_includes_context_text(self):
        from airtype.core.asr_qwen_vulkan import QwenVulkanEngine

        engine = QwenVulkanEngine()
        engine.set_context("語境文字")
        assert "語境文字" in engine._build_prompt()

    def test_includes_hot_words(self):
        from airtype.core.asr_engine import HotWord
        from airtype.core.asr_qwen_vulkan import QwenVulkanEngine

        engine = QwenVulkanEngine()
        engine.set_hot_words([HotWord(word="PostgreSQL", weight=8)])
        assert "PostgreSQL" in engine._build_prompt()


class TestVulkanRecognizeWithMockSubprocess:
    """使用 mock subprocess 驗證 recognize() 流程。"""

    def _make_loaded_engine(self, tmp_path: Path) -> tuple[Any, str]:
        from airtype.core.asr_qwen_vulkan import QwenVulkanEngine

        engine = QwenVulkanEngine()
        model_file = tmp_path / "model.gguf"
        model_file.write_bytes(b"\x00")
        mock_binary = tmp_path / "chatllm"

        with patch("airtype.core.asr_qwen_vulkan._find_chatllm_binary", return_value=mock_binary):
            engine.load_model(str(model_file), {})

        return engine, str(model_file)

    def test_recognize_returns_asr_result_on_success(self, tmp_path):
        from airtype.core.asr_engine import ASRResult

        engine, _ = self._make_loaded_engine(tmp_path)
        audio = np.zeros(16000, dtype=np.float32)

        mock_proc_result = MagicMock()
        mock_proc_result.returncode = 0
        mock_proc_result.stdout = json.dumps({"text": "辨識結果"})
        mock_proc_result.stderr = ""

        with patch("subprocess.run", return_value=mock_proc_result):
            result = engine.recognize(audio)

        assert isinstance(result, ASRResult)
        assert result.text == "辨識結果"

    def test_recognize_returns_empty_text_on_failure(self, tmp_path):
        engine, _ = self._make_loaded_engine(tmp_path)
        audio = np.zeros(16000, dtype=np.float32)

        mock_proc_result = MagicMock()
        mock_proc_result.returncode = 1
        mock_proc_result.stdout = ""
        mock_proc_result.stderr = "Error occurred"

        with patch("subprocess.run", return_value=mock_proc_result):
            result = engine.recognize(audio)

        assert result.text == ""

    def test_recognize_confidence_is_0_85(self, tmp_path):
        """Vulkan 路徑固定回傳 0.85 信心分數。"""
        engine, _ = self._make_loaded_engine(tmp_path)
        audio = np.zeros(16000, dtype=np.float32)

        mock_proc_result = MagicMock()
        mock_proc_result.returncode = 0
        mock_proc_result.stdout = json.dumps({"text": "test"})
        mock_proc_result.stderr = ""

        with patch("subprocess.run", return_value=mock_proc_result):
            result = engine.recognize(audio)

        assert result.confidence == pytest.approx(0.85)

    def test_recognize_segment_end_matches_duration(self, tmp_path):
        """時間段 end 應等於音訊長度（秒）。"""
        engine, _ = self._make_loaded_engine(tmp_path)
        audio = np.zeros(16000 * 3, dtype=np.float32)  # 3 秒

        mock_proc_result = MagicMock()
        mock_proc_result.returncode = 0
        mock_proc_result.stdout = json.dumps({"text": "三秒音訊"})
        mock_proc_result.stderr = ""

        with patch("subprocess.run", return_value=mock_proc_result):
            result = engine.recognize(audio)

        assert result.segments[0].end == pytest.approx(3.0)


class TestVulkanWriteWav:
    """_write_wav WAV 格式正確性。"""

    def test_write_wav_creates_valid_16bit_mono_file(self, tmp_path):
        from airtype.core.asr_qwen_vulkan import QwenVulkanEngine

        wav_path = str(tmp_path / "test.wav")
        audio = np.random.uniform(-1.0, 1.0, 8000).astype(np.float32)
        QwenVulkanEngine._write_wav(wav_path, audio)

        with wave.open(wav_path, "rb") as wf:
            assert wf.getnchannels() == 1
            assert wf.getsampwidth() == 2
            assert wf.getframerate() == 16000
            assert wf.getnframes() == len(audio)

    def test_write_wav_clips_to_int16_range(self, tmp_path):
        from airtype.core.asr_qwen_vulkan import QwenVulkanEngine

        wav_path = str(tmp_path / "test_clip.wav")
        # 超出 [-1.0, 1.0] 的音訊
        audio = np.array([2.0, -2.0, 0.5], dtype=np.float32)
        QwenVulkanEngine._write_wav(wav_path, audio)  # 不應拋出錯誤

        with wave.open(wav_path, "rb") as wf:
            assert wf.getnframes() == 3


# ════════════════════════════════════════════════════════════════════════════
# Task 4.1c — 引擎登錄表整合性（兩引擎 ID 正確）
# ════════════════════════════════════════════════════════════════════════════


class TestBothEnginesRegistration:
    """驗證兩引擎同時登錄的需求。"""

    def test_both_engines_register_when_both_available(self):
        """torch+CUDA 與 chatllm.cpp 均可用時，兩個 ID 均應在 registry 中。"""
        from airtype.core.asr_engine import ASREngineRegistry
        from airtype.core.asr_qwen_pytorch import register as register_pytorch
        from airtype.core.asr_qwen_vulkan import register as register_vulkan

        mock_torch = MagicMock()
        mock_torch.cuda.is_available.return_value = True

        registry = ASREngineRegistry()
        with patch.dict(sys.modules, {"torch": mock_torch}):
            register_pytorch(registry)

        with patch("airtype.core.asr_qwen_vulkan._is_chatllm_available", return_value=True):
            register_vulkan(registry)

        assert "qwen3-pytorch-cuda" in registry.registered_ids
        assert "qwen3-vulkan" in registry.registered_ids

    def test_pytorch_id_is_distinct_from_vulkan_id(self):
        from airtype.core.asr_qwen_pytorch import QwenPyTorchEngine
        from airtype.core.asr_qwen_vulkan import QwenVulkanEngine

        assert QwenPyTorchEngine.ENGINE_ID != QwenVulkanEngine.ENGINE_ID


# ════════════════════════════════════════════════════════════════════════════
# Task 4.2 — 整合測試（無 GPU / chatllm 時跳過）
# ════════════════════════════════════════════════════════════════════════════


@pytest.mark.skipif(
    not _HAS_CUDA or not _HAS_PYTORCH_MODEL,
    reason=(
        "跳過 PyTorch CUDA 整合測試："
        f"CUDA={'可用' if _HAS_CUDA else '不可用'}，"
        f"模型={'存在' if _HAS_PYTORCH_MODEL else '不存在（models/asr/qwen3_asr）'}"
    ),
)
class TestPyTorchIntegration:
    """Task 4.2：PyTorch CUDA 整合測試。"""

    @pytest.fixture(scope="class")
    def loaded_engine(self):
        from airtype.core.asr_qwen_pytorch import QwenPyTorchEngine

        engine = QwenPyTorchEngine()
        engine.load_model(str(_PYTORCH_MODEL_DIR), {"device": "cuda"})
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

    def test_recognize_returns_at_least_one_segment(self, loaded_engine):
        audio = np.zeros(16000 * 5, dtype=np.float32)
        result = loaded_engine.recognize(audio)
        assert len(result.segments) >= 1

    def test_lazy_load_then_recognize(self):
        from airtype.core.asr_engine import ASRResult
        from airtype.core.asr_qwen_pytorch import QwenPyTorchEngine

        engine = QwenPyTorchEngine()
        engine.prepare(str(_PYTORCH_MODEL_DIR))
        assert not engine._loaded

        audio = np.zeros(16000, dtype=np.float32)
        result = engine.recognize(audio)
        assert engine._loaded
        assert isinstance(result, ASRResult)
        engine.unload()

    def test_hot_words_do_not_crash_recognize(self, loaded_engine):
        from airtype.core.asr_engine import HotWord

        loaded_engine.set_hot_words([HotWord(word="PostgreSQL", weight=8)])
        audio = np.zeros(16000 * 2, dtype=np.float32)
        result = loaded_engine.recognize(audio)
        assert result is not None
        loaded_engine.set_hot_words([])


@pytest.mark.skipif(
    not _HAS_CHATLLM or not _HAS_GGUF_MODEL,
    reason=(
        "跳過 Vulkan 整合測試："
        f"chatllm.cpp={'可用' if _HAS_CHATLLM else '不可用'}，"
        f"模型={'存在' if _HAS_GGUF_MODEL else '不存在（models/asr/qwen3_asr_q8.gguf）'}"
    ),
)
class TestVulkanIntegration:
    """Task 4.2：Vulkan chatllm.cpp 整合測試。"""

    @pytest.fixture(scope="class")
    def loaded_engine(self):
        from airtype.core.asr_qwen_vulkan import QwenVulkanEngine

        engine = QwenVulkanEngine()
        engine.load_model(str(_GGUF_MODEL_FILE), {})
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

    def test_recognize_returns_at_least_one_segment(self, loaded_engine):
        audio = np.zeros(16000 * 5, dtype=np.float32)
        result = loaded_engine.recognize(audio)
        assert len(result.segments) >= 1

    def test_lazy_load_then_recognize(self):
        from airtype.core.asr_engine import ASRResult
        from airtype.core.asr_qwen_vulkan import QwenVulkanEngine

        engine = QwenVulkanEngine()
        engine.prepare(str(_GGUF_MODEL_FILE))
        assert not engine._loaded

        audio = np.zeros(16000, dtype=np.float32)
        result = engine.recognize(audio)
        assert engine._loaded
        assert isinstance(result, ASRResult)
        engine.unload()
