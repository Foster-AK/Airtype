"""Airtype 設定模型與 JSON 持久化。

設定檔位於 ~/.airtype/config.json，符合 PRD §7.4。
採用 Python dataclass 模型 + 原子寫入（write-then-replace）。

API 金鑰透過系統 keyring 儲存（不寫入 config.json），符合 PRD §9（安全性）。
"""

from __future__ import annotations

import json
import logging
import os
import stat
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional, Union

logger = logging.getLogger(__name__)

CONFIG_VERSION = "2.0"
CONFIG_DIR = Path.home() / ".airtype"
CONFIG_FILE = CONFIG_DIR / "config.json"

# keyring 服務名稱（PRD §9：API 金鑰透過系統 keyring 加密儲存）
KEYRING_SERVICE = "airtype"


# ---------------------------------------------------------------------------
# 巢狀設定區段
# ---------------------------------------------------------------------------

@dataclass
class GeneralConfig:
    language: str = "zh_TW"
    auto_start: bool = False
    start_minimized: bool = True
    silence_timeout: float = 1.5
    append_space: bool = False
    append_newline: bool = False
    notifications: bool = True
    log_level: str = "INFO"
    clipboard_restore_delay_ms: int = 150


@dataclass
class VoiceConfig:
    input_device: Union[str, int] = "default"
    noise_reduction: bool = False
    asr_model: str = "qwen3-asr-0.6b-onnx"
    asr_inference_backend: str = "auto"
    asr_language: str = "zh-TW"
    recognition_mode: str = "batch"


@dataclass
class LlmConfig:
    enabled: bool = False
    mode: str = "light"
    preview_before_inject: bool = True
    source: str = "local"
    local_model: str = "qwen2.5-1.5b"
    model_size_b: float = 1.5
    api_provider: Optional[str] = None
    api_endpoint: Optional[str] = None
    custom_prompt: Optional[str] = None
    auto_punctuation: bool = True
    fix_homophones: bool = True
    colloquial_to_formal: bool = False
    keep_fillers: bool = True
    cjk_conversion: str = "none"
    number_format: str = "smart"
    # 注意：API 金鑰不儲存於此；請使用 get_api_key() / set_api_key()


@dataclass
class DictionaryConfig:
    active_sets: list[str] = field(default_factory=lambda: ["default"])
    hot_words: list[dict[str, Any]] = field(
        default_factory=lambda: [
            {"word": "鼎新 Workflow", "weight": 8, "enabled": True},
            {"word": "PostgreSQL", "weight": 9, "enabled": True},
        ]
    )
    replace_rules: list[dict[str, Any]] = field(
        default_factory=lambda: [
            {"from": "頂新", "to": "鼎新", "regex": False, "enabled": True},
        ]
    )


@dataclass
class AppearanceConfig:
    theme: str = "system"
    pill_position: str = "center"
    pill_scale: float = 1.0
    pill_opacity: float = 0.92
    waveform_style: str = "bars"
    waveform_color: str = "#60a5fa"
    show_status_text: bool = True
    show_realtime_preview: bool = True


@dataclass
class ShortcutsConfig:
    toggle_voice: str = "ctrl+shift+space"
    cancel: str = "escape"
    open_settings: str = "ctrl+shift+s"
    switch_language: str = "ctrl+shift+l"
    switch_dictionary: str = "ctrl+shift+d"
    toggle_polish: str = "ctrl+shift+p"


# ---------------------------------------------------------------------------
# 頂層設定物件
# ---------------------------------------------------------------------------

@dataclass
class AirtypeConfig:
    version: str = CONFIG_VERSION
    general: GeneralConfig = field(default_factory=GeneralConfig)
    voice: VoiceConfig = field(default_factory=VoiceConfig)
    llm: LlmConfig = field(default_factory=LlmConfig)
    dictionary: DictionaryConfig = field(default_factory=DictionaryConfig)
    appearance: AppearanceConfig = field(default_factory=AppearanceConfig)
    shortcuts: ShortcutsConfig = field(default_factory=ShortcutsConfig)

    # ------------------------------------------------------------------
    # 序列化
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        """將設定轉換為可 JSON 序列化的字典。"""
        def _section(obj: Any) -> dict[str, Any]:
            result: dict[str, Any] = {}
            for f in obj.__dataclass_fields__:
                result[f] = getattr(obj, f)
            return result

        return {
            "version": self.version,
            "general": _section(self.general),
            "voice": _section(self.voice),
            "llm": _section(self.llm),
            "dictionary": _section(self.dictionary),
            "appearance": _section(self.appearance),
            "shortcuts": _section(self.shortcuts),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AirtypeConfig":
        """從字典建立設定，缺少的欄位補上預設值。"""

        def _fill(dc_class, raw: dict[str, Any]):
            defaults = dc_class()
            kwargs: dict[str, Any] = {}
            for f in dc_class.__dataclass_fields__:
                kwargs[f] = raw.get(f, getattr(defaults, f))
            return dc_class(**kwargs)

        return cls(
            version=data.get("version", CONFIG_VERSION),
            general=_fill(GeneralConfig, data.get("general", {})),
            voice=_fill(VoiceConfig, data.get("voice", {})),
            llm=_fill(LlmConfig, data.get("llm", {})),
            dictionary=_fill(DictionaryConfig, data.get("dictionary", {})),
            appearance=_fill(AppearanceConfig, data.get("appearance", {})),
            shortcuts=_fill(ShortcutsConfig, data.get("shortcuts", {})),
        )

    # ------------------------------------------------------------------
    # 持久化
    # ------------------------------------------------------------------

    def save(self, path: Path = CONFIG_FILE) -> None:
        """以原子寫入方式儲存設定至指定路徑。

        先寫入同目錄的暫存檔，再以 os.replace() 原子取代，
        避免寫到一半時程序崩潰造成檔案損毀。
        """
        path.parent.mkdir(parents=True, exist_ok=True)
        # Windows 上 os.replace 需要 tmp 與目標在同一磁碟
        fd, tmp_path = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)
            os.replace(tmp_path, path)
        except Exception:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise

    @classmethod
    def load(cls, path: Path = CONFIG_FILE) -> "AirtypeConfig":
        """從指定路徑載入設定。

        - 路徑不存在：建立預設設定並儲存。
        - JSON 損毀：重新命名為 .bak，建立預設設定並儲存。
        - 欄位缺少：補上預設值。
        """
        _ensure_config_dir()

        if not path.exists():
            logger.info("未找到設定檔，建立預設設定：%s", path)
            cfg = cls()
            cfg.save(path)
            return cfg

        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            cfg = cls.from_dict(data)
            if _migrate_asr_model(cfg, path):
                logger.info("已遷移舊版 ASR model ID，設定已更新")
            return cfg
        except (json.JSONDecodeError, ValueError) as exc:
            bak = path.with_suffix(".json.bak")
            logger.warning("設定檔損毀（%s），備份為 %s，重建預設設定", exc, bak)
            try:
                os.replace(path, bak)
            except OSError:
                pass
            cfg = cls()
            cfg.save(path)
            return cfg


