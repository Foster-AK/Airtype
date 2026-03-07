"""CoreController 單元測試（TDD）。

涵蓋：
- 任務 5.1：狀態機轉換（所有有效與無效轉換）
- 任務 5.2：取消行為（任何活躍狀態按 Escape → IDLE）

使用純 Python 版本的 CoreController（不依賴 PySide6），透過
connect_state_changed 回呼驗證 Signal 行為。
"""

from __future__ import annotations

import importlib
import sys
from unittest.mock import MagicMock, call, patch

import pytest

# 強制使用純 Python 版（在 PySide6 未安裝或測試隔離環境下均可運作）
# 若 PySide6 已安裝，Qt 版本會在模組匯入時被建立；
# 我們直接測試純 Python 基礎類別的行為（轉換邏輯完全相同）。
from airtype.core.controller import (
    AppState,
    CoreController,
    _TRANSITIONS,
    get_controller,
    init_controller,
)


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture()
def ctrl():
    """建立無外部相依的 CoreController 實例。"""
    return CoreController()


@pytest.fixture()
def state_log(ctrl):
    """記錄所有 state_changed 事件的列表。"""
    log: list[AppState] = []
    ctrl.connect_state_changed(log.append)
    return log


# ─────────────────────────────────────────────────────────────────────────────
# 任務 5.1：狀態機轉換測試
# ─────────────────────────────────────────────────────────────────────────────


