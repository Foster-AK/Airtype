"""核心控制器：應用程式狀態機與事件分發。

CoreController 繼承 QObject，擁有 6 狀態應用程式狀態機，並透過 Qt Signals
將工作執行緒事件橋接至 Qt 主執行緒。

狀態轉換（正常流程）：
    IDLE → ACTIVATING → LISTENING → PROCESSING → INJECTING → IDLE

特殊轉換：
    任何狀態 → ERROR（發生錯誤時）
    任何狀態 → IDLE（取消操作）

相依：04-hotkey-focus、12-recognition-pipeline
"""

from __future__ import annotations

import logging
import threading
from enum import Enum, auto
from typing import Optional

from airtype.ui.polish_preview import PolishPreviewDialog

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# 應用程式狀態
# ─────────────────────────────────────────────────────────────────────────────


class AppState(Enum):
    """應用程式狀態列舉（6 個狀態）。"""

    IDLE = auto()        # 閒置，等待使用者觸發
    ACTIVATING = auto()  # 啟動中（管線初始化）
    LISTENING = auto()   # 偵聽中（VAD 活躍）
    PROCESSING = auto()  # 處理中（ASR 辨識）
    INJECTING = auto()   # 注入中（文字注入目標視窗）
    ERROR = auto()       # 錯誤狀態


# 有效轉換表：{來源狀態: 允許的目標狀態列表}
# 取消操作（任何狀態 → IDLE）和錯誤轉換（任何狀態 → ERROR）由
# cancel() 與 set_error() 方法處理，不需全部列在轉換表中。
_TRANSITIONS: dict[AppState, list[AppState]] = {
    AppState.IDLE:       [AppState.ACTIVATING],
    AppState.ACTIVATING: [AppState.LISTENING, AppState.IDLE, AppState.ERROR],
    AppState.LISTENING:  [AppState.PROCESSING, AppState.IDLE, AppState.ERROR],
    AppState.PROCESSING: [AppState.INJECTING, AppState.IDLE, AppState.ERROR],
    AppState.INJECTING:  [AppState.IDLE, AppState.ERROR],
    AppState.ERROR:      [AppState.IDLE],
}


# ─────────────────────────────────────────────────────────────────────────────
# CoreController
# ─────────────────────────────────────────────────────────────────────────────


