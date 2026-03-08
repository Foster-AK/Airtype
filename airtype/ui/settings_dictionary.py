"""辭典設定頁面。

提供 SettingsDictionaryPage：
- 辭典集清單（多選啟用、新增/刪除）
- 熱詞編輯表格（詞彙、權重 1-10、啟用切換）
- 替換規則編輯表格（原文、替換文、正規表達式切換、啟用切換）
- 匯入（.txt/.csv/.json）/ 匯出（.txt/.csv/.json/.airtype-dict）
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from airtype.config import AirtypeConfig
    from airtype.core.asr_engine import ASREngineRegistry
    from airtype.core.dictionary import DictionaryEngine

logger = logging.getLogger(__name__)

from airtype.utils.i18n import tr  # noqa: E402

try:
    from PySide6.QtWidgets import (
        QAbstractItemView,
        QCheckBox,
        QFileDialog,
        QGroupBox,
        QHBoxLayout,
        QHeaderView,
        QLabel,
        QListWidget,
        QListWidgetItem,
        QMessageBox,
        QPushButton,
        QTableWidget,
        QTableWidgetItem,
        QVBoxLayout,
        QWidget,
    )
    from PySide6.QtCore import Qt, QSize

    _PYSIDE6_AVAILABLE = True
except ImportError:
    _PYSIDE6_AVAILABLE = False


if _PYSIDE6_AVAILABLE:

    class SettingsDictionaryPage(QWidget):
        """辭典設定頁面。

        分為三個區塊：
        1. 辭典集清單（左側）：顯示所有辭典集，勾選即啟用。
        2. 熱詞表格（右上）：編輯所選辭典集的熱詞。
        3. 替換規則表格（右下）：編輯所選辭典集的替換規則。
        """

        def __init__(
            self,
            config: "AirtypeConfig",
            schedule_save_fn=None,
            dictionary_engine: Optional["DictionaryEngine"] = None,
            on_hot_words_changed=None,
            asr_registry: Optional["ASREngineRegistry"] = None,
            parent: Optional[QWidget] = None,
        ) -> None:
            super().__init__(parent)
            self._config = config
            self._schedule_save = schedule_save_fn
            self._dict_engine = dictionary_engine
            self._on_hot_words_changed = on_hot_words_changed
            self._asr_registry = asr_registry
            self._current_set: str = "default"
            self._build_ui()
            self._reload_sets_list()
            self._load_set_data(self._current_set)

        # ── UI 建構 ──────────────────────────────────────────────────────────

        def _build_ui(self) -> None:
            outer = QVBoxLayout(self)
            outer.setContentsMargins(16, 16, 16, 16)
            outer.setSpacing(12)

            self._title_label = QLabel(tr("settings.dictionary.title"))
            self._title_label.setStyleSheet("font-size: 16px; font-weight: bold;")
            outer.addWidget(self._title_label)

            # 水平排列：左側辭典集 / 右側內容
            h_layout = QHBoxLayout()
            h_layout.setSpacing(8)
            outer.addLayout(h_layout, stretch=1)

            # 左側：辭典集清單
            h_layout.addWidget(self._build_sets_panel(), stretch=0)

            # 右側：熱詞 + 替換規則（垂直排列）
            right = QWidget()
            right_layout = QVBoxLayout(right)
            right_layout.setContentsMargins(0, 0, 0, 0)
            right_layout.setSpacing(8)
            self._hw_group = self._build_hot_words_group()
            right_layout.addWidget(self._hw_group)
            self._rr_group = self._build_replace_rules_group()
            right_layout.addWidget(self._rr_group)
            h_layout.addWidget(right, stretch=1)

            # 底部匯入/匯出按鈕
            outer.addWidget(self._build_import_export_bar())

        def _build_sets_panel(self) -> QGroupBox:
            panel = QGroupBox(tr("settings.dictionary.sets_label"))
            panel.setFixedWidth(160)
            self._sets_group = panel
            layout = QVBoxLayout(panel)
            layout.setContentsMargins(8, 4, 8, 8)
            layout.setSpacing(4)

            self._sets_list = QListWidget()
            self._sets_list.setToolTip(tr("settings.dictionary.sets_tooltip"))
            self._sets_list.currentRowChanged.connect(self._on_set_selected)
            layout.addWidget(self._sets_list, stretch=1)

            btn_row = QHBoxLayout()
            btn_row.setSpacing(4)
            self._btn_add_set = QPushButton("＋")
            self._btn_add_set.setFixedWidth(32)
            self._btn_add_set.setToolTip(tr("settings.dictionary.add_set_tooltip"))
            self._btn_add_set.clicked.connect(self._on_add_set)
            self._btn_del_set = QPushButton("－")
            self._btn_del_set.setFixedWidth(32)
            self._btn_del_set.setToolTip(tr("settings.dictionary.del_set_tooltip"))
            self._btn_del_set.clicked.connect(self._on_delete_set)
            btn_row.addWidget(self._btn_add_set)
            btn_row.addWidget(self._btn_del_set)
            btn_row.addStretch()
            layout.addLayout(btn_row)
            return panel

        def _build_hot_words_group(self) -> QGroupBox:
            box = QGroupBox(tr("settings.dictionary.hot_words_group"))
            layout = QVBoxLayout(box)
            layout.setSpacing(4)

            # 引擎不支援熱詞時的警告標籤
            self._hw_warning = QLabel(tr("settings.dictionary.hw_unsupported_warning"))
            self._hw_warning.setWordWrap(True)
            self._hw_warning.setStyleSheet(
                "QLabel { color: #b35900; background-color: #fff3cd; "
                "border: 1px solid #ffc107; border-radius: 4px; padding: 6px; }"
            )
            self._hw_warning.setVisible(False)
            layout.addWidget(self._hw_warning)
            self._update_hw_warning()

            # 表格
            self._hw_table = QTableWidget(0, 3)
            self._hw_table.setHorizontalHeaderLabels([
                tr("settings.dictionary.hw_col.enabled"),
                tr("settings.dictionary.hw_col.word"),
                tr("settings.dictionary.hw_col.weight"),
            ])
            self._hw_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
            self._hw_table.horizontalHeader().setDefaultSectionSize(60)
            self._hw_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
            self._hw_table.setEditTriggers(
                QAbstractItemView.EditTrigger.DoubleClicked
                | QAbstractItemView.EditTrigger.SelectedClicked
            )
            self._hw_table.setAlternatingRowColors(True)
            self._hw_table.verticalHeader().setVisible(False)
            self._hw_table.itemChanged.connect(self._on_hw_changed)
            layout.addWidget(self._hw_table)

            # 工具列
            toolbar = QHBoxLayout()
            toolbar.setSpacing(4)
            btn_add = QPushButton(tr("settings.dictionary.btn.add"))
            btn_add.clicked.connect(self._on_add_hot_word)
            btn_del = QPushButton(tr("settings.dictionary.btn.delete"))
            btn_del.clicked.connect(self._on_delete_hot_word)
            toolbar.addWidget(btn_add)
            toolbar.addWidget(btn_del)
            toolbar.addStretch()
            layout.addLayout(toolbar)
            return box

        def _build_replace_rules_group(self) -> QGroupBox:
            box = QGroupBox(tr("settings.dictionary.replace_rules_group"))
            layout = QVBoxLayout(box)
            layout.setSpacing(4)

            # 表格
            self._rr_table = QTableWidget(0, 4)
            self._rr_table.setHorizontalHeaderLabels([
                tr("settings.dictionary.rr_col.enabled"),
                tr("settings.dictionary.rr_col.original"),
                tr("settings.dictionary.rr_col.replacement"),
                tr("settings.dictionary.rr_col.regex"),
            ])
            self._rr_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
            self._rr_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
            self._rr_table.horizontalHeader().setDefaultSectionSize(60)
            self._rr_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
            self._rr_table.setEditTriggers(
                QAbstractItemView.EditTrigger.DoubleClicked
                | QAbstractItemView.EditTrigger.SelectedClicked
            )
            self._rr_table.setAlternatingRowColors(True)
            self._rr_table.verticalHeader().setVisible(False)
            self._rr_table.itemChanged.connect(self._on_rr_changed)
            layout.addWidget(self._rr_table)

            # 工具列
            toolbar = QHBoxLayout()
            toolbar.setSpacing(4)
            btn_add = QPushButton(tr("settings.dictionary.btn.add"))
            btn_add.clicked.connect(self._on_add_replace_rule)
            btn_del = QPushButton(tr("settings.dictionary.btn.delete"))
            btn_del.clicked.connect(self._on_delete_replace_rule)
            toolbar.addWidget(btn_add)
            toolbar.addWidget(btn_del)
            toolbar.addStretch()
            layout.addLayout(toolbar)
            return box

        def _make_check_widget(self, checked: bool, on_change) -> QWidget:
            """建立置中的 QCheckBox 容器 widget，用於表格 cell。"""
            container = QWidget()
            layout = QHBoxLayout(container)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            cb = QCheckBox()
            cb.blockSignals(True)
            cb.setChecked(checked)
            cb.blockSignals(False)
            cb.stateChanged.connect(on_change)
            layout.addWidget(cb)
            return container

        def _get_cell_check(self, table: "QTableWidget", row: int, col: int) -> bool:
            """從 cell widget 讀取 QCheckBox 的勾選狀態。"""
            widget = table.cellWidget(row, col)
            if widget is None:
                return True
            cb = widget.findChild(QCheckBox)
            return cb.isChecked() if cb else True

        def _build_import_export_bar(self) -> QWidget:
            bar = QWidget()
            layout = QHBoxLayout(bar)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(8)

            self._ops_lbl = QLabel(tr("settings.dictionary.ops_label"))
            layout.addWidget(self._ops_lbl)

            self._btn_import_hw = QPushButton(tr("settings.dictionary.import_hot_words_btn"))
            self._btn_import_hw.setToolTip(tr("settings.dictionary.import_hot_words_tooltip"))
            self._btn_import_hw.clicked.connect(self._on_import_hot_words)
            layout.addWidget(self._btn_import_hw)

            self._btn_import_rr = QPushButton(tr("settings.dictionary.import_rules_btn"))
            self._btn_import_rr.setToolTip(tr("settings.dictionary.import_rules_tooltip"))
            self._btn_import_rr.clicked.connect(self._on_import_replace_rules)
            layout.addWidget(self._btn_import_rr)

            self._btn_export = QPushButton(tr("settings.dictionary.export_btn"))
            self._btn_export.setToolTip(tr("settings.dictionary.export_tooltip"))
            self._btn_export.clicked.connect(self._on_export_set)
            layout.addWidget(self._btn_export)

            layout.addStretch()
            return bar

        def retranslate_ui(self, _: str = None) -> None:
            """語言切換時刷新所有標籤文字。"""
            self._title_label.setText(tr("settings.dictionary.title"))
            self._sets_group.setTitle(tr("settings.dictionary.sets_label"))
            self._sets_list.setToolTip(tr("settings.dictionary.sets_tooltip"))
            self._btn_add_set.setToolTip(tr("settings.dictionary.add_set_tooltip"))
            self._btn_del_set.setToolTip(tr("settings.dictionary.del_set_tooltip"))
            self._hw_group.setTitle(tr("settings.dictionary.hot_words_group"))
            self._hw_warning.setText(tr("settings.dictionary.hw_unsupported_warning"))
            self._hw_table.setHorizontalHeaderLabels([
                tr("settings.dictionary.hw_col.enabled"),
                tr("settings.dictionary.hw_col.word"),
                tr("settings.dictionary.hw_col.weight"),
            ])
            self._rr_group.setTitle(tr("settings.dictionary.replace_rules_group"))
            self._rr_table.setHorizontalHeaderLabels([
                tr("settings.dictionary.rr_col.enabled"),
                tr("settings.dictionary.rr_col.original"),
                tr("settings.dictionary.rr_col.replacement"),
                tr("settings.dictionary.rr_col.regex"),
            ])
            self._ops_lbl.setText(tr("settings.dictionary.ops_label"))
            self._btn_import_hw.setText(tr("settings.dictionary.import_hot_words_btn"))
            self._btn_import_hw.setToolTip(tr("settings.dictionary.import_hot_words_tooltip"))
            self._btn_import_rr.setText(tr("settings.dictionary.import_rules_btn"))
            self._btn_import_rr.setToolTip(tr("settings.dictionary.import_rules_tooltip"))
            self._btn_export.setText(tr("settings.dictionary.export_btn"))
            self._btn_export.setToolTip(tr("settings.dictionary.export_tooltip"))

        # ── 資料載入 ────────────────────────────────────────────────────────

        def _reload_sets_list(self) -> None:
            """重新整理左側辭典集清單。"""
            self._sets_list.blockSignals(True)
            self._sets_list.clear()
            if self._dict_engine is None:
                # 無辭典引擎時顯示 config 內的辭典集名稱
                names = list(self._config.dictionary.active_sets) or ["default"]
            else:
                names = self._dict_engine.list_sets()

            active = set(self._config.dictionary.active_sets)
            for name in names:
                item = QListWidgetItem()
                self._sets_list.addItem(item)
                cb = QCheckBox(name)
                cb.blockSignals(True)
                cb.setChecked(name in active)
                cb.blockSignals(False)
                cb.stateChanged.connect(
                    lambda state, n=name: self._on_set_active_changed(n, bool(state))
                )
                item.setSizeHint(QSize(0, cb.sizeHint().height() + 4))
                self._sets_list.setItemWidget(item, cb)

            # 選取目前編輯中的辭典集
            for i in range(self._sets_list.count()):
                w = self._sets_list.itemWidget(self._sets_list.item(i))
                if isinstance(w, QCheckBox) and w.text() == self._current_set:
                    self._sets_list.setCurrentRow(i)
                    break
            else:
                if self._sets_list.count() > 0:
                    self._sets_list.setCurrentRow(0)
            self._sets_list.blockSignals(False)

        def _load_set_data(self, name: str) -> None:
            """將指定辭典集的熱詞與替換規則載入表格。"""
            self._current_set = name

            if self._dict_engine is not None:
                try:
                    ds = self._dict_engine.get_set(name)
                    hot_words = [hw.to_dict() for hw in ds.hot_words]
                    replace_rules = [rr.to_dict() for rr in ds.replace_rules]
                except KeyError:
                    hot_words = []
                    replace_rules = []
            elif name == "default":
                hot_words = self._config.dictionary.hot_words
                replace_rules = self._config.dictionary.replace_rules
            else:
                hot_words = []
                replace_rules = []

            self._populate_hw_table(hot_words)
            self._populate_rr_table(replace_rules)

        def _populate_hw_table(self, hot_words: list) -> None:
            """填入熱詞表格。"""
            self._hw_table.blockSignals(True)
            self._hw_table.setRowCount(0)
            for hw in hot_words:
                row = self._hw_table.rowCount()
                self._hw_table.insertRow(row)
                self._set_hw_row(row, hw)
            self._hw_table.blockSignals(False)

        def _set_hw_row(self, row: int, hw: dict) -> None:
            # 啟用核取框（使用 QCheckBox widget 取代 QTableWidgetItem）
            self._hw_table.setCellWidget(
                row, 0,
                self._make_check_widget(
                    hw.get("enabled", True),
                    lambda: (self._flush_hw_to_engine(), self._trigger_save()),
                ),
            )
            # 詞彙
            self._hw_table.setItem(row, 1, QTableWidgetItem(str(hw.get("word", ""))))
            # 權重
            weight_item = QTableWidgetItem(str(hw.get("weight", 5)))
            weight_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._hw_table.setItem(row, 2, weight_item)

        def _populate_rr_table(self, rules: list) -> None:
            """填入替換規則表格。"""
            self._rr_table.blockSignals(True)
            self._rr_table.setRowCount(0)
            for rr in rules:
                row = self._rr_table.rowCount()
                self._rr_table.insertRow(row)
                self._set_rr_row(row, rr)
            self._rr_table.blockSignals(False)

        def _set_rr_row(self, row: int, rr: dict) -> None:
            # 啟用（使用 QCheckBox widget 取代 QTableWidgetItem）
            self._rr_table.setCellWidget(
                row, 0,
                self._make_check_widget(
                    rr.get("enabled", True),
                    lambda: (self._flush_rr_to_engine(), self._trigger_save()),
                ),
            )
            # 原始文字
            self._rr_table.setItem(row, 1, QTableWidgetItem(str(rr.get("from", ""))))
            # 替換文字
            self._rr_table.setItem(row, 2, QTableWidgetItem(str(rr.get("to", ""))))
            # 正規表達式（使用 QCheckBox widget 取代 QTableWidgetItem）
            self._rr_table.setCellWidget(
                row, 3,
                self._make_check_widget(
                    rr.get("regex", False),
                    lambda: (self._flush_rr_to_engine(), self._trigger_save()),
                ),
            )

        # ── 事件：辭典集清單 ────────────────────────────────────────────────

        def _on_set_selected(self, row: int) -> None:
            if row < 0:
                return
            item = self._sets_list.item(row)
            if item:
                w = self._sets_list.itemWidget(item)
                name = w.text() if isinstance(w, QCheckBox) else ""
                if name:
                    self._load_set_data(name)

        def _on_set_active_changed(self, name: str, checked: bool) -> None:
            """使用者勾選/取消辭典集 checkbox 時更新 active_sets。"""
            active = list(self._config.dictionary.active_sets)
            if checked:
                if name not in active:
                    active.append(name)
            else:
                if name in active:
                    active.remove(name)
            self._config.dictionary.active_sets = active
            if self._dict_engine is not None:
                self._dict_engine.set_active_sets(active)
            self._trigger_save()

        def _on_add_set(self) -> None:
            """新增辭典集（彈出輸入對話框）。"""
            from PySide6.QtWidgets import QInputDialog
            name, ok = QInputDialog.getText(self, "新增辭典集", "辭典集名稱：")
            if not ok or not name.strip():
                return
            name = name.strip()
            if self._dict_engine is None:
                QMessageBox.warning(self, "無法新增", "辭典引擎尚未初始化，無法新增辭典集。")
                return
            try:
                self._dict_engine.create_set(name)
                self._dict_engine.save_set(name)
            except (ValueError, Exception) as exc:
                QMessageBox.warning(self, "建立失敗", str(exc))
                return
            self._current_set = name
            self._reload_sets_list()
            self._load_set_data(name)

        def _on_delete_set(self) -> None:
            """刪除選取辭典集（需確認）。"""
            item = self._sets_list.currentItem()
            if item is None:
                return
            w = self._sets_list.itemWidget(item)
            name = w.text() if isinstance(w, QCheckBox) else ""
            if not name:
                return
            if name == "default":
                QMessageBox.warning(self, "無法刪除", "預設辭典集不可刪除。")
                return
            reply = QMessageBox.question(
                self,
                "確認刪除",
                f"確定要刪除辭典集「{name}」嗎？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
            if self._dict_engine is not None:
                try:
                    self._dict_engine.delete_set(name)
                except Exception as exc:
                    QMessageBox.warning(self, "刪除失敗", str(exc))
                    return
            self._current_set = "default"
            self._reload_sets_list()
            self._load_set_data("default")
            self._trigger_save()

        # ── 事件：熱詞表格 ──────────────────────────────────────────────────

        def _on_hw_changed(self, item: "QTableWidgetItem") -> None:
            self._flush_hw_to_engine()
            self._trigger_save()

        def _on_add_hot_word(self) -> None:
            row = self._hw_table.rowCount()
            self._hw_table.blockSignals(True)
            self._hw_table.insertRow(row)
            self._set_hw_row(row, {"word": "", "weight": 5, "enabled": True})
            self._hw_table.blockSignals(False)
            self._hw_table.editItem(self._hw_table.item(row, 1))
            self._flush_hw_to_engine()
            self._trigger_save()

        def _on_delete_hot_word(self) -> None:
            rows = sorted(
                {idx.row() for idx in self._hw_table.selectedIndexes()},
                reverse=True,
            )
            self._hw_table.blockSignals(True)
            for row in rows:
                self._hw_table.removeRow(row)
            self._hw_table.blockSignals(False)
            self._flush_hw_to_engine()
            self._trigger_save()

        def _flush_hw_to_engine(self) -> None:
            """將目前熱詞表格資料寫回辭典引擎（或 config）。"""
            hot_words = []
            for row in range(self._hw_table.rowCount()):
                word_item = self._hw_table.item(row, 1)
                w_item = self._hw_table.item(row, 2)
                if word_item is None:
                    continue
                word = word_item.text().strip()
                if not word:
                    continue
                enabled = self._get_cell_check(self._hw_table, row, 0)
                try:
                    weight = max(1, min(10, int(w_item.text()))) if w_item else 5
                except ValueError:
                    weight = 5
                hot_words.append({"word": word, "weight": weight, "enabled": enabled})

            if self._dict_engine is not None and self._dict_engine.has_set(self._current_set):
                from airtype.core.dictionary import HotWordEntry
                ds = self._dict_engine.get_set(self._current_set)
                ds.hot_words = [HotWordEntry.from_dict(hw) for hw in hot_words]
                try:
                    self._dict_engine.save_set(self._current_set)
                except Exception as exc:
                    logger.warning("儲存熱詞失敗：%s", exc)
            elif self._current_set == "default":
                self._config.dictionary.hot_words = hot_words

            if self._on_hot_words_changed is not None:
                try:
                    self._on_hot_words_changed()
                except Exception as exc:
                    logger.warning("熱詞變更回呼失敗：%s", exc)

        # ── 事件：替換規則表格 ──────────────────────────────────────────────

        def _on_rr_changed(self, item: "QTableWidgetItem") -> None:
            self._flush_rr_to_engine()
            self._trigger_save()

        def _on_add_replace_rule(self) -> None:
            row = self._rr_table.rowCount()
            self._rr_table.blockSignals(True)
            self._rr_table.insertRow(row)
            self._set_rr_row(row, {"from": "", "to": "", "regex": False, "enabled": True})
            self._rr_table.blockSignals(False)
            self._rr_table.editItem(self._rr_table.item(row, 1))
            self._flush_rr_to_engine()
            self._trigger_save()

        def _on_delete_replace_rule(self) -> None:
            rows = sorted(
                {idx.row() for idx in self._rr_table.selectedIndexes()},
                reverse=True,
            )
            self._rr_table.blockSignals(True)
            for row in rows:
                self._rr_table.removeRow(row)
            self._rr_table.blockSignals(False)
            self._flush_rr_to_engine()
            self._trigger_save()

        def _flush_rr_to_engine(self) -> None:
            """將目前替換規則表格資料寫回辭典引擎（或 config）。"""
            rules = []
            for row in range(self._rr_table.rowCount()):
                from_item = self._rr_table.item(row, 1)
                to_item = self._rr_table.item(row, 2)
                if from_item is None:
                    continue
                from_text = from_item.text().strip()
                if not from_text:
                    continue
                enabled = self._get_cell_check(self._rr_table, row, 0)
                regex = self._get_cell_check(self._rr_table, row, 3)
                rules.append({
                    "from": from_text,
                    "to": to_item.text().strip() if to_item else "",
                    "regex": regex,
                    "enabled": enabled,
                })

            if self._dict_engine is not None and self._dict_engine.has_set(self._current_set):
                from airtype.core.dictionary import ReplaceRule
                ds = self._dict_engine.get_set(self._current_set)
                ds.replace_rules = [ReplaceRule.from_dict(rr) for rr in rules]
                try:
                    self._dict_engine.save_set(self._current_set)
                except Exception as exc:
                    logger.warning("儲存替換規則失敗：%s", exc)
            elif self._current_set == "default":
                self._config.dictionary.replace_rules = rules

        # ── 匯入 / 匯出 ─────────────────────────────────────────────────────

        def _on_import_hot_words(self) -> None:
            path, _ = QFileDialog.getOpenFileName(
                self,
                "匯入熱詞",
                "",
                "支援格式 (*.txt *.csv *.json);;全部檔案 (*)",
            )
            if not path:
                return
            p = Path(path)
            if self._dict_engine is None:
                QMessageBox.warning(self, "無法匯入", "辭典引擎尚未初始化。")
                return
            try:
                count = self._dict_engine.import_hot_words(p, self._current_set)
                self._dict_engine.save_set(self._current_set)
                self._load_set_data(self._current_set)
                QMessageBox.information(self, "匯入成功", f"已匯入 {count} 個熱詞。")
            except Exception as exc:
                QMessageBox.critical(self, "匯入失敗", str(exc))

        def _on_import_replace_rules(self) -> None:
            path, _ = QFileDialog.getOpenFileName(
                self,
                "匯入替換規則",
                "",
                "支援格式 (*.csv *.json);;全部檔案 (*)",
            )
            if not path:
                return
            p = Path(path)
            if self._dict_engine is None:
                QMessageBox.warning(self, "無法匯入", "辭典引擎尚未初始化。")
                return
            try:
                count = self._dict_engine.import_replace_rules(p, self._current_set)
                self._dict_engine.save_set(self._current_set)
                self._load_set_data(self._current_set)
                QMessageBox.information(self, "匯入成功", f"已匯入 {count} 條替換規則。")
            except Exception as exc:
                QMessageBox.critical(self, "匯入失敗", str(exc))

        def _on_export_set(self) -> None:
            path, _ = QFileDialog.getSaveFileName(
                self,
                "匯出辭典集",
                f"{self._current_set}.airtype-dict",
                "Airtype 辭典 (*.airtype-dict);;JSON (*.json);;純文字 (*.txt);;CSV (*.csv);;全部檔案 (*)",
            )
            if not path:
                return
            p = Path(path)
            if self._dict_engine is None:
                QMessageBox.warning(self, "無法匯出", "辭典引擎尚未初始化。")
                return
            try:
                self._dict_engine.export_set(self._current_set, p)
                QMessageBox.information(self, "匯出成功", f"已匯出至：{path}")
            except Exception as exc:
                QMessageBox.critical(self, "匯出失敗", str(exc))

        # ── 輔助 ────────────────────────────────────────────────────────────

        def _update_hw_warning(self) -> None:
            """依 ASR 引擎是否支援熱詞，顯示/隱藏警告標籤。"""
            if self._asr_registry is None:
                self._hw_warning.setVisible(False)
                return
            engine = self._asr_registry.active_engine
            if engine is None or getattr(engine, "supports_hot_words", True):
                self._hw_warning.setVisible(False)
            else:
                self._hw_warning.setVisible(True)

        def _trigger_save(self) -> None:
            if self._schedule_save is not None:
                self._schedule_save()

else:

    class SettingsDictionaryPage:  # type: ignore[no-redef]
        pass
