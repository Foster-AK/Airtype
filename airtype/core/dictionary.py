"""辭典引擎：熱詞管理、替換規則、辭典集管理。

辭典集以 JSON 格式儲存於 ~/.airtype/dictionaries/，每個辭典集為獨立檔案。
JSON 格式：
    {
        "hot_words": [{"word": "PostgreSQL", "weight": 9, "enabled": true}],
        "replace_rules": [{"from": "頂新", "to": "鼎新", "regex": false, "enabled": true}]
    }

主要用途：
- 熱詞（hot words）：在辨識前透過 set_hot_words() 注入 ASR 引擎以提升辨識率。
- 替換規則（replace rules）：在 ASR 輸出後、LLM 潤飾前對文字進行字串或正規表達式替換。
- 辭典集（dictionary sets）：具名分組，可同時啟用多組，取聯集套用。

使用方式::

    engine = DictionaryEngine(config)
    engine.load_sets()
    engine.sync_hot_words(asr_engine)   # 啟動時注入熱詞
    text = engine.apply_rules(text)     # ASR 後套用替換規則

相依：01-project-setup（設定）、06-asr-abstraction（HotWord）
"""

from __future__ import annotations

import json
import logging
import re
import tempfile
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

from airtype.core.asr_engine import HotWord

if TYPE_CHECKING:
    from airtype.config import AirtypeConfig

logger = logging.getLogger(__name__)

DICT_DIR: Path = Path.home() / ".airtype" / "dictionaries"

# 替換規則數量上限（防效能影響）
MAX_RULES: int = 100


# ---------------------------------------------------------------------------
# 資料模型
# ---------------------------------------------------------------------------


@dataclass
class HotWordEntry:
    """辭典集中的單一熱詞項目。"""

    word: str
    weight: int
    enabled: bool = True

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "HotWordEntry":
        return cls(
            word=str(d["word"]),
            weight=int(d.get("weight", 5)),
            enabled=bool(d.get("enabled", True)),
        )

    def to_dict(self) -> dict[str, Any]:
        return {"word": self.word, "weight": self.weight, "enabled": self.enabled}

    def to_hot_word(self) -> HotWord:
        return HotWord(word=self.word, weight=self.weight)


@dataclass
class ReplaceRule:
    """辭典集中的單一替換規則。"""

    from_text: str
    to_text: str
    regex: bool = False
    enabled: bool = True

    # 預先編譯的正規表達式（None 表示尚未編譯）
    _compiled: Optional[re.Pattern] = field(default=None, repr=False, compare=False)

    def __post_init__(self) -> None:
        if self.regex and self.from_text:
            try:
                self._compiled = re.compile(self.from_text)
            except re.error as exc:
                logger.warning("替換規則正規表達式編譯失敗 %r：%s", self.from_text, exc)
                self._compiled = None

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "ReplaceRule":
        return cls(
            from_text=str(d["from"]),
            to_text=str(d["to"]),
            regex=bool(d.get("regex", False)),
            enabled=bool(d.get("enabled", True)),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "from": self.from_text,
            "to": self.to_text,
            "regex": self.regex,
            "enabled": self.enabled,
        }

    def apply(self, text: str) -> str:
        """對文字套用本規則，回傳替換後文字。"""
        if not self.enabled or not self.from_text:
            return text
        if self.regex:
            pattern = self._compiled
            if pattern is None:
                return text
            return pattern.sub(self.to_text, text)
        return text.replace(self.from_text, self.to_text)


# ---------------------------------------------------------------------------
# 辭典集
# ---------------------------------------------------------------------------


@dataclass
class DictionarySet:
    """具名辭典集，包含熱詞與替換規則清單。"""

    name: str
    hot_words: list[HotWordEntry] = field(default_factory=list)
    replace_rules: list[ReplaceRule] = field(default_factory=list)

    @classmethod
    def from_dict(cls, name: str, data: dict[str, Any]) -> "DictionarySet":
        hot_words = [HotWordEntry.from_dict(hw) for hw in data.get("hot_words", [])]
        replace_rules = [ReplaceRule.from_dict(rr) for rr in data.get("replace_rules", [])]
        return cls(name=name, hot_words=hot_words, replace_rules=replace_rules)

    def to_dict(self) -> dict[str, Any]:
        return {
            "hot_words": [hw.to_dict() for hw in self.hot_words],
            "replace_rules": [rr.to_dict() for rr in self.replace_rules],
        }

    def get_enabled_hot_words(self) -> list[HotWord]:
        """取得所有啟用的熱詞（轉換為 HotWord dataclass）。"""
        return [hw.to_hot_word() for hw in self.hot_words if hw.enabled]

    def apply_rules(self, text: str) -> str:
        """對文字依序套用所有啟用的替換規則。"""
        for rule in self.replace_rules[:MAX_RULES]:
            text = rule.apply(text)
        return text


