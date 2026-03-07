"""i18n 翻譯系統單元測試。

涵蓋：
- tr() key 查詢（存在 key、退回鏈、缺少 key）
- JSON 翻譯檔載入（正常、缺少語言檔）
- 執行期間語言切換（Signal 發出、元件刷新）
"""

from __future__ import annotations

import json

import pytest


# ─── 夾具 ────────────────────────────────────────────────────────────────────


@pytest.fixture()
def locales_dir(tmp_path):
    """建立暫存翻譯檔目錄，含 4 種語言的測試資料。"""
    zh_tw = {
        "settings.general.title": "一般設定",
        "settings.voice.title": "語音設定",
        "tray.status.idle": "待機",
        "only.in.zh_tw": "只有繁中有這個",
        "app.name": "Airtype",
    }
    zh_cn = {
        "settings.general.title": "常规设置",
        "settings.voice.title": "语音设置",
        "tray.status.idle": "待机",
        "app.name": "Airtype",
    }
    en = {
        "settings.general.title": "General Settings",
        "settings.voice.title": "Voice Settings",
        "tray.status.idle": "Idle",
        "app.name": "Airtype",
    }
    ja = {
        "settings.general.title": "一般設定",
        "settings.voice.title": "音声設定",
        "tray.status.idle": "待機",
        "app.name": "Airtype",
    }
    for name, data in [
        ("zh_TW.json", zh_tw),
        ("zh_CN.json", zh_cn),
        ("en.json", en),
        ("ja.json", ja),
    ]:
        (tmp_path / name).write_text(
            json.dumps(data, ensure_ascii=False), encoding="utf-8"
        )
    return tmp_path


@pytest.fixture()
def manager(locales_dir):
    """建立測試用 I18nManager（使用暫存翻譯檔目錄）。"""
    from airtype.utils.i18n import I18nManager

    return I18nManager(locales_dir=locales_dir)


# ─── tr() 函式測試 ─────────────────────────────────────────────────────────────


class TestTrFunction:
    """測試 tr() key 查詢與退回鏈。"""

    def test_tr_existing_key_default_language(self, manager):
        """預設語言（zh_TW）存在的 key 應回傳對應翻譯。"""
        assert manager.tr("settings.general.title") == "一般設定"

    def test_tr_existing_key_english(self, manager):
        """切換英文後，存在的 key 應回傳英文翻譯。"""
        manager.set_language("en")
        assert manager.tr("settings.general.title") == "General Settings"

    def test_tr_existing_key_zh_cn(self, manager):
        """切換簡體中文後，存在的 key 應回傳簡中翻譯。"""
        manager.set_language("zh_CN")
        assert manager.tr("settings.general.title") == "常规设置"

    def test_tr_existing_key_ja(self, manager):
        """切換日文後，存在的 key 應回傳日文翻譯。"""
        manager.set_language("ja")
        assert manager.tr("settings.voice.title") == "音声設定"

    def test_tr_fallback_to_zh_tw_when_key_missing(self, manager):
        """當前語言缺少 key 時，應退回 zh_TW 翻譯。"""
        manager.set_language("en")
        # "only.in.zh_tw" 不存在於 en.json，但存在於 zh_TW.json
        assert manager.tr("only.in.zh_tw") == "只有繁中有這個"

    def test_tr_fallback_to_key_when_missing_in_all_languages(self, manager):
        """key 在所有語言中均不存在時，應回傳 key 本身。"""
        manager.set_language("en")
        assert manager.tr("nonexistent.key.xyz") == "nonexistent.key.xyz"

    def test_tr_fallback_to_key_in_default_language(self, manager):
        """即使在 zh_TW 中，key 不存在時也應回傳 key 本身。"""
        assert manager.tr("totally.missing.key") == "totally.missing.key"


# ─── JSON 翻譯檔載入測試 ────────────────────────────────────────────────────────


