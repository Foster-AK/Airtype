"""跨平台視窗焦點管理。

提供 FocusManager 抽象介面，封裝 Windows（Win32 API）、macOS（osascript）、
Linux (X11, xdotool) 的視窗焦點記錄與還原。
符合 PRD §6.5（焦點管理）與 specs/focus-management/spec.md。
"""

from __future__ import annotations

import logging
import subprocess
import sys
from abc import ABC, abstractmethod
from typing import Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 抽象介面
# ---------------------------------------------------------------------------


class FocusManager(ABC):
    """跨平台視窗焦點管理介面。

    子類別針對各平台實作 :meth:`record` 與 :meth:`restore`。
    使用工廠函式 :func:`create_focus_manager` 取得對應當前平台的實例。
    """

    @abstractmethod
    def record(self) -> None:
        """記錄目前的前景視窗，供稍後 :meth:`restore` 使用。"""

    @abstractmethod
    def restore(self) -> None:
        """將焦點還原至先前由 :meth:`record` 記錄的視窗。

        若記錄的視窗已不存在，應記錄警告而非拋出例外。
        """


# ---------------------------------------------------------------------------
# Windows 實作
# ---------------------------------------------------------------------------


class WindowsFocusManager(FocusManager):
    """Windows 焦點管理：使用 ctypes 呼叫 Win32 API。

    - 記錄：``GetForegroundWindow``
    - 還原：``SetForegroundWindow`` 搭配 ``AttachThreadInput``
    """

    def __init__(self) -> None:
        self._hwnd: Optional[int] = None

    def record(self) -> None:
        """以 GetForegroundWindow 記錄目前前景視窗 handle。"""
        import ctypes

        self._hwnd = ctypes.windll.user32.GetForegroundWindow()
        logger.debug("已記錄視窗 handle：%s", self._hwnd)

    def restore(self) -> None:
        """以 SetForegroundWindow + AttachThreadInput 可靠地還原焦點。

        若目標視窗已不存在，記錄 WARNING 後直接返回（不崩潰）。
        """
        if self._hwnd is None:
            logger.warning("尚未記錄視窗，無法還原焦點")
            return

        import ctypes

        user32 = ctypes.windll.user32

        # 檢查目標視窗是否仍然存在
        if not user32.IsWindow(self._hwnd):
            logger.warning("目標視窗（handle=%s）已不存在，跳過焦點還原", self._hwnd)
            return

        try:
            # 取得目前前景視窗執行緒 ID 與目標視窗執行緒 ID
            fg_hwnd = user32.GetForegroundWindow()
            fg_tid = user32.GetWindowThreadProcessId(fg_hwnd, None)
            target_tid = user32.GetWindowThreadProcessId(self._hwnd, None)

            # AttachThreadInput 確保可以可靠地切換前景視窗
            if fg_tid != target_tid:
                user32.AttachThreadInput(fg_tid, target_tid, True)
            user32.SetForegroundWindow(self._hwnd)
            if fg_tid != target_tid:
                user32.AttachThreadInput(fg_tid, target_tid, False)

            logger.debug("已還原焦點至視窗 handle：%s", self._hwnd)
        except Exception as exc:  # noqa: BLE001
            logger.warning("還原焦點失敗（handle=%s）：%s", self._hwnd, exc)


# ---------------------------------------------------------------------------
# macOS 實作
# ---------------------------------------------------------------------------


