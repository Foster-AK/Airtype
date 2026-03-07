"""安全性審查自動化測試套件。

驗證四項核心安全需求（PRD §9）：
1. 音訊資料非持久化
2. API 金鑰透過系統 keyring 加密儲存
3. 設定目錄權限 0o700（Unix）
4. 日誌清理（辨識文字不出現於日誌）

執行：pytest tests/test_security.py
"""

from __future__ import annotations

import logging
import stat
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# 1. 音訊資料非持久化
# ---------------------------------------------------------------------------

class TestAudioNonPersistence:
    """音訊資料非持久化需求驗證。"""

    def test_no_audio_files_in_empty_dir(self, tmp_path: Path) -> None:
        """空目錄應回傳 True（無音訊檔案）。"""
        from airtype.core.audio_capture import verify_no_audio_files

        assert verify_no_audio_files(tmp_path) is True

    def test_no_audio_files_with_config_files(self, tmp_path: Path) -> None:
        """目錄中只有 config.json 時應回傳 True。"""
        from airtype.core.audio_capture import verify_no_audio_files

        (tmp_path / "config.json").write_text("{}")
        assert verify_no_audio_files(tmp_path) is True

    @pytest.mark.parametrize("filename", [
        "audio.wav", "recording.mp3", "sample.pcm", "data.raw",
        "speech.flac", "sound.ogg", "clip.m4a", "stream.opus", "voice.aac",
    ])
    def test_detects_audio_file(self, tmp_path: Path, filename: str) -> None:
        """發現任何音訊檔案時應回傳 False（安全性違規）。"""
        from airtype.core.audio_capture import verify_no_audio_files

        (tmp_path / filename).write_bytes(b"\x00" * 16)
        assert verify_no_audio_files(tmp_path) is False

    def test_detects_audio_in_subdirectory(self, tmp_path: Path) -> None:
        """遞迴掃描子目錄中的音訊檔案。"""
        from airtype.core.audio_capture import verify_no_audio_files

        subdir = tmp_path / "cache" / "asr"
        subdir.mkdir(parents=True)
        (subdir / "temp.wav").write_bytes(b"\x00" * 16)
        assert verify_no_audio_files(tmp_path) is False

    def test_nonexistent_dir_returns_true(self, tmp_path: Path) -> None:
        """不存在的目錄應回傳 True（無音訊檔案）。"""
        from airtype.core.audio_capture import verify_no_audio_files

        assert verify_no_audio_files(tmp_path / "nonexistent") is True

    def test_audio_capture_uses_only_memory(self) -> None:
        """AudioCaptureService 的 _callback 只使用記憶體資料結構，不呼叫任何檔案 I/O。"""
        import inspect
        from airtype.core.audio_capture import AudioCaptureService

        source = inspect.getsource(AudioCaptureService._callback)
        # 確認 callback 中沒有 open()、tofile()、wavfile 等檔案 I/O 操作
        # （.write() 是 RingBuffer 的記憶體操作，不在禁止清單內）
        forbidden = ("open(", "tofile(", "wavfile", "soundfile", "scipy.io")
        for token in forbidden:
            assert token not in source, f"_callback 含禁止的檔案 I/O 呼叫：{token}"


# ---------------------------------------------------------------------------
# 2. API 金鑰透過系統 keyring 加密
# ---------------------------------------------------------------------------