# ---------------------------------------------------------------------------
# 工具函式
# ---------------------------------------------------------------------------

# 舊版 model ID → 新版 model ID 對照表（manifest 重構後需更新）
_LEGACY_ASR_MODEL_MAP: dict[str, str] = {
    "qwen3-asr-0.6b": "qwen3-asr-0.6b-onnx",
    "qwen3-asr-1.7b": "qwen3-asr-0.6b-onnx",
    "qwen3-asr-1.7b-openvino": "qwen3-asr-0.6b-onnx",
    "qwen3-asr-0.6b-openvino": "qwen3-asr-0.6b-onnx",
}


def _migrate_asr_model(cfg: "AirtypeConfig", path: Path) -> bool:
    """若 cfg.voice.asr_model 為舊版 ID，遷移至對應的新 ID 並儲存。

    回傳 True 表示已遷移並儲存，False 表示無需遷移。
    """
    old_id = cfg.voice.asr_model
    new_id = _LEGACY_ASR_MODEL_MAP.get(old_id)
    if new_id is None:
        return False
    logger.warning("ASR model ID 已過時：'%s' → '%s'，自動遷移", old_id, new_id)
    cfg.voice.asr_model = new_id
    try:
        cfg.save(path)
    except Exception as exc:  # noqa: BLE001
        logger.warning("遷移後儲存設定失敗：%s", exc)
    return True


def _ensure_config_dir() -> None:
    """確保 ~/.airtype/ 目錄存在，並設定 0o700 權限（僅限首次建立）。"""
    if not CONFIG_DIR.exists():
        CONFIG_DIR.mkdir(parents=True, mode=0o700, exist_ok=True)
        logger.info("已建立設定目錄：%s", CONFIG_DIR)
    verify_config_dir_permissions()


def verify_config_dir_permissions() -> bool:
    """驗證設定目錄 (~/.airtype/) 具有正確的 0o700 權限（僅限 Unix）。

    Windows 不支援 Unix 風格權限，此函式在 Windows 上永遠回傳 True。

    Returns:
        True 表示權限正確或平台不支援；False 表示權限不正確（已發出警告）。
    """
    if sys.platform == "win32":
        return True

    if not CONFIG_DIR.exists():
        return True

    try:
        mode = CONFIG_DIR.stat().st_mode
        perms = stat.S_IMODE(mode)
        if perms != 0o700:
            logger.warning(
                "安全性警告：設定目錄權限為 0o%o，應為 0o700。"
                "請執行：chmod 700 %s",
                perms,
                CONFIG_DIR,
            )
            return False
    except OSError as exc:
        logger.warning("無法驗證設定目錄權限：%s", exc)
        return False

    return True


# ---------------------------------------------------------------------------
# API 金鑰（透過系統 keyring 加密儲存）
# ---------------------------------------------------------------------------

def get_api_key(provider: str) -> Optional[str]:
    """從系統 keyring 取得 API 金鑰。

    Args:
        provider: API 提供者識別碼（例如 "openai"、"anthropic"）。

    Returns:
        API 金鑰字串，或 None（若尚未設定或 keyring 不可用）。
    """
    try:
        import keyring  # noqa: PLC0415
        return keyring.get_password(KEYRING_SERVICE, provider)
    except Exception as exc:
        logger.warning("無法從 keyring 讀取 API 金鑰（provider=%s）：%s", provider, exc)
        return None


def set_api_key(provider: str, key: Optional[str]) -> None:
    """儲存或刪除 API 金鑰至系統 keyring。

    Args:
        provider: API 提供者識別碼（例如 "openai"、"anthropic"）。
        key: API 金鑰字串；傳入 None 則刪除現有金鑰。
    """
    try:
        import keyring  # noqa: PLC0415
        if key is None:
            try:
                keyring.delete_password(KEYRING_SERVICE, provider)
            except keyring.errors.PasswordDeleteError:
                pass  # 金鑰不存在，忽略
        else:
            keyring.set_password(KEYRING_SERVICE, provider, key)
    except Exception as exc:
        logger.warning("無法儲存 API 金鑰至 keyring（provider=%s）：%s", provider, exc)