class CoreController:
    """核心應用程式控制器。

    實作 6 狀態應用程式狀態機，並透過 Qt Signals 將工作執行緒事件
    橋接至 Qt 主執行緒。

    當 PySide6 可用時，繼承 QObject 並使用 Qt Signals；
    當 PySide6 不可用時（如單元測試），退化為純 Python 版本以支援測試。

    使用方式::

        controller = CoreController(config=cfg, hotkey_manager=hk, pipeline=pl)
        init_controller(controller)
        controller.startup()
        ...
        controller.shutdown()
    """

    # Qt Signals（在類別定義後動態附加，見模組底部）

    def __init__(
        self,
        config=None,
        hotkey_manager=None,
        pipeline=None,
        text_injector=None,
        polish_engine=None,
        dictionary_engine=None,
        focus_manager=None,
    ) -> None:
        """
        Args:
            config:            :class:`airtype.config.AirtypeConfig` 實例（可選）。
            hotkey_manager:    :class:`airtype.core.hotkey.HotkeyManager` 實例（可選）。
            pipeline:          批次或串流辨識管線實例（可選）。
            text_injector:     :class:`airtype.core.text_injector.TextInjector` 實例（可選）。
            polish_engine:     :class:`airtype.core.llm_polish.PolishEngine` 實例（可選）。
                               為 None 時，LLM 潤飾功能停用。
            dictionary_engine: :class:`airtype.core.dictionary.DictionaryEngine` 實例（可選）。
                               為 None 時，辭典後處理停用。
            focus_manager:     :class:`airtype.core.hotkey.FocusManager` 實例（可選）。
                               用於在開始錄音時擷取焦點視窗。
        """
        self._state = AppState.IDLE
        self._config = config
        self._hotkey_manager = hotkey_manager
        self._pipeline = pipeline
        self._text_injector = text_injector
        self._polish_engine = polish_engine
        self._dictionary_engine = dictionary_engine
        self._focus_manager = focus_manager

        # PROCESSING 超時保護（30 秒 threading.Timer，執行緒安全）
        self._processing_timer = None   # 由 _start_processing_timeout() 建立
        self._processing_timer_lock = threading.Lock()
        self._processing_timeout_sec: int = 30

        # Signal 回呼列表（QObject 不可用時的備援）
        self._state_changed_callbacks: list = []
        self._error_callbacks: list = []
        self._recognition_complete_callbacks: list = []

        # 跨執行緒辨識結果暫存（工作執行緒 → GUI 執行緒）
        self._pending_original: str = ""
        self._pending_polished: str = ""

        # 串流部分結果回呼列表
        self._partial_result_callbacks: list = []

    # ------------------------------------------------------------------
    # 狀態屬性
    # ------------------------------------------------------------------

    @property
    def state(self) -> AppState:
        """目前應用程式狀態。"""
        return self._state

    # ------------------------------------------------------------------
    # 狀態機轉換
    # ------------------------------------------------------------------

    def transition(self, new_state: AppState) -> bool:
        """依轉換表執行狀態轉換。

        無效的轉換記錄 WARNING 並忽略，不拋出例外。

        Args:
            new_state: 目標狀態。

        Returns:
            True 表示轉換成功；False 表示轉換無效（已忽略）。
        """
        allowed = _TRANSITIONS.get(self._state, [])
        if new_state not in allowed:
            logger.warning(
                "無效的狀態轉換：%s → %s（已忽略）",
                self._state.name,
                new_state.name,
            )
            return False

        logger.debug("狀態轉換：%s → %s", self._state.name, new_state.name)
        self._state = new_state
        self._emit_state_changed(new_state)
        return True

    def cancel(self) -> None:
        """取消目前操作，強制返回 IDLE（繞過轉換表）。

        在任何非 IDLE 狀態下均有效（「任何活躍狀態 → IDLE」特殊規則）。
        同步重置 HotkeyManager 狀態，確保下次按快捷鍵正確觸發「開始」。
        """
        if self._state == AppState.IDLE:
            return
        self._cancel_processing_timeout()
        logger.debug("取消操作：%s → IDLE（強制）", self._state.name)
        self._state = AppState.IDLE
        self._emit_state_changed(AppState.IDLE)
        if self._hotkey_manager is not None and hasattr(self._hotkey_manager, "reset_state"):
            self._hotkey_manager.reset_state()

    def set_error(self, message: str) -> None:
        """發生錯誤時從任何狀態轉換至 ERROR，再自動回到 IDLE。

        同步重置 HotkeyManager 狀態，確保錯誤恢復後快捷鍵行為正確。

        Args:
            message: 錯誤訊息。
        """
        self._cancel_processing_timeout()
        logger.error("控制器錯誤：%s（狀態：%s）", message, self._state.name)
        self._state = AppState.ERROR
        self._emit_state_changed(AppState.ERROR)
        self._emit_error(message)
        self._state = AppState.IDLE
        self._emit_state_changed(AppState.IDLE)
        if self._hotkey_manager is not None and hasattr(self._hotkey_manager, "reset_state"):
            self._hotkey_manager.reset_state()

    # ------------------------------------------------------------------
    # Signal 輔助（支援 QObject 與純 Python 兩種模式）
    # ------------------------------------------------------------------

    def _emit_state_changed(self, new_state: AppState) -> None:
        for cb in self._state_changed_callbacks:
            try:
                cb(new_state)
            except Exception as exc:
                logger.debug("state_changed 回呼例外：%s", exc)

    def _emit_error(self, message: str) -> None:
        for cb in self._error_callbacks:
            try:
                cb(message)
            except Exception as exc:
                logger.debug("error 回呼例外：%s", exc)

    def _emit_recognition_complete(self, text: str) -> None:
        for cb in self._recognition_complete_callbacks:
            try:
                cb(text)
            except Exception as exc:
                logger.debug("recognition_complete 回呼例外：%s", exc)

    def connect_state_changed(self, callback) -> None:
        """連接 state_changed 事件（純 Python 模式用）。"""
        self._state_changed_callbacks.append(callback)

    def connect_error(self, callback) -> None:
        """連接 error 事件（純 Python 模式用）。"""
        self._error_callbacks.append(callback)

    def connect_recognition_complete(self, callback) -> None:
        """連接 recognition_complete 事件（純 Python 模式用）。"""
        self._recognition_complete_callbacks.append(callback)

    def _emit_partial_result(self, text: str, is_final: bool) -> None:
        for cb in self._partial_result_callbacks:
            try:
                cb(text, is_final)
            except Exception as exc:
                logger.debug("partial_result 回呼例外：%s", exc)

    def connect_partial_result(self, callback) -> None:
        """連接 partial_result 事件（純 Python 模式用）。"""
        self._partial_result_callbacks.append(callback)

    def on_partial_result(self, text: str, is_final: bool) -> None:
        """串流管線部分結果回呼（可從工作執行緒呼叫）。"""
        self._emit_partial_result(text, is_final)

    # ------------------------------------------------------------------
    # PROCESSING 超時保護
    # ------------------------------------------------------------------

    def _start_processing_timeout(self) -> None:
        """啟動 30 秒 threading.Timer，超時觸發 set_error()。

        使用 threading.Timer 取代 QTimer，確保跨執行緒安全：
        - _on_hotkey_stop 在 pynput 執行緒呼叫 _start_processing_timeout
        - on_recognition_complete 在 ASR 工作執行緒呼叫 _cancel_processing_timeout
        - QTimer 不允許跨執行緒 start/stop，threading.Timer 則安全
        """
        self._cancel_processing_timeout()
        with self._processing_timer_lock:
            timer = threading.Timer(
                self._processing_timeout_sec,
                self._on_processing_timeout,
            )
            timer.daemon = True
            timer.name = "processing-timeout"
            timer.start()
            self._processing_timer = timer
        logger.debug("PROCESSING 超時保護已啟動（%ds）", self._processing_timeout_sec)

    def _cancel_processing_timeout(self) -> None:
        """取消 PROCESSING 超時計時器（執行緒安全）。"""
        with self._processing_timer_lock:
            if self._processing_timer is not None:
                self._processing_timer.cancel()
                self._processing_timer = None

    def _on_processing_timeout(self) -> None:
        """PROCESSING 超時 callback（在 daemon 執行緒中執行）。

        透過 _deferred_timeout Signal 將 set_error 轉發至 GUI 執行緒，
        避免從背景執行緒直接操作狀態機與 Qt 物件。
        """
        with self._processing_timer_lock:
            self._processing_timer = None
        logger.warning("PROCESSING 超時（%ds），自動恢復 IDLE", self._processing_timeout_sec)
        if hasattr(self, "_deferred_timeout"):
            self._deferred_timeout.emit()  # type: ignore[attr-defined]
        else:
            self.set_error("辨識超時，請重試")

    # ------------------------------------------------------------------
    # 公開錄音控制方法（供 UI 按鈕呼叫）
    # ------------------------------------------------------------------

    def request_start(self) -> None:
        """請求開始錄音（公開 API，委派至 _on_hotkey_start）。"""
        self._on_hotkey_start()

    def request_stop(self) -> None:
        """請求停止錄音（公開 API，委派至 _on_hotkey_stop）。"""
        self._on_hotkey_stop()

    # ------------------------------------------------------------------
    # 快捷鍵事件 callbacks
    # ------------------------------------------------------------------

    def _on_hotkey_start(self) -> None:
        """處理「開始錄音」快捷鍵：IDLE → ACTIVATING，然後啟動管線。"""
        if self._focus_manager is not None:
            self._focus_manager.capture_focus()
        if not self.transition(AppState.ACTIVATING):
            return
        # 啟動管線後立即轉入 LISTENING 狀態
        if self._pipeline is not None:
            try:
                self._pipeline.start()
                self.transition(AppState.LISTENING)
            except Exception as exc:
                self.set_error(f"管線啟動失敗：{exc}")
        else:
            self.transition(AppState.LISTENING)

    def _on_hotkey_stop(self) -> None:
        """處理「停止錄音」快捷鍵（切換停止）。

        若目前在 LISTENING，轉入 PROCESSING 並呼叫 pipeline.flush_and_recognize()。
        若 pipeline 為 None，直接 cancel() 回 IDLE。
        """
        if self._state == AppState.LISTENING:
            self.transition(AppState.PROCESSING)
            if self._pipeline is not None:
                self._pipeline.flush_and_recognize()
                self._start_processing_timeout()
            else:
                self.cancel()

    def _on_hotkey_cancel(self) -> None:
        """處理 Escape 取消鍵：任何狀態 → IDLE。"""
        if self._state != AppState.IDLE:
            # 停止管線（如果正在執行）
            if self._pipeline is not None:
                try:
                    self._pipeline.stop()
                except Exception as exc:
                    logger.debug("取消時停止管線失敗：%s", exc)
            self.cancel()

    # ------------------------------------------------------------------
    # 管線事件 callbacks
    # ------------------------------------------------------------------

    def on_recognition_complete(self, text: str) -> None:
        """管線辨識完成時呼叫（可從工作執行緒呼叫）。

        在工作執行緒上執行辭典與 LLM 潤飾（CPU-bound），
        然後將結果轉發至 GUI 執行緒進行預覽對話框與文字注入。

        Args:
            text: 辨識結果文字。
        """
        self._cancel_processing_timeout()

        if not text:
            logger.debug("辨識結果為空，轉回 IDLE")
            self._state = AppState.IDLE
            self._emit_state_changed(AppState.IDLE)
            return

        logger.debug("辨識完成，文字長度：%d", len(text))
        self._emit_recognition_complete(text)

        # ── 工作執行緒上的 CPU-bound 處理 ──────────────────────────────

        # 辭典後處理（ASR 之後、LLM 之前）
        chosen = text
        if self._dictionary_engine is not None:
            chosen = self._dictionary_engine.apply_rules(chosen)

        # LLM 潤飾
        polished = chosen  # 預設：潤飾結果 = 原始（無變更）
        if (
            self._polish_engine is not None
            and self._config is not None
            and self._config.llm.enabled
        ):
            try:
                polished = self._polish_engine.polish(chosen)
            except Exception as exc:
                logger.error("LLM 潤飾失敗，回退至原始文字：%s", exc)
                polished = chosen

        # ── 轉發至 GUI 執行緒（預覽對話框 + 注入）──────────────────────
        # 存入暫存屬性，供 GUI 執行緒 slot 讀取
        self._pending_original = chosen
        self._pending_polished = polished

        if hasattr(self, "_deferred_inject"):
            self._deferred_inject.emit()  # type: ignore[attr-defined]
        else:
            # PySide6 不可用（純 Python 版本）→ 直接處理
            self._do_inject()

    def _do_inject(self) -> None:
        """在 GUI 執行緒上執行預覽對話框與文字注入。"""
        chosen = self._pending_original
        polished = self._pending_polished

        # 預覽對話框（僅當潤飾結果與原始不同時）
        if (
            self._config is not None
            and self._config.llm.enabled
            and self._config.llm.preview_before_inject
        ):
            if polished != chosen:
                try:
                    dialog = PolishPreviewDialog(chosen, polished)
                    if dialog.exec():  # QDialog.Accepted = 1
                        chosen = dialog.selected_text()
                    # else: 使用者關閉對話框 → chosen 維持原始文字
                except Exception as exc:
                    logger.error("預覽對話框失敗：%s", exc)
            else:
                # 潤飾結果與原始相同（可能是 fallback），直接注入
                logger.debug("潤飾結果與原始相同，跳過預覽")
        elif polished != chosen:
            # 不需預覽但有潤飾結果 → 直接使用潤飾版本
            chosen = polished

        if self.transition(AppState.INJECTING):
            if self._text_injector is not None:
                # 根據設定附加空格 / 換行
                if self._config is not None:
                    if self._config.general.append_newline:
                        chosen += "\n"
                    elif self._config.general.append_space:
                        chosen += " "
                try:
                    self._text_injector.inject(chosen)
                except Exception as exc:
                    logger.error("文字注入失敗：%s", exc)
            # 注入完成後回到 IDLE
            self.transition(AppState.IDLE)

    def on_pipeline_error(self, message: str) -> None:
        """管線發生錯誤時呼叫（可從工作執行緒呼叫）。

        Args:
            message: 錯誤訊息。
        """
        self.set_error(message)

    # ------------------------------------------------------------------
    # 生命週期
    # ------------------------------------------------------------------

    def startup(self) -> None:
        """啟動順序：連接元件 → 進入 IDLE 就緒狀態。

        應在 QApplication 建立後、顯示 UI 之前呼叫。
        """
        # 連接快捷鍵事件
        if self._hotkey_manager is not None:
            self._hotkey_manager.on_start(self._on_hotkey_start)
            self._hotkey_manager.on_stop(self._on_hotkey_stop)
            self._hotkey_manager.on_cancel(self._on_hotkey_cancel)
            try:
                self._hotkey_manager.start()
                logger.info("HotkeyManager 已啟動")
            except Exception as exc:
                logger.error("HotkeyManager 啟動失敗：%s", exc)

        # 連接管線回呼（若管線支援）
        if self._pipeline is not None:
            if hasattr(self._pipeline, "on_recognition_complete"):
                self._pipeline.on_recognition_complete(self.on_recognition_complete)
            if hasattr(self._pipeline, "on_error"):
                self._pipeline.on_error(self.on_pipeline_error)
            # 串流管線：連接部分結果回呼
            if hasattr(self._pipeline, "_on_partial"):
                self._pipeline._on_partial = self.on_partial_result

        # 啟動時背景更新檢查（僅當 config.general.notifications 為 True）
        if self._config is not None and getattr(self._config.general, "notifications", True):
            self._start_background_update_check()

        logger.info("CoreController 已啟動，狀態：%s", self._state.name)

    def _start_background_update_check(self) -> None:
        """在 daemon 執行緒中背景執行更新檢查，不阻塞啟動流程。"""
        import threading
        from airtype.utils.update_checker import check_for_update
        from airtype.ui.settings_about import APP_VERSION

        def _run() -> None:
            try:
                info = check_for_update(APP_VERSION)
                if info.is_update_available:
                    logger.info(
                        "有新版本可用：%s（下載：%s）",
                        info.latest_version,
                        info.download_url,
                    )
                elif info.is_error:
                    logger.debug("啟動更新檢查失敗：%s", info.error)
                else:
                    logger.debug("版本已是最新：%s", info.current_version)
            except Exception as exc:
                logger.debug("啟動更新檢查發生非預期錯誤：%s", exc)

        t = threading.Thread(target=_run, daemon=True, name="airtype-update-check")
        t.start()

    def shutdown(self) -> None:
        """關閉順序：停止管線 → 停止快捷鍵監聽 → 清理資源。"""
        self._cancel_processing_timeout()
        # 停止辨識管線
        if self._pipeline is not None:
            try:
                self._pipeline.stop()
                logger.info("管線已停止")
            except Exception as exc:
                logger.debug("停止管線時發生例外：%s", exc)

        # 停止快捷鍵監聽器
        if self._hotkey_manager is not None:
            try:
                self._hotkey_manager.stop()
                logger.info("HotkeyManager 已停止")
            except Exception as exc:
                logger.debug("停止 HotkeyManager 時發生例外：%s", exc)

        self._state = AppState.IDLE
        logger.info("CoreController 已關閉")


