"""Single Instance Enforcement 單元測試。

測試 _acquire_instance_lock() 的四個場景：
1. 首次啟動成功取得鎖
2. 第二個實例被拒絕
3. 正常關閉後鎖釋放
4. crash 後鎖自動釋放
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from airtype.__main__ import _acquire_instance_lock


def test_first_instance_acquires_lock():
    """首次啟動成功取得鎖，回傳非 None 檔案物件。"""
    with tempfile.TemporaryDirectory() as tmp:
        lock_path = Path(tmp) / "airtype.lock"
        result = _acquire_instance_lock(lock_path=lock_path)
        try:
            assert result is not None
            assert lock_path.exists()
        finally:
            if result is not None:
                result.close()


def test_second_instance_rejected():
    """第二個實例嘗試取得鎖時回傳 None。"""
    with tempfile.TemporaryDirectory() as tmp:
        lock_path = Path(tmp) / "airtype.lock"
        first = _acquire_instance_lock(lock_path=lock_path)
        try:
            assert first is not None
            second = _acquire_instance_lock(lock_path=lock_path)
            assert second is None
        finally:
            if first is not None:
                first.close()


def test_lock_released_after_close():
    """正常關閉（close）後鎖釋放，新實例可取得鎖。"""
    with tempfile.TemporaryDirectory() as tmp:
        lock_path = Path(tmp) / "airtype.lock"
        first = _acquire_instance_lock(lock_path=lock_path)
        assert first is not None
        first.close()

        second = _acquire_instance_lock(lock_path=lock_path)
        try:
            assert second is not None
        finally:
            if second is not None:
                second.close()


@pytest.mark.skipif(
    sys.platform == "win32",
    reason="Windows msvcrt.locking 的鎖釋放時機依賴 GC 行為，"
           "在 CPython 以外或 Windows 上不保證可靠性；改用 test_lock_released_after_close 驗證主要場景",
)
def test_lock_released_after_crash():
    """模擬 crash（del file object）後鎖自動釋放。

    POSIX flock 在 FD 關閉時立即釋放；CPython 的參考計數 GC 在 del 後立即回收。
    此測試在 Linux/macOS 下穩定，Windows 跳過（見 skipif）。
    """
    import gc

    with tempfile.TemporaryDirectory() as tmp:
        lock_path = Path(tmp) / "airtype.lock"
        first = _acquire_instance_lock(lock_path=lock_path)
        assert first is not None

        # 模擬 crash：刪除參考並強制 GC
        del first
        gc.collect()

        second = _acquire_instance_lock(lock_path=lock_path)
        try:
            assert second is not None
        finally:
            if second is not None:
                second.close()


def test_lock_directory_auto_creation():
    """鎖檔案目錄不存在時自動建立。"""
    with tempfile.TemporaryDirectory() as tmp:
        nested = Path(tmp) / "subdir" / "airtype.lock"
        result = _acquire_instance_lock(lock_path=nested)
        try:
            assert result is not None
            assert nested.parent.exists()
        finally:
            if result is not None:
                result.close()
