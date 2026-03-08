"""airtype.config 單元測試與整合測試。"""

import json
import logging
import os
import subprocess
import sys
from pathlib import Path

import pytest

import airtype.logging_setup as _ls
from airtype.config import (
    AirtypeConfig,
    AppearanceConfig,
    DictionaryConfig,
    GeneralConfig,
    LlmConfig,
    ShortcutsConfig,
    VoiceConfig,
)
from airtype.logging_setup import setup_logging


@pytest.fixture()
def reset_logging():
    """重置 logging_setup 模組狀態，避免測試間互相干擾。"""
    original_level = logging.getLogger().level
    original_initialized = _ls._initialized
    yield
    logging.getLogger().setLevel(original_level)
    _ls._initialized = original_initialized


# ---------------------------------------------------------------------------
# Structured logging — spec: project-structure/spec.md §Structured logging
# ---------------------------------------------------------------------------

class TestLogging:
    def test_default_log_level_is_info(self, reset_logging):
        """預設 log_level 為 INFO → root logger 等級應為 INFO。"""
        setup_logging("INFO")
        assert logging.getLogger().level == logging.INFO

    def test_custom_log_level_debug(self, reset_logging):
        """config log_level=DEBUG → root logger 等級應設為 DEBUG（Scenario: Custom log level）。"""
        setup_logging("DEBUG")
        assert logging.getLogger().level == logging.DEBUG

    def test_custom_log_level_warning(self, reset_logging):
        """config log_level=WARNING → root logger 等級應設為 WARNING。"""
        setup_logging("WARNING")
        assert logging.getLogger().level == logging.WARNING

    def test_custom_log_level_error(self, reset_logging):
        """config log_level=ERROR → root logger 等級應設為 ERROR。"""
        setup_logging("ERROR")
        assert logging.getLogger().level == logging.ERROR

    def test_level_update_after_init(self, reset_logging):
        """二次呼叫 setup_logging 應更新等級，不重複新增 handler。"""
        setup_logging("INFO")
        handler_count = len(logging.getLogger().handlers)
        setup_logging("DEBUG")
        assert logging.getLogger().level == logging.DEBUG
        assert len(logging.getLogger().handlers) == handler_count


# ---------------------------------------------------------------------------
# 6.1 單元測試
# ---------------------------------------------------------------------------

class TestDefaultValues:
    def test_general_defaults(self):
        cfg = AirtypeConfig()
        assert cfg.general.language == "zh_TW"
        assert cfg.general.silence_timeout == 1.5
        assert cfg.general.auto_start is False
        assert cfg.general.start_minimized is True
        assert cfg.general.log_level == "INFO"

    def test_voice_defaults(self):
        cfg = AirtypeConfig()
        assert cfg.voice.asr_model == "qwen3-asr-0.6b"
        assert cfg.voice.asr_inference_backend == "auto"
        assert cfg.voice.recognition_mode == "batch"

    def test_appearance_defaults(self):
        cfg = AirtypeConfig()
        assert cfg.appearance.theme == "system"
        assert cfg.appearance.pill_opacity == pytest.approx(0.92)

    def test_version_default(self):
        cfg = AirtypeConfig()
        assert cfg.version == "2.0"

    def test_shortcuts_defaults(self):
        cfg = AirtypeConfig()
        assert cfg.shortcuts.toggle_voice == "ctrl+shift+space"
        assert cfg.shortcuts.cancel == "escape"


class TestSerializationRoundTrip:
    def test_to_dict_contains_version(self):
        d = AirtypeConfig().to_dict()
        assert d["version"] == "2.0"

    def test_round_trip_equality(self):
        original = AirtypeConfig()
        restored = AirtypeConfig.from_dict(original.to_dict())
        assert original.version == restored.version
        assert original.general.language == restored.general.language
        assert original.voice.asr_model == restored.voice.asr_model
        assert original.appearance.theme == restored.appearance.theme
        assert original.shortcuts.toggle_voice == restored.shortcuts.toggle_voice

    def test_modified_values_survive_round_trip(self):
        cfg = AirtypeConfig()
        cfg.general.language = "en-US"
        cfg.voice.asr_model = "breeze-asr-25"
        cfg.appearance.theme = "dark"
        restored = AirtypeConfig.from_dict(cfg.to_dict())
        assert restored.general.language == "en-US"
        assert restored.voice.asr_model == "breeze-asr-25"
        assert restored.appearance.theme == "dark"


class TestIntegerDeviceIndexRoundTrip:
    """Scenario: Integer device index round-trip（fix-device-name-collision）。"""

    def test_voice_config_accepts_int_device(self):
        """VoiceConfig(input_device=41) 可建立。"""
        vc = VoiceConfig(input_device=41)
        assert vc.input_device == 41

    def test_int_device_round_trip_preserves_type(self):
        """to_dict → from_dict round-trip 保持 int 型別。"""
        cfg = AirtypeConfig()
        cfg.voice.input_device = 41
        data = cfg.to_dict()
        assert isinstance(data["voice"]["input_device"], int)
        restored = AirtypeConfig.from_dict(data)
        assert restored.voice.input_device == 41
        assert isinstance(restored.voice.input_device, int)

    def test_default_device_string_preserved(self):
        """"default" 字串在 round-trip 後仍為字串。"""
        cfg = AirtypeConfig()
        assert cfg.voice.input_device == "default"
        restored = AirtypeConfig.from_dict(cfg.to_dict())
        assert restored.voice.input_device == "default"
        assert isinstance(restored.voice.input_device, str)

    def test_int_device_json_persistence(self, tmp_path):
        """JSON 檔案中 int device index 不會變成字串。"""
        cfg_file = tmp_path / "config.json"
        cfg = AirtypeConfig()
        cfg.voice.input_device = 7
        cfg.save(cfg_file)
        loaded = AirtypeConfig.load(cfg_file)
        assert loaded.voice.input_device == 7
        assert isinstance(loaded.voice.input_device, int)


