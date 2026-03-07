"""tests/test_logging_setup.py — RotatingFileHandler 單元測試。

驗證：
- log file creation（首次啟動建立目錄與檔案）
- log file rotation（超過 5MB 時輪替）
- log file available in packaged application（無 console 時檔案仍可寫入）
- log file handler failure（磁碟權限錯誤時不中斷）
"""

import logging
import sys
from pathlib import Path
from unittest import mock

import pytest


@pytest.fixture(autouse=True)
def _reset_logging_state():
    """每個測試前重置 logging_setup 的全域狀態。"""
    import airtype.logging_setup as ls

    ls._initialized = False
    # 移除所有 root logger handlers（避免測試間交互污染）
    root = logging.getLogger()
    for h in root.handlers[:]:
        root.removeHandler(h)
        h.close()
    yield
    # 清理
    ls._initialized = False
    for h in root.handlers[:]:
        root.removeHandler(h)
        h.close()


class TestDefaultLogLevel:
    """Scenario: Default log level — 預設 INFO。"""

    def test_default_level_is_info(self, tmp_path: Path):
        """未指定 log_level 時，console handler 等級應為 INFO。"""
        from airtype.logging_setup import setup_logging

        log_dir = tmp_path / "logs"

        with mock.patch("airtype.logging_setup._LOG_DIR", log_dir):
            setup_logging()

        root = logging.getLogger()
        console = self._find_console_handler(root)
        assert console is not None, "應有 console handler"
        assert console.level == logging.INFO

    @staticmethod
    def _find_console_handler(root: logging.Logger) -> logging.Handler | None:
        for h in root.handlers:
            if (
                type(h) is logging.StreamHandler
                and not hasattr(h, "baseFilename")
            ):
                return h
        return None


class TestCustomLogLevel:
    """Scenario: Custom log level — 自訂等級套用於 console handler。"""

    def test_custom_level_applied_to_console_handler(self, tmp_path: Path):
        """console handler 等級應跟隨 log_level 參數。"""
        from airtype.logging_setup import setup_logging

        log_dir = tmp_path / "logs"

        with mock.patch("airtype.logging_setup._LOG_DIR", log_dir):
            setup_logging("DEBUG")

        root = logging.getLogger()
        console = self._find_console_handler(root)
        assert console is not None
        assert console.level == logging.DEBUG

    @staticmethod
    def _find_console_handler(root: logging.Logger) -> logging.Handler | None:
        for h in root.handlers:
            if (
                type(h) is logging.StreamHandler
                and not hasattr(h, "baseFilename")
            ):
                return h
        return None

    def test_file_handler_stays_debug_regardless(self, tmp_path: Path):
        """即使 console 設為 WARNING，file handler 仍為 DEBUG。"""
        from airtype.logging_setup import setup_logging

        log_dir = tmp_path / "logs"

        with mock.patch("airtype.logging_setup._LOG_DIR", log_dir):
            setup_logging("WARNING")

        root = logging.getLogger()
        file_handlers = [
            h for h in root.handlers if hasattr(h, "baseFilename")
        ]
        assert file_handlers[0].level == logging.DEBUG


class TestLogFileCreation:
    """Scenario: Log file creation — 首次啟動建立目錄與檔案。"""

    def test_creates_log_dir_and_file(self, tmp_path: Path):
        """setup_logging 應建立 logs 目錄並寫入 airtype.log。"""
        from airtype.logging_setup import setup_logging

        log_dir = tmp_path / "logs"
        log_file = log_dir / "airtype.log"

        with mock.patch("airtype.logging_setup._LOG_DIR", log_dir):
            setup_logging("INFO")

        assert log_dir.is_dir(), "logs 目錄應被建立"
        # 寫入一條訊息
        logging.getLogger("test").info("hello")
        assert log_file.exists(), "airtype.log 應存在"
        content = log_file.read_text(encoding="utf-8")
        assert "hello" in content

    def test_file_handler_uses_debug_level(self, tmp_path: Path):
        """檔案 handler 等級應固定為 DEBUG，不隨 log_level 變化。"""
        from airtype.logging_setup import setup_logging

        log_dir = tmp_path / "logs"
        log_file = log_dir / "airtype.log"

        with mock.patch("airtype.logging_setup._LOG_DIR", log_dir):
            setup_logging("WARNING")

        # console handler 等級為 WARNING，但檔案 handler 應為 DEBUG
        logging.getLogger("test").debug("debug-msg")
        # root level 需 <= DEBUG 才能讓 debug-msg 通過
        # 但 setup_logging("WARNING") 設定 root 為 WARNING…
        # 因此 root.setLevel 不能阻擋 file handler 的 debug-msg
        # 設計決策：root level = min(console_level, DEBUG) = DEBUG
        content = log_file.read_text(encoding="utf-8")
        assert "debug-msg" in content, "檔案 handler 應記錄 DEBUG 等級訊息"

    def test_sanitizing_filter_applied_to_file_handler(self, tmp_path: Path):
        """檔案 handler 應套用 SanitizingFilter。"""
        from airtype.logging_setup import SanitizingFilter, setup_logging

        log_dir = tmp_path / "logs"

        with mock.patch("airtype.logging_setup._LOG_DIR", log_dir):
            setup_logging("DEBUG")

        root = logging.getLogger()
        file_handlers = [
            h
            for h in root.handlers
            if hasattr(h, "baseFilename")
        ]
        assert len(file_handlers) == 1
        filters = file_handlers[0].filters
        assert any(isinstance(f, SanitizingFilter) for f in filters)