class TestStateMachineTransitions:
    """測試所有有效與無效的狀態機轉換。"""

    def test_initial_state_is_idle(self, ctrl):
        """初始狀態應為 IDLE。"""
        assert ctrl.state == AppState.IDLE

    # ------------------------------------------------------------------
    # 正常流程：IDLE → ACTIVATING → LISTENING → PROCESSING → INJECTING → IDLE
    # ------------------------------------------------------------------

    def test_idle_to_activating(self, ctrl, state_log):
        """IDLE → ACTIVATING 應成功。"""
        result = ctrl.transition(AppState.ACTIVATING)
        assert result is True
        assert ctrl.state == AppState.ACTIVATING
        assert state_log == [AppState.ACTIVATING]

    def test_activating_to_listening(self, ctrl, state_log):
        """ACTIVATING → LISTENING 應成功。"""
        ctrl.transition(AppState.ACTIVATING)
        result = ctrl.transition(AppState.LISTENING)
        assert result is True
        assert ctrl.state == AppState.LISTENING

    def test_listening_to_processing(self, ctrl, state_log):
        """LISTENING → PROCESSING 應成功（VAD 偵測語音結束）。"""
        ctrl.transition(AppState.ACTIVATING)
        ctrl.transition(AppState.LISTENING)
        result = ctrl.transition(AppState.PROCESSING)
        assert result is True
        assert ctrl.state == AppState.PROCESSING

    def test_processing_to_injecting(self, ctrl, state_log):
        """PROCESSING → INJECTING 應成功（ASR 辨識完成）。"""
        ctrl.transition(AppState.ACTIVATING)
        ctrl.transition(AppState.LISTENING)
        ctrl.transition(AppState.PROCESSING)
        result = ctrl.transition(AppState.INJECTING)
        assert result is True
        assert ctrl.state == AppState.INJECTING

    def test_injecting_to_idle(self, ctrl, state_log):
        """INJECTING → IDLE 應成功（注入完成）。"""
        ctrl.transition(AppState.ACTIVATING)
        ctrl.transition(AppState.LISTENING)
        ctrl.transition(AppState.PROCESSING)
        ctrl.transition(AppState.INJECTING)
        result = ctrl.transition(AppState.IDLE)
        assert result is True
        assert ctrl.state == AppState.IDLE

    def test_full_normal_flow(self, ctrl, state_log):
        """完整正常流程：IDLE → ACTIVATING → LISTENING → PROCESSING → INJECTING → IDLE。"""
        flow = [
            AppState.ACTIVATING,
            AppState.LISTENING,
            AppState.PROCESSING,
            AppState.INJECTING,
            AppState.IDLE,
        ]
        for s in flow:
            assert ctrl.transition(s) is True
        assert ctrl.state == AppState.IDLE
        assert state_log == flow

    # ------------------------------------------------------------------
    # 錯誤轉換：任何狀態 → ERROR → IDLE
    # ------------------------------------------------------------------

    def test_activating_to_error(self, ctrl):
        """ACTIVATING → ERROR 應成功。"""
        ctrl.transition(AppState.ACTIVATING)
        assert ctrl.transition(AppState.ERROR) is True
        assert ctrl.state == AppState.ERROR

    def test_listening_to_error(self, ctrl):
        """LISTENING → ERROR 應成功。"""
        ctrl.transition(AppState.ACTIVATING)
        ctrl.transition(AppState.LISTENING)
        assert ctrl.transition(AppState.ERROR) is True

    def test_processing_to_error(self, ctrl):
        """PROCESSING → ERROR 應成功。"""
        ctrl.transition(AppState.ACTIVATING)
        ctrl.transition(AppState.LISTENING)
        ctrl.transition(AppState.PROCESSING)
        assert ctrl.transition(AppState.ERROR) is True

    def test_injecting_to_error(self, ctrl):
        """INJECTING → ERROR 應成功。"""
        ctrl.transition(AppState.ACTIVATING)
        ctrl.transition(AppState.LISTENING)
        ctrl.transition(AppState.PROCESSING)
        ctrl.transition(AppState.INJECTING)
        assert ctrl.transition(AppState.ERROR) is True

    def test_error_to_idle(self, ctrl):
        """ERROR → IDLE 應成功。"""
        ctrl.transition(AppState.ACTIVATING)
        ctrl.transition(AppState.ERROR)
        assert ctrl.transition(AppState.IDLE) is True
        assert ctrl.state == AppState.IDLE

    # ------------------------------------------------------------------
    # 無效轉換（應記錄 WARNING 並回傳 False）
    # ------------------------------------------------------------------

    def test_idle_to_injecting_is_invalid(self, ctrl, state_log):
        """IDLE → INJECTING 為無效轉換（spec §Invalid Transition Attempted）。"""
        result = ctrl.transition(AppState.INJECTING)
        assert result is False
        assert ctrl.state == AppState.IDLE  # 狀態不變
        assert state_log == []              # 未發射 signal

    def test_idle_to_processing_is_invalid(self, ctrl):
        """IDLE → PROCESSING 為無效轉換。"""
        assert ctrl.transition(AppState.PROCESSING) is False
        assert ctrl.state == AppState.IDLE

    def test_idle_to_listening_is_invalid(self, ctrl):
        """IDLE → LISTENING 為無效轉換。"""
        assert ctrl.transition(AppState.LISTENING) is False
        assert ctrl.state == AppState.IDLE

    def test_listening_to_activating_is_invalid(self, ctrl):
        """LISTENING → ACTIVATING 為無效轉換。"""
        ctrl.transition(AppState.ACTIVATING)
        ctrl.transition(AppState.LISTENING)
        assert ctrl.transition(AppState.ACTIVATING) is False
        assert ctrl.state == AppState.LISTENING

    def test_processing_to_listening_is_invalid(self, ctrl):
        """PROCESSING → LISTENING 為無效轉換。"""
        ctrl.transition(AppState.ACTIVATING)
        ctrl.transition(AppState.LISTENING)
        ctrl.transition(AppState.PROCESSING)
        assert ctrl.transition(AppState.LISTENING) is False

    def test_injecting_to_processing_is_invalid(self, ctrl):
        """INJECTING → PROCESSING 為無效轉換。"""
        ctrl.transition(AppState.ACTIVATING)
        ctrl.transition(AppState.LISTENING)
        ctrl.transition(AppState.PROCESSING)
        ctrl.transition(AppState.INJECTING)
        assert ctrl.transition(AppState.PROCESSING) is False

    def test_invalid_transition_logs_warning(self, ctrl, caplog):
        """無效轉換應記錄 WARNING 訊息。"""
        import logging
        with caplog.at_level(logging.WARNING, logger="airtype.core.controller"):
            ctrl.transition(AppState.INJECTING)
        assert any("無效的狀態轉換" in r.message for r in caplog.records)

    # ------------------------------------------------------------------
    # 轉換表完整性驗證
    # ------------------------------------------------------------------

    def test_all_states_in_transition_table(self):
        """所有 AppState 枚舉值均應出現在轉換表中。"""
        for state in AppState:
            assert state in _TRANSITIONS, f"{state.name} 不在轉換表中"

    def test_transition_targets_are_valid_states(self):
        """轉換表的所有目標狀態均應為有效的 AppState。"""
        for src, targets in _TRANSITIONS.items():
            for target in targets:
                assert isinstance(target, AppState), (
                    f"無效轉換目標：{target!r}（來源：{src.name}）"
                )

    # ------------------------------------------------------------------
    # set_error 方法（any → ERROR → IDLE 捷徑）
    # ------------------------------------------------------------------

    def test_set_error_from_listening(self, ctrl, state_log):
        """set_error() 應從 LISTENING 轉換至 ERROR 再到 IDLE。"""
        ctrl.transition(AppState.ACTIVATING)
        ctrl.transition(AppState.LISTENING)
        ctrl.set_error("測試錯誤")
        assert ctrl.state == AppState.IDLE
        # state_log 應包含 ACTIVATING, LISTENING, ERROR, IDLE
        assert AppState.ERROR in state_log
        assert state_log[-1] == AppState.IDLE

    def test_set_error_emits_error_signal(self, ctrl):
        """set_error() 應發射錯誤事件。"""
        errors: list[str] = []
        ctrl.connect_error(errors.append)
        ctrl.set_error("ASR 失敗")
        assert errors == ["ASR 失敗"]


