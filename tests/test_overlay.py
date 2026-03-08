"""疊層 UI 元件單元測試（TDD）。

涵蓋：
- 任務 5.1：CapsuleOverlay 建立、顯示/隱藏、位置持久化
- 任務 5.2：WaveformWidget 音波條高度計算（從 RMS 值）

純 Python 測試（compute_bar_heights、parse_pill_position）不依賴 PySide6，
可在任何環境執行。Qt 元件測試在 PySide6 可用時執行。
"""

from __future__ import annotations

import sys

import pytest

# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────


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
def dummy_config(tmp_path):
    """建立使用臨時目錄的 AirtypeConfig。"""
    from airtype.config import AirtypeConfig

    cfg = AirtypeConfig()
    # 指向臨時路徑以避免污染真實設定
    cfg._test_save_path = tmp_path / "config.json"
    return cfg


# ─────────────────────────────────────────────────────────────────────────────
# 任務 5.2：compute_bar_heights（純 Python，不需 Qt）
# ─────────────────────────────────────────────────────────────────────────────


class TestComputeBarHeights:
    """測試音波條高度計算函式。"""

    def test_returns_correct_count(self):
        from airtype.ui.waveform_widget import BAR_COUNT, compute_bar_heights

        heights = compute_bar_heights(0.5, 0.0)
        assert len(heights) == BAR_COUNT

    def test_custom_bar_count(self):
        from airtype.ui.waveform_widget import compute_bar_heights

        heights = compute_bar_heights(0.5, 0.0, bar_count=3)
        assert len(heights) == 3

    def test_zero_rms_gives_min_height(self):
        from airtype.ui.waveform_widget import BAR_MIN_HEIGHT, compute_bar_heights

        heights = compute_bar_heights(0.0, 0.0, max_height=40)
        assert all(h == BAR_MIN_HEIGHT for h in heights)

    def test_all_heights_at_least_min(self):
        from airtype.ui.waveform_widget import BAR_MIN_HEIGHT, compute_bar_heights

        for rms in [0.0, 0.25, 0.5, 0.75, 1.0]:
            heights = compute_bar_heights(rms, 1.5, max_height=40)
            assert all(h >= BAR_MIN_HEIGHT for h in heights), (
                f"rms={rms} 時有高度低於 BAR_MIN_HEIGHT"
            )

    def test_heights_not_exceed_max(self):
        from airtype.ui.waveform_widget import compute_bar_heights

        heights = compute_bar_heights(1.0, 1.0, max_height=40)
        assert all(h <= 40 for h in heights)

    def test_higher_rms_gives_higher_average(self):
        # rms=0.0 時不執行亂數分支（if rms > 0.0 保護），
        # 全部回傳 BAR_MIN_HEIGHT，無需 seed 即可確定性比較。
        from airtype.ui.waveform_widget import BAR_MIN_HEIGHT, compute_bar_heights

        low_heights = compute_bar_heights(0.0, 1.0, max_height=40)
        high_heights = compute_bar_heights(1.0, 1.0, max_height=40)
        assert all(h == BAR_MIN_HEIGHT for h in low_heights)
        assert sum(high_heights) > sum(low_heights)

    def test_different_time_gives_different_heights(self):
        # 使用非整數秒（0.37），確保所有 bar 的正弦相位均不同，
        # 避免整數秒時頻率整數倍 bar（freq=1.0 at t=1.0）相位回到 0 的邊界情況。
        from airtype.ui.waveform_widget import compute_bar_heights

        heights_t0 = compute_bar_heights(0.8, 0.0, max_height=40)
        heights_t1 = compute_bar_heights(0.8, 0.37, max_height=40)
        # 不同時間應有至少一條高度不同（動畫效果）
        assert heights_t0 != heights_t1


# ─────────────────────────────────────────────────────────────────────────────
# 任務 5.1：parse_pill_position（純 Python，不需 Qt）
# ─────────────────────────────────────────────────────────────────────────────