class TestJsonTranslationFiles:
    """測試 JSON 翻譯檔的載入行為。"""

    def test_loads_zh_tw_by_default(self, manager):
        """預設應載入 zh_TW.json。"""
        assert manager.tr("tray.status.idle") == "待機"

    def test_loads_en_file_when_set(self, manager):
        """設定語言為 en 後，應載入 en.json。"""
        manager.set_language("en")
        assert manager.tr("tray.status.idle") == "Idle"

    def test_loads_zh_cn_file_when_set(self, manager):
        """設定語言為 zh_CN 後，應載入 zh_CN.json。"""
        manager.set_language("zh_CN")
        assert manager.tr("tray.status.idle") == "待机"

    def test_loads_ja_file_when_set(self, manager):
        """設定語言為 ja 後，應載入 ja.json。"""
        manager.set_language("ja")
        assert manager.tr("tray.status.idle") == "待機"

    def test_missing_locale_file_falls_back_to_zh_tw(self, manager):
        """缺少語言檔時，系統不應崩潰，應退回 zh_TW。"""
        manager.set_language("fr")  # fr.json 不存在
        # 退回 zh_TW
        assert manager.tr("settings.general.title") == "一般設定"

    def test_missing_locale_file_key_returns_key_itself(self, manager):
        """缺少語言檔且 zh_TW 也無此 key 時，回傳 key 本身。"""
        manager.set_language("fr")
        assert manager.tr("nonexistent.key") == "nonexistent.key"

    def test_translation_cached_after_first_load(self, manager, locales_dir):
        """翻譯檔應快取，不重複讀取磁碟。"""
        manager.set_language("en")
        _ = manager.tr("settings.general.title")
        # 刪除翻譯檔後仍應能查詢（已快取）
        (locales_dir / "en.json").unlink()
        assert manager.tr("settings.general.title") == "General Settings"


# ─── 執行期間語言切換測試 ────────────────────────────────────────────────────────


class TestRuntimeLanguageSwitching:
    """測試語言切換 Signal 發出與元件刷新。"""

    def _connect_signal(self, manager, callback):
        """連接 language_changed signal（相容 Qt 與非 Qt 模式）。"""
        try:
            manager.language_changed.connect(callback)
        except AttributeError:
            manager.connect_language_changed(callback)

    def test_set_language_changes_current_lang(self, manager):
        """set_language() 應更新 current_lang 屬性。"""
        manager.set_language("en")
        assert manager.current_lang == "en"

    def test_set_language_to_zh_cn(self, manager):
        """set_language() 可切換至 zh_CN。"""
        manager.set_language("zh_CN")
        assert manager.current_lang == "zh_CN"

    def test_language_changed_signal_emits_on_switch(self, manager):
        """切換語言時 language_changed 應發射新語言代碼。"""
        received = []
        self._connect_signal(manager, lambda lang: received.append(lang))

        manager.set_language("en")

        assert received == ["en"]

    def test_language_changed_signal_emits_multiple_times(self, manager):
        """多次切換語言時，Signal 應依序發射對應語言代碼。"""
        received = []
        self._connect_signal(manager, lambda lang: received.append(lang))

        manager.set_language("en")
        manager.set_language("ja")
        manager.set_language("zh_TW")

        assert received == ["en", "ja", "zh_TW"]

    def test_component_refreshes_text_on_language_change(self, manager):
        """UI 元件連接 Signal 後，語言切換時應能刷新顯示文字。"""
        labels: list[str] = []

        def refresh(lang):
            labels.append(manager.tr("settings.general.title"))

        self._connect_signal(manager, refresh)

        manager.set_language("en")
        assert labels == ["General Settings"]

        manager.set_language("zh_TW")
        assert labels == ["General Settings", "一般設定"]

    def test_tr_returns_new_language_after_switch(self, manager):
        """語言切換後，tr() 應立即反映新語言的翻譯。"""
        assert manager.tr("tray.status.idle") == "待機"  # zh_TW

        manager.set_language("en")
        assert manager.tr("tray.status.idle") == "Idle"

        manager.set_language("ja")
        assert manager.tr("tray.status.idle") == "待機"

    def test_switch_back_to_zh_tw(self, manager):
        """可從其他語言切換回 zh_TW。"""
        manager.set_language("en")
        manager.set_language("zh_TW")
        assert manager.tr("settings.general.title") == "一般設定"


