"""懶加載與閒置逾時自動卸載機制。

``IdleUnloader`` 追蹤 ASR / LLM 引擎的最後使用時間，
並在閒置逾時後（預設 5 分鐘）自動呼叫卸載函式以釋放 RAM。

符合 specs/performance-optimization/spec.md：
    - Requirement: Lazy Loading and On-Demand Model Management
    - Scenario: Unload Model After Idle Timeout

使用方式::

    from airtype.utils.idle_unloader import IdleUnloader

    def do_unload() -> None:
        engine.unload()

    unloader = IdleUnloader(do_unload, timeout_sec=300)
    unloader.start()

    # 每次使用引擎時呼叫：
    unloader.mark_used()

    # 應用程式關閉時：
    unloader.stop()
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Callable, Optional

logger = logging.getLogger(__name__)

# 預設閒置逾時（秒）
DEFAULT_IDLE_TIMEOUT_SEC: float = 5.0 * 60  # 5 分鐘

# 預設背景檢查間隔（秒）
DEFAULT_CHECK_INTERVAL_SEC: float = 30.0


class IdleUnloader:
    """閒置逾時後自動卸載引擎的監控器。

    在 daemon 背景執行緒中以固定間隔檢查閒置時間，
    一旦超過設定的逾時閾值即呼叫 ``unload_fn``。

    Args:
        unload_fn:          無參數 callable，呼叫後執行卸載邏輯。
        timeout_sec:        閒置逾時秒數（預設 300 秒 = 5 分鐘）。
        check_interval_sec: 背景監控執行緒檢查間隔（預設 30 秒）。
    """

    def __init__(
        self,
        unload_fn: Callable[[], None],
        timeout_sec: float = DEFAULT_IDLE_TIMEOUT_SEC,
        check_interval_sec: float = DEFAULT_CHECK_INTERVAL_SEC,
    ) -> None:
        self._unload_fn = unload_fn
        self._timeout_sec = timeout_sec
        self._check_interval_sec = check_interval_sec

        self._lock = threading.Lock()
        self._last_used: float = time.monotonic()
        self._loaded: bool = False

        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

    # ------------------------------------------------------------------
    # 公開介面
    # ------------------------------------------------------------------

    def mark_used(self) -> None:
        """記錄最後使用時間，並將載入狀態設為 True。

        每次使用引擎（例如呼叫 ``recognize``）前後應呼叫此方法，
        以重設閒置計時器。
        """
        with self._lock:
            self._last_used = time.monotonic()
            self._loaded = True

    def mark_unloaded(self) -> None:
        """將載入狀態標記為 False（通常由外部呼叫 unload 後使用）。

        供外部程式碼主動通知 ``IdleUnloader`` 引擎已被卸載，
        避免監控執行緒重複呼叫 ``unload_fn``。
        """
        with self._lock:
            self._loaded = False

    def is_loaded(self) -> bool:
        """回傳引擎目前是否處於已載入狀態。

        Returns:
            True 表示引擎目前已載入且尚未被卸載。
        """
        with self._lock:
            return self._loaded

    def start(self) -> None:
        """啟動背景閒置監控執行緒（daemon）。

        若監控執行緒已在運行，則忽略此呼叫。
        """
        if self._thread is not None and self._thread.is_alive():
            logger.debug("IdleUnloader 已在運行，略過重複啟動")
            return

        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._monitor_loop,
            daemon=True,
            name="idle-unloader",
        )
        self._thread.start()
        logger.debug(
            "IdleUnloader 已啟動（逾時 %.0f 秒，檢查間隔 %.0f 秒）",
            self._timeout_sec,
            self._check_interval_sec,
        )

    def stop(self) -> None:
        """停止背景監控執行緒並等待其結束。

        此方法為阻塞呼叫，最多等待 ``check_interval_sec + 1`` 秒。
        """
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=self._check_interval_sec + 1.0)
            self._thread = None
        logger.debug("IdleUnloader 已停止")

    # ------------------------------------------------------------------
    # 內部監控迴圈
    # ------------------------------------------------------------------

    def _monitor_loop(self) -> None:
        """背景監控迴圈：定期檢查閒置時間並在逾時後卸載。"""
        while not self._stop_event.wait(self._check_interval_sec):
            with self._lock:
                loaded = self._loaded
                idle_sec = time.monotonic() - self._last_used

            if not loaded:
                continue

            if idle_sec >= self._timeout_sec:
                logger.info(
                    "IdleUnloader：閒置 %.0f 秒（逾時 %.0f 秒），執行卸載",
                    idle_sec,
                    self._timeout_sec,
                )
                try:
                    self._unload_fn()
                except Exception as exc:  # noqa: BLE001
                    logger.warning("IdleUnloader：卸載函式執行失敗：%s", exc)
                with self._lock:
                    self._loaded = False
