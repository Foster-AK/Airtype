"""sherpa-onnx 引擎熱詞功能單元測試。

涵蓋：
- _write_hotwords_file() 產生正確的 sherpa-onnx hotwords 格式（word :weight）
- _build_offline_recognizer() 傳遞 hotwords_file 參數
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from airtype.core.asr_engine import HotWord


class TestWriteHotwordsFile:
    """測試 _write_hotwords_file() 產生正確的 sherpa-onnx hotwords 格式。"""

    def _make_engine(self):
        from airtype.core.asr_sherpa import SherpaOnnxEngine
        return SherpaOnnxEngine(model_type="sensevoice")

    def test_hotwords_file_format_includes_weight(self) -> None:
        """每行應為 'word :weight' 格式。"""
        engine = self._make_engine()
        engine._hot_words = [HotWord(word="PostgreSQL", weight=9)]
        engine._write_hotwords_file()

        assert engine._hotwords_file_path is not None
        content = Path(engine._hotwords_file_path).read_text(encoding="utf-8")
        assert "PostgreSQL :9" in content
        # 清理臨時檔案
        Path(engine._hotwords_file_path).unlink(missing_ok=True)

    def test_hotwords_file_multiple_words(self) -> None:
        """多個熱詞應各佔一行。"""
        engine = self._make_engine()
        engine._hot_words = [
            HotWord(word="龔玉惠", weight=7),
            HotWord(word="鼎新", weight=8),
        ]
        engine._write_hotwords_file()

        content = Path(engine._hotwords_file_path).read_text(encoding="utf-8")
        lines = [line for line in content.strip().splitlines() if line.strip()]
        assert len(lines) == 2
        assert "龔玉惠 :7" in lines[0]
        assert "鼎新 :8" in lines[1]
        Path(engine._hotwords_file_path).unlink(missing_ok=True)

    def test_hotwords_file_empty_list(self) -> None:
        """空列表不應產生檔案。"""
        engine = self._make_engine()
        engine._hot_words = []
        engine._write_hotwords_file()
        assert engine._hotwords_file_path is None


class TestBuildOfflineRecognizerHotwords:
    """測試 _build_offline_recognizer() 傳遞 hotwords_file 參數。"""

    def _make_engine(self):
        from airtype.core.asr_sherpa import SherpaOnnxEngine
        return SherpaOnnxEngine(model_type="sensevoice")

    def test_sensevoice_passes_hotwords_file(self) -> None:
        """SenseVoice 工廠方法應收到 hotwords_file 參數。"""
        engine = self._make_engine()
        engine._hotwords_file_path = "/tmp/test_hotwords.txt"

        mock_sherpa = MagicMock()
        mock_sherpa.OfflineRecognizer.from_sense_voice.return_value = MagicMock()

        engine._build_offline_recognizer(
            mock_sherpa, Path("/fake/model"), {"tokens": "/fake/tokens.txt", "model": "/fake/model.onnx"}
        )

        call_kwargs = mock_sherpa.OfflineRecognizer.from_sense_voice.call_args
        assert "hotwords_file" in (call_kwargs.kwargs or {}), \
            "from_sense_voice() 未收到 hotwords_file 參數"
        assert call_kwargs.kwargs["hotwords_file"] == "/tmp/test_hotwords.txt"

    def test_paraformer_passes_hotwords_file(self) -> None:
        """Paraformer 工廠方法應收到 hotwords_file 參數。"""
        from airtype.core.asr_sherpa import SherpaOnnxEngine
        engine = SherpaOnnxEngine(model_type="paraformer")
        engine._hotwords_file_path = "/tmp/test_hotwords.txt"

        mock_sherpa = MagicMock()
        mock_sherpa.OfflineRecognizer.from_paraformer.return_value = MagicMock()

        engine._build_offline_recognizer(
            mock_sherpa, Path("/fake/model"), {"tokens": "/fake/tokens.txt", "model": "/fake/model.onnx"}
        )

        call_kwargs = mock_sherpa.OfflineRecognizer.from_paraformer.call_args
        assert "hotwords_file" in (call_kwargs.kwargs or {}), \
            "from_paraformer() 未收到 hotwords_file 參數"

    def test_no_hotwords_file_when_none(self) -> None:
        """hotwords_file_path 為 None 時不應傳遞 hotwords_file。"""
        engine = self._make_engine()
        engine._hotwords_file_path = None

        mock_sherpa = MagicMock()
        mock_sherpa.OfflineRecognizer.from_sense_voice.return_value = MagicMock()

        engine._build_offline_recognizer(
            mock_sherpa, Path("/fake/model"), {"tokens": "/fake/tokens.txt", "model": "/fake/model.onnx"}
        )

        call_kwargs = mock_sherpa.OfflineRecognizer.from_sense_voice.call_args
        assert "hotwords_file" not in (call_kwargs.kwargs or {}), \
            "hotwords_file_path 為 None 時不應傳遞 hotwords_file"