# ─────────────────────────────────────────────────────────────────────────────
# 任務 5.2：取消行為測試
# ─────────────────────────────────────────────────────────────────────────────


class TestCancelBehavior:
    """測試取消行為（任何活躍狀態 → IDLE）。"""

    @pytest.mark.parametrize("setup_states", [
        [AppState.ACTIVATING],
        [AppState.ACTIVATING, AppState.LISTENING],
        [AppState.ACTIVATING, AppState.LISTENING, AppState.PROCESSING],
        [AppState.ACTIVATING, AppState.LISTENING, AppState.PROCESSING, AppState.INJECTING],
    ])
    def test_cancel_from_any_active_state(self, ctrl, state_log, setup_states):
        """cancel() 應從任何活躍狀態返回 IDLE。"""
        for s in setup_states:
            ctrl.transition(s)
        ctrl.cancel()
        assert ctrl.state == AppState.IDLE

    def test_cancel_emits_state_changed_to_idle(self, ctrl, state_log):
        """cancel() 應發射 state_changed(IDLE) 事件。"""
        ctrl.transition(AppState.ACTIVATING)
        ctrl.transition(AppState.LISTENING)
        ctrl.cancel()
        assert state_log[-1] == AppState.IDLE

    def test_cancel_from_idle_is_noop(self, ctrl, state_log):
        """在 IDLE 狀態呼叫 cancel() 應為 no-op，不發射事件。"""
        state_log.clear()
        ctrl.cancel()
        assert ctrl.state == AppState.IDLE
        assert state_log == []  # 不應發射任何事件

    def test_cancel_from_listening(self, ctrl, state_log):
        """Escape 取消（LISTENING → IDLE）：不執行文字注入（spec §Cancel During Listening）。"""
        injected: list[str] = []
        ctrl.connect_recognition_complete(injected.append)

        ctrl.transition(AppState.ACTIVATING)
        ctrl.transition(AppState.LISTENING)
        ctrl.cancel()  # 模擬 Escape 鍵

        assert ctrl.state == AppState.IDLE
        assert injected == []  # 取消後不觸發辨識完成事件

    def test_hotkey_cancel_callback(self):
        """_on_hotkey_cancel() 應呼叫 cancel()，使狀態回到 IDLE。"""
        ctrl = CoreController()
        ctrl.transition(AppState.ACTIVATING)
        ctrl.transition(AppState.LISTENING)
        ctrl._on_hotkey_cancel()
        assert ctrl.state == AppState.IDLE

    def test_escape_during_processing(self, ctrl):
        """在 PROCESSING 狀態下取消，應返回 IDLE。"""
        ctrl.transition(AppState.ACTIVATING)
        ctrl.transition(AppState.LISTENING)
        ctrl.transition(AppState.PROCESSING)
        ctrl.cancel()
        assert ctrl.state == AppState.IDLE

    def test_escape_during_injecting(self, ctrl):
        """在 INJECTING 狀態下取消，應返回 IDLE。"""
        ctrl.transition(AppState.ACTIVATING)
        ctrl.transition(AppState.LISTENING)
        ctrl.transition(AppState.PROCESSING)
        ctrl.transition(AppState.INJECTING)
        ctrl.cancel()
        assert ctrl.state == AppState.IDLE

    def test_escape_during_error(self, ctrl):
        """在 ERROR 狀態下取消，應返回 IDLE。"""
        ctrl.transition(AppState.ACTIVATING)
        ctrl.transition(AppState.ERROR)
        ctrl.cancel()
        assert ctrl.state == AppState.IDLE