class TestMissingFieldHandling:
    def test_missing_section_uses_defaults(self):
        # 只提供 general 區段
        cfg = AirtypeConfig.from_dict({"general": {"language": "ja-JP"}})
        assert cfg.general.language == "ja-JP"
        # 其他區段應使用預設值
        assert cfg.voice.asr_model == "qwen3-asr-0.6b"
        assert cfg.appearance.theme == "system"

    def test_missing_field_in_section_uses_default(self):
        # general 區段缺少 log_level
        cfg = AirtypeConfig.from_dict({"general": {"language": "zh-TW"}})
        assert cfg.general.log_level == "INFO"

    def test_empty_dict_uses_all_defaults(self):
        cfg = AirtypeConfig.from_dict({})
        assert cfg.version == "2.0"
        assert cfg.general.language == "zh_TW"


class TestPersistence:
    def test_save_and_load(self, tmp_path):
        cfg_file = tmp_path / "config.json"
        original = AirtypeConfig()
        original.general.language = "ja-JP"
        original.save(cfg_file)

        assert cfg_file.exists()
        loaded = AirtypeConfig.load(cfg_file)
        assert loaded.general.language == "ja-JP"
        assert loaded.version == "2.0"

    def test_save_is_formatted_json(self, tmp_path):
        cfg_file = tmp_path / "config.json"
        AirtypeConfig().save(cfg_file)
        raw = cfg_file.read_text(encoding="utf-8")
        # 格式化 JSON 有縮排
        assert "  " in raw
        # 可正常解析
        data = json.loads(raw)
        assert data["version"] == "2.0"

    def test_save_creates_parent_dirs(self, tmp_path):
        nested = tmp_path / "a" / "b" / "config.json"
        AirtypeConfig().save(nested)
        assert nested.exists()

    def test_load_nonexistent_creates_default(self, tmp_path):
        cfg_file = tmp_path / "config.json"
        assert not cfg_file.exists()
        loaded = AirtypeConfig.load(cfg_file)
        assert cfg_file.exists()
        assert loaded.version == "2.0"

    def test_load_corrupt_renames_to_bak(self, tmp_path):
        cfg_file = tmp_path / "config.json"
        cfg_file.write_text("{ not valid json !!!}", encoding="utf-8")
        loaded = AirtypeConfig.load(cfg_file)
        bak_file = tmp_path / "config.json.bak"
        assert bak_file.exists()
        assert cfg_file.exists()
        assert loaded.version == "2.0"

    def test_load_corrupt_bak_contains_original(self, tmp_path):
        cfg_file = tmp_path / "config.json"
        corrupt = "THIS IS GARBAGE"
        cfg_file.write_text(corrupt, encoding="utf-8")
        AirtypeConfig.load(cfg_file)
        bak = tmp_path / "config.json.bak"
        assert bak.read_text(encoding="utf-8") == corrupt

    def test_load_when_dir_already_exists(self, tmp_path):
        """目錄已存在時 load() 應成功，且不更改目錄本身（Scenario: Config directory already exists）。"""
        cfg_dir = tmp_path / ".airtype"
        cfg_dir.mkdir(mode=0o700)
        cfg_file = cfg_dir / "config.json"
        AirtypeConfig().save(cfg_file)
        loaded = AirtypeConfig.load(cfg_file)
        assert loaded.version == "2.0"
        assert cfg_dir.is_dir()


# ---------------------------------------------------------------------------
# 6.2 整合測試
# ---------------------------------------------------------------------------

class TestIntegration:
    def test_python_m_airtype_exit_code_zero(self, tmp_path):
        """乾淨環境執行 python -m airtype，應 exit code 0。"""
        env = os.environ.copy()
        env["HOME"] = str(tmp_path)          # Unix
        env["USERPROFILE"] = str(tmp_path)   # Windows
        result = subprocess.run(
            [sys.executable, "-m", "airtype"],
            capture_output=True,
            env=env,
            cwd=str(Path(__file__).parent.parent),
        )
        assert result.returncode == 0, result.stderr.decode(errors="replace")

    def test_first_run_creates_config_dir_and_file(self, tmp_path):
        """首次執行後 ~/.airtype/config.json 應存在。"""
        env = os.environ.copy()
        env["HOME"] = str(tmp_path)
        env["USERPROFILE"] = str(tmp_path)
        subprocess.run(
            [sys.executable, "-m", "airtype"],
            capture_output=True,
            env=env,
            cwd=str(Path(__file__).parent.parent),
        )
        config_dir = tmp_path / ".airtype"
        config_file = config_dir / "config.json"
        assert config_dir.is_dir(), "設定目錄未建立"
        assert config_file.is_file(), "config.json 未建立"
        data = json.loads(config_file.read_text(encoding="utf-8"))
        assert data["version"] == "2.0"