class TestKeyringStorage:
    """API 金鑰 keyring 加密需求驗證。"""

    def test_set_and_get_api_key(self) -> None:
        """set_api_key 應呼叫 keyring.set_password，get_api_key 應呼叫 keyring.get_password。"""
        mock_keyring = MagicMock()
        mock_keyring.get_password.return_value = "sk-test-key-12345"

        with patch.dict("sys.modules", {"keyring": mock_keyring}):
            from airtype.config import get_api_key, set_api_key, KEYRING_SERVICE

            set_api_key("openai", "sk-test-key-12345")
            mock_keyring.set_password.assert_called_once_with(
                KEYRING_SERVICE, "openai", "sk-test-key-12345"
            )

            result = get_api_key("openai")
            mock_keyring.get_password.assert_called_once_with(KEYRING_SERVICE, "openai")
            assert result == "sk-test-key-12345"

    def test_delete_api_key_when_none(self) -> None:
        """set_api_key(provider, None) 應呼叫 keyring.delete_password。"""
        mock_keyring = MagicMock()
        mock_keyring.errors = MagicMock()
        mock_keyring.errors.PasswordDeleteError = Exception

        with patch.dict("sys.modules", {"keyring": mock_keyring}):
            from airtype.config import set_api_key

            set_api_key("openai", None)
            mock_keyring.delete_password.assert_called_once()

    def test_api_key_not_in_config_json(self, tmp_path: Path) -> None:
        """config.json 不應包含 api_key 或 api_key_encrypted 欄位。"""
        from airtype.config import AirtypeConfig

        cfg = AirtypeConfig()
        config_file = tmp_path / "config.json"
        cfg.save(config_file)

        import json
        data = json.loads(config_file.read_text(encoding="utf-8"))
        llm_section = data.get("llm", {})
        assert "api_key" not in llm_section, "config.json 包含明文 api_key"
        assert "api_key_encrypted" not in llm_section, "config.json 包含 api_key_encrypted"

    def test_get_api_key_returns_none_on_keyring_error(self) -> None:
        """keyring 不可用時 get_api_key 應回傳 None，不拋出例外。"""
        mock_keyring = MagicMock()
        mock_keyring.get_password.side_effect = RuntimeError("keyring unavailable")

        with patch.dict("sys.modules", {"keyring": mock_keyring}):
            from airtype.config import get_api_key

            result = get_api_key("openai")
            assert result is None

    def test_set_api_key_silent_on_keyring_error(self) -> None:
        """keyring 不可用時 set_api_key 應靜默失敗，不拋出例外。"""
        mock_keyring = MagicMock()
        mock_keyring.set_password.side_effect = RuntimeError("keyring unavailable")

        with patch.dict("sys.modules", {"keyring": mock_keyring}):
            from airtype.config import set_api_key

            # 不應拋出例外
            set_api_key("openai", "sk-abc")


# ---------------------------------------------------------------------------
# 3. 設定目錄權限 0o700
# ---------------------------------------------------------------------------

class TestConfigDirPermissions:
    """設定目錄權限需求驗證。"""

    @pytest.mark.skipif(sys.platform == "win32", reason="Unix only")
    def test_correct_permissions_returns_true(self, tmp_path: Path) -> None:
        """0o700 權限應回傳 True。"""
        import airtype.config as cfg_module

        test_dir = tmp_path / ".airtype"
        test_dir.mkdir(mode=0o700)

        with patch.object(cfg_module, "CONFIG_DIR", test_dir):
            result = cfg_module.verify_config_dir_permissions()

        assert result is True

    @pytest.mark.skipif(sys.platform == "win32", reason="Unix only")
    def test_wrong_permissions_returns_false(self, tmp_path: Path) -> None:
        """非 0o700 權限應回傳 False 並發出警告。"""
        import airtype.config as cfg_module

        test_dir = tmp_path / ".airtype"
        test_dir.mkdir(mode=0o755)

        with patch.object(cfg_module, "CONFIG_DIR", test_dir):
            result = cfg_module.verify_config_dir_permissions()

        assert result is False

    def test_windows_always_returns_true(self) -> None:
        """Windows 平台應直接回傳 True（不支援 Unix 權限）。"""
        import airtype.config as cfg_module

        with patch("sys.platform", "win32"):
            result = cfg_module.verify_config_dir_permissions()

        assert result is True

    def test_nonexistent_dir_returns_true(self, tmp_path: Path) -> None:
        """不存在的目錄應回傳 True（無需驗證）。"""
        import airtype.config as cfg_module

        with patch.object(cfg_module, "CONFIG_DIR", tmp_path / "nonexistent"):
            result = cfg_module.verify_config_dir_permissions()

        assert result is True

    @pytest.mark.skipif(sys.platform == "win32", reason="Unix only")
    def test_ensure_config_dir_sets_700(self, tmp_path: Path) -> None:
        """_ensure_config_dir() 建立目錄後應具有 0o700 權限。"""
        import airtype.config as cfg_module

        new_dir = tmp_path / ".airtype"
        with patch.object(cfg_module, "CONFIG_DIR", new_dir):
            cfg_module._ensure_config_dir()

        mode = stat.S_IMODE(new_dir.stat().st_mode)
        assert mode == 0o700, f"期望 0o700，實際 0o{mode:o}"


