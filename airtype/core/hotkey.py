"""全域快捷鍵監聽器。

使用 pynput 在 daemon thread 中監聽系統級快捷鍵，支援 Windows、macOS、Linux (X11)。
實作切換行為（INACTIVE/ACTIVE 狀態機）與 Escape 取消鍵。
符合 PRD §4.3（快捷鍵規格）與 specs/global-hotkey/spec.md。
"""

from __future__ import annotations

import logging
import os
import sys
from enum import Enum, auto
from typing import Callable, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 按鍵對照表
# ---------------------------------------------------------------------------

_MODIFIER_MAP: dict[str, str] = {
    "ctrl": "<ctrl>",
    "shift": "<shift>",
    "alt": "<alt>",
    "cmd": "<cmd>",
    "super": "<cmd>",
}

_SPECIAL_KEY_MAP: dict[str, str] = {
    "space": "<space>",
    "escape": "<esc>",
    "esc": "<esc>",
    "enter": "<enter>",
    "return": "<enter>",
    "tab": "<tab>",
    "backspace": "<backspace>",
    "delete": "<delete>",
    "up": "<up>",
    "down": "<down>",
    "left": "<left>",
    "right": "<right>",
    "home": "<home>",
    "end": "<end>",
    "page_up": "<page_up>",
    "page_down": "<page_down>",
    **{f"f{i}": f"<f{i}>" for i in range(1, 25)},
}

# ---------------------------------------------------------------------------
# 切換狀態
# ---------------------------------------------------------------------------


class HotkeyState(Enum):
    INACTIVE = auto()
    ACTIVE = auto()


# ---------------------------------------------------------------------------
# 按鍵組合解析
# ---------------------------------------------------------------------------


def parse_key_combo(combo_str: str) -> str:
    """將按鍵組合字串解析為 pynput GlobalHotKeys 格式。

    Args:
        combo_str: 例如 ``"ctrl+shift+space"``、``"ctrl+alt+r"``、``"alt+f1"``。

    Returns:
        pynput 格式的按鍵組合，例如 ``"<ctrl>+<shift>+<space>"``。

    Raises:
        ValueError: 按鍵組合為空或包含無法辨識的按鍵。
    """
    parts = [p.strip().lower() for p in combo_str.split("+")]
    parts = [p for p in parts if p]  # 過濾空字串

    if not parts:
        raise ValueError(f"無效的按鍵組合（空字串）：{combo_str!r}")

    converted: list[str] = []
    for part in parts:
        if part in _MODIFIER_MAP:
            converted.append(_MODIFIER_MAP[part])
        elif part in _SPECIAL_KEY_MAP:
            converted.append(_SPECIAL_KEY_MAP[part])
        elif len(part) == 1 and (part.isalpha() or part.isdigit()):
            converted.append(part)
        else:
            raise ValueError(f"無法辨識的按鍵：{part!r}（來自 {combo_str!r}）")

    return "+".join(converted)


# ---------------------------------------------------------------------------
# 平台支援性檢查
# ---------------------------------------------------------------------------


def _check_platform_support() -> None:
    """檢查目前平台的快捷鍵支援性，並在必要時記錄警告或錯誤。"""
    if sys.platform == "darwin":
        _check_macos_accessibility()
    elif sys.platform.startswith("linux"):
        _check_linux_wayland()


def _check_macos_accessibility() -> None:
    """偵測 macOS 輔助使用權限是否已授予。

    若未授予，記錄 ERROR 並包含啟用說明；不崩潰。
    """
    try:
        import ctypes
        import ctypes.util

        lib_path = ctypes.util.find_library("ApplicationServices")
        if lib_path:
            app_services = ctypes.CDLL(lib_path)
            trusted: int = app_services.AXIsProcessTrusted()
            if not trusted:
                logger.error(
                    "macOS 輔助使用權限未授予。pynput 全域快捷鍵將無法運作。\n"
                    "請前往：系統設定 > 隱私權與安全性 > 輔助使用，\n"
                    "並將 Airtype 加入允許列表。"
                )
    except Exception as exc:  # noqa: BLE001
        logger.debug("無法檢查 macOS 輔助使用權限：%s", exc)