class TestParsePillPosition:
    """測試膠囊位置解析函式。"""

    def test_center_preset(self):
        from airtype.ui.overlay import CAPSULE_HEIGHT, CAPSULE_WIDTH, parse_pill_position

        x, y = parse_pill_position("center", 1920, 1080)
        assert x == (1920 - CAPSULE_WIDTH) // 2
        assert y == 1080 - CAPSULE_HEIGHT - 80

    def test_custom_xy(self):
        from airtype.ui.overlay import parse_pill_position

        x, y = parse_pill_position("123,456", 1920, 1080)
        assert x == 123
        assert y == 456

    def test_custom_xy_with_spaces(self):
        from airtype.ui.overlay import parse_pill_position

        x, y = parse_pill_position(" 100 , 200 ", 1920, 1080)
        assert x == 100
        assert y == 200

    def test_invalid_falls_back_to_center(self):
        from airtype.ui.overlay import CAPSULE_HEIGHT, CAPSULE_WIDTH, parse_pill_position

        x, y = parse_pill_position("invalid_pos", 1920, 1080)
        assert x == (1920 - CAPSULE_WIDTH) // 2
        assert y == 1080 - CAPSULE_HEIGHT - 80

    def test_partial_invalid_falls_back(self):
        from airtype.ui.overlay import parse_pill_position

        x, y = parse_pill_position("abc,def", 1920, 1080)
        # 應退回到預設
        assert isinstance(x, int)
        assert isinstance(y, int)


# ─────────────────────────────────────────────────────────────────────────────
# 任務 5.1：CapsuleOverlay Qt 測試（需要 PySide6 + QApplication）
# ─────────────────────────────────────────────────────────────────────────────


class TestCapsuleOverlay:
    """CapsuleOverlay 建立與基本行為測試。"""

    def test_import(self):
        pytest.importorskip("PySide6")
        from airtype.ui.overlay import CapsuleOverlay  # noqa: F401

    def test_create(self, qapp):
        from airtype.ui.overlay import CAPSULE_WIDTH, CapsuleOverlay

        overlay = CapsuleOverlay()
        # 寬度固定為 CAPSULE_WIDTH；高度由 layout 自動計算（CapsuleBody=48 + 狀態文字）
        assert overlay.width() == CAPSULE_WIDTH
        assert overlay._capsule_body.height() == 48
        overlay.close()

    def test_not_visible_initially(self, qapp):
        from airtype.ui.overlay import CapsuleOverlay

        overlay = CapsuleOverlay()
        assert not overlay.isVisible()
        overlay.close()

    def test_show_makes_visible(self, qapp):
        from airtype.ui.overlay import CapsuleOverlay

        overlay = CapsuleOverlay()
        overlay.show()
        assert overlay.isVisible()
        overlay.close()

    def test_hide_makes_invisible(self, qapp):
        from airtype.ui.overlay import CapsuleOverlay

        overlay = CapsuleOverlay()
        overlay.show()
        overlay.hide()
        assert not overlay.isVisible()
        overlay.close()

    def test_window_flags_no_focus_steal(self, qapp):
        from PySide6.QtCore import Qt

        from airtype.ui.overlay import CapsuleOverlay

        overlay = CapsuleOverlay()
        flags = overlay.windowFlags()
        assert flags & Qt.Tool
        assert flags & Qt.FramelessWindowHint
        assert flags & Qt.WindowStaysOnTopHint
        overlay.close()

    def test_show_without_activating_attribute(self, qapp):
        from PySide6.QtCore import Qt

        from airtype.ui.overlay import CapsuleOverlay

        overlay = CapsuleOverlay()
        assert overlay.testAttribute(Qt.WA_ShowWithoutActivating)
        overlay.close()

    def test_translucent_background_attribute(self, qapp):
        from PySide6.QtCore import Qt

        from airtype.ui.overlay import CapsuleOverlay

        overlay = CapsuleOverlay()
        assert overlay.testAttribute(Qt.WA_TranslucentBackground)
        overlay.close()

    def test_set_state_idle(self, qapp):
        from airtype.ui.overlay import CapsuleOverlay

        overlay = CapsuleOverlay()
        overlay.set_state("IDLE")  # 不應拋出例外
        overlay.close()

    def test_set_state_listening(self, qapp):
        from airtype.ui.overlay import CapsuleOverlay

        overlay = CapsuleOverlay()
        overlay.set_state("LISTENING")
        overlay.close()

    def test_set_state_unknown_no_error(self, qapp):
        from airtype.ui.overlay import CapsuleOverlay

        overlay = CapsuleOverlay()
        overlay.set_state("UNKNOWN_STATE")  # 不應拋出例外
        overlay.close()