# ─────────────────────────────────────────────────────────────────────────────
# HotkeyManager 狀態同步測試（WARNING 修正）
# ─────────────────────────────────────────────────────────────────────────────


class TestHotkeyStateSync:
    """確認 cancel/set_error 後 HotkeyManager 狀態同步重置。"""

    def test_cancel_resets_hotkey_state(self):
        """cancel() 應呼叫 hotkey_manager.reset_state()。"""
        mock_hotkey = MagicMock()
        ctrl = CoreController(hotkey_manager=mock_hotkey)
        ctrl.transition(AppState.ACTIVATING)
        ctrl.cancel()
        mock_hotkey.reset_state.assert_called_once()

    def test_set_error_resets_hotkey_state(self):
        """set_error() 應呼叫 hotkey_manager.reset_state()。"""
        mock_hotkey = MagicMock()
        ctrl = CoreController(hotkey_manager=mock_hotkey)
        ctrl.transition(AppState.ACTIVATING)
        ctrl.transition(AppState.LISTENING)
        ctrl.set_error("管線錯誤")
        mock_hotkey.reset_state.assert_called_once()

    def test_cancel_from_idle_does_not_reset_hotkey(self):
        """IDLE 狀態呼叫 cancel() 是 no-op，不應呼叫 reset_state()。"""
        mock_hotkey = MagicMock()
        ctrl = CoreController(hotkey_manager=mock_hotkey)
        ctrl.cancel()
        mock_hotkey.reset_state.assert_not_called()

    def test_cancel_without_hotkey_manager_is_safe(self):
        """無 hotkey_manager 時 cancel() 不應拋出例外。"""
        ctrl = CoreController()
        ctrl.transition(AppState.ACTIVATING)
        ctrl.cancel()  # should not raise
        assert ctrl.state == AppState.IDLE


# ─────────────────────────────────────────────────────────────────────────────
# 全域單例測試
# ─────────────────────────────────────────────────────────────────────────────


class TestSingletonController:
    """測試全域單例控制器存取（spec §Globally Accessible Singleton Controller）。"""

    def test_get_controller_before_init_raises(self):
        """在 init_controller() 前呼叫 get_controller() 應拋出 RuntimeError。"""
        import airtype.core.controller as mod
        orig = mod._controller
        try:
            mod._controller = None
            with pytest.raises(RuntimeError, match="尚未初始化"):
                get_controller()
        finally:
            mod._controller = orig

    def test_init_and_get_controller_returns_same_instance(self):
        """init_controller() 後 get_controller() 應回傳相同實例。"""
        import airtype.core.controller as mod
        orig = mod._controller
        try:
            ctrl = CoreController()
            init_controller(ctrl)
            assert get_controller() is ctrl
        finally:
            mod._controller = orig

    def test_get_controller_from_multiple_calls(self):
        """多次呼叫 get_controller() 應回傳相同實例。"""
        import airtype.core.controller as mod
        orig = mod._controller
        try:
            ctrl = CoreController()
            init_controller(ctrl)
            assert get_controller() is get_controller()
        finally:
            mod._controller = orig