def _check_linux_wayland() -> None:
    """偵測 Linux Wayland 顯示伺服器。

    若為 Wayland，記錄 WARNING（全域快捷鍵及 xdotool 焦點管理可能無法運作）。
    """
    wayland_display = os.environ.get("WAYLAND_DISPLAY", "")
    xdg_session = os.environ.get("XDG_SESSION_TYPE", "").lower()
    if wayland_display or xdg_session == "wayland":
        logger.warning(
            "偵測到 Wayland 顯示伺服器（WAYLAND_DISPLAY=%r, XDG_SESSION_TYPE=%r）。"
            "全域快捷鍵及焦點管理可能無法正常運作（需要 X11）。",
            wayland_display,
            xdg_session,
        )


# ---------------------------------------------------------------------------
# HotkeyManager
# ---------------------------------------------------------------------------


class HotkeyManager:
    """全域快捷鍵管理器。

    在 daemon thread 中執行 pynput 監聽器，支援：

    - 可設定的切換快捷鍵（INACTIVE ↔ ACTIVE）
    - Escape 取消鍵（回到 INACTIVE 並觸發 on_cancel callback）
    - 透過 on_start / on_stop / on_cancel 註冊 callback

    使用方式::

        mgr = HotkeyManager(config.shortcuts)
        mgr.on_start(lambda: print("開始錄音"))
        mgr.on_stop(lambda: print("停止錄音"))
        mgr.on_cancel(lambda: print("取消錄音"))
        mgr.start()
        ...
        mgr.stop()
    """

    def __init__(self, shortcuts_config) -> None:
        """
        Args:
            shortcuts_config: :class:`airtype.config.ShortcutsConfig` 實例。
        """
        self._config = shortcuts_config
        self._state = HotkeyState.INACTIVE
        self._on_start_cb: Optional[Callable[[], None]] = None
        self._on_stop_cb: Optional[Callable[[], None]] = None
        self._on_cancel_cb: Optional[Callable[[], None]] = None
        self._hotkey_listener = None
        self._escape_listener = None

    # ------------------------------------------------------------------
    # Callback 註冊
    # ------------------------------------------------------------------

    def on_start(self, callback: Callable[[], None]) -> None:
        """註冊「開始錄音」callback。"""
        self._on_start_cb = callback

    def on_stop(self, callback: Callable[[], None]) -> None:
        """註冊「停止錄音」callback。"""
        self._on_stop_cb = callback

    def on_cancel(self, callback: Callable[[], None]) -> None:
        """註冊「取消錄音」callback。"""
        self._on_cancel_cb = callback

    # ------------------------------------------------------------------
    # 狀態屬性
    # ------------------------------------------------------------------

    @property
    def state(self) -> HotkeyState:
        """目前切換狀態（INACTIVE / ACTIVE）。"""
        return self._state

    def reset_state(self) -> None:
        """強制將內部切換狀態重置為 INACTIVE，不停止監聽器。

        供 CoreController 在取消或錯誤後呼叫，確保下次按快捷鍵時
        正確觸發「開始錄音」而非「停止錄音」。
        """
        self._state = HotkeyState.INACTIVE
        logger.debug("HotkeyManager 狀態已重置為 INACTIVE")

    # ------------------------------------------------------------------
    # 生命週期
    # ------------------------------------------------------------------

    def start(self) -> None:
        """啟動快捷鍵監聽器（daemon thread）。"""
        from pynput import keyboard  # 延遲匯入，允許在無 pynput 環境下匯入本模組

        _check_platform_support()

        # 解析 toggle_voice 快捷鍵
        try:
            toggle_combo = parse_key_combo(self._config.toggle_voice)
        except ValueError as exc:
            logger.error(
                "toggle_voice 快捷鍵解析失敗：%s，使用預設值 <ctrl>+<shift>+<space>",
                exc,
            )
            toggle_combo = "<ctrl>+<shift>+<space>"

        # GlobalHotKeys 監聽 toggle_voice
        try:
            self._hotkey_listener = keyboard.GlobalHotKeys(
                {toggle_combo: self._handle_toggle},
                daemon=True,
            )
            self._hotkey_listener.start()
            logger.debug("已註冊切換快捷鍵：%s", toggle_combo)
        except Exception as exc:  # noqa: BLE001
            logger.error("無法啟動快捷鍵監聽器：%s", exc)

        # 獨立 Listener 監聽 Escape 取消鍵
        try:
            self._escape_listener = keyboard.Listener(
                on_press=self._handle_key_press,
                daemon=True,
            )
            self._escape_listener.start()
            logger.debug("已啟動 Escape 取消鍵監聽")
        except Exception as exc:  # noqa: BLE001
            logger.error("無法啟動 Escape 監聽器：%s", exc)

    def stop(self) -> None:
        """停止快捷鍵監聽器並釋放資源。"""
        if self._hotkey_listener is not None:
            try:
                self._hotkey_listener.stop()
            except Exception as exc:  # noqa: BLE001
                logger.debug("停止 hotkey_listener 時發生例外：%s", exc)
            self._hotkey_listener = None

        if self._escape_listener is not None:
            try:
                self._escape_listener.stop()
            except Exception as exc:  # noqa: BLE001
                logger.debug("停止 escape_listener 時發生例外：%s", exc)
            self._escape_listener = None

        self._state = HotkeyState.INACTIVE
        logger.debug("HotkeyManager 已停止")

    def reload(self) -> None:
        """以目前 config 中的快捷鍵組合重新啟動監聽器。

        設定面板變更快捷鍵後應呼叫此方法，使新組合立即生效。
        保留已註冊的 on_start / on_stop / on_cancel callbacks。
        """
        logger.debug("HotkeyManager 重新載入快捷鍵設定")
        self.stop()
        self.start()

    # ------------------------------------------------------------------
    # 內部事件處理
    # ------------------------------------------------------------------

    def _handle_toggle(self) -> None:
        """處理 toggle_voice 快捷鍵按下事件（切換狀態機）。"""
        if self._state == HotkeyState.INACTIVE:
            self._state = HotkeyState.ACTIVE
            logger.debug("快捷鍵狀態切換：INACTIVE → ACTIVE")
            if self._on_start_cb is not None:
                self._on_start_cb()
        else:
            self._state = HotkeyState.INACTIVE
            logger.debug("快捷鍵狀態切換：ACTIVE → INACTIVE")
            if self._on_stop_cb is not None:
                self._on_stop_cb()

    def _handle_key_press(self, key) -> None:
        """處理所有按鍵事件（用於 Escape 取消）。"""
        try:
            from pynput.keyboard import Key

            if key == Key.esc:
                if self._state == HotkeyState.ACTIVE:
                    self._state = HotkeyState.INACTIVE
                    logger.debug("Escape 取消：ACTIVE → INACTIVE")
                    if self._on_cancel_cb is not None:
                        self._on_cancel_cb()
                # INACTIVE 狀態下 Escape 為 no-op
        except Exception as exc:  # noqa: BLE001
            logger.debug("_handle_key_press 例外：%s", exc)