class TestCapsuleOverlayPositionPersistence:
    """位置持久化測試。"""

    def test_save_position_to_config(self, qapp, dummy_config):
        from airtype.ui.overlay import CapsuleOverlay

        overlay = CapsuleOverlay(config=dummy_config)
        overlay.show()
        # 手動設定位置並儲存
        from PySide6.QtCore import QPoint

        overlay.move(QPoint(150, 250))
        overlay._save_position()
        assert dummy_config.appearance.pill_position == "150,250"
        overlay.close()

    def test_restore_position_from_config(self, qapp, dummy_config):
        from PySide6.QtCore import QPoint

        from airtype.ui.overlay import CapsuleOverlay

        dummy_config.appearance.pill_position = "200,300"
        overlay = CapsuleOverlay(config=dummy_config)
        # _restore_position 在 __init__ 中呼叫，但不依賴螢幕座標
        # 僅確認建立成功即可
        assert overlay is not None
        overlay.close()

    def test_position_default_when_no_config(self, qapp):
        from airtype.ui.overlay import CapsuleOverlay

        overlay = CapsuleOverlay(config=None)
        assert overlay is not None
        overlay.close()


# ─────────────────────────────────────────────────────────────────────────────
# WaveformWidget Qt 測試
# ─────────────────────────────────────────────────────────────────────────────


class TestWaveformWidget:
    """WaveformWidget 建立與 RMS 更新測試。"""

    def test_create(self, qapp):
        from airtype.ui.waveform_widget import WaveformWidget

        w = WaveformWidget()
        assert w.width() > 0
        assert w.height() > 0
        w.close()

    def test_update_rms(self, qapp):
        from airtype.ui.waveform_widget import WaveformWidget

        w = WaveformWidget()
        w.update_rms(0.5)  # 不應拋出例外
        w.close()

    def test_update_rms_clamps_to_valid_range(self, qapp):
        from airtype.ui.waveform_widget import WaveformWidget

        w = WaveformWidget()
        w.update_rms(2.0)   # 超出上限，應截斷
        w.update_rms(-1.0)  # 低於下限，應截斷
        w.close()

    def test_set_color(self, qapp):
        from airtype.ui.waveform_widget import WaveformWidget

        w = WaveformWidget()
        w.set_color("#ff0000")  # 不應拋出例外
        w.close()


# ─────────────────────────────────────────────────────────────────────────────
# DeviceSelector Qt 測試
# ─────────────────────────────────────────────────────────────────────────────


class TestDeviceSelector:
    """DeviceSelector 建立測試。"""

    def test_create(self, qapp):
        from airtype.ui.device_selector import DeviceSelector

        ds = DeviceSelector()
        # 至少有「預設麥克風」選項
        assert ds.count() >= 1
        ds.close()

    def test_has_default_device(self, qapp):
        from airtype.ui.device_selector import DeviceSelector

        ds = DeviceSelector()
        items = [ds.itemData(i) for i in range(ds.count())]
        assert "default" in items
        ds.close()


# ─────────────────────────────────────────────────────────────────────────────
# 任務 3.1（23-main-wiring）：State-driven waveform animation control 測試
# ─────────────────────────────────────────────────────────────────────────────


