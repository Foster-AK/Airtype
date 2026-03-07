"""辭典引擎單元測試。

涵蓋：
- 任務 3.1：熱詞管理（載入、儲存、套用至模擬 ASR 引擎）
- 任務 3.2：替換規則（字串與正規表達式比對）
- 任務 3.3：辭典集切換（多組聯集）
- 任務 3.4：匯入/匯出格式（txt/csv/json/airtype-dict）
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from airtype.core.dictionary import (
    DICT_DIR,
    DictionaryEngine,
    DictionarySet,
    HotWordEntry,
    ReplaceRule,
)


# ─────────────────────────────────────────────────────────────────────────────
# Mock & Fixture 輔助
# ─────────────────────────────────────────────────────────────────────────────


def _make_config(
    active_sets: list[str] | None = None,
    hot_words: list[dict] | None = None,
    replace_rules: list[dict] | None = None,
) -> MagicMock:
    """建立最小化的 AirtypeConfig mock。"""
    config = MagicMock()
    config.dictionary.active_sets = active_sets if active_sets is not None else ["default"]
    config.dictionary.hot_words = hot_words if hot_words is not None else []
    config.dictionary.replace_rules = replace_rules if replace_rules is not None else []
    return config


def _make_engine(config=None, tmp_dir: Path | None = None) -> DictionaryEngine:
    """建立指向臨時目錄的 DictionaryEngine。"""
    if config is None:
        config = _make_config()
    engine = DictionaryEngine(config)
    if tmp_dir is not None:
        engine.__class__  # ensure class attr not patched at instance level
    return engine


@pytest.fixture()
def tmp_dict_dir(tmp_path: Path):
    """Patch DICT_DIR 至臨時目錄，測試結束後還原。"""
    import airtype.core.dictionary as dict_module
    original = dict_module.DICT_DIR
    dict_module.DICT_DIR = tmp_path / "dictionaries"
    yield dict_module.DICT_DIR
    dict_module.DICT_DIR = original


# ─────────────────────────────────────────────────────────────────────────────
# HotWordEntry 資料模型測試
# ─────────────────────────────────────────────────────────────────────────────


class TestHotWordEntry:
    def test_from_dict_basic(self) -> None:
        hw = HotWordEntry.from_dict({"word": "PostgreSQL", "weight": 9, "enabled": True})
        assert hw.word == "PostgreSQL"
        assert hw.weight == 9
        assert hw.enabled is True

    def test_from_dict_defaults(self) -> None:
        hw = HotWordEntry.from_dict({"word": "foo"})
        assert hw.weight == 5
        assert hw.enabled is True

    def test_to_dict_roundtrip(self) -> None:
        hw = HotWordEntry(word="鼎新", weight=8, enabled=False)
        d = hw.to_dict()
        hw2 = HotWordEntry.from_dict(d)
        assert hw2.word == "鼎新"
        assert hw2.weight == 8
        assert hw2.enabled is False

    def test_to_hot_word(self) -> None:
        from airtype.core.asr_engine import HotWord
        hw = HotWordEntry(word="ERP", weight=7, enabled=True)
        result = hw.to_hot_word()
        assert isinstance(result, HotWord)
        assert result.word == "ERP"
        assert result.weight == 7


# ─────────────────────────────────────────────────────────────────────────────
# ReplaceRule 資料模型測試
# ─────────────────────────────────────────────────────────────────────────────


class TestReplaceRule:
    def test_string_replace(self) -> None:
        rule = ReplaceRule(from_text="頂新", to_text="鼎新")
        assert rule.apply("公司是頂新集團") == "公司是鼎新集團"

    def test_string_replace_disabled(self) -> None:
        rule = ReplaceRule(from_text="頂新", to_text="鼎新", enabled=False)
        assert rule.apply("公司是頂新集團") == "公司是頂新集團"

    def test_string_no_match(self) -> None:
        rule = ReplaceRule(from_text="ABC", to_text="XYZ")
        assert rule.apply("hello world") == "hello world"

    def test_regex_replace(self) -> None:
        rule = ReplaceRule(from_text=r"\d+", to_text="NUM", regex=True)
        assert rule.apply("today is 2024 year") == "today is NUM year"

    def test_regex_replace_groups(self) -> None:
        rule = ReplaceRule(from_text=r"(\w+)@(\w+)", to_text=r"\2@\1", regex=True)
        result = rule.apply("user@host")
        assert result == "host@user"

    def test_regex_invalid_pattern_no_raise(self) -> None:
        """無效正規表達式不應拋出例外，原文原樣返回。"""
        rule = ReplaceRule(from_text="[invalid", to_text="x", regex=True)
        assert rule.apply("test") == "test"

    def test_from_dict_roundtrip(self) -> None:
        d = {"from": "A", "to": "B", "regex": True, "enabled": False}
        rule = ReplaceRule.from_dict(d)
        assert rule.from_text == "A"
        assert rule.to_text == "B"
        assert rule.regex is True
        assert rule.enabled is False
        assert rule.to_dict() == d


# ─────────────────────────────────────────────────────────────────────────────
# DictionarySet 測試
# ─────────────────────────────────────────────────────────────────────────────


class TestDictionarySet:
    def test_from_dict(self) -> None:
        data = {
            "hot_words": [{"word": "foo", "weight": 5, "enabled": True}],
            "replace_rules": [{"from": "a", "to": "b", "regex": False, "enabled": True}],
        }
        ds = DictionarySet.from_dict("test", data)
        assert ds.name == "test"
        assert len(ds.hot_words) == 1
        assert len(ds.replace_rules) == 1

    def test_get_enabled_hot_words(self) -> None:
        ds = DictionarySet(
            name="x",
            hot_words=[
                HotWordEntry("foo", 5, True),
                HotWordEntry("bar", 3, False),
            ],
        )
        words = ds.get_enabled_hot_words()
        assert len(words) == 1
        assert words[0].word == "foo"

    def test_apply_rules(self) -> None:
        ds = DictionarySet(
            name="x",
            replace_rules=[
                ReplaceRule("頂新", "鼎新"),
                ReplaceRule("ERP系統", "ERP"),
            ],
        )
        result = ds.apply_rules("頂新 ERP系統導入")
        assert result == "鼎新 ERP導入"

    def test_to_dict_roundtrip(self) -> None:
        ds = DictionarySet(
            name="sample",
            hot_words=[HotWordEntry("PostgreSQL", 9, True)],
            replace_rules=[ReplaceRule("a", "b", False, True)],
        )
        d = ds.to_dict()
        ds2 = DictionarySet.from_dict("sample", d)
        assert ds2.hot_words[0].word == "PostgreSQL"
        assert ds2.replace_rules[0].from_text == "a"


# ─────────────────────────────────────────────────────────────────────────────
# 任務 3.1：熱詞管理（載入、儲存、套用至模擬引擎）
# ─────────────────────────────────────────────────────────────────────────────


class TestHotWordManagement:
    def test_load_creates_default_from_config(self, tmp_dict_dir: Path) -> None:
        config = _make_config(
            hot_words=[{"word": "PostgreSQL", "weight": 9, "enabled": True}],
        )
        engine = DictionaryEngine(config)
        engine.load_sets()
        assert "default" in engine.list_sets()
        default = engine.get_set("default")
        assert len(default.hot_words) == 1
        assert default.hot_words[0].word == "PostgreSQL"

    def test_load_from_existing_json(self, tmp_dict_dir: Path) -> None:
        tmp_dict_dir.mkdir(parents=True, exist_ok=True)
        data = {
            "hot_words": [{"word": "ERP", "weight": 8, "enabled": True}],
            "replace_rules": [],
        }
        (tmp_dict_dir / "mydict.json").write_text(json.dumps(data), encoding="utf-8")
        config = _make_config()
        engine = DictionaryEngine(config)
        engine.load_sets()
        assert "mydict" in engine.list_sets()
        assert engine.get_set("mydict").hot_words[0].word == "ERP"

    def test_save_and_reload(self, tmp_dict_dir: Path) -> None:
        config = _make_config()
        engine = DictionaryEngine(config)
        engine.load_sets()
        # 修改 default 並儲存
        default = engine.get_set("default")
        default.hot_words.append(HotWordEntry("新詞彙", 7, True))
        engine.save_set("default")
        # 重新載入
        engine2 = DictionaryEngine(config)
        engine2.load_sets()
        words = engine2.get_set("default").hot_words
        assert any(hw.word == "新詞彙" for hw in words)

    def test_sync_hot_words_to_engine(self, tmp_dict_dir: Path) -> None:
        config = _make_config(
            active_sets=["default"],
            hot_words=[
                {"word": "PostgreSQL", "weight": 9, "enabled": True},
                {"word": "舊詞", "weight": 3, "enabled": False},
            ],
        )
        engine = DictionaryEngine(config)
        engine.load_sets()

        mock_asr = MagicMock()
        engine.sync_hot_words(mock_asr)
        mock_asr.set_hot_words.assert_called_once()
        called_words = mock_asr.set_hot_words.call_args[0][0]
        # 只有啟用的詞彙
        assert len(called_words) == 1
        assert called_words[0].word == "PostgreSQL"

    def test_sync_hot_words_asr_exception_handled(self, tmp_dict_dir: Path) -> None:
        config = _make_config(
            hot_words=[{"word": "foo", "weight": 5, "enabled": True}],
        )
        engine = DictionaryEngine(config)
        engine.load_sets()
        mock_asr = MagicMock()
        mock_asr.set_hot_words.side_effect = RuntimeError("engine not ready")
        # 不應拋出例外
        engine.sync_hot_words(mock_asr)


# ─────────────────────────────────────────────────────────────────────────────
# 任務 3.2：替換規則（字串與正規表達式比對）
# ─────────────────────────────────────────────────────────────────────────────


class TestReplacementRules:
    def test_string_rule_applied(self, tmp_dict_dir: Path) -> None:
        config = _make_config(
            active_sets=["default"],
            replace_rules=[{"from": "頂新", "to": "鼎新", "regex": False, "enabled": True}],
        )
        engine = DictionaryEngine(config)
        engine.load_sets()
        result = engine.apply_rules("今天頂新開會")
        assert result == "今天鼎新開會"

    def test_regex_rule_applied(self, tmp_dict_dir: Path) -> None:
        config = _make_config(
            active_sets=["default"],
            replace_rules=[{"from": r"\b(\d{4})/(\d{2})/(\d{2})\b", "to": r"\1-\2-\3", "regex": True, "enabled": True}],
        )
        engine = DictionaryEngine(config)
        engine.load_sets()
        result = engine.apply_rules("會議時間 2024/03/15")
        assert "2024-03-15" in result

    def test_disabled_rule_not_applied(self, tmp_dict_dir: Path) -> None:
        config = _make_config(
            active_sets=["default"],
            replace_rules=[{"from": "頂新", "to": "鼎新", "regex": False, "enabled": False}],
        )
        engine = DictionaryEngine(config)
        engine.load_sets()
        result = engine.apply_rules("頂新集團")
        assert result == "頂新集團"

    def test_multiple_rules_applied_in_order(self, tmp_dict_dir: Path) -> None:
        config = _make_config(
            active_sets=["default"],
            replace_rules=[
                {"from": "A", "to": "B", "regex": False, "enabled": True},
                {"from": "B", "to": "C", "regex": False, "enabled": True},
            ],
        )
        engine = DictionaryEngine(config)
        engine.load_sets()
        result = engine.apply_rules("A")
        assert result == "C"

    def test_no_active_set_returns_original(self, tmp_dict_dir: Path) -> None:
        config = _make_config(active_sets=[])
        engine = DictionaryEngine(config)
        engine.load_sets()
        result = engine.apply_rules("原始文字")
        assert result == "原始文字"


# ─────────────────────────────────────────────────────────────────────────────
# 任務 3.3：辭典集切換測試
# ─────────────────────────────────────────────────────────────────────────────


class TestDictionarySetSwitching:
    def _setup_two_sets(self, tmp_dict_dir: Path):
        """建立兩個辭典集（erp / tech）於臨時目錄。"""
        tmp_dict_dir.mkdir(parents=True, exist_ok=True)
        erp = {
            "hot_words": [{"word": "ERP", "weight": 9, "enabled": True}],
            "replace_rules": [{"from": "頂新", "to": "鼎新", "regex": False, "enabled": True}],
        }
        tech = {
            "hot_words": [{"word": "PostgreSQL", "weight": 8, "enabled": True}],
            "replace_rules": [{"from": "postgreSQL", "to": "PostgreSQL", "regex": False, "enabled": True}],
        }
        (tmp_dict_dir / "erp.json").write_text(json.dumps(erp), encoding="utf-8")
        (tmp_dict_dir / "tech.json").write_text(json.dumps(tech), encoding="utf-8")

    def test_single_set_active(self, tmp_dict_dir: Path) -> None:
        self._setup_two_sets(tmp_dict_dir)
        config = _make_config(active_sets=["erp"])
        engine = DictionaryEngine(config)
        engine.load_sets()

        result = engine.apply_rules("頂新 postgreSQL")
        assert "鼎新" in result
        assert "postgreSQL" in result  # tech 未啟用，不替換

    def test_multiple_sets_merged(self, tmp_dict_dir: Path) -> None:
        self._setup_two_sets(tmp_dict_dir)
        config = _make_config(active_sets=["erp", "tech"])
        engine = DictionaryEngine(config)
        engine.load_sets()

        result = engine.apply_rules("頂新 postgreSQL")
        assert "鼎新" in result
        assert "PostgreSQL" in result

    def test_set_active_sets_updates_config(self, tmp_dict_dir: Path) -> None:
        self._setup_two_sets(tmp_dict_dir)
        config = _make_config(active_sets=["erp"])
        engine = DictionaryEngine(config)
        engine.load_sets()
        engine.set_active_sets(["erp", "tech"])
        assert "tech" in config.dictionary.active_sets

    def test_hot_words_union_from_multiple_sets(self, tmp_dict_dir: Path) -> None:
        self._setup_two_sets(tmp_dict_dir)
        config = _make_config(active_sets=["erp", "tech"])
        engine = DictionaryEngine(config)
        engine.load_sets()

        mock_asr = MagicMock()
        engine.sync_hot_words(mock_asr)
        called_words = mock_asr.set_hot_words.call_args[0][0]
        word_names = {w.word for w in called_words}
        assert "ERP" in word_names
        assert "PostgreSQL" in word_names

    def test_create_and_delete_set(self, tmp_dict_dir: Path) -> None:
        config = _make_config()
        engine = DictionaryEngine(config)
        engine.load_sets()
        engine.create_set("custom")
        engine.save_set("custom")
        assert "custom" in engine.list_sets()
        assert (tmp_dict_dir / "custom.json").exists()

        engine.delete_set("custom")
        assert "custom" not in engine.list_sets()
        assert not (tmp_dict_dir / "custom.json").exists()

    def test_delete_default_raises(self, tmp_dict_dir: Path) -> None:
        config = _make_config()
        engine = DictionaryEngine(config)
        engine.load_sets()
        with pytest.raises(ValueError, match="預設辭典集"):
            engine.delete_set("default")

    def test_create_duplicate_raises(self, tmp_dict_dir: Path) -> None:
        config = _make_config()
        engine = DictionaryEngine(config)
        engine.load_sets()
        with pytest.raises(ValueError, match="已存在"):
            engine.create_set("default")


# ─────────────────────────────────────────────────────────────────────────────
# 任務 3.4：匯入/匯出格式測試
# ─────────────────────────────────────────────────────────────────────────────


class TestImportExport:
    def test_import_txt_hot_words(self, tmp_dict_dir: Path, tmp_path: Path) -> None:
        txt = tmp_path / "words.txt"
        txt.write_text("PostgreSQL\t9\nERP\t8\n# comment\nfoo", encoding="utf-8")
        config = _make_config()
        engine = DictionaryEngine(config)
        engine.load_sets()
        count = engine.import_hot_words(txt, "default", fmt="txt")
        assert count == 3
        words = engine.get_set("default").hot_words
        word_names = [hw.word for hw in words]
        assert "PostgreSQL" in word_names
        assert "foo" in word_names

    def test_import_csv_hot_words(self, tmp_dict_dir: Path, tmp_path: Path) -> None:
        csv = tmp_path / "words.csv"
        csv.write_text("word,weight,enabled\nPostgreSQL,9,true\nOldWord,3,false", encoding="utf-8")
        config = _make_config()
        engine = DictionaryEngine(config)
        engine.load_sets()
        count = engine.import_hot_words(csv, "default", fmt="csv")
        assert count == 2
        words = engine.get_set("default").hot_words
        names = {hw.word for hw in words}
        assert "PostgreSQL" in names
        assert "OldWord" in names

    def test_import_json_hot_words(self, tmp_dict_dir: Path, tmp_path: Path) -> None:
        data = {
            "hot_words": [
                {"word": "Kubernetes", "weight": 8, "enabled": True},
            ]
        }
        jf = tmp_path / "data.json"
        jf.write_text(json.dumps(data), encoding="utf-8")
        config = _make_config()
        engine = DictionaryEngine(config)
        engine.load_sets()
        count = engine.import_hot_words(jf, "default", fmt="json")
        assert count == 1
        assert engine.get_set("default").hot_words[-1].word == "Kubernetes"

    def test_import_csv_replace_rules(self, tmp_dict_dir: Path, tmp_path: Path) -> None:
        csv = tmp_path / "rules.csv"
        csv.write_text("from,to,regex,enabled\n頂新,鼎新,false,true", encoding="utf-8")
        config = _make_config()
        engine = DictionaryEngine(config)
        engine.load_sets()
        count = engine.import_replace_rules(csv, "default", fmt="csv")
        assert count == 1
        rule = engine.get_set("default").replace_rules[0]
        assert rule.from_text == "頂新"
        assert rule.to_text == "鼎新"

    def test_export_json(self, tmp_dict_dir: Path, tmp_path: Path) -> None:
        config = _make_config(
            hot_words=[{"word": "ERP", "weight": 8, "enabled": True}],
            replace_rules=[{"from": "A", "to": "B", "regex": False, "enabled": True}],
        )
        engine = DictionaryEngine(config)
        engine.load_sets()
        out = tmp_path / "out.json"
        engine.export_set("default", out, fmt="json")
        data = json.loads(out.read_text(encoding="utf-8"))
        assert "hot_words" in data
        assert "replace_rules" in data
        assert any(hw["word"] == "ERP" for hw in data["hot_words"])

    def test_export_airtype_dict(self, tmp_dict_dir: Path, tmp_path: Path) -> None:
        config = _make_config(
            hot_words=[{"word": "ERP", "weight": 8, "enabled": True}],
        )
        engine = DictionaryEngine(config)
        engine.load_sets()
        out = tmp_path / "export.airtype-dict"
        engine.export_set("default", out, fmt="airtype-dict")
        data = json.loads(out.read_text(encoding="utf-8"))
        assert "hot_words" in data

    def test_export_txt(self, tmp_dict_dir: Path, tmp_path: Path) -> None:
        config = _make_config(
            hot_words=[{"word": "ERP", "weight": 8, "enabled": True}],
        )
        engine = DictionaryEngine(config)
        engine.load_sets()
        out = tmp_path / "out.txt"
        engine.export_set("default", out, fmt="txt")
        content = out.read_text(encoding="utf-8")
        assert "ERP" in content
        assert "8" in content

    def test_export_csv(self, tmp_dict_dir: Path, tmp_path: Path) -> None:
        import csv as csv_module
        config = _make_config(
            hot_words=[{"word": "PostgreSQL", "weight": 9, "enabled": True}],
        )
        engine = DictionaryEngine(config)
        engine.load_sets()
        out = tmp_path / "out.csv"
        engine.export_set("default", out, fmt="csv")
        with open(out, newline="", encoding="utf-8") as f:
            rows = list(csv_module.DictReader(f))
        assert any(r["word"] == "PostgreSQL" for r in rows)

    def test_import_unknown_set_raises(self, tmp_dict_dir: Path, tmp_path: Path) -> None:
        txt = tmp_path / "words.txt"
        txt.write_text("foo", encoding="utf-8")
        config = _make_config()
        engine = DictionaryEngine(config)
        engine.load_sets()
        with pytest.raises(KeyError):
            engine.import_hot_words(txt, "nonexistent", fmt="txt")

    def test_export_unknown_format_raises(self, tmp_dict_dir: Path, tmp_path: Path) -> None:
        config = _make_config()
        engine = DictionaryEngine(config)
        engine.load_sets()
        out = tmp_path / "out.xyz"
        with pytest.raises(ValueError, match="不支援"):
            engine.export_set("default", out, fmt="xyz")

    def test_import_unsupported_format_raises(self, tmp_dict_dir: Path, tmp_path: Path) -> None:
        p = tmp_path / "foo.bar"
        p.write_text("x", encoding="utf-8")
        config = _make_config()
        engine = DictionaryEngine(config)
        engine.load_sets()
        with pytest.raises(ValueError, match="不支援"):
            engine.import_hot_words(p, "default", fmt="bar")
