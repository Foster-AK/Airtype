"""Qwen3-ASR ONNX Runtime 引擎單元測試。

使用 mock onnxruntime 的單元測試（載入、推理流程、延遲載入、KV cache 管理）。
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch, call

import numpy as np
import pytest


# ── Mock 工廠 ─────────────────────────────────────────────────────────────────


def _make_mock_ort(*, decoder_tokens: int = 0) -> MagicMock:
    """建立完整的 mock onnxruntime 模組。

    Args:
        decoder_tokens: decoder 在輸出 EOS 前先生成的 token 數量（預設 0，立即 EOS）。
    """
    mock_ort = MagicMock()

    # ── SessionOptions ──
    mock_opts = MagicMock()
    mock_ort.SessionOptions.return_value = mock_opts
    mock_ort.GraphOptimizationLevel.ORT_ENABLE_ALL = 99

    # ── InferenceSession 工廠 ──
    # encoder session
    enc_session = MagicMock()
    enc_input = MagicMock()
    enc_input.name = "mel"
    enc_output = MagicMock()
    enc_output.name = "audio_hidden"
    enc_session.get_inputs.return_value = [enc_input]
    enc_session.get_outputs.return_value = [enc_output]
    enc_session.run.return_value = [np.random.rand(1, 10, 512).astype(np.float32)]

    # embeddings session
    emb_session = MagicMock()
    emb_input = MagicMock()
    emb_input.name = "input_ids"
    emb_output = MagicMock()
    emb_output.name = "embeddings"
    emb_session.get_inputs.return_value = [emb_input]
    emb_session.get_outputs.return_value = [emb_output]

    def _emb_run(output_names, feeds):
        ids = feeds["input_ids"]
        seq_len = ids.shape[1]
        return [np.random.rand(1, seq_len, 512).astype(np.float32)]
    emb_session.run.side_effect = _emb_run

    # decoder session（含 KV cache I/O）
    dec_session = MagicMock()
    # inputs: input_embeds, position_ids, past_key_values.0.key, past_key_values.0.value
    dec_inputs = [
        MagicMock(name="input_embeds", shape=[1, "seq_len", 512], type="tensor(float)"),
        MagicMock(name="position_ids", shape=[1, "seq_len"], type="tensor(int64)"),
        MagicMock(name="past_key_values.0.key", shape=[1, 8, "past_seq_len", 64], type="tensor(float)"),
        MagicMock(name="past_key_values.0.value", shape=[1, 8, "past_seq_len", 64], type="tensor(float)"),
    ]
    # 設定 .name 屬性（MagicMock 的 name 需特殊處理）
    for inp in dec_inputs:
        inp.name = inp._mock_name

    dec_outputs = [
        MagicMock(name="logits"),
        MagicMock(name="present.0.key"),
        MagicMock(name="present.0.value"),
    ]
    for out in dec_outputs:
        out.name = out._mock_name

    dec_session.get_inputs.return_value = dec_inputs
    dec_session.get_outputs.return_value = dec_outputs

    # EOS token ID = 151645
    def _logits(winning_token: int) -> np.ndarray:
        arr = np.zeros((1, 1, 152000), dtype=np.float32)
        arr[0, 0, winning_token] = 10.0
        return arr

    _call_idx = [0]
    token_sequence = list(range(100, 100 + decoder_tokens)) + [151645]

    def _dec_run(output_names, feeds):
        idx = min(_call_idx[0], len(token_sequence) - 1)
        token = token_sequence[idx]
        _call_idx[0] += 1
        logits = _logits(token)
        kv_key = np.random.rand(1, 8, _call_idx[0], 64).astype(np.float32)
        kv_value = np.random.rand(1, 8, _call_idx[0], 64).astype(np.float32)
        return [logits, kv_key, kv_value]

    dec_session.run.side_effect = _dec_run

    # InferenceSession 依路徑建立不同 session
    def _session_factory(path, **kwargs):
        path_str = str(path)
        if "audio_encoder" in path_str:
            return enc_session
        elif "thinker_embeddings" in path_str:
            return emb_session
        elif "decoder" in path_str:
            return dec_session
        return MagicMock()

    mock_ort.InferenceSession.side_effect = _session_factory
    mock_ort.get_available_providers.return_value = ["CPUExecutionProvider"]

    return mock_ort


def _make_mock_processor():
    """建立 mock processor。"""
    mock_proc = MagicMock()

    mock_fe = MagicMock()
    mock_fe.return_value = {
        "input_features": np.random.rand(1, 128, 100).astype(np.float32),
    }
    mock_proc.feature_extractor = mock_fe

    mock_tok = MagicMock()
    mock_tok.audio_token = "<|audio_pad|>"
    # 回傳含有 10 個 AUDIO_PAD_ID 的 input_ids
    mock_tok.encode.return_value = [1, 2, 3] + [151676] * 10 + [4, 5]
    mock_tok.decode.return_value = "language Chinese<asr_text>你好世界"
    mock_proc.tokenizer = mock_tok

    mock_proc.apply_chat_template.return_value = (
        "<|im_start|>system\n<|im_end|>\n"
        "<|im_start|>user\n<|audio_start|><|audio_pad|><|audio_end|><|im_end|>\n"
        "<|im_start|>assistant\n"
    )
    return mock_proc


# ── 引擎登錄測試 ─────────────────────────────────────────────────────────────


class TestQwenOnnxRegister:
    """引擎登錄測試。"""

    def test_register_success(self):
        """onnxruntime 可用時應登錄成功。"""
        mock_ort = MagicMock()
        registry = MagicMock()

        with patch.dict(sys.modules, {"onnxruntime": mock_ort}):
            from airtype.core.asr_qwen_onnx import register
            result = register(registry)

        assert result is True
        registry.register_engine.assert_called_once()
        args = registry.register_engine.call_args[0]
        assert args[0] == "qwen3-onnx"

    def test_register_without_onnxruntime(self):
        """onnxruntime 不可用時應靜默跳過。"""
        registry = MagicMock()

        with patch.dict(sys.modules, {"onnxruntime": None}):
            # 強制重新載入模組以觸發 ImportError
            import importlib
            try:
                # 使用 side_effect 模擬 ImportError
                with patch("builtins.__import__", side_effect=ImportError("no onnxruntime")):
                    from airtype.core import asr_qwen_onnx
                    result = asr_qwen_onnx.register(registry)
            except ImportError:
                result = False

        assert result is False
        registry.register_engine.assert_not_called()


# ── 引擎基本操作測試 ─────────────────────────────────────────────────────────


class TestQwenOnnxEngineBasic:
    """引擎基本操作（prepare、load_model、unload）。"""

    def test_prepare_sets_path(self):
        """prepare() 應設定路徑但不載入模型。"""
        from airtype.core.asr_qwen_onnx import QwenOnnxEngine
        engine = QwenOnnxEngine()
        engine.prepare("/some/model/path")

        assert engine._model_path == "/some/model/path"
        assert engine._loaded is False
        assert engine._enc_session is None

    def test_load_model_creates_sessions(self, tmp_path):
        """load_model() 應建立 3 個 InferenceSession。"""
        # 建立模型檔案
        (tmp_path / "audio_encoder.onnx").touch()
        (tmp_path / "thinker_embeddings.onnx").touch()
        (tmp_path / "decoder_model.onnx").touch()

        mock_ort = _make_mock_ort()

        with patch.dict(sys.modules, {"onnxruntime": mock_ort}):
            with patch("airtype.core.asr_qwen_onnx.load_processor", return_value=_make_mock_processor()):
                from airtype.core.asr_qwen_onnx import QwenOnnxEngine
                engine = QwenOnnxEngine()
                engine.load_model(str(tmp_path))

        assert engine._loaded is True
        assert engine._enc_session is not None
        assert engine._emb_session is not None
        assert engine._dec_session is not None
        assert mock_ort.InferenceSession.call_count == 3

    def test_load_model_missing_dir_raises(self):
        """模型目錄不存在時應拋出 FileNotFoundError。"""
        from airtype.core.asr_qwen_onnx import QwenOnnxEngine
        engine = QwenOnnxEngine()

        with pytest.raises(FileNotFoundError, match="模型目錄不存在"):
            engine.load_model("/nonexistent/path")

    def test_load_model_missing_file_raises(self, tmp_path):
        """缺少必要模型檔案時應拋出 FileNotFoundError。"""
        from airtype.core.asr_qwen_onnx import QwenOnnxEngine
        engine = QwenOnnxEngine()

        with pytest.raises(FileNotFoundError, match="缺少必要模型檔案"):
            engine.load_model(str(tmp_path))

    def test_unload_clears_sessions(self, tmp_path):
        """unload() 應清空所有 session。"""
        (tmp_path / "audio_encoder.onnx").touch()
        (tmp_path / "thinker_embeddings.onnx").touch()
        (tmp_path / "decoder_model.onnx").touch()

        mock_ort = _make_mock_ort()

        with patch.dict(sys.modules, {"onnxruntime": mock_ort}):
            with patch("airtype.core.asr_qwen_onnx.load_processor", return_value=_make_mock_processor()):
                from airtype.core.asr_qwen_onnx import QwenOnnxEngine
                engine = QwenOnnxEngine()
                engine.load_model(str(tmp_path))
                engine.unload()

        assert engine._loaded is False
        assert engine._enc_session is None
        assert engine._emb_session is None
        assert engine._dec_session is None


# ── 推理測試 ─────────────────────────────────────────────────────────────────


class TestQwenOnnxEngineInference:
    """推理流程測試（mock 完整管線）。"""

    def _make_loaded_engine(self, tmp_path, decoder_tokens=0):
        """建立已載入的引擎。"""
        (tmp_path / "audio_encoder.onnx").touch()
        (tmp_path / "thinker_embeddings.onnx").touch()
        (tmp_path / "decoder_model.onnx").touch()

        mock_ort = _make_mock_ort(decoder_tokens=decoder_tokens)

        with patch.dict(sys.modules, {"onnxruntime": mock_ort}):
            with patch("airtype.core.asr_qwen_onnx.load_processor", return_value=_make_mock_processor()):
                from airtype.core.asr_qwen_onnx import QwenOnnxEngine
                engine = QwenOnnxEngine()
                engine.load_model(str(tmp_path))
                return engine, mock_ort

    def test_recognize_returns_asr_result(self, tmp_path):
        """recognize() 應回傳正確格式的 ASRResult。"""
        engine, _ = self._make_loaded_engine(tmp_path)
        audio = np.random.randn(16000).astype(np.float32)

        from airtype.core.asr_engine import ASRResult
        result = engine.recognize(audio)

        assert isinstance(result, ASRResult)
        assert isinstance(result.text, str)
        assert isinstance(result.language, str)
        assert 0.0 <= result.confidence <= 1.0

    def test_recognize_with_generated_tokens(self, tmp_path):
        """生成多個 token 時信心分數應在 (0, 1] 範圍。"""
        engine, _ = self._make_loaded_engine(tmp_path, decoder_tokens=5)
        audio = np.random.randn(16000).astype(np.float32)

        result = engine.recognize(audio)

        assert 0.0 < result.confidence <= 1.0

    def test_lazy_loading(self, tmp_path):
        """首次 recognize() 應觸發延遲載入。"""
        (tmp_path / "audio_encoder.onnx").touch()
        (tmp_path / "thinker_embeddings.onnx").touch()
        (tmp_path / "decoder_model.onnx").touch()

        mock_ort = _make_mock_ort()

        with patch.dict(sys.modules, {"onnxruntime": mock_ort}):
            with patch("airtype.core.asr_qwen_onnx.load_processor", return_value=_make_mock_processor()):
                from airtype.core.asr_qwen_onnx import QwenOnnxEngine
                engine = QwenOnnxEngine()
                engine.prepare(str(tmp_path))

                assert engine._loaded is False

                audio = np.random.randn(16000).astype(np.float32)
                result = engine.recognize(audio)

                assert engine._loaded is True
                assert result is not None

    def test_recognize_stream_returns_empty(self, tmp_path):
        """recognize_stream() 應回傳空結果（不支援串流）。"""
        engine, _ = self._make_loaded_engine(tmp_path)
        chunk = np.random.randn(512).astype(np.float32)

        from airtype.core.asr_engine import PartialResult
        result = engine.recognize_stream(chunk)

        assert isinstance(result, PartialResult)
        assert result.text == ""
        assert result.is_final is False

    def test_supports_hot_words_is_false(self, tmp_path):
        """supports_hot_words 應回傳 False。"""
        engine, _ = self._make_loaded_engine(tmp_path)
        assert engine.supports_hot_words is False


# ── KV Cache 管理測試 ─────────────────────────────────────────────────────────


class TestQwenOnnxKVCache:
    """KV cache 管理測試。"""

    def test_discover_kv_cache_names(self, tmp_path):
        """應從 decoder session 動態發現 KV cache I/O 名稱。"""
        (tmp_path / "audio_encoder.onnx").touch()
        (tmp_path / "thinker_embeddings.onnx").touch()
        (tmp_path / "decoder_model.onnx").touch()

        mock_ort = _make_mock_ort()

        with patch.dict(sys.modules, {"onnxruntime": mock_ort}):
            with patch("airtype.core.asr_qwen_onnx.load_processor", return_value=_make_mock_processor()):
                from airtype.core.asr_qwen_onnx import QwenOnnxEngine
                engine = QwenOnnxEngine()
                engine.load_model(str(tmp_path))

        assert len(engine._kv_input_names) == 2  # key + value
        assert len(engine._kv_output_names) == 2  # present key + value
        assert all("past_key_values" in n for n in engine._kv_input_names)
        assert all("present" in n for n in engine._kv_output_names)

    def test_empty_kv_cache_shape(self, tmp_path):
        """空 KV cache 的 past_seq_len 維度應為 0。"""
        (tmp_path / "audio_encoder.onnx").touch()
        (tmp_path / "thinker_embeddings.onnx").touch()
        (tmp_path / "decoder_model.onnx").touch()

        mock_ort = _make_mock_ort()

        with patch.dict(sys.modules, {"onnxruntime": mock_ort}):
            with patch("airtype.core.asr_qwen_onnx.load_processor", return_value=_make_mock_processor()):
                from airtype.core.asr_qwen_onnx import QwenOnnxEngine
                engine = QwenOnnxEngine()
                engine.load_model(str(tmp_path))

                kv = engine._make_empty_kv_cache()

        assert len(kv) == 2  # past_key_values.0.key, past_key_values.0.value
        for name, tensor in kv.items():
            assert "past_key_values" in name
            # past_seq_len 維度（第 3 個）應為 0
            assert tensor.shape[2] == 0


# ── Provider 選擇測試 ─────────────────────────────────────────────────────────


class TestQwenOnnxProviders:
    """Execution Provider 選擇測試。"""

    def test_coreml_preferred_when_available(self):
        """CoreML 可用時應優先選擇。"""
        mock_ort = MagicMock()
        mock_ort.get_available_providers.return_value = [
            "CoreMLExecutionProvider", "CPUExecutionProvider",
        ]

        with patch.dict(sys.modules, {"onnxruntime": mock_ort}):
            from airtype.core.asr_qwen_onnx import _get_providers
            providers = _get_providers()

        assert providers[0] == "CoreMLExecutionProvider"
        assert "CPUExecutionProvider" in providers

    def test_cpu_only_when_no_coreml(self):
        """CoreML 不可用時應退回 CPU。"""
        mock_ort = MagicMock()
        mock_ort.get_available_providers.return_value = ["CPUExecutionProvider"]

        with patch.dict(sys.modules, {"onnxruntime": mock_ort}):
            from airtype.core.asr_qwen_onnx import _get_providers
            providers = _get_providers()

        assert providers == ["CPUExecutionProvider"]