# ---------------------------------------------------------------------------
# FocusManager
# ---------------------------------------------------------------------------


class FocusManager:
    """作用中視窗焦點管理器。

    在觸發快捷鍵前擷取焦點視窗控制代碼，並於文字注入前還原焦點至目標視窗。

    Windows 使用 ctypes win32 API；其他平台記錄 debug 訊息（尚不支援）。

    使用方式::

        focus_mgr = FocusManager()
        focus_mgr.capture_focus()   # 快捷鍵觸發前呼叫
        ...
        focus_mgr.restore_focus()   # 注入前呼叫
    """

    def __init__(self) -> None:
        self._focused_hwnd: Optional[int] = None

    def capture_focus(self) -> None:
        """儲存目前作用中視窗的控制代碼。"""
        if sys.platform == "win32":
            try:
                import ctypes

                self._focused_hwnd = ctypes.windll.user32.GetForegroundWindow()
                logger.debug("已擷取焦點視窗：hwnd=%s", self._focused_hwnd)
            except Exception as exc:  # noqa: BLE001
                logger.debug("擷取焦點視窗失敗：%s", exc)
        else:
            logger.debug("FocusManager.capture_focus 在此平台尚未支援：%s", sys.platform)

    def restore_focus(self) -> None:
        """還原焦點至先前擷取的視窗。"""
        if sys.platform == "win32":
            if self._focused_hwnd:
                try:
                    import ctypes

                    ctypes.windll.user32.SetForegroundWindow(self._focused_hwnd)
                    logger.debug("已還原焦點至視窗：hwnd=%s", self._focused_hwnd)
                except Exception as exc:  # noqa: BLE001
                    logger.debug("還原焦點失敗：%s", exc)
        else:
            logger.debug("FocusManager.restore_focus 在此平台尚未支援：%s", sys.platform)