# ---------------------------------------------------------------------------
# 4. 日誌清理
# ---------------------------------------------------------------------------

class TestLogSanitization:
    """日誌清理需求驗證（辨識文字不出現於日誌）。"""

    def _make_filter(self):
        from airtype.logging_setup import SanitizingFilter
        return SanitizingFilter()

    def _apply_filter(self, args: tuple) -> tuple:
        """建立 LogRecord，套用 filter，回傳處理後的 args。"""
        record = logging.LogRecord(
            name="test", level=logging.DEBUG,
            pathname="", lineno=0,
            msg="msg: %s", args=args, exc_info=None,
        )
        f = self._make_filter()
        f.filter(record)
        return record.args  # type: ignore[return-value]

    def test_recognized_text_is_redacted(self) -> None:
        """辨識的使用者文字（含空格，≥15 字元）應被遮蔽。"""
        result = self._apply_filter(("my password is 12345",))
        assert result == ("[REDACTED]",), f"期望 [REDACTED]，實際 {result}"
        assert "my password is 12345" not in str(result)

    def test_chinese_recognized_text_is_redacted(self) -> None:
        """中文辨識文字（含 CJK 字元，≥15 字元）應被遮蔽。"""
        long_cjk = "今天天氣很好我想去公園散步看看花草"  # 17 個中文字
        result = self._apply_filter((long_cjk,))
        assert result == ("[REDACTED]",)

    def test_short_string_not_redacted(self) -> None:
        """短字串（< 15 字元）不應被遮蔽。"""
        result = self._apply_filter(("hello world",))
        assert result == ("hello world",)

    def test_numeric_arg_not_redacted(self) -> None:
        """數值參數不應被遮蔽。"""
        result = self._apply_filter((42,))
        assert result == (42,)

    def test_file_path_not_redacted(self) -> None:
        """檔案路徑不應被遮蔽（以 / 或 ~ 開頭）。"""
        path = "/home/user/.airtype/config.json"
        result = self._apply_filter((path,))
        assert result == (path,), f"路徑不應被遮蔽：{result}"

    def test_url_not_redacted(self) -> None:
        """URL 不應被遮蔽（含 ://）。"""
        url = "https://api.openai.com/v1/chat"
        result = self._apply_filter((url,))
        assert result == (url,)

    def test_dict_args_sanitized(self) -> None:
        """dict 形式的 args 也應被清理。"""
        from airtype.logging_setup import SanitizingFilter

        f = SanitizingFilter()
        # 先建立 LogRecord（空 args），再手動設定 dict args 以避免建構函式的型別檢查衝突
        record = logging.LogRecord(
            name="test", level=logging.DEBUG,
            pathname="", lineno=0,
            msg="msg: %(text)s",
            args=(),
            exc_info=None,
        )
        record.args = {"text": "this is a long recognized sentence from the user"}
        f.filter(record)
        assert record.args["text"] == "[REDACTED]"  # type: ignore[index]

    def test_filter_allows_record_through(self) -> None:
        """filter() 應永遠回傳 True（不丟棄 log record）。"""
        from airtype.logging_setup import SanitizingFilter

        f = SanitizingFilter()
        record = logging.LogRecord(
            name="test", level=logging.DEBUG,
            pathname="", lineno=0,
            msg="normal log message", args=(), exc_info=None,
        )
        assert f.filter(record) is True

    def test_log_output_does_not_contain_recognized_text(self) -> None:
        """完整 logging 流程：辨識文字不出現在格式化後的輸出中。"""
        import io
        from airtype.logging_setup import SanitizingFilter

        stream = io.StringIO()
        handler = logging.StreamHandler(stream)
        handler.addFilter(SanitizingFilter())
        handler.setFormatter(logging.Formatter("%(message)s"))

        test_logger = logging.getLogger("test_security_output")
        test_logger.addHandler(handler)
        test_logger.setLevel(logging.DEBUG)

        recognized_text = "my password is 12345"
        test_logger.debug("辨識結果：%s", recognized_text)

        output = stream.getvalue()
        assert recognized_text not in output, f"辨識文字出現於日誌輸出：{output!r}"
        assert "[REDACTED]" in output

        test_logger.removeHandler(handler)