class TestLogFileRotation:
    """Scenario: Log file rotation — 超過 5MB 時輪替。"""

    def test_rotation_at_5mb(self, tmp_path: Path):
        """超過 5MB 時應產生 .log.1 備份檔。"""
        from airtype.logging_setup import setup_logging

        log_dir = tmp_path / "logs"
        log_file = log_dir / "airtype.log"

        with mock.patch("airtype.logging_setup._LOG_DIR", log_dir):
            setup_logging("DEBUG")

        logger = logging.getLogger("rotation_test")
        # 每行約 100 bytes，寫入 ~6 MB → 應觸發至少一次輪替
        line = "X" * 90
        for _ in range(65_000):
            logger.debug(line)

        backup = log_dir / "airtype.log.1"
        assert backup.exists(), "超過 5MB 應產生 airtype.log.1 備份"

    def test_max_3_backups(self, tmp_path: Path):
        """最多保留 3 份備份（.log.1, .log.2, .log.3）。"""
        from airtype.logging_setup import setup_logging

        log_dir = tmp_path / "logs"

        with mock.patch("airtype.logging_setup._LOG_DIR", log_dir):
            setup_logging("DEBUG")

        logger = logging.getLogger("rotation_max")
        line = "Y" * 90
        # 寫入約 25 MB → 應產生 3 份備份但不超過
        for _ in range(270_000):
            logger.debug(line)

        assert (log_dir / "airtype.log.1").exists()
        assert (log_dir / "airtype.log.2").exists()
        assert (log_dir / "airtype.log.3").exists()
        assert not (log_dir / "airtype.log.4").exists(), "不應超過 3 份備份"


class TestLogFileInPackagedApp:
    """Scenario: Log file available in packaged application。"""

    def test_file_logging_works_without_console(self, tmp_path: Path):
        """即使 sys.stderr 不可用，檔案日誌仍可寫入。"""
        from airtype.logging_setup import setup_logging

        log_dir = tmp_path / "logs"
        log_file = log_dir / "airtype.log"

        with (
            mock.patch("airtype.logging_setup._LOG_DIR", log_dir),
            mock.patch("sys.stderr", None),
        ):
            setup_logging("INFO")

        logging.getLogger("packaged").info("packaged-msg")
        content = log_file.read_text(encoding="utf-8")
        assert "packaged-msg" in content


class TestLogFileHandlerFailure:
    """Scenario: Log file handler failure — 磁碟權限錯誤時不中斷。"""

    def test_continues_without_file_handler_on_permission_error(
        self, tmp_path: Path, capsys
    ):
        """建立 file handler 失敗時應印出 stderr 警告，但不中斷啟動。"""
        from airtype.logging_setup import setup_logging

        # 模擬無法建立目錄
        bad_dir = tmp_path / "no_access" / "logs"

        with (
            mock.patch("airtype.logging_setup._LOG_DIR", bad_dir),
            mock.patch.object(Path, "mkdir", side_effect=PermissionError("denied")),
        ):
            # 不應拋出例外
            setup_logging("INFO")

        # 應至少有 console handler（可能無 file handler）
        root = logging.getLogger()
        assert len(root.handlers) >= 1

        # stderr 應有警告訊息
        captured = capsys.readouterr()
        assert "無法建立日誌檔案" in captured.err