# ─────────────────────────────────────────────────────────────────────────────
# Qt Signal 整合（在 PySide6 可用時提升為 QObject 子類別）
# ─────────────────────────────────────────────────────────────────────────────

try:
    from PySide6.QtCore import QObject, Signal as _Signal, Slot as _Slot

    class CoreController(CoreController, QObject):  # type: ignore[no-redef]
        """Qt-aware 版本的 CoreController（PySide6 可用時使用）。

        繼承 QObject 以啟用 Qt Signals 進行執行緒安全通訊。
        Qt Signals 自動橋接工作執行緒 → Qt 主執行緒。
        """

        # Qt Signals（名稱與 spec 一致）
        state_changed = _Signal(AppState)
        error = _Signal(str)
        recognition_complete = _Signal(str)
        partial_result = _Signal(str, bool)  # (text, is_final)
        # 內部信號：從工作執行緒安全轉發注入動作至 GUI 執行緒
        _deferred_inject = _Signal()
        # 內部信號：從超時背景執行緒安全轉發 set_error 至 GUI 執行緒
        _deferred_timeout = _Signal()

        def __init__(self, config=None, hotkey_manager=None, pipeline=None,
                     text_injector=None, polish_engine=None, dictionary_engine=None,
                     focus_manager=None) -> None:
            QObject.__init__(self)
            # 呼叫純 Python 版本的 __init__（不透過 MRO super() 以避免衝突）
            self._state = AppState.IDLE
            self._config = config
            self._hotkey_manager = hotkey_manager
            self._pipeline = pipeline
            self._text_injector = text_injector
            self._polish_engine = polish_engine
            self._dictionary_engine = dictionary_engine
            self._focus_manager = focus_manager
            self._processing_timer = None
            self._processing_timer_lock = threading.Lock()
            self._processing_timeout_sec = 30
            self._state_changed_callbacks = []
            self._error_callbacks = []
            self._recognition_complete_callbacks = []
            self._partial_result_callbacks = []
            self._pending_original = ""
            self._pending_polished = ""
            # 連接 deferred signal → GUI 執行緒 slot
            self._deferred_inject.connect(self._do_inject)
            self._deferred_timeout.connect(self._on_deferred_timeout)

        def _emit_state_changed(self, new_state: AppState) -> None:
            self.state_changed.emit(new_state)  # type: ignore[attr-defined]
            super()._emit_state_changed(new_state)

        def _emit_error(self, message: str) -> None:
            self.error.emit(message)  # type: ignore[attr-defined]
            super()._emit_error(message)

        def _emit_recognition_complete(self, text: str) -> None:
            self.recognition_complete.emit(text)  # type: ignore[attr-defined]
            super()._emit_recognition_complete(text)

        def _emit_partial_result(self, text: str, is_final: bool) -> None:
            self.partial_result.emit(text, is_final)  # type: ignore[attr-defined]
            super()._emit_partial_result(text, is_final)

        @_Slot()
        def _do_inject(self) -> None:
            """Qt Slot 版本（確保在 GUI 執行緒執行）。"""
            # 在 GUI 執行緒再次確認取消超時計時器，
            # 防止對話框開啟期間超時觸發干擾狀態機
            self._cancel_processing_timeout()
            super()._do_inject()

        @_Slot()
        def _on_deferred_timeout(self) -> None:
            """超時 Signal 的 GUI 執行緒 Slot。"""
            self.set_error("辨識超時，請重試")

    PYSIDE6_AVAILABLE = True
    logger.debug("CoreController：已載入 PySide6 QObject 版本")

except ImportError:
    PYSIDE6_AVAILABLE = False
    logger.debug("CoreController：PySide6 不可用，使用純 Python 版本")


# ─────────────────────────────────────────────────────────────────────────────
# 全域單例存取
# ─────────────────────────────────────────────────────────────────────────────

_controller: Optional[CoreController] = None


def init_controller(controller: CoreController) -> None:
    """設定全域單例控制器實例。

    應在應用程式啟動時（建立 CoreController 後）呼叫一次。

    Args:
        controller: 已建立的 CoreController 實例。
    """
    global _controller
    _controller = controller
    logger.debug("全域 CoreController 單例已設定")


def get_controller() -> CoreController:
    """取得全域單例控制器實例。

    Returns:
        全域 CoreController 實例。

    Raises:
        RuntimeError: 若尚未呼叫 init_controller()。
    """
    if _controller is None:
        raise RuntimeError(
            "CoreController 尚未初始化，請先呼叫 init_controller()"
        )
    return _controller