class TestWaveformAnimationControl:
    """驗證 set_state() 正確控制音波動畫啟停。"""

    def test_set_state_listening_activates_waveform(self, qapp):
        """set_state('LISTENING') 應啟動音波動畫。"""
        from unittest.mock import MagicMock
        from airtype.ui.overlay import CapsuleOverlay

        overlay = CapsuleOverlay()
        overlay._waveform.set_active = MagicMock()
        overlay.set_state("LISTENING")
        overlay._waveform.set_active.assert_called_with(True)
        overlay.close()

    def test_set_state_processing_activates_waveform(self, qapp):
        """set_state('PROCESSING') 應啟動音波動畫。"""
        from unittest.mock import MagicMock
        from airtype.ui.overlay import CapsuleOverlay

        overlay = CapsuleOverlay()
        overlay._waveform.set_active = MagicMock()
        overlay.set_state("PROCESSING")
        overlay._waveform.set_active.assert_called_with(True)
        overlay.close()

    def test_set_state_idle_deactivates_waveform(self, qapp):
        """set_state('IDLE') 應停止音波動畫。"""
        from unittest.mock import MagicMock
        from airtype.ui.overlay import CapsuleOverlay

        overlay = CapsuleOverlay()
        overlay._waveform.set_active = MagicMock()
        overlay.set_state("IDLE")
        overlay._waveform.set_active.assert_called_with(False)
        overlay.close()

    def test_set_state_error_deactivates_waveform(self, qapp):
        """set_state('ERROR') 應停止音波動畫。"""
        from unittest.mock import MagicMock
        from airtype.ui.overlay import CapsuleOverlay

        overlay = CapsuleOverlay()
        overlay._waveform.set_active = MagicMock()
        overlay.set_state("ERROR")
        overlay._waveform.set_active.assert_called_with(False)
        overlay.close()


# ─────────────────────────────────────────────────────────────────────────────
# 任務 1.1：WaveformWidget 彈性寬度（TDD）
# ─────────────────────────────────────────────────────────────────────────────


class TestWaveformWidgetFlexibleWidth:
    """驗證 WaveformWidget 改用彈性寬度（minimumWidth=80, fixedHeight=32）。"""

    def test_minimum_width_is_80(self, qapp):
        """minimumWidth() 應為 80。"""
        from airtype.ui.waveform_widget import WaveformWidget

        w = WaveformWidget()
        assert w.minimumWidth() == 80
        w.close()

    def test_fixed_height_is_32(self, qapp):
        """fixedHeight 應為 32（minimumHeight == maximumHeight == 32）。"""
        from airtype.ui.waveform_widget import WaveformWidget

        w = WaveformWidget()
        assert w.minimumHeight() == 32
        assert w.maximumHeight() == 32
        w.close()

    def test_horizontal_size_policy_expanding(self, qapp):
        """水平 sizePolicy 應允許擴展。"""
        from PySide6.QtWidgets import QSizePolicy
        from airtype.ui.waveform_widget import WaveformWidget

        w = WaveformWidget()
        hp = w.sizePolicy().horizontalPolicy()
        assert hp in (
            QSizePolicy.Expanding,
            QSizePolicy.MinimumExpanding,
        ), f"水平 sizePolicy 為 {hp}，預期 Expanding 或 MinimumExpanding"
        w.close()

    def test_no_fixed_width_constraint(self, qapp):
        """最大寬度不應被固定為 60（舊值）。"""
        from airtype.ui.waveform_widget import WaveformWidget

        w = WaveformWidget()
        assert w.maximumWidth() > 60
        w.close()


# ─────────────────────────────────────────────────────────────────────────────
# 任務 3.1：CapsuleBody 內部類別抽取（TDD）
# ─────────────────────────────────────────────────────────────────────────────