# ─────────────────────────────────────────────────────────────────────────────
# 管線整合測試
# ─────────────────────────────────────────────────────────────────────────────


class TestPipelineIntegration:
    """測試控制器與管線事件的整合。"""

    def test_on_recognition_complete_transitions_injecting_then_idle(self, ctrl, state_log):
        """辨識完成應觸發 PROCESSING → INJECTING → IDLE 轉換。"""
        ctrl.transition(AppState.ACTIVATING)
        ctrl.transition(AppState.LISTENING)
        ctrl.transition(AppState.PROCESSING)

        ctrl.on_recognition_complete("你好世界")

        assert ctrl.state == AppState.IDLE
        assert AppState.INJECTING in state_log
        assert state_log[-1] == AppState.IDLE

    def test_on_recognition_complete_emits_recognition_signal(self, ctrl):
        """辨識完成應發射 recognition_complete 事件。"""
        texts: list[str] = []
        ctrl.connect_recognition_complete(texts.append)

        ctrl.transition(AppState.ACTIVATING)
        ctrl.transition(AppState.LISTENING)
        ctrl.transition(AppState.PROCESSING)
        ctrl.on_recognition_complete("測試文字")

        assert texts == ["測試文字"]

    def test_startup_connects_hotkey_callbacks(self):
        """startup() 應連接 HotkeyManager 的三個 callback。"""
        mock_hotkey = MagicMock()
        mock_hotkey.start = MagicMock()

        ctrl = CoreController(hotkey_manager=mock_hotkey)
        ctrl.startup()

        mock_hotkey.on_start.assert_called_once()
        mock_hotkey.on_stop.assert_called_once()
        mock_hotkey.on_cancel.assert_called_once()
        mock_hotkey.start.assert_called_once()

    def test_startup_connects_pipeline_callbacks(self):
        """startup() 應連接管線的 on_recognition_complete 與 on_error 回呼。"""
        mock_pipeline = MagicMock()

        ctrl = CoreController(pipeline=mock_pipeline)
        ctrl.startup()

        mock_pipeline.on_recognition_complete.assert_called_once_with(
            ctrl.on_recognition_complete
        )
        mock_pipeline.on_error.assert_called_once_with(ctrl.on_pipeline_error)

    def test_shutdown_stops_pipeline_and_hotkey(self):
        """shutdown() 應停止管線與 HotkeyManager。"""
        mock_pipeline = MagicMock()
        mock_hotkey = MagicMock()
        mock_hotkey.start = MagicMock()

        ctrl = CoreController(pipeline=mock_pipeline, hotkey_manager=mock_hotkey)
        ctrl.shutdown()

        mock_pipeline.stop.assert_called_once()
        mock_hotkey.stop.assert_called_once()

    def test_shutdown_sets_state_to_idle(self, ctrl):
        """shutdown() 後狀態應為 IDLE。"""
        ctrl.transition(AppState.ACTIVATING)
        ctrl.shutdown()
        assert ctrl.state == AppState.IDLE


# ─────────────────────────────────────────────────────────────────────────────
# 任務 1.1：PolishEngine 依賴注入測試（TDD 失敗測試）
# ─────────────────────────────────────────────────────────────────────────────


class TestPolishEngineDI:
    """驗證 PolishEngine 透過建構子注入 CoreController（spec §PolishEngine Dependency Injection）。"""

    def _make_ctrl_in_processing(self, polish_engine=None, config=None, text_injector=None):
        """建立並將 CoreController 推進至 PROCESSING 狀態。"""
        ctrl = CoreController(
            config=config,
            text_injector=text_injector,
            polish_engine=polish_engine,
        )
        ctrl.transition(AppState.ACTIVATING)
        ctrl.transition(AppState.LISTENING)
        ctrl.transition(AppState.PROCESSING)
        return ctrl

    def test_no_polish_engine_injects_original(self):
        """no polish_engine：直接注入原始文字，不呼叫 PolishEngine（spec §No polish engine provided）。"""
        mock_injector = MagicMock()
        ctrl = self._make_ctrl_in_processing(text_injector=mock_injector)
        ctrl.on_recognition_complete("原始文字")
        mock_injector.inject.assert_called_once_with("原始文字")

    def test_polish_disabled_does_not_call_polish(self):
        """polish disabled (config.llm.enabled=False)：不呼叫 PolishEngine，注入原始文字（spec §Polish disabled）。"""
        mock_engine = MagicMock()
        mock_injector = MagicMock()
        config = MagicMock()
        config.llm.enabled = False

        ctrl = self._make_ctrl_in_processing(
            polish_engine=mock_engine,
            config=config,
            text_injector=mock_injector,
        )
        ctrl.on_recognition_complete("原始文字")
        mock_engine.polish.assert_not_called()
        mock_injector.inject.assert_called_once_with("原始文字")