# ─── 模組等級函式測試 ─────────────────────────────────────────────────────────


class TestModuleLevelFunctions:
    """測試模組等級 tr() / set_language() / get_manager() 函式。"""

    def test_module_tr_returns_string(self):
        """模組等級 tr() 應回傳字串（即使 key 不存在）。"""
        from airtype.utils.i18n import tr

        result = tr("some.key")
        assert isinstance(result, str)

    def test_module_set_language_and_tr(self, locales_dir, monkeypatch):
        """模組等級 set_language() 切換語言後，tr() 應反映變更。"""
        import airtype.utils.i18n as i18n_mod

        # 使用暫存 locales_dir 建立新管理器
        original_manager = i18n_mod._manager
        test_manager = i18n_mod.I18nManager(locales_dir=locales_dir)
        monkeypatch.setattr(i18n_mod, "_manager", test_manager)
        try:
            test_manager.set_language("en")
            assert i18n_mod.tr("settings.general.title") == "General Settings"
        finally:
            monkeypatch.setattr(i18n_mod, "_manager", original_manager)

    def test_get_manager_returns_i18n_manager(self):
        """get_manager() 應回傳 I18nManager 實例。"""
        from airtype.utils.i18n import I18nManager, get_manager

        assert isinstance(get_manager(), I18nManager)

    def test_module_set_language_simulates_on_lang_changed(self, locales_dir, monkeypatch):
        """模擬 _on_lang_changed() 呼叫模組級 set_language() 後，tr() 應立即反映新語言。"""
        import airtype.utils.i18n as i18n_mod

        original_manager = i18n_mod._manager
        test_manager = i18n_mod.I18nManager(locales_dir=locales_dir)
        monkeypatch.setattr(i18n_mod, "_manager", test_manager)
        try:
            # 模擬 _on_lang_changed("en") 的行為
            i18n_mod.set_language("en")
            assert i18n_mod.tr("settings.general.title") == "General Settings"

            # 切回 zh_TW（使用底線格式）
            i18n_mod.set_language("zh_TW")
            assert i18n_mod.tr("settings.general.title") == "一般設定"
        finally:
            monkeypatch.setattr(i18n_mod, "_manager", original_manager)


# ─── 語言代碼格式與 Config 預設值測試 ─────────────────────────────────────────────


class TestLanguageCodeFormat:
    """測試語言代碼格式一致性（底線格式 zh_TW / zh_CN）。"""

    def test_config_default_language_uses_underscore(self):
        """AirtypeConfig 預設語言應使用底線格式 'zh_TW'（與 locale 檔名一致）。"""
        from airtype.config import AirtypeConfig

        config = AirtypeConfig()
        assert config.general.language == "zh_TW", (
            f"預期 'zh_TW'（底線），實際得到 '{config.general.language}'。"
            "請確認 config.py 中 language 預設值使用底線而非連字號。"
        )

    def test_set_language_underscore_zh_tw(self, manager):
        """set_language('zh_TW')（底線）應正確載入繁體中文翻譯。"""
        manager.set_language("zh_TW")
        assert manager.tr("settings.general.title") == "一般設定"
        assert manager.current_lang == "zh_TW"

    def test_set_language_underscore_zh_cn(self, manager):
        """set_language('zh_CN')（底線）應正確載入簡體中文翻譯。"""
        manager.set_language("zh_CN")
        assert manager.tr("settings.general.title") == "常规设置"
        assert manager.current_lang == "zh_CN"

    def test_hyphen_lang_code_falls_back_gracefully(self, manager):
        """若誤傳連字號格式 'zh-TW'，系統應退回 zh_TW 而不崩潰。"""
        # zh-TW.json 不存在，應退回 zh_TW
        manager.set_language("zh-TW")
        # 退回行為：回傳 zh_TW 翻譯或 key 本身，不應 raise
        result = manager.tr("settings.general.title")
        assert isinstance(result, str)
