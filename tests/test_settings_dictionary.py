"""辭典設定頁面 UI 佈局測試（TDD）。

涵蓋：
- 任務 1.1：_build_ui() 使用 QHBoxLayout 而非 QSplitter
- 任務 2.1：_build_sets_panel() 回傳 QGroupBox
- fix-dictionary-ui-bugs 1.1：engine 可用時新增辭典集後 _current_set 更新
- fix-dictionary-ui-bugs 1.2：engine 不可用時新增辭典集顯示警告
- fix-checkbox-rendering 1.1：checkbox 欄使用 setCellWidget + QCheckBox
"""

from __future__ import annotations

import sys

import pytest


@pytest.fixture(scope="session")
def qapp():
    """建立或重用 QApplication。若 PySide6 不可用則跳過。"""
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    yield app


@pytest.fixture()
def dummy_config():
    """建立最簡 AirtypeConfig。"""
    from airtype.config import AirtypeConfig
    return AirtypeConfig()


@pytest.fixture()
def dictionary_page(qapp, dummy_config):
    """建立 SettingsDictionaryPage 實例。"""
    from airtype.ui.settings_dictionary import SettingsDictionaryPage
    page = SettingsDictionaryPage(config=dummy_config)
    yield page
    page.deleteLater()


# ─────────────────────────────────────────────────────────────────────────────
# 佈局測試
# ─────────────────────────────────────────────────────────────────────────────

def test_layout_uses_hboxlayout_not_splitter(dictionary_page):
    """_build_ui() 的中間區域 SHALL 使用 QHBoxLayout，不使用 QSplitter。"""
    from PySide6.QtWidgets import QSplitter

    splitters = dictionary_page.findChildren(QSplitter)
    assert len(splitters) == 0, (
        f"頁面不應包含 QSplitter，但找到 {len(splitters)} 個"
    )


def test_sets_panel_is_groupbox(dictionary_page):
    """辭典集面板 SHALL 是 QGroupBox，與熱詞、替換規則面板風格一致。"""
    from PySide6.QtWidgets import QGroupBox

    group_boxes = dictionary_page.findChildren(QGroupBox)
    # 應有 3 個 QGroupBox：辭典集、熱詞、替換規則
    assert len(group_boxes) >= 3, (
        f"頁面應有至少 3 個 QGroupBox，但找到 {len(group_boxes)} 個"
    )


def test_sets_panel_fixed_width(dictionary_page):
    """辭典集 QGroupBox SHALL 固定寬度為 160px。"""
    from PySide6.QtWidgets import QGroupBox

    group_boxes = dictionary_page.findChildren(QGroupBox)
    # 第一個 GroupBox 應為辭典集面板（加入順序）
    sets_box = group_boxes[0]
    assert sets_box.maximumWidth() == 160, (
        f"辭典集面板寬度應為 160px，實際為 {sets_box.maximumWidth()}"
    )


# ─────────────────────────────────────────────────────────────────────────────
# fix-dictionary-ui-bugs：辭典集新增 & Checkbox 渲染
# ─────────────────────────────────────────────────────────────────────────────

def test_add_set_with_engine_updates_current_set(qapp, dummy_config):
    """Dictionary Set Creation Updates UI Immediately（engine 可用）。

    當 _dict_engine 提供時，呼叫 _on_add_set 後：
    - _current_set 應更新為新辭典集名稱
    - 清單中應出現新辭典集且被自動選取
    """
    from unittest.mock import MagicMock, patch
    from airtype.ui.settings_dictionary import SettingsDictionaryPage
    from airtype.core.dictionary import DictionarySet

    mock_engine = MagicMock()
    # 首次呼叫（__init__ 中）只有 "default"；第二次（_on_add_set 後）含新辭典集
    mock_engine.list_sets.side_effect = [
        ["default"],
        ["default", "my-new-set"],
    ]
    mock_engine.get_set.return_value = DictionarySet(name="default")
    mock_engine.has_set.return_value = True

    page = SettingsDictionaryPage(config=dummy_config, dictionary_engine=mock_engine)

    with patch("PySide6.QtWidgets.QInputDialog.getText", return_value=("my-new-set", True)):
        page._on_add_set()

    # _current_set 應已切換至新辭典集
    assert page._current_set == "my-new-set", (
        f"_current_set 應為 'my-new-set'，實際為 {page._current_set!r}"
    )
    # 清單中應出現新辭典集（名稱在 QCheckBox widget 中）
    from PySide6.QtWidgets import QCheckBox as _QCheckBox
    def _item_name(lst, i):
        w = lst.itemWidget(lst.item(i))
        return w.text() if isinstance(w, _QCheckBox) else ""
    items = [_item_name(page._sets_list, i) for i in range(page._sets_list.count())]
    assert "my-new-set" in items, f"清單應含 'my-new-set'，實際：{items}"
    # 新辭典集應被選取
    selected = page._sets_list.currentItem()
    selected_name = _item_name(page._sets_list, page._sets_list.currentRow()) if selected else None
    assert selected_name == "my-new-set", (
        f"選取項目應為 'my-new-set'，實際為 {selected_name!r}"
    )
    page.deleteLater()