class MacOSFocusManager(FocusManager):
    """macOS 焦點管理：使用 osascript（AppleScript）。

    - 記錄：查詢最前方應用程式名稱
    - 還原：依名稱啟動應用程式
    """

    def __init__(self) -> None:
        self._app_name: Optional[str] = None

    def record(self) -> None:
        """透過 osascript 記錄最前方應用程式名稱。"""
        script = (
            'tell application "System Events" to '
            "get name of first process whose frontmost is true"
        )
        try:
            result = subprocess.run(
                ["osascript", "-e", script],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                self._app_name = result.stdout.strip()
                logger.debug("已記錄前景應用程式：%s", self._app_name)
            else:
                logger.warning("osascript 記錄焦點失敗：%s", result.stderr.strip())
        except FileNotFoundError:
            logger.warning("未找到 osascript（非 macOS 環境？）")
        except subprocess.TimeoutExpired:
            logger.warning("osascript getactiveapp 逾時")

    def restore(self) -> None:
        """透過 osascript activate 還原至先前記錄的應用程式。

        若應用程式已不存在或啟動失敗，記錄 WARNING 後返回（不崩潰）。
        """
        if not self._app_name:
            logger.warning("尚未記錄應用程式，無法還原焦點")
            return

        script = f'tell application "{self._app_name}" to activate'
        try:
            result = subprocess.run(
                ["osascript", "-e", script],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                logger.debug("已還原焦點至應用程式：%s", self._app_name)
            else:
                logger.warning(
                    "osascript 還原焦點失敗（app=%s）：%s",
                    self._app_name,
                    result.stderr.strip(),
                )
        except FileNotFoundError:
            logger.warning("未找到 osascript（非 macOS 環境？）")
        except subprocess.TimeoutExpired:
            logger.warning(
                "osascript activate 逾時（app=%s）", self._app_name
            )


# ---------------------------------------------------------------------------
# Linux 實作
# ---------------------------------------------------------------------------


class LinuxFocusManager(FocusManager):
    """Linux (X11) 焦點管理：使用 xdotool。

    - 記錄：``xdotool getactivewindow``
    - 還原：``xdotool windowactivate``
    """

    def __init__(self) -> None:
        self._window_id: Optional[str] = None

    def record(self) -> None:
        """以 xdotool getactivewindow 記錄目前作用中視窗 ID。"""
        try:
            result = subprocess.run(
                ["xdotool", "getactivewindow"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                self._window_id = result.stdout.strip()
                logger.debug("已記錄視窗 ID：%s", self._window_id)
            else:
                logger.warning("xdotool 記錄焦點失敗：%s", result.stderr.strip())
        except FileNotFoundError:
            logger.warning(
                "未找到 xdotool，請安裝後再試（sudo apt install xdotool）"
            )
        except subprocess.TimeoutExpired:
            logger.warning("xdotool getactivewindow 逾時")

    def restore(self) -> None:
        """以 xdotool windowactivate 還原視窗焦點。

        若視窗已不存在，xdotool 會返回非零 exit code；
        偵測到後記錄 WARNING 並返回（不崩潰）。
        """
        if not self._window_id:
            logger.warning("尚未記錄視窗 ID，無法還原焦點")
            return

        try:
            result = subprocess.run(
                ["xdotool", "windowactivate", self._window_id],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                logger.debug("已還原焦點至視窗 ID：%s", self._window_id)
            else:
                logger.warning(
                    "xdotool 還原焦點失敗（window_id=%s）：%s",
                    self._window_id,
                    result.stderr.strip(),
                )
        except FileNotFoundError:
            logger.warning(
                "未找到 xdotool，請安裝後再試（sudo apt install xdotool）"
            )
        except subprocess.TimeoutExpired:
            logger.warning(
                "xdotool windowactivate 逾時（window_id=%s）", self._window_id
            )


# ---------------------------------------------------------------------------
# 工廠函式
# ---------------------------------------------------------------------------


def create_focus_manager() -> FocusManager:
    """根據目前平台回傳對應的 FocusManager 實例。

    Returns:
        - Windows：:class:`WindowsFocusManager`
        - macOS：:class:`MacOSFocusManager`
        - Linux：:class:`LinuxFocusManager`

    Raises:
        NotImplementedError: 不支援的平台。
    """
    if sys.platform == "win32":
        return WindowsFocusManager()
    elif sys.platform == "darwin":
        return MacOSFocusManager()
    elif sys.platform.startswith("linux"):
        return LinuxFocusManager()
    else:
        raise NotImplementedError(f"不支援的平台：{sys.platform!r}")