# ---------------------------------------------------------------------------
# 辭典引擎
# ---------------------------------------------------------------------------


class DictionaryEngine:
    """辭典引擎：載入、管理並套用辭典集。

    Args:
        config: AirtypeConfig 實例，用於讀取 active_sets 設定。
    """

    def __init__(self, config: "AirtypeConfig") -> None:
        self._config = config
        self._sets: dict[str, DictionarySet] = {}

    # ------------------------------------------------------------------
    # 載入與儲存
    # ------------------------------------------------------------------

    def load_sets(self) -> None:
        """從 DICT_DIR 載入所有辭典集 JSON 檔案。

        若 'default' 辭典集不存在，則從 config.dictionary 建立。
        """
        DICT_DIR.mkdir(parents=True, exist_ok=True)
        loaded: list[str] = []
        for json_file in sorted(DICT_DIR.glob("*.json")):
            try:
                data = json.loads(json_file.read_text(encoding="utf-8"))
                name = json_file.stem
                self._sets[name] = DictionarySet.from_dict(name, data)
                loaded.append(name)
            except Exception as exc:
                logger.warning("載入辭典集 %s 失敗：%s", json_file.name, exc)
        logger.info("已載入 %d 個辭典集：%s", len(loaded), loaded)

        if "default" not in self._sets:
            self._create_default_set()

    def _create_default_set(self) -> None:
        """從 config.dictionary.hot_words / replace_rules 建立預設辭典集。"""
        cfg = self._config.dictionary
        hot_words = [HotWordEntry.from_dict(hw) for hw in cfg.hot_words]
        replace_rules = [ReplaceRule.from_dict(rr) for rr in cfg.replace_rules]
        ds = DictionarySet(name="default", hot_words=hot_words, replace_rules=replace_rules)
        self._sets["default"] = ds
        try:
            self.save_set("default")
            logger.info("已從設定建立預設辭典集並儲存")
        except Exception as exc:
            logger.warning("儲存預設辭典集失敗：%s", exc)

    def save_set(self, name: str) -> None:
        """以原子寫入方式儲存指定辭典集至 DICT_DIR/{name}.json。

        Args:
            name: 辭典集名稱。

        Raises:
            KeyError: 若 name 不存在。
        """
        if name not in self._sets:
            raise KeyError(f"辭典集 {name!r} 不存在")
        DICT_DIR.mkdir(parents=True, exist_ok=True)
        target = DICT_DIR / f"{name}.json"
        fd, tmp = tempfile.mkstemp(dir=DICT_DIR, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(self._sets[name].to_dict(), f, ensure_ascii=False, indent=2)
            os.replace(tmp, target)
            logger.debug("已儲存辭典集：%s", name)
        except Exception:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise

    # ------------------------------------------------------------------
    # 辭典集 CRUD
    # ------------------------------------------------------------------

    def create_set(self, name: str) -> DictionarySet:
        """建立新空辭典集（不自動儲存）。

        Args:
            name: 辭典集名稱。

        Returns:
            新建的 DictionarySet。

        Raises:
            ValueError: 若名稱已存在或包含非法字元。
        """
        if name in self._sets:
            raise ValueError(f"辭典集 {name!r} 已存在")
        if not name or "/" in name or "\\" in name or name.startswith("."):
            raise ValueError(f"辭典集名稱不合法：{name!r}")
        ds = DictionarySet(name=name)
        self._sets[name] = ds
        return ds

    def delete_set(self, name: str) -> None:
        """刪除辭典集（同時刪除 JSON 檔）。

        Args:
            name: 辭典集名稱。

        Raises:
            ValueError: 若試圖刪除 'default' 辭典集。
            KeyError: 若名稱不存在。
        """
        if name == "default":
            raise ValueError("不可刪除預設辭典集")
        if name not in self._sets:
            raise KeyError(f"辭典集 {name!r} 不存在")
        del self._sets[name]
        json_file = DICT_DIR / f"{name}.json"
        try:
            if json_file.exists():
                json_file.unlink()
        except OSError as exc:
            logger.warning("刪除辭典集檔案 %s 失敗：%s", json_file, exc)
        # 從 active_sets 中移除
        if name in self._config.dictionary.active_sets:
            self._config.dictionary.active_sets.remove(name)

    def get_set(self, name: str) -> DictionarySet:
        """取得指定辭典集。

        Raises:
            KeyError: 若名稱不存在。
        """
        if name not in self._sets:
            raise KeyError(f"辭典集 {name!r} 不存在")
        return self._sets[name]

    def list_sets(self) -> list[str]:
        """回傳所有辭典集名稱清單（已排序）。"""
        return sorted(self._sets.keys())

    def has_set(self, name: str) -> bool:
        """回傳辭典集是否存在。"""
        return name in self._sets

    # ------------------------------------------------------------------
    # 作用中辭典集
    # ------------------------------------------------------------------

    @property
    def active_set_names(self) -> list[str]:
        """目前設定的作用中辭典集名稱清單。"""
        return self._config.dictionary.active_sets

    def set_active_sets(self, names: list[str]) -> None:
        """設定作用中辭典集清單，並更新 config（不自動儲存 config）。

        Args:
            names: 要啟用的辭典集名稱列表。
        """
        valid = [n for n in names if n in self._sets]
        self._config.dictionary.active_sets = valid
        logger.debug("作用中辭典集：%s", valid)

    # ------------------------------------------------------------------
    # 核心功能
    # ------------------------------------------------------------------

    def apply_rules(self, text: str) -> str:
        """對文字依序套用所有作用中辭典集的啟用替換規則。

        Args:
            text: ASR 輸出文字。

        Returns:
            套用替換規則後的文字。
        """
        for name in self._config.dictionary.active_sets:
            ds = self._sets.get(name)
            if ds is not None:
                text = ds.apply_rules(text)
        return text

    def sync_hot_words(self, asr_engine) -> None:
        """將所有作用中辭典集的啟用熱詞套用至 ASR 引擎。

        取所有作用中辭典集啟用熱詞的聯集，呼叫 asr_engine.set_hot_words()。

        Args:
            asr_engine: 實作 ASREngine Protocol 的引擎實例。
        """
        words: list[HotWord] = []
        for name in self._config.dictionary.active_sets:
            ds = self._sets.get(name)
            if ds is not None:
                words.extend(ds.get_enabled_hot_words())
        try:
            asr_engine.set_hot_words(words)
            logger.debug("已套用 %d 個熱詞至 ASR 引擎", len(words))
        except Exception as exc:
            logger.warning("套用熱詞至 ASR 引擎失敗：%s", exc)

    # ------------------------------------------------------------------
    # 匯入 / 匯出
    # ------------------------------------------------------------------

    def import_hot_words(
        self,
        path: Path,
        target_set: str = "default",
        fmt: str = "auto",
    ) -> int:
        """從檔案匯入熱詞至指定辭典集。

        支援格式：
        - .txt：每行一個詞，可附加 [TAB/逗號] 數字作為權重
        - .csv：需含 'word' 欄，選填 'weight' 欄
        - .json：完整辭典集 JSON

        Args:
            path:       來源檔案路徑。
            target_set: 目標辭典集名稱。
            fmt:        格式（'auto'、'txt'、'csv'、'json'）。

        Returns:
            成功匯入的熱詞數量。

        Raises:
            KeyError: 若 target_set 不存在。
            ValueError: 若格式不支援或解析失敗。
        """
        if target_set not in self._sets:
            raise KeyError(f"辭典集 {target_set!r} 不存在")

        if fmt == "auto":
            fmt = path.suffix.lstrip(".").lower()

        entries: list[HotWordEntry] = []

        if fmt == "txt":
            entries = self._parse_txt_hot_words(path)
        elif fmt == "csv":
            entries = self._parse_csv_hot_words(path)
        elif fmt == "json":
            data = json.loads(path.read_text(encoding="utf-8"))
            hw_list = data.get("hot_words", data) if isinstance(data, dict) else data
            entries = [HotWordEntry.from_dict(hw) for hw in hw_list]
        else:
            raise ValueError(f"不支援的匯入格式：{fmt!r}")

        ds = self._sets[target_set]
        ds.hot_words.extend(entries)
        logger.info("已匯入 %d 個熱詞至辭典集 %r", len(entries), target_set)
        return len(entries)

    def import_replace_rules(
        self,
        path: Path,
        target_set: str = "default",
        fmt: str = "auto",
    ) -> int:
        """從檔案匯入替換規則至指定辭典集。

        支援格式：
        - .csv：需含 'from'、'to' 欄，選填 'regex'、'enabled' 欄
        - .json：完整辭典集 JSON

        Args:
            path:       來源檔案路徑。
            target_set: 目標辭典集名稱。
            fmt:        格式（'auto'、'csv'、'json'）。

        Returns:
            成功匯入的規則數量。
        """
        if target_set not in self._sets:
            raise KeyError(f"辭典集 {target_set!r} 不存在")

        if fmt == "auto":
            fmt = path.suffix.lstrip(".").lower()

        rules: list[ReplaceRule] = []

        if fmt == "csv":
            rules = self._parse_csv_rules(path)
        elif fmt == "json":
            data = json.loads(path.read_text(encoding="utf-8"))
            rr_list = data.get("replace_rules", []) if isinstance(data, dict) else data
            rules = [ReplaceRule.from_dict(rr) for rr in rr_list]
        else:
            raise ValueError(f"不支援的替換規則匯入格式：{fmt!r}")

        ds = self._sets[target_set]
        ds.replace_rules.extend(rules)
        logger.info("已匯入 %d 條替換規則至辭典集 %r", len(rules), target_set)
        return len(rules)

    def export_set(self, name: str, path: Path, fmt: str = "auto") -> None:
        """匯出辭典集至檔案。

        支援格式：
        - .json：完整辭典集 JSON
        - .airtype-dict：同 JSON，副檔名不同（用於分享）
        - .txt：僅匯出熱詞，每行 "word\\tweight"
        - .csv：匯出熱詞至 CSV（含 word/weight/enabled 欄）

        Args:
            name: 辭典集名稱。
            path: 目標檔案路徑。
            fmt:  格式（'auto'、'json'、'airtype-dict'、'txt'、'csv'）。

        Raises:
            KeyError: 若 name 不存在。
        """
        if name not in self._sets:
            raise KeyError(f"辭典集 {name!r} 不存在")

        if fmt == "auto":
            suffix = path.suffix.lstrip(".")
            fmt = "airtype-dict" if suffix == "airtype-dict" else suffix.lower() or "json"

        ds = self._sets[name]

        if fmt in ("json", "airtype-dict"):
            path.write_text(
                json.dumps(ds.to_dict(), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        elif fmt == "txt":
            lines = [f"{hw.word}\t{hw.weight}" for hw in ds.hot_words]
            path.write_text("\n".join(lines), encoding="utf-8")
        elif fmt == "csv":
            import csv
            with open(path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=["word", "weight", "enabled"])
                writer.writeheader()
                for hw in ds.hot_words:
                    writer.writerow(hw.to_dict())
        else:
            raise ValueError(f"不支援的匯出格式：{fmt!r}")

        logger.info("已匯出辭典集 %r 至 %s（格式：%s）", name, path, fmt)

    # ------------------------------------------------------------------
    # 內部：解析輔助
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_txt_hot_words(path: Path) -> list[HotWordEntry]:
        """解析 .txt 熱詞檔：每行 "word" 或 "word[TAB/,]weight"。"""
        entries: list[HotWordEntry] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            for sep in ("\t", ","):
                if sep in line:
                    parts = line.split(sep, 1)
                    word = parts[0].strip()
                    try:
                        weight = max(1, min(10, int(parts[1].strip())))
                    except ValueError:
                        weight = 5
                    entries.append(HotWordEntry(word=word, weight=weight))
                    break
            else:
                entries.append(HotWordEntry(word=line, weight=5))
        return entries

    @staticmethod
    def _parse_csv_hot_words(path: Path) -> list[HotWordEntry]:
        """解析 .csv 熱詞檔：需含 'word' 欄，選填 'weight'、'enabled' 欄。"""
        import csv
        entries: list[HotWordEntry] = []
        with open(path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if "word" not in row:
                    continue
                word = row["word"].strip()
                if not word:
                    continue
                try:
                    weight = max(1, min(10, int(row.get("weight", "5"))))
                except ValueError:
                    weight = 5
                enabled_raw = row.get("enabled", "true").strip().lower()
                enabled = enabled_raw not in ("false", "0", "no")
                entries.append(HotWordEntry(word=word, weight=weight, enabled=enabled))
        return entries

    @staticmethod
    def _parse_csv_rules(path: Path) -> list[ReplaceRule]:
        """解析 .csv 替換規則檔：需含 'from'、'to' 欄。"""
        import csv
        rules: list[ReplaceRule] = []
        with open(path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if "from" not in row or "to" not in row:
                    continue
                from_text = row["from"].strip()
                if not from_text:
                    continue
                regex_raw = row.get("regex", "false").strip().lower()
                regex = regex_raw not in ("false", "0", "no")
                enabled_raw = row.get("enabled", "true").strip().lower()
                enabled = enabled_raw not in ("false", "0", "no")
                rules.append(ReplaceRule(
                    from_text=from_text,
                    to_text=row["to"].strip(),
                    regex=regex,
                    enabled=enabled,
                ))
        return rules