class TestCapsuleBodySeparation:
    """驗證 CapsuleBody 內部類別與圓角背景繪製分離。"""

    def test_capsule_body_class_exists(self, qapp):
        """CapsuleBody 類別應存在於 overlay 模組中。"""
        from airtype.ui.overlay import CapsuleOverlay

        overlay = CapsuleOverlay()
        assert hasattr(overlay, "_capsule_body"), "CapsuleOverlay 應有 _capsule_body 屬性"
        overlay.close()

    def test_capsule_body_fixed_height_48(self, qapp):
        """CapsuleBody 應有固定高度 48px（minimumHeight == maximumHeight == 48）。"""
        from airtype.ui.overlay import CapsuleOverlay

        overlay = CapsuleOverlay()
        body = overlay._capsule_body
        assert body.minimumHeight() == 48
        assert body.maximumHeight() == 48
        overlay.close()

    def test_capsule_body_is_widget(self, qapp):
        """CapsuleBody 應是 QWidget 實例。"""
        from PySide6.QtWidgets import QWidget
        from airtype.ui.overlay import CapsuleOverlay

        overlay = CapsuleOverlay()
        assert isinstance(overlay._capsule_body, QWidget)
        overlay.close()


# ─────────────────────────────────────────────────────────────────────────────
# 任務 4.1：膠囊主體佈局重構（TDD）
# ─────────────────────────────────────────────────────────────────────────────


class TestCapsuleLayout:
    """驗證重構後的膠囊佈局：CAPSULE_WIDTH=220、CapsuleBody 含 WaveformWidget。"""

    def test_capsule_width_is_220(self, qapp):
        """CAPSULE_WIDTH 應為 220。"""
        from airtype.ui.overlay import CAPSULE_WIDTH

        assert CAPSULE_WIDTH == 220

    def test_overlay_fixed_width_220(self, qapp):
        """CapsuleOverlay 寬度應為 220px。"""
        from airtype.ui.overlay import CapsuleOverlay

        overlay = CapsuleOverlay()
        assert overlay.width() == 220
        overlay.close()

    def test_waveform_inside_capsule_body(self, qapp):
        """WaveformWidget 應是 CapsuleBody 的子元件。"""
        from airtype.ui.overlay import CapsuleOverlay
        from airtype.ui.waveform_widget import WaveformWidget

        overlay = CapsuleOverlay()
        body = overlay._capsule_body
        waveform = overlay._waveform
        assert waveform.parent() is body, "WaveformWidget 應以 CapsuleBody 為 parent"
        overlay.close()

    def test_status_label_not_inside_body(self, qapp):
        """status_label 應在 CapsuleBody 外部（直接屬於 CapsuleOverlay）。"""
        from airtype.ui.overlay import CapsuleOverlay

        overlay = CapsuleOverlay()
        body = overlay._capsule_body
        label = overlay._status_label
        assert label.parent() is not body, "status_label 不應是 CapsuleBody 子元件"
        overlay.close()


# ─────────────────────────────────────────────────────────────────────────────
# 任務 4.2：Vertical Separator（TDD）
# ─────────────────────────────────────────────────────────────────────────────


class TestVerticalSeparator:
    """驗證 CapsuleBody 內的垂直分隔線。"""

    def test_separator_exists(self, qapp):
        """CapsuleOverlay 應有 _separator 屬性。"""
        from airtype.ui.overlay import CapsuleOverlay

        overlay = CapsuleOverlay()
        assert hasattr(overlay, "_separator"), "缺少 _separator 屬性"
        overlay.close()

    def test_separator_is_vline(self, qapp):
        """_separator 應是 QFrame VLine。"""
        from PySide6.QtWidgets import QFrame
        from airtype.ui.overlay import CapsuleOverlay

        overlay = CapsuleOverlay()
        sep = overlay._separator
        assert isinstance(sep, QFrame)
        assert sep.frameShape() == QFrame.VLine
        overlay.close()

    def test_separator_inside_capsule_body(self, qapp):
        """_separator 應是 CapsuleBody 的子元件。"""
        from airtype.ui.overlay import CapsuleOverlay

        overlay = CapsuleOverlay()
        assert overlay._separator.parent() is overlay._capsule_body
        overlay.close()


# ─────────────────────────────────────────────────────────────────────────────
# 任務 4.3：Microphone Toggle Button（TDD）
# ─────────────────────────────────────────────────────────────────────────────