# ─────────────────────────────────────────────────────────────────────────────
# 任務 1.2：LLM 潤飾整合至辨識管線（TDD 失敗測試）
# ─────────────────────────────────────────────────────────────────────────────


class TestLLMPolishPipeline:
    """驗證 LLM 潤飾在辨識管線中的整合（spec §LLM Polish Integration in Recognition Pipeline）。"""

    def _make_ctrl_in_processing(self, polish_engine, config, text_injector=None):
        ctrl = CoreController(
            config=config,
            text_injector=text_injector,
            polish_engine=polish_engine,
        )
        ctrl.transition(AppState.ACTIVATING)
        ctrl.transition(AppState.LISTENING)
        ctrl.transition(AppState.PROCESSING)
        return ctrl

    def _config_no_preview(self):
        config = MagicMock()
        config.llm.enabled = True
        config.llm.preview_before_inject = False
        return config

    def test_polish_enabled_no_preview_injects_polished(self):
        """polish enabled, no preview：呼叫 polish() 並注入潤飾結果（spec §Polish enabled, no preview）。"""
        mock_engine = MagicMock()
        mock_engine.polish.return_value = "潤飾後文字"
        mock_injector = MagicMock()

        ctrl = self._make_ctrl_in_processing(mock_engine, self._config_no_preview(), mock_injector)
        ctrl.on_recognition_complete("原始文字")

        mock_engine.polish.assert_called_once_with("原始文字")
        mock_injector.inject.assert_called_once_with("潤飾後文字")

    def test_polish_failure_fallback_injects_original(self, caplog):
        """polish failure fallback：polish() 拋出例外，注入原始文字，不進入 ERROR，並記錄 error log（spec §Polish failure fallback）。"""
        import logging
        mock_engine = MagicMock()
        mock_engine.polish.side_effect = Exception("LLM 失敗")
        mock_injector = MagicMock()

        ctrl = self._make_ctrl_in_processing(mock_engine, self._config_no_preview(), mock_injector)
        with caplog.at_level(logging.ERROR, logger="airtype.core.controller"):
            ctrl.on_recognition_complete("原始文字")

        mock_injector.inject.assert_called_once_with("原始文字")
        assert ctrl.state == AppState.IDLE  # 不進入 ERROR 狀態
        assert any("LLM 潤飾失敗" in r.message for r in caplog.records)


# ─────────────────────────────────────────────────────────────────────────────
# 任務 1.3：Polish Preview Dialog 整合（TDD 失敗測試）
# ─────────────────────────────────────────────────────────────────────────────


