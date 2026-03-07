"""Breeze-ASR-25 與 sherpa-onnx 引擎單元測試與整合測試。

Task 4.1：使用 mock faster-whisper 的 BreezeAsrEngine 單元測試。
Task 4.2：使用 mock sherpa-onnx 的 SherpaOnnxEngine 單元測試。
Task 4.3：整合測試（模型未下載時跳過）。
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch, call

import numpy as np
import pytest


# ── 可用性旗標（整合測試用）─────────────────────────────────────────────────

def _faster_whisper_available() -> bool:
    try:
        import faster_whisper  # noqa: F401, PLC0415
        return True
    except ImportError:
        return False


def _sherpa_available() -> bool:
    try:
        import sherpa_onnx  # noqa: F401, PLC0415
        return True
    except ImportError:
        return False


_HAS_FASTER_WHISPER = _faster_whisper_available()
_HAS_SHERPA = _sherpa_available()

_BREEZE_MODEL_DIR = Path("models/asr/breeze_asr_25")
_SHERPA_SENSEVOICE_DIR = Path("models/asr/sherpa_sensevoice")
_SHERPA_PARAFORMER_DIR = Path("models/asr/sherpa_paraformer")

_HAS_BREEZE_MODEL = _BREEZE_MODEL_DIR.exists()
_HAS_SENSEVOICE_MODEL = _SHERPA_SENSEVOICE_DIR.exists()


# ════════════════════════════════════════════════════════════════════════════
# Task 4.1 — BreezeAsrEngine 單元測試
# ════════════════════════════════════════════════════════════════════════════


class TestBreezeProtocolConformance:
    """BreezeAsrEngine 符合 ASREngine Protocol。"""

    def test_conforms_to_protocol(self):
        from airtype.core.asr_engine import ASREngine
        from airtype.core.asr_breeze import BreezeAsrEngine

        engine = BreezeAsrEngine()
        assert isinstance(engine, ASREngine)


class TestBreezeEngineId:
    """ENGINE_ID 正確性。"""

    def test_engine_id_is_correct(self):
        from airtype.core.asr_breeze import BreezeAsrEngine

        assert BreezeAsrEngine.ENGINE_ID == "breeze-asr-25"


class TestBreezeGracefulDegradation:
    """可選依賴缺失時優雅降級（Task 4.1 重點）。"""

    def test_import_module_does_not_require_faster_whisper(self):
        """匯入 asr_breeze 模組不需要 faster-whisper 套件。"""
        import airtype.core.asr_breeze  # noqa: F401, PLC0415

    def test_register_returns_false_when_both_backends_missing(self):
        """faster-whisper 與 transformers 均不可用時 register() 應回傳 False。"""
        from airtype.core.asr_engine import ASREngineRegistry
        from airtype.core.asr_breeze import register

        registry = ASREngineRegistry()
        with patch.dict(sys.modules, {"faster_whisper": None, "transformers": None}):
            result = register(registry)

        assert result is False
        assert "breeze-asr-25" not in registry.registered_ids

    def test_register_returns_true_when_faster_whisper_available(self):
        """faster-whisper 可用時 register() 應回傳 True 並登錄 'breeze-asr-25'。"""
        from airtype.core.asr_engine import ASREngineRegistry
        from airtype.core.asr_breeze import register

        registry = ASREngineRegistry()
        mock_fw = MagicMock()
        with patch.dict(sys.modules, {"faster_whisper": mock_fw}):
            result = register(registry)

        assert result is True
        assert "breeze-asr-25" in registry.registered_ids

    def test_register_returns_true_when_only_transformers_available(self):
        """faster-whisper 不可用但 transformers 可用時，仍應登錄。"""
        from airtype.core.asr_engine import ASREngineRegistry
        from airtype.core.asr_breeze import register

        registry = ASREngineRegistry()
        mock_tf = MagicMock()
        with patch.dict(sys.modules, {"faster_whisper": None, "transformers": mock_tf}):
            result = register(registry)

        assert result is True
        assert "breeze-asr-25" in registry.registered_ids


class TestBreezeInitialState:
    """BreezeAsrEngine 初始狀態。"""

    def test_initial_not_loaded(self):
        from airtype.core.asr_breeze import BreezeAsrEngine

        engine = BreezeAsrEngine()
        assert not engine._loaded

    def test_prepare_does_not_load(self, tmp_path):
        from airtype.core.asr_breeze import BreezeAsrEngine

        engine = BreezeAsrEngine()
        engine.prepare(str(tmp_path))
        assert not engine._loaded

    def test_recognize_without_prepare_raises_runtime_error(self):
        from airtype.core.asr_breeze import BreezeAsrEngine

        engine = BreezeAsrEngine()
        with pytest.raises(RuntimeError, match="模型路徑"):
            engine.recognize(np.zeros(16000, dtype=np.float32))


class TestBreezeLoadModel:
    """BreezeAsrEngine.load_model 行為。"""

    def test_load_missing_directory_raises_file_not_found(self):
        from airtype.core.asr_breeze import BreezeAsrEngine

        engine = BreezeAsrEngine()
        with pytest.raises(FileNotFoundError, match="不存在"):
            engine.load_model("/nonexistent/model/path", {})

    def test_load_uses_faster_whisper_when_available(self, tmp_path):
        from airtype.core.asr_breeze import BreezeAsrEngine

        engine = BreezeAsrEngine()
        mock_fw = MagicMock()
        mock_fw.WhisperModel.return_value = MagicMock()

        with patch.dict(sys.modules, {"faster_whisper": mock_fw}):
            engine.load_model(str(tmp_path), {})

        assert engine._loaded
        assert engine._backend == "faster-whisper"
        mock_fw.WhisperModel.assert_called_once()

    def test_load_falls_back_to_transformers_when_no_faster_whisper(self, tmp_path):
        from airtype.core.asr_breeze import BreezeAsrEngine

        engine = BreezeAsrEngine()
        mock_tf = MagicMock()
        mock_pipeline = MagicMock()
        mock_tf.pipeline.return_value = mock_pipeline

        with patch.dict(sys.modules, {"faster_whisper": None, "transformers": mock_tf}):
            engine.load_model(str(tmp_path), {})

        assert engine._loaded
        assert engine._backend == "transformers"

    def test_load_raises_import_error_when_no_backend(self, tmp_path):
        from airtype.core.asr_breeze import BreezeAsrEngine

        engine = BreezeAsrEngine()
        with patch.dict(sys.modules, {"faster_whisper": None, "transformers": None}):
            with pytest.raises(ImportError, match="faster-whisper"):
                engine.load_model(str(tmp_path), {})


class TestBreezeProtocolMethods:
    """ASREngine Protocol 其他方法。"""

    def test_recognize_stream_returns_partial_result(self):
        from airtype.core.asr_engine import PartialResult
        from airtype.core.asr_breeze import BreezeAsrEngine

        engine = BreezeAsrEngine()
        result = engine.recognize_stream(np.zeros(1024, dtype=np.float32))
        assert isinstance(result, PartialResult)
        assert not result.is_final

    def test_set_hot_words_stores_list(self):
        from airtype.core.asr_engine import HotWord
        from airtype.core.asr_breeze import BreezeAsrEngine

        engine = BreezeAsrEngine()
        words = [HotWord(word="PostgreSQL", weight=8)]
        engine.set_hot_words(words)
        assert engine._hot_words == words

    def test_set_context_stores_text(self):
        from airtype.core.asr_breeze import BreezeAsrEngine

        engine = BreezeAsrEngine()
        engine.set_context("今天天氣很好")
        assert engine._context_text == "今天天氣很好"

    def test_get_supported_languages_includes_chinese_and_english(self):
        from airtype.core.asr_breeze import BreezeAsrEngine

        engine = BreezeAsrEngine()
        langs = engine.get_supported_languages()
        assert isinstance(langs, list)
        assert any("zh" in lang for lang in langs)
        assert any("en" in lang for lang in langs)

    def test_get_supported_languages_returns_copy(self):
        from airtype.core.asr_breeze import BreezeAsrEngine

        engine = BreezeAsrEngine()
        assert engine.get_supported_languages() is not engine.get_supported_languages()

    def test_unload_clears_loaded_flag(self):
        from airtype.core.asr_breeze import BreezeAsrEngine

        engine = BreezeAsrEngine()
        engine._loaded = True
        engine._model = MagicMock()
        engine.unload()
        assert not engine._loaded
        assert engine._model is None


class TestBreezeRecognizeWithMock:
    """使用 mock faster-whisper 驗證 recognize() 流程。"""

    def _make_loaded_engine_faster_whisper(self, tmp_path: Path):
        """建立使用 faster-whisper 後端的已載入引擎。"""
        from airtype.core.asr_breeze import BreezeAsrEngine

        mock_fw = MagicMock()
        mock_segment = MagicMock()
        mock_segment.text = "你好世界"
        mock_model = MagicMock()
        mock_info = MagicMock()
        mock_model.transcribe.return_value = (iter([mock_segment]), mock_info)
        mock_fw.WhisperModel.return_value = mock_model

        engine = BreezeAsrEngine()
        with patch.dict(sys.modules, {"faster_whisper": mock_fw}):
            engine.load_model(str(tmp_path), {})

        return engine, mock_fw

    def test_recognize_returns_asr_result(self, tmp_path):
        from airtype.core.asr_engine import ASRResult

        engine, mock_fw = self._make_loaded_engine_faster_whisper(tmp_path)
        audio = np.zeros(16000, dtype=np.float32)

        with patch.dict(sys.modules, {"faster_whisper": mock_fw}):
            result = engine.recognize(audio)

        assert isinstance(result, ASRResult)

    def test_recognize_returns_correct_text(self, tmp_path):
        """辨識文字應來自 faster-whisper segments。"""
        engine, mock_fw = self._make_loaded_engine_faster_whisper(tmp_path)
        audio = np.zeros(16000, dtype=np.float32)

        with patch.dict(sys.modules, {"faster_whisper": mock_fw}):
            result = engine.recognize(audio)

        assert "你好世界" in result.text

    def test_recognize_result_has_segment(self, tmp_path):
        engine, mock_fw = self._make_loaded_engine_faster_whisper(tmp_path)
        audio = np.zeros(32000, dtype=np.float32)  # 2 秒

        with patch.dict(sys.modules, {"faster_whisper": mock_fw}):
            result = engine.recognize(audio)

        assert len(result.segments) >= 1
        assert result.segments[0].end == pytest.approx(2.0)

    def test_recognize_confidence_in_range(self, tmp_path):
        engine, mock_fw = self._make_loaded_engine_faster_whisper(tmp_path)
        audio = np.zeros(16000, dtype=np.float32)

        with patch.dict(sys.modules, {"faster_whisper": mock_fw}):
            result = engine.recognize(audio)

        assert 0.0 <= result.confidence <= 1.0

    def test_recognize_with_transformers_backend(self, tmp_path):
        """transformers 後端也應正確回傳 ASRResult。"""
        from airtype.core.asr_engine import ASRResult
        from airtype.core.asr_breeze import BreezeAsrEngine

        mock_tf = MagicMock()
        mock_pipeline = MagicMock()
        mock_pipeline.return_value = {"text": "Hello World"}
        mock_tf.pipeline.return_value = mock_pipeline

        engine = BreezeAsrEngine()
        with patch.dict(sys.modules, {"faster_whisper": None, "transformers": mock_tf}):
            engine.load_model(str(tmp_path), {})
            audio = np.zeros(16000, dtype=np.float32)
            result = engine.recognize(audio)

        assert isinstance(result, ASRResult)
        assert "Hello World" in result.text

    def test_code_switching_language_detection(self):
        """code-switching 文字（中英混合）語言應被偵測為 zh-TW。"""
        from airtype.core.asr_breeze import BreezeAsrEngine

        engine = BreezeAsrEngine()
        # 超過 30% CJK → zh-TW
        text_zh = "請幫我 check 一下 database 的狀態"
        lang = engine._detect_language(text_zh)
        assert lang == "zh-TW"

        # 純英文 → en
        text_en = "check the database status"
        lang_en = engine._detect_language(text_en)
        assert lang_en == "en"


# ════════════════════════════════════════════════════════════════════════════
# Task 4.2 — SherpaOnnxEngine 單元測試
# ════════════════════════════════════════════════════════════════════════════


def _make_mock_sherpa() -> MagicMock:
    """建立完整的 mock sherpa_onnx 模組。"""
    mock_sherpa = MagicMock()

    # OfflineRecognizer mock
    mock_result = MagicMock()
    mock_result.text = "辨識結果"
    mock_offline_stream = MagicMock()
    mock_offline_stream.result = mock_result
    mock_offline_rec = MagicMock()
    mock_offline_rec.create_stream.return_value = mock_offline_stream
    mock_sherpa.OfflineRecognizer.return_value = mock_offline_rec

    # OnlineRecognizer mock
    mock_online_result = MagicMock()
    mock_online_result.text = "串流結果"
    mock_online_stream = MagicMock()
    mock_online_rec = MagicMock()
    mock_online_rec.create_stream.return_value = mock_online_stream
    mock_online_rec.is_ready.return_value = False
    mock_online_rec.is_endpoint.return_value = True
    mock_online_rec.get_result.return_value = mock_online_result
    mock_sherpa.OnlineRecognizer.return_value = mock_online_rec

    return mock_sherpa


class TestSherpaProtocolConformance:
    """SherpaOnnxEngine 符合 ASREngine Protocol。"""

    def test_conforms_to_protocol(self):
        from airtype.core.asr_engine import ASREngine
        from airtype.core.asr_sherpa import SherpaOnnxEngine

        engine = SherpaOnnxEngine()
        assert isinstance(engine, ASREngine)


class TestSherpaEngineIds:
    """ENGINE_ID 正確性（兩個 ID）。"""

    def test_sensevoice_engine_id_is_correct(self):
        from airtype.core.asr_sherpa import SherpaOnnxEngine

        assert SherpaOnnxEngine.SENSEVOICE_ENGINE_ID == "sherpa-sensevoice"

    def test_paraformer_engine_id_is_correct(self):
        from airtype.core.asr_sherpa import SherpaOnnxEngine

        assert SherpaOnnxEngine.PARAFORMER_ENGINE_ID == "sherpa-paraformer"

    def test_two_ids_are_distinct(self):
        from airtype.core.asr_sherpa import SherpaOnnxEngine

        assert SherpaOnnxEngine.SENSEVOICE_ENGINE_ID != SherpaOnnxEngine.PARAFORMER_ENGINE_ID


class TestSherpaGracefulDegradation:
    """sherpa-onnx 不可用時優雅降級（Task 4.2 重點）。"""

    def test_import_module_does_not_require_sherpa_onnx(self):
        """匯入 asr_sherpa 模組不需要 sherpa_onnx 套件。"""
        import airtype.core.asr_sherpa  # noqa: F401, PLC0415

    def test_register_returns_false_when_sherpa_not_installed(self):
        """sherpa_onnx 未安裝時 register() 應回傳 False，兩個 ID 均不登錄。"""
        from airtype.core.asr_engine import ASREngineRegistry
        from airtype.core.asr_sherpa import register

        registry = ASREngineRegistry()
        with patch.dict(sys.modules, {"sherpa_onnx": None}):
            result = register(registry)

        assert result is False
        assert "sherpa-sensevoice" not in registry.registered_ids
        assert "sherpa-paraformer" not in registry.registered_ids

    def test_register_returns_true_and_registers_both_when_sherpa_available(self):
        """sherpa_onnx 可用時 register() 應回傳 True 並登錄兩個引擎 ID。"""
        from airtype.core.asr_engine import ASREngineRegistry
        from airtype.core.asr_sherpa import register

        registry = ASREngineRegistry()
        mock_sherpa = MagicMock()
        with patch.dict(sys.modules, {"sherpa_onnx": mock_sherpa}):
            result = register(registry)

        assert result is True
        assert "sherpa-sensevoice" in registry.registered_ids
        assert "sherpa-paraformer" in registry.registered_ids

    def test_sensevoice_factory_creates_sensevoice_engine(self):
        """'sherpa-sensevoice' 工廠應建立 model_type='sensevoice' 的引擎。"""
        from airtype.core.asr_engine import ASREngineRegistry
        from airtype.core.asr_sherpa import register, SherpaOnnxEngine

        registry = ASREngineRegistry()
        mock_sherpa = MagicMock()
        with patch.dict(sys.modules, {"sherpa_onnx": mock_sherpa}):
            register(registry)

        engine = registry.get_engine("sherpa-sensevoice")
        assert isinstance(engine, SherpaOnnxEngine)
        assert engine._model_type == "sensevoice"

    def test_paraformer_factory_creates_paraformer_engine(self):
        """'sherpa-paraformer' 工廠應建立 model_type='paraformer' 的引擎。"""
        from airtype.core.asr_engine import ASREngineRegistry
        from airtype.core.asr_sherpa import register, SherpaOnnxEngine

        registry = ASREngineRegistry()
        mock_sherpa = MagicMock()
        with patch.dict(sys.modules, {"sherpa_onnx": mock_sherpa}):
            register(registry)

        engine = registry.get_engine("sherpa-paraformer")
        assert isinstance(engine, SherpaOnnxEngine)
        assert engine._model_type == "paraformer"


class TestSherpaInitialState:
    """SherpaOnnxEngine 初始狀態。"""

    def test_initial_not_loaded(self):
        from airtype.core.asr_sherpa import SherpaOnnxEngine

        engine = SherpaOnnxEngine()
        assert not engine._loaded

    def test_prepare_does_not_load(self, tmp_path):
        from airtype.core.asr_sherpa import SherpaOnnxEngine

        engine = SherpaOnnxEngine()
        engine.prepare(str(tmp_path))
        assert not engine._loaded

    def test_recognize_without_prepare_raises_runtime_error(self):
        from airtype.core.asr_sherpa import SherpaOnnxEngine

        engine = SherpaOnnxEngine()
        with pytest.raises(RuntimeError, match="模型路徑"):
            engine.recognize(np.zeros(16000, dtype=np.float32))

    def test_default_model_type_is_sensevoice(self):
        from airtype.core.asr_sherpa import SherpaOnnxEngine

        engine = SherpaOnnxEngine()
        assert engine._model_type == "sensevoice"


class TestSherpaLoadModel:
    """SherpaOnnxEngine.load_model 行為。"""

    def test_load_missing_directory_raises_file_not_found(self):
        from airtype.core.asr_sherpa import SherpaOnnxEngine

        engine = SherpaOnnxEngine()
        with pytest.raises(FileNotFoundError, match="不存在"):
            engine.load_model("/nonexistent/model/path", {})

    def test_load_model_sets_loaded_flag(self, tmp_path):
        from airtype.core.asr_sherpa import SherpaOnnxEngine

        mock_sherpa = _make_mock_sherpa()
        engine = SherpaOnnxEngine()

        with patch.dict(sys.modules, {"sherpa_onnx": mock_sherpa}):
            engine.load_model(str(tmp_path), {"tokens": str(tmp_path / "tokens.txt")})

        assert engine._loaded

    def test_load_sensevoice_creates_offline_recognizer(self, tmp_path):
        from airtype.core.asr_sherpa import SherpaOnnxEngine

        mock_sherpa = _make_mock_sherpa()
        engine = SherpaOnnxEngine(model_type="sensevoice")

        with patch.dict(sys.modules, {"sherpa_onnx": mock_sherpa}):
            engine.load_model(str(tmp_path), {})

        mock_sherpa.OfflineRecognizer.assert_called_once()
        assert engine._offline_recognizer is not None

    def test_load_paraformer_creates_offline_recognizer(self, tmp_path):
        from airtype.core.asr_sherpa import SherpaOnnxEngine

        mock_sherpa = _make_mock_sherpa()
        engine = SherpaOnnxEngine(model_type="paraformer")

        with patch.dict(sys.modules, {"sherpa_onnx": mock_sherpa}):
            engine.load_model(str(tmp_path), {})

        mock_sherpa.OfflineRecognizer.assert_called_once()
        assert engine._offline_recognizer is not None


class TestSherpaHotWords:
    """sherpa-onnx 熱詞支援（Task 2.3 驗證）。"""

    def test_set_hot_words_writes_temp_file(self):
        """set_hot_words() 應將熱詞寫入臨時檔案。"""
        from airtype.core.asr_engine import HotWord
        from airtype.core.asr_sherpa import SherpaOnnxEngine

        engine = SherpaOnnxEngine()
        engine.set_hot_words([HotWord(word="PostgreSQL", weight=9)])

        assert engine._hotwords_file_path is not None
        hotwords_path = Path(engine._hotwords_file_path)
        assert hotwords_path.exists()
        content = hotwords_path.read_text(encoding="utf-8")
        assert "PostgreSQL" in content

    def test_set_hot_words_stores_list(self):
        from airtype.core.asr_engine import HotWord
        from airtype.core.asr_sherpa import SherpaOnnxEngine

        engine = SherpaOnnxEngine()
        words = [HotWord(word="鼎新", weight=6)]
        engine.set_hot_words(words)
        assert engine._hot_words == words

    def test_set_hot_words_clears_previous(self):
        from airtype.core.asr_engine import HotWord
        from airtype.core.asr_sherpa import SherpaOnnxEngine

        engine = SherpaOnnxEngine()
        engine.set_hot_words([HotWord(word="A", weight=5)])
        engine.set_hot_words([HotWord(word="B", weight=3)])
        assert len(engine._hot_words) == 1
        assert engine._hot_words[0].word == "B"

    def test_set_hot_words_rebuilds_recognizer_when_loaded(self, tmp_path):
        """引擎已載入時 set_hot_words() 應觸發重建 recognizer。"""
        from airtype.core.asr_engine import HotWord
        from airtype.core.asr_sherpa import SherpaOnnxEngine

        mock_sherpa = _make_mock_sherpa()
        engine = SherpaOnnxEngine()

        with patch.dict(sys.modules, {"sherpa_onnx": mock_sherpa}):
            engine.load_model(str(tmp_path), {})
            initial_call_count = mock_sherpa.OfflineRecognizer.call_count

            engine.set_hot_words([HotWord(word="PostgreSQL", weight=9)])
            # 應再次呼叫 OfflineRecognizer 以重建（含熱詞）
            assert mock_sherpa.OfflineRecognizer.call_count > initial_call_count

    def test_hotwords_file_passed_to_offline_recognizer(self, tmp_path):
        """載入時若有熱詞，hotwords_file 應傳遞至 OfflineRecognizerConfig。"""
        from airtype.core.asr_engine import HotWord
        from airtype.core.asr_sherpa import SherpaOnnxEngine

        mock_sherpa = _make_mock_sherpa()
        engine = SherpaOnnxEngine()
        engine.set_hot_words([HotWord(word="PostgreSQL", weight=9)])

        with patch.dict(sys.modules, {"sherpa_onnx": mock_sherpa}):
            engine.load_model(str(tmp_path), {})

        # OfflineRecognizerConfig 應被呼叫含 hotwords_file
        config_calls = mock_sherpa.OfflineRecognizerConfig.call_args_list
        assert len(config_calls) >= 1
        # 確認 hotwords_file 參數存在
        call_kwargs = config_calls[-1].kwargs
        assert "hotwords_file" in call_kwargs
        assert call_kwargs["hotwords_file"] is not None


class TestSherpaStreamRecognize:
    """sherpa-onnx 串流辨識（Task 2.2 驗證）。"""

    def test_recognize_stream_returns_partial_result_when_no_online_recognizer(self):
        """無 OnlineRecognizer 時應回傳空 PartialResult。"""
        from airtype.core.asr_engine import PartialResult
        from airtype.core.asr_sherpa import SherpaOnnxEngine

        engine = SherpaOnnxEngine()
        result = engine.recognize_stream(np.zeros(1024, dtype=np.float32))
        assert isinstance(result, PartialResult)
        assert not result.is_final

    def test_recognize_stream_uses_online_recognizer_when_available(self, tmp_path):
        """有 OnlineRecognizer 時應用串流辨識並回傳 PartialResult。"""
        from airtype.core.asr_engine import PartialResult
        from airtype.core.asr_sherpa import SherpaOnnxEngine

        mock_sherpa = _make_mock_sherpa()
        engine = SherpaOnnxEngine()

        with patch.dict(sys.modules, {"sherpa_onnx": mock_sherpa}):
            # 提供 online_model_path 以觸發 OnlineRecognizer 建立
            engine.load_model(
                str(tmp_path),
                {"online_model_path": str(tmp_path)},
            )
            chunk = np.zeros(1024, dtype=np.float32)
            result = engine.recognize_stream(chunk)

        assert isinstance(result, PartialResult)
        assert isinstance(result.text, str)


class TestSherpaRecognizeWithMock:
    """使用 mock sherpa-onnx 驗證 recognize() 流程（Task 2.1 驗證）。"""

    def _make_loaded_engine(self, tmp_path: Path, model_type: str = "sensevoice"):
        from airtype.core.asr_sherpa import SherpaOnnxEngine

        mock_sherpa = _make_mock_sherpa()
        engine = SherpaOnnxEngine(model_type=model_type)

        with patch.dict(sys.modules, {"sherpa_onnx": mock_sherpa}):
            engine.load_model(str(tmp_path), {})

        return engine, mock_sherpa

    def test_recognize_returns_asr_result(self, tmp_path):
        from airtype.core.asr_engine import ASRResult

        engine, mock_sherpa = self._make_loaded_engine(tmp_path)
        audio = np.zeros(16000, dtype=np.float32)

        with patch.dict(sys.modules, {"sherpa_onnx": mock_sherpa}):
            result = engine.recognize(audio)

        assert isinstance(result, ASRResult)

    def test_recognize_returns_text_from_offline_recognizer(self, tmp_path):
        engine, mock_sherpa = self._make_loaded_engine(tmp_path)
        audio = np.zeros(16000, dtype=np.float32)

        with patch.dict(sys.modules, {"sherpa_onnx": mock_sherpa}):
            result = engine.recognize(audio)

        assert result.text == "辨識結果"

    def test_recognize_segment_end_matches_duration(self, tmp_path):
        engine, mock_sherpa = self._make_loaded_engine(tmp_path)
        audio = np.zeros(16000 * 3, dtype=np.float32)  # 3 秒

        with patch.dict(sys.modules, {"sherpa_onnx": mock_sherpa}):
            result = engine.recognize(audio)

        assert result.segments[0].end == pytest.approx(3.0)

    def test_recognize_confidence_in_range(self, tmp_path):
        engine, mock_sherpa = self._make_loaded_engine(tmp_path)
        audio = np.zeros(16000, dtype=np.float32)

        with patch.dict(sys.modules, {"sherpa_onnx": mock_sherpa}):
            result = engine.recognize(audio)

        assert 0.0 <= result.confidence <= 1.0

    def test_paraformer_engine_also_returns_asr_result(self, tmp_path):
        from airtype.core.asr_engine import ASRResult

        engine, mock_sherpa = self._make_loaded_engine(tmp_path, model_type="paraformer")
        audio = np.zeros(16000, dtype=np.float32)

        with patch.dict(sys.modules, {"sherpa_onnx": mock_sherpa}):
            result = engine.recognize(audio)

        assert isinstance(result, ASRResult)


class TestSherpaProtocolMethods:
    """SherpaOnnxEngine Protocol 其他方法。"""

    def test_set_context_stores_text(self):
        from airtype.core.asr_sherpa import SherpaOnnxEngine

        engine = SherpaOnnxEngine()
        engine.set_context("今天天氣很好")
        assert engine._context_text == "今天天氣很好"

    def test_get_supported_languages_returns_list(self):
        from airtype.core.asr_sherpa import SherpaOnnxEngine

        engine = SherpaOnnxEngine()
        langs = engine.get_supported_languages()
        assert isinstance(langs, list)
        assert len(langs) >= 1

    def test_get_supported_languages_returns_copy(self):
        from airtype.core.asr_sherpa import SherpaOnnxEngine

        engine = SherpaOnnxEngine()
        assert engine.get_supported_languages() is not engine.get_supported_languages()

    def test_unload_clears_loaded_flag(self, tmp_path):
        from airtype.core.asr_sherpa import SherpaOnnxEngine

        mock_sherpa = _make_mock_sherpa()
        engine = SherpaOnnxEngine()

        with patch.dict(sys.modules, {"sherpa_onnx": mock_sherpa}):
            engine.load_model(str(tmp_path), {})

        engine.unload()
        assert not engine._loaded
        assert engine._offline_recognizer is None

    def test_unload_cleans_hotwords_temp_file(self, tmp_path):
        """unload() 應清除熱詞臨時檔案。"""
        from airtype.core.asr_engine import HotWord
        from airtype.core.asr_sherpa import SherpaOnnxEngine

        engine = SherpaOnnxEngine()
        engine.set_hot_words([HotWord(word="PostgreSQL", weight=9)])
        hotwords_path = engine._hotwords_file_path

        engine.unload()
        # 臨時檔案應在 unload 後被刪除
        if hotwords_path:
            assert not Path(hotwords_path).exists()


# ════════════════════════════════════════════════════════════════════════════
# Task 4.3 — 整合測試（模型未下載時跳過）
# ════════════════════════════════════════════════════════════════════════════


@pytest.mark.skipif(
    not _HAS_FASTER_WHISPER or not _HAS_BREEZE_MODEL,
    reason=(
        "跳過 Breeze-ASR-25 整合測試："
        f"faster-whisper={'可用' if _HAS_FASTER_WHISPER else '不可用'}，"
        f"模型={'存在' if _HAS_BREEZE_MODEL else '不存在（models/asr/breeze_asr_25）'}"
    ),
)
class TestBreezeIntegration:
    """Task 4.3：Breeze-ASR-25 整合測試。"""

    @pytest.fixture(scope="class")
    def loaded_engine(self):
        from airtype.core.asr_breeze import BreezeAsrEngine

        engine = BreezeAsrEngine()
        engine.load_model(str(_BREEZE_MODEL_DIR))
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


@pytest.mark.skipif(
    not _HAS_SHERPA or not _HAS_SENSEVOICE_MODEL,
    reason=(
        "跳過 sherpa-onnx 整合測試："
        f"sherpa-onnx={'可用' if _HAS_SHERPA else '不可用'}，"
        f"模型={'存在' if _HAS_SENSEVOICE_MODEL else '不存在（models/asr/sherpa_sensevoice）'}"
    ),
)
class TestSherpaIntegration:
    """Task 4.3：sherpa-onnx 整合測試。"""

    @pytest.fixture(scope="class")
    def loaded_engine(self):
        from airtype.core.asr_sherpa import SherpaOnnxEngine

        engine = SherpaOnnxEngine(model_type="sensevoice")
        engine.load_model(str(_SHERPA_SENSEVOICE_DIR))
        yield engine
        engine.unload()

    def test_recognize_silent_audio_returns_asr_result(self, loaded_engine):
        from airtype.core.asr_engine import ASRResult

        audio = np.zeros(16000 * 3, dtype=np.float32)
        result = loaded_engine.recognize(audio)
        assert isinstance(result, ASRResult)
        assert isinstance(result.text, str)

    def test_recognize_returns_valid_language_code(self, loaded_engine):
        audio = np.zeros(16000, dtype=np.float32)
        result = loaded_engine.recognize(audio)
        assert isinstance(result.language, str)
        assert len(result.language) >= 2
