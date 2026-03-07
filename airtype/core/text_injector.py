"""跨平台文字注入器。

使用剪貼簿備份/還原策略將 ASR 辨識文字注入至目標應用程式的游標位置。

注入流程（符合 PRD §6.5，總週期 < 300ms）：
  1. 備份剪貼簿（~5ms）
  2. 寫入待注入文字至剪貼簿（~5ms）
  3. 透過 FocusManager 還原焦點至目標視窗（~25ms）
  4. 等待 50ms 讓焦點穩定
  5. 模擬 Ctrl+V（Windows/Linux）或 Cmd+V（macOS）貼上（~5ms）
  6. 等待 clipboard_restore_delay_ms（預設 150ms）讓目標應用程式處理
  7. 還原原始剪貼簿內容

相依：01-project-setup（設定、日誌記錄）、04-hotkey-focus（FocusManager）。
"""

from __future__ import annotations

import logging
import sys
import time
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from airtype.core.hotkey import FocusManager

logger = logging.getLogger(__name__)


class TextInjector:
    """基於剪貼簿的跨平台文字注入器。

    使用方式::

        injector = TextInjector(config, focus_manager=focus_mgr)
        injector.inject("你好世界")
    """

    def __init__(self, config, focus_manager: Optional["FocusManager"] = None) -> None:
        """
        Args:
            config: AirtypeConfig 實例，用於讀取 general.clipboard_restore_delay_ms。
            focus_manager: FocusManager 實例（來自 airtype.core.hotkey）；
                           可為 None（此時跳過焦點還原步驟）。
        """
        self._config = config
        self._focus_manager = focus_manager
        self._backup: str = ""

    # ------------------------------------------------------------------
    # 剪貼簿備份 / 還原
    # ------------------------------------------------------------------

    def _backup_clipboard(self) -> None:
        """備份目前剪貼簿文字內容。

        若剪貼簿為空或含非文字內容（pyperclip 擲出例外），備份值為空字串。
        """
        import pyperclip

        try:
            self._backup = pyperclip.paste() or ""
        except Exception as exc:  # noqa: BLE001
            logger.debug("剪貼簿備份失敗，使用空字串：%s", exc)
            self._backup = ""

    def _restore_clipboard(self) -> None:
        """將已備份的內容寫回剪貼簿。"""
        import pyperclip

        try:
            pyperclip.copy(self._backup)
            logger.debug("剪貼簿已還原（長度 %d）", len(self._backup))
        except Exception as exc:  # noqa: BLE001
            logger.warning("還原剪貼簿失敗：%s", exc)

    # ------------------------------------------------------------------
    # 貼上模擬
    # ------------------------------------------------------------------

    def _simulate_paste(self) -> None:
        """模擬貼上按鍵（Windows/Linux 為 Ctrl+V，macOS 為 Cmd+V）。

        透過 sys.platform 於執行時偵測平台。
        """
        import pyautogui

        try:
            if sys.platform == "darwin":
                pyautogui.hotkey("command", "v")
            else:
                pyautogui.hotkey("ctrl", "v")
            logger.debug("已模擬貼上按鍵（platform=%s）", sys.platform)
        except Exception as exc:  # noqa: BLE001
            logger.warning("模擬貼上失敗：%s", exc)

    # ------------------------------------------------------------------
    # 公開介面
    # ------------------------------------------------------------------

    def inject(self, text: str) -> None:
        """將文字注入至目前焦點視窗的游標位置。

        完整注入流程：
          1. 備份剪貼簿
          2. 寫入待注入文字至剪貼簿
          3. 透過 FocusManager 還原焦點（若有）
          4. 等待 50ms 讓焦點穩定
          5. 模擬 Ctrl/Cmd+V 貼上
          6. 等待 clipboard_restore_delay_ms（預設 150ms）
          7. 還原原始剪貼簿內容

        Args:
            text: 要注入的文字字串。
        """
        import pyperclip

        logger.debug("開始注入文字（長度 %d）", len(text))

        # 1. 備份剪貼簿
        self._backup_clipboard()

        # 2. 寫入待注入文字
        try:
            pyperclip.copy(text)
        except Exception as exc:  # noqa: BLE001
            logger.error("寫入剪貼簿失敗，注入中止：%s", exc)
            return

        # 3. 還原焦點至目標視窗
        if self._focus_manager is not None:
            self._focus_manager.restore_focus()

        # 4. 等待焦點穩定（50ms）
        time.sleep(0.050)

        # 5. 模擬 Ctrl/Cmd+V 貼上
        self._simulate_paste()

        # 6. 等待目標應用程式消費剪貼簿
        delay_ms: int = getattr(self._config.general, "clipboard_restore_delay_ms", 150)
        time.sleep(delay_ms / 1000)

        # 7. 還原原始剪貼簿內容
        self._restore_clipboard()

        logger.debug("文字注入完成")