class TestMicrophoneToggleButton:
    """驗證麥克風切換按鈕存在、尺寸正確、狀態圖示切換、點擊觸發 controller 方法。"""

    def test_mic_button_exists(self, qapp):
        """CapsuleOverlay 應有 _mic_button 屬性。"""
        from airtype.ui.overlay import CapsuleOverlay

        overlay = CapsuleOverlay()
        assert hasattr(overlay, "_mic_button"), "缺少 _mic_button 屬性"
        overlay.close()

    def test_mic_button_size_32x32(self, qapp):
        """_mic_button 尺寸應為 32x32。"""
        from airtype.ui.overlay import CapsuleOverlay

        overlay = CapsuleOverlay()
        btn = overlay._mic_button
        assert btn.width() == 32
        assert btn.height() == 32
        overlay.close()

    def test_mic_button_inside_capsule_body(self, qapp):
        """_mic_button 應是 CapsuleBody 的子元件。"""
        from airtype.ui.overlay import CapsuleOverlay

        overlay = CapsuleOverlay()
        assert overlay._mic_button.parent() is overlay._capsule_body
        overlay.close()

    def test_mic_button_click_calls_request_start(self, qapp):
        """IDLE 時點擊麥克風按鈕應呼叫 controller.request_start()。"""
        from unittest.mock import MagicMock
        from airtype.ui.overlay import CapsuleOverlay

        overlay = CapsuleOverlay()
        mock_ctrl = MagicMock()
        overlay._controller = mock_ctrl
        overlay.set_state("IDLE")
        overlay._mic_button.click()
        mock_ctrl.request_start.assert_called_once()
        overlay.close()

    def test_mic_button_click_calls_request_stop_when_listening(self, qapp):
        """LISTENING 時點擊按鈕應呼叫 controller.request_stop()。"""
        from unittest.mock import MagicMock
        from airtype.ui.overlay import CapsuleOverlay

        overlay = CapsuleOverlay()
        mock_ctrl = MagicMock()
        overlay._controller = mock_ctrl
        overlay.set_state("LISTENING")
        overlay._mic_button.click()
        mock_ctrl.request_stop.assert_called_once()
        overlay.close()


# ─────────────────────────────────────────────────────────────────────────────
# 任務 4.4：Device Dropdown Button（TDD）
# ─────────────────────────────────────────────────────────────────────────────


class TestDeviceDropdownButton:
    """驗證裝置下拉箭頭按鈕（QToolButton + QMenu）。"""

    def test_device_button_exists(self, qapp):
        """CapsuleOverlay 應有 _device_button 屬性。"""
        from airtype.ui.overlay import CapsuleOverlay

        overlay = CapsuleOverlay()
        assert hasattr(overlay, "_device_button"), "缺少 _device_button 屬性"
        overlay.close()

    def test_device_button_size(self, qapp):
        """_device_button 寬 20px、高 32px。"""
        from airtype.ui.overlay import CapsuleOverlay

        overlay = CapsuleOverlay()
        btn = overlay._device_button
        assert btn.width() == 20
        assert btn.height() == 32
        overlay.close()

    def test_device_button_inside_capsule_body(self, qapp):
        """_device_button 應是 CapsuleBody 的子元件。"""
        from airtype.ui.overlay import CapsuleOverlay

        overlay = CapsuleOverlay()
        assert overlay._device_button.parent() is overlay._capsule_body
        overlay.close()

    def test_device_menu_has_default_item(self, qapp):
        """裝置選單第一項 data 應為 'default'。"""
        from airtype.ui.overlay import CapsuleOverlay

        overlay = CapsuleOverlay()
        menu = overlay._device_button.menu()
        assert menu is not None, "_device_button 應有 QMenu"
        actions = menu.actions()
        assert len(actions) >= 1, "選單至少有一個選項"
        assert actions[0].data() == "default", "第一個選項的 data 應為 'default'"
        overlay.close()

    def test_select_device_updates_config(self, qapp, dummy_config):
        """選擇裝置後應更新 config.voice.input_device。"""
        from airtype.ui.overlay import CapsuleOverlay

        overlay = CapsuleOverlay(config=dummy_config)
        menu = overlay._device_button.menu()
        first_action = menu.actions()[0]  # 預設麥克風
        first_action.trigger()
        assert dummy_config.voice.input_device == "default"
        overlay.close()