class TestPolishPreviewDialogIntegration:
    """驗證 Polish Preview Dialog 整合（spec §Polish Preview Dialog Integration）。"""

    def _make_ctrl_in_processing(self, polish_engine, config, text_injector=None):
        ctrl = CoreController(
            config=config,
            text_injector=text_injector,
            polish_engine=polish_engine,
        )
        ctrl.transition(AppState.ACTIVATING)
        ctrl.transition(AppState.LISTENING)
        ctrl.transition(AppState.PROCESSING)
        return ctrl

    def _config_with_preview(self):
        config = MagicMock()
        config.llm.enabled = True
        config.llm.preview_before_inject = True
        return config

    def test_user_selects_polished_text(self):
        """user selects polished text：對話框接受，selected_text() 回傳潤飾文字 → 注入潤飾文字（spec §User selects polished text）。"""
        mock_engine = MagicMock()
        mock_engine.polish.return_value = "潤飾後文字"
        mock_injector = MagicMock()

        mock_dialog = MagicMock()
        mock_dialog.exec.return_value = 1  # QDialog.Accepted
        mock_dialog.selected_text.return_value = "潤飾後文字"

        with patch("airtype.core.controller.PolishPreviewDialog", return_value=mock_dialog):
            ctrl = self._make_ctrl_in_processing(mock_engine, self._config_with_preview(), mock_injector)
            ctrl.on_recognition_complete("原始文字")

        mock_injector.inject.assert_called_once_with("潤飾後文字")

    def test_user_selects_original_text(self):
        """user selects original text：對話框接受，selected_text() 回傳原始文字 → 注入原始文字（spec §User selects original text）。"""
        mock_engine = MagicMock()
        mock_engine.polish.return_value = "潤飾後文字"
        mock_injector = MagicMock()

        mock_dialog = MagicMock()
        mock_dialog.exec.return_value = 1  # QDialog.Accepted
        mock_dialog.selected_text.return_value = "原始文字"

        with patch("airtype.core.controller.PolishPreviewDialog", return_value=mock_dialog):
            ctrl = self._make_ctrl_in_processing(mock_engine, self._config_with_preview(), mock_injector)
            ctrl.on_recognition_complete("原始文字")

        mock_injector.inject.assert_called_once_with("原始文字")

    def test_user_dismisses_dialog(self):
        """user dismisses dialog：對話框拒絕 (exec=0) → 注入原始文字（spec §User dismisses dialog）。"""
        mock_engine = MagicMock()
        mock_engine.polish.return_value = "潤飾後文字"
        mock_injector = MagicMock()

        mock_dialog = MagicMock()
        mock_dialog.exec.return_value = 0  # QDialog.Rejected

        with patch("airtype.core.controller.PolishPreviewDialog", return_value=mock_dialog):
            ctrl = self._make_ctrl_in_processing(mock_engine, self._config_with_preview(), mock_injector)
            ctrl.on_recognition_complete("原始文字")

        mock_injector.inject.assert_called_once_with("原始文字")


# ─────────────────────────────────────────────────────────────────────────────
# 任務 2.1-2.5（23-main-wiring）：PROCESSING 超時保護測試
# ─────────────────────────────────────────────────────────────────────────────


class TestProcessingTimeoutProtection:
    """驗證 PROCESSING 狀態超時保護機制（spec §PROCESSING State Timeout Protection）。"""

    def test_controller_has_processing_timer_attrs(self):
        """CoreController.__init__ 應有 _processing_timer 與 _processing_timeout_sec 屬性。"""
        ctrl = CoreController()
        assert hasattr(ctrl, "_processing_timer")
        assert hasattr(ctrl, "_processing_timeout_sec")
        assert ctrl._processing_timeout_sec == 30

    def test_hotkey_stop_without_pipeline_calls_cancel(self):
        """_on_hotkey_stop() pipeline 為 None 時應直接 cancel() 回 IDLE。"""
        ctrl = CoreController()
        # 手動推至 LISTENING
        ctrl.transition(AppState.ACTIVATING)
        ctrl.transition(AppState.LISTENING)

        ctrl._on_hotkey_stop()

        assert ctrl.state == AppState.IDLE

    def test_hotkey_stop_with_pipeline_calls_flush_and_recognize(self):
        """_on_hotkey_stop() 有 pipeline 時應呼叫 flush_and_recognize() 並轉 PROCESSING。"""
        mock_pipeline = MagicMock()
        ctrl = CoreController(pipeline=mock_pipeline)
        ctrl.transition(AppState.ACTIVATING)
        ctrl.transition(AppState.LISTENING)

        ctrl._on_hotkey_stop()

        assert ctrl.state == AppState.PROCESSING
        mock_pipeline.flush_and_recognize.assert_called_once()

    def test_on_recognition_complete_empty_text_returns_to_idle(self):
        """on_recognition_complete("") 應直接轉 IDLE 不觸發注入。"""
        mock_injector = MagicMock()
        ctrl = CoreController(text_injector=mock_injector)
        ctrl.transition(AppState.ACTIVATING)
        ctrl.transition(AppState.LISTENING)
        ctrl.transition(AppState.PROCESSING)

        ctrl.on_recognition_complete("")

        assert ctrl.state == AppState.IDLE
        mock_injector.inject.assert_not_called()

    def test_cancel_calls_cancel_processing_timeout(self):
        """cancel() 應呼叫 _cancel_processing_timeout()。"""
        ctrl = CoreController()
        ctrl.transition(AppState.ACTIVATING)
        cancelled = []
        ctrl._cancel_processing_timeout = lambda: cancelled.append(True)

        ctrl.cancel()

        assert cancelled, "cancel() 應呼叫 _cancel_processing_timeout()"

    def test_set_error_calls_cancel_processing_timeout(self):
        """set_error() 應呼叫 _cancel_processing_timeout()。"""
        ctrl = CoreController()
        ctrl.transition(AppState.ACTIVATING)
        cancelled = []
        ctrl._cancel_processing_timeout = lambda: cancelled.append(True)

        ctrl.set_error("測試錯誤")

        assert cancelled, "set_error() 應呼叫 _cancel_processing_timeout()"

    def test_shutdown_calls_cancel_processing_timeout(self):
        """shutdown() 應呼叫 _cancel_processing_timeout()。"""
        ctrl = CoreController()
        cancelled = []
        ctrl._cancel_processing_timeout = lambda: cancelled.append(True)

        ctrl.shutdown()

        assert cancelled, "shutdown() 應呼叫 _cancel_processing_timeout()"


