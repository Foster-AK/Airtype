"""多語系翻譯系統（i18n）。

提供 tr(key) 函式查詢當前語言的翻譯字串。
Fallback chain：當前語言 → zh_TW → key 本身。
支援執行期間語言切換，透過 Qt Signal 通知 UI 元件刷新。

使用方式::

    from airtype.utils.i18n import tr, set_language, get_manager

    # 查詢翻譯
    label = tr("settings.general.title")  # "一般設定"

    # 切換語言（非同步通知所有連接元件）
    set_language("en")

    # 連接 Signal 以在語言切換時刷新 UI
    get_manager().language_changed.connect(my_widget.retranslate_ui)
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Callable, List, Optional

logger = logging.getLogger(__name__)

# 預設翻譯檔目錄（支援 PyInstaller 打包環境）
from airtype.utils.paths import get_bundled_root

_DEFAULT_LOCALES_DIR: Path = get_bundled_root() / "locales"
_DEFAULT_LANG: str = "zh_TW"


# ─── Qt 版本（PySide6 可用時） ─────────────────────────────────────────────────

try:
    from PySide6.QtCore import QObject, Signal

    class I18nManager(QObject):
        """多語系管理器（Qt 版本）。

        透過 Qt Signal 通知所有連接的 UI 元件刷新文字。

        Attributes:
            language_changed: 語言切換時發射的 Signal，帶新語言代碼（str）。
        """

        language_changed = Signal(str)

        def __init__(
            self,
            locales_dir: Optional[Path | str] = None,
            parent: Optional[QObject] = None,
        ) -> None:
            super().__init__(parent)
            self._locales_dir = Path(locales_dir) if locales_dir else _DEFAULT_LOCALES_DIR
            self._translations: dict[str, dict] = {}
            self._current_lang: str = _DEFAULT_LANG
            # 預載預設語言
            self._load_translation(_DEFAULT_LANG)

        @property
        def current_lang(self) -> str:
            """當前語言代碼。"""
            return self._current_lang

        def set_language(self, lang_code: str) -> None:
            """切換語言並通知所有連接的 UI 元件刷新。

            Args:
                lang_code: 語言代碼，如 ``"zh_TW"``、``"en"``、``"zh_CN"``、``"ja"``。
            """
            self._current_lang = lang_code
            self._load_translation(lang_code)
            self.language_changed.emit(lang_code)

        def _load_translation(self, lang_code: str) -> dict:
            """載入指定語言的翻譯 JSON 檔（有快取）。

            Args:
                lang_code: 語言代碼。

            Returns:
                翻譯字典（key → 翻譯字串）；載入失敗時回傳空字典。
            """
            if lang_code in self._translations:
                return self._translations[lang_code]

            lang_file = self._locales_dir / f"{lang_code}.json"
            if lang_file.exists():
                try:
                    with open(lang_file, encoding="utf-8") as f:
                        self._translations[lang_code] = json.load(f)
                    logger.debug("已載入翻譯檔：%s", lang_file)
                except Exception as exc:
                    logger.warning("載入翻譯檔失敗 %s：%s", lang_file, exc)
                    self._translations[lang_code] = {}
            else:
                logger.debug("翻譯檔不存在：%s", lang_file)
                self._translations[lang_code] = {}

            return self._translations[lang_code]

        def tr(self, key: str) -> str:
            """查詢翻譯字串。

            Fallback chain：
            1. 當前語言
            2. zh_TW（若當前語言不是 zh_TW）
            3. key 本身

            Args:
                key: 翻譯 key，如 ``"settings.general.title"``。

            Returns:
                對應翻譯字串；找不到時依 fallback chain 回退。
            """
            # 當前語言查詢
            data = self._load_translation(self._current_lang)
            if key in data:
                return data[key]

            # 退回 zh_TW
            if self._current_lang != _DEFAULT_LANG:
                zhtw_data = self._load_translation(_DEFAULT_LANG)
                if key in zhtw_data:
                    return zhtw_data[key]

            # 最終退回：key 本身
            logger.debug("翻譯 key 未找到：%s（語言：%s）", key, self._current_lang)
            return key

    PYSIDE6_AVAILABLE = True
    logger.debug("i18n：已載入 PySide6 版本")

except ImportError:
    PYSIDE6_AVAILABLE = False
    logger.debug("i18n：PySide6 不可用，使用無 Signal 版本")

    class I18nManager:  # type: ignore[no-redef]
        """多語系管理器（非 Qt 版本）。

        無 Qt Signal，改用回呼函式清單通知語言變更。
        """

        def __init__(
            self,
            locales_dir: Optional[Path | str] = None,
        ) -> None:
            self._locales_dir = Path(locales_dir) if locales_dir else _DEFAULT_LOCALES_DIR
            self._translations: dict = {}
            self._current_lang: str = _DEFAULT_LANG
            self._callbacks: List[Callable[[str], None]] = []
            self._load_translation(_DEFAULT_LANG)

        @property
        def current_lang(self) -> str:
            return self._current_lang

        def connect_language_changed(self, callback: Callable[[str], None]) -> None:
            """註冊語言變更回呼函式。

            Args:
                callback: 接受語言代碼（str）的可呼叫物件。
            """
            self._callbacks.append(callback)

        def set_language(self, lang_code: str) -> None:
            self._current_lang = lang_code
            self._load_translation(lang_code)
            for cb in self._callbacks:
                try:
                    cb(lang_code)
                except Exception as exc:
                    logger.warning("語言變更回呼執行失敗：%s", exc)

        def _load_translation(self, lang_code: str) -> dict:
            if lang_code in self._translations:
                return self._translations[lang_code]

            lang_file = self._locales_dir / f"{lang_code}.json"
            if lang_file.exists():
                try:
                    with open(lang_file, encoding="utf-8") as f:
                        self._translations[lang_code] = json.load(f)
                except Exception as exc:
                    logger.warning("載入翻譯檔失敗 %s：%s", lang_file, exc)
                    self._translations[lang_code] = {}
            else:
                self._translations[lang_code] = {}

            return self._translations[lang_code]

        def tr(self, key: str) -> str:
            data = self._load_translation(self._current_lang)
            if key in data:
                return data[key]

            if self._current_lang != _DEFAULT_LANG:
                zhtw_data = self._load_translation(_DEFAULT_LANG)
                if key in zhtw_data:
                    return zhtw_data[key]

            return key


# ─── 模組等級單例 ─────────────────────────────────────────────────────────────

_manager: Optional[I18nManager] = None


def _get_manager() -> I18nManager:
    global _manager
    if _manager is None:
        _manager = I18nManager()
    return _manager


def tr(key: str) -> str:
    """查詢當前語言的翻譯字串（模組等級便利函式）。

    Fallback chain：當前語言 → zh_TW → key 本身。

    Args:
        key: 翻譯 key，如 ``"settings.general.title"``。

    Returns:
        對應翻譯字串；找不到時依 fallback chain 回退。
    """
    return _get_manager().tr(key)


def set_language(lang_code: str) -> None:
    """切換全域語言並通知所有 UI 元件刷新（模組等級便利函式）。

    Args:
        lang_code: 語言代碼，如 ``"zh_TW"``、``"en"``、``"zh_CN"``、``"ja"``。
    """
    _get_manager().set_language(lang_code)


def get_manager() -> I18nManager:
    """取得全域 I18nManager 單例。

    Returns:
        全域 :class:`I18nManager` 實例。
    """
    return _get_manager()