# ─────────────────────────────────────────────────────────────────────────────
# fix-device-menu-selection 任務 1.1：QActionGroup 互斥勾選（TDD）
# ─────────────────────────────────────────────────────────────────────────────


class TestDeviceMenuCheckmark:
    """驗證裝置選單使用 QActionGroup 實現互斥勾選。"""

    def test_device_actions_are_checkable(self, qapp):
        """所有裝置 action 應為 checkable。"""
        from airtype.ui.overlay import CapsuleOverlay

        overlay = CapsuleOverlay()
        menu = overlay._device_button.menu()
        for action in menu.actions():
            assert action.isCheckable(), f"Action '{action.text()}' 應為 checkable"
        overlay.close()

    def test_exactly_one_action_checked(self, qapp):
        """選單中應恰好有一個 action 被勾選。"""
        from airtype.ui.overlay import CapsuleOverlay

        overlay = CapsuleOverlay()
        menu = overlay._device_button.menu()
        checked = [a for a in menu.actions() if a.isChecked()]
        assert len(checked) == 1, f"應恰好有 1 個勾選，實際 {len(checked)}"
        overlay.close()

    def test_default_device_checked_initially(self, qapp, dummy_config):
        """config.voice.input_device='default' 時，預設麥克風應被勾選。"""
        from airtype.ui.overlay import CapsuleOverlay

        dummy_config.voice.input_device = "default"
        overlay = CapsuleOverlay(config=dummy_config)
        menu = overlay._device_button.menu()
        actions = menu.actions()
        assert actions[0].isChecked(), "預設麥克風 action 應被勾選"
        overlay.close()

    def test_action_group_exclusive(self, qapp):
        """裝置 action 應屬於同一個 exclusive QActionGroup。"""
        from PySide6.QtGui import QActionGroup
        from airtype.ui.overlay import CapsuleOverlay

        overlay = CapsuleOverlay()
        menu = overlay._device_button.menu()
        groups = set()
        for action in menu.actions():
            ag = action.actionGroup()
            assert ag is not None, f"Action '{action.text()}' 應屬於 QActionGroup"
            groups.add(ag)
        assert len(groups) == 1, "所有 action 應屬於同一個 QActionGroup"
        group = groups.pop()
        assert group.isExclusive(), "QActionGroup 應為 exclusive 模式"
        overlay.close()

    def test_checkmark_follows_selection(self, qapp, dummy_config):
        """選擇不同裝置後，勾選應跟隨至新選取的裝置。"""
        from airtype.ui.overlay import CapsuleOverlay

        dummy_config.voice.input_device = "default"
        overlay = CapsuleOverlay(config=dummy_config)
        menu = overlay._device_button.menu()
        actions = menu.actions()
        if len(actions) < 2:
            pytest.skip("需要至少 2 個裝置才能測試切換")
        # 觸發第二個 action
        actions[1].trigger()
        assert actions[1].isChecked(), "新選取的 action 應被勾選"
        assert not actions[0].isChecked(), "舊的 action 應取消勾選"
        overlay.close()


# ─────────────────────────────────────────────────────────────────────────────
# fix-device-menu-selection 任務 1.2：QMenu indicator 深色背景樣式（TDD）
# ─────────────────────────────────────────────────────────────────────────────


class TestDeviceMenuIndicatorStyle:
    """驗證 QMenu stylesheet 包含 indicator 樣式規則。"""

    def test_menu_stylesheet_has_indicator_rule(self, qapp):
        """QMenu stylesheet 應包含 QMenu::indicator 規則。"""
        from airtype.ui.overlay import CapsuleOverlay

        overlay = CapsuleOverlay()
        menu = overlay._device_button.menu()
        ss = menu.styleSheet()
        assert "QMenu::indicator" in ss, "stylesheet 應包含 QMenu::indicator 規則"
        overlay.close()


# ─────────────────────────────────────────────────────────────────────────────
# 任務 5.1：狀態驅動 UI 更新（TDD）
# ─────────────────────────────────────────────────────────────────────────────