# ─────────────────────────────────────────────────────────────────────────────
# 任務 2.1：CoreController 公開方法（TDD）
# ─────────────────────────────────────────────────────────────────────────────


class TestPublicRecordingControlMethods:
    """驗證 request_start() / request_stop() 公開方法。"""

    def test_request_start_exists(self):
        """CoreController 應有 request_start() 公開方法。"""
        ctrl = CoreController()
        assert hasattr(ctrl, "request_start"), "缺少 request_start() 方法"
        assert callable(ctrl.request_start)

    def test_request_stop_exists(self):
        """CoreController 應有 request_stop() 公開方法。"""
        ctrl = CoreController()
        assert hasattr(ctrl, "request_stop"), "缺少 request_stop() 方法"
        assert callable(ctrl.request_stop)

    def test_request_start_triggers_idle_to_listening(self):
        """IDLE 時呼叫 request_start() 應轉入 LISTENING。"""
        ctrl = CoreController()
        ctrl.request_start()
        assert ctrl.state == AppState.LISTENING

    def test_request_stop_triggers_listening_to_processing(self):
        """LISTENING 時呼叫 request_stop() 應轉入 PROCESSING（pipeline mock）。"""
        from unittest.mock import MagicMock

        mock_pipeline = MagicMock()
        ctrl = CoreController(pipeline=mock_pipeline)
        ctrl.request_start()  # → LISTENING
        ctrl.request_stop()
        # 有 pipeline 時停在 PROCESSING（等待辨識結果）
        assert ctrl.state == AppState.PROCESSING

    def test_request_start_ignored_when_not_idle(self):
        """非 IDLE 狀態呼叫 request_start() 應被忽略。"""
        ctrl = CoreController()
        ctrl.request_start()  # → LISTENING
        ctrl.request_start()  # 應被忽略
        assert ctrl.state == AppState.LISTENING

    def test_request_start_delegates_to_on_hotkey_start(self):
        """request_start() 應委派至 _on_hotkey_start()。"""
        from unittest.mock import MagicMock

        ctrl = CoreController()
        ctrl._on_hotkey_start = MagicMock()
        ctrl.request_start()
        ctrl._on_hotkey_start.assert_called_once()

    def test_request_stop_delegates_to_on_hotkey_stop(self):
        """request_stop() 應委派至 _on_hotkey_stop()。"""
        from unittest.mock import MagicMock

        ctrl = CoreController()
        ctrl._on_hotkey_stop = MagicMock()
        ctrl.request_stop()
        ctrl._on_hotkey_stop.assert_called_once()