def test_add_set_without_engine_shows_warning(qapp, dummy_config):
    """Dictionary Set Creation Updates UI Immediately（engine unavailable）。

    當 _dict_engine is None 時，_on_add_set 應顯示 QMessageBox.warning 且不新增項目。
    """
    from unittest.mock import patch
    from airtype.ui.settings_dictionary import SettingsDictionaryPage

    page = SettingsDictionaryPage(config=dummy_config)  # engine=None
    initial_count = page._sets_list.count()

    with patch("PySide6.QtWidgets.QInputDialog.getText", return_value=("new-set", True)), \
         patch("airtype.ui.settings_dictionary.QMessageBox") as mock_mb:
        page._on_add_set()
        mock_mb.warning.assert_called_once()

    # 清單不應增加新項目
    assert page._sets_list.count() == initial_count, (
        f"清單數量不應改變（期望 {initial_count}，實際 {page._sets_list.count()}）"
    )
    page.deleteLater()


def test_checkbox_items_use_qcheckbox_widget(qapp):
    """Checkbox Items Render Correctly on All Platforms。

    熱詞 enabled、替換規則 enabled 與 regex 欄應使用 QCheckBox widget
    （setCellWidget），確保深色/淺色主題下均可正確渲染。
    驗證：cellWidget 不為 None、含有 QCheckBox、isChecked() 與輸入資料一致。
    """
    from PySide6.QtWidgets import QCheckBox
    from airtype.config import AirtypeConfig
    from airtype.ui.settings_dictionary import SettingsDictionaryPage

    config = AirtypeConfig()
    config.dictionary.hot_words = [{"word": "測試", "weight": 5, "enabled": True}]
    config.dictionary.replace_rules = [{"from": "a", "to": "b", "regex": True, "enabled": False}]

    page = SettingsDictionaryPage(config=config)

    # 熱詞 col 0（enabled=True）
    hw_widget = page._hw_table.cellWidget(0, 0)
    assert hw_widget is not None, "熱詞 enabled cellWidget 不應為 None"
    hw_cb = hw_widget.findChild(QCheckBox)
    assert hw_cb is not None, "熱詞 enabled cellWidget 應含有 QCheckBox"
    assert hw_cb.isChecked() is True, "熱詞 enabled=True 時 QCheckBox 應為 checked"

    # 替換規則 col 0（enabled=False）
    rr_enabled_widget = page._rr_table.cellWidget(0, 0)
    assert rr_enabled_widget is not None, "替換規則 enabled cellWidget 不應為 None"
    rr_enabled_cb = rr_enabled_widget.findChild(QCheckBox)
    assert rr_enabled_cb is not None, "替換規則 enabled cellWidget 應含有 QCheckBox"
    assert rr_enabled_cb.isChecked() is False, "替換規則 enabled=False 時 QCheckBox 應為 unchecked"

    # 替換規則 col 3（regex=True）
    rr_regex_widget = page._rr_table.cellWidget(0, 3)
    assert rr_regex_widget is not None, "替換規則 regex cellWidget 不應為 None"
    rr_regex_cb = rr_regex_widget.findChild(QCheckBox)
    assert rr_regex_cb is not None, "替換規則 regex cellWidget 應含有 QCheckBox"
    assert rr_regex_cb.isChecked() is True, "替換規則 regex=True 時 QCheckBox 應為 checked"

    page.deleteLater()