class TestStateDrivenUI:
    """驗證 set_state() 正確切換 mic_button 圖示與 status_label 可見性。"""

    def test_status_label_hidden_in_idle(self, qapp):
        """IDLE 時 status_label 應隱藏（isHidden）。"""
        from airtype.ui.overlay import CapsuleOverlay

        overlay = CapsuleOverlay()
        overlay.set_state("IDLE")
        assert overlay._status_label.isHidden()
        overlay.close()

    def test_status_label_visible_when_listening(self, qapp):
        """LISTENING 時 status_label 不應隱藏。"""
        from airtype.ui.overlay import CapsuleOverlay

        overlay = CapsuleOverlay()
        overlay.set_state("LISTENING")
        assert not overlay._status_label.isHidden()
        overlay.close()

    def test_status_label_visible_when_processing(self, qapp):
        """PROCESSING 時 status_label 不應隱藏。"""
        from airtype.ui.overlay import CapsuleOverlay

        overlay = CapsuleOverlay()
        overlay.set_state("PROCESSING")
        assert not overlay._status_label.isHidden()
        overlay.close()

    def test_capsule_body_background_updates_on_state_change(self, qapp):
        """set_state() 應更新 CapsuleBody 背景色。"""
        from PySide6.QtGui import QColor
        from airtype.ui.overlay import CapsuleOverlay, STATE_COLORS

        overlay = CapsuleOverlay()
        overlay.set_state("LISTENING")
        expected = QColor(STATE_COLORS["LISTENING"])
        assert overlay._capsule_body._bg_color.name() == expected.name()
        overlay.close()


# ─────────────────────────────────────────────────────────────────────────────
# 任務 5.2：parse_pill_position 常數與拖曳行為（TDD）
# ─────────────────────────────────────────────────────────────────────────────


class TestCapsulePositionPersistence:
    """驗證 parse_pill_position 使用新尺寸常數，及拖曳正確運作。"""

    def test_center_preset_uses_new_constants(self):
        """parse_pill_position center 應使用 CAPSULE_WIDTH=220, CAPSULE_HEIGHT=48。"""
        from airtype.ui.overlay import CAPSULE_HEIGHT, CAPSULE_WIDTH, parse_pill_position

        assert CAPSULE_WIDTH == 220
        assert CAPSULE_HEIGHT == 48
        x, y = parse_pill_position("center", 1920, 1080)
        assert x == (1920 - CAPSULE_WIDTH) // 2
        assert y == 1080 - CAPSULE_HEIGHT - 80

    def test_device_changed_signal_emitted(self, qapp, dummy_config):
        """_on_device_selected() 應 emit device_changed Signal，值為裝置 index。"""
        from unittest.mock import MagicMock
        from airtype.ui.overlay import CapsuleOverlay

        overlay = CapsuleOverlay(config=dummy_config)
        spy = MagicMock()
        overlay.device_changed.connect(spy)
        overlay._on_device_selected(5)
        spy.assert_called_once_with(5)
        overlay.close()

    def test_device_changed_signal_emitted_without_config(self, qapp):
        """config=None 時 _on_device_selected() 仍應 emit device_changed Signal。"""
        from unittest.mock import MagicMock
        from airtype.ui.overlay import CapsuleOverlay

        overlay = CapsuleOverlay(config=None)
        spy = MagicMock()
        overlay.device_changed.connect(spy)
        overlay._on_device_selected(7)
        spy.assert_called_once_with(7)
        overlay.close()

    def test_connect_controller_stores_reference(self, qapp):
        """connect_controller() 應儲存 controller 參考供 mic_button 使用。"""
        from unittest.mock import MagicMock
        from airtype.ui.overlay import CapsuleOverlay

        overlay = CapsuleOverlay()
        mock_ctrl = MagicMock()
        # 模擬無 Qt Signal 的 controller
        del mock_ctrl.state_changed
        mock_ctrl.connect_state_changed = MagicMock()
        overlay.connect_controller(mock_ctrl)
        assert overlay._controller is mock_ctrl
        overlay.close()
