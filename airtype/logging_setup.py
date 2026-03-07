"""Airtype 結構化日誌初始化模組。

格式：[時間] [等級] [Logger 名稱] 訊息
等級由設定檔 general.log_level 控制（DEBUG / INFO / WARNING / ERROR）。

安全性：SanitizingFilter 遮蔽可能包含使用者辨識文字的日誌參數（PRD §9）。
"""

import logging
import sys
from typing import Any


_LOG_FORMAT = "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s"
_DATE_FORMAT = "%Y-%m-%dT%H:%M:%S"

_initialized = False

# 需遮蔽的最短字串長度（短於此值的字串幾乎不可能是使用者語音文字）
_SANITIZE_MIN_LEN = 15

# 不遮蔽以下開頭的字串（路徑、URL、錯誤前綴）
_PATH_PREFIXES = ("/", "\\", "~", ".", "http", "C:", "D:", "E:", "F:")


class SanitizingFilter(logging.Filter):
    """日誌清理 Filter：遮蔽可能包含使用者辨識文字的字串參數。

    原則：
    - 只遮蔽傳入 logging 呼叫的「參數」（record.args），不遮蔽格式字串本身。
    - 字串長度 >= 15 且含空格或 CJK 字元，視為可能的使用者文字。
    - 路徑、URL 等不遮蔽。
    """

    _REDACTED = "[REDACTED]"

    def filter(self, record: logging.LogRecord) -> bool:
        if record.args:
            if isinstance(record.args, tuple):
                record.args = tuple(self._maybe_redact(a) for a in record.args)
            elif isinstance(record.args, dict):
                record.args = {k: self._maybe_redact(v) for k, v in record.args.items()}
        return True

    def _maybe_redact(self, value: Any) -> Any:
        if not isinstance(value, str):
            return value
        if len(value) < _SANITIZE_MIN_LEN:
            return value
        # 排除路徑與 URL 類字串
        if value.startswith(_PATH_PREFIXES) or "://" in value:
            return value
        # 含空格（英文自然語言）或 CJK 字元（中文辨識文字）→ 遮蔽
        has_space = " " in value
        has_cjk = any("\u4e00" <= c <= "\u9fff" for c in value)
        if has_space or has_cjk:
            return self._REDACTED
        return value


def setup_logging(log_level: str = "INFO") -> None:
    """初始化 root logger。

    若已初始化則更新等級，不重複新增 handler。
    首次初始化時自動加入 SanitizingFilter 遮蔽敏感使用者文字。

    Args:
        log_level: 'DEBUG' | 'INFO' | 'WARNING' | 'ERROR'（不區分大小寫）
    """
    global _initialized  # noqa: PLW0603

    numeric_level = getattr(logging, log_level.upper(), logging.INFO)
    root = logging.getLogger()

    if not _initialized:
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(logging.Formatter(_LOG_FORMAT, datefmt=_DATE_FORMAT))
        handler.addFilter(SanitizingFilter())
        root.addHandler(handler)
        _initialized = True

    root.setLevel(numeric_level)
