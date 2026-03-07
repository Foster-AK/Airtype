"""PyInstaller 相容的路徑解析工具。"""

from __future__ import annotations

import sys
from pathlib import Path


def get_manifest_path() -> Path:
    """取得 models/manifest.json 路徑，支援 PyInstaller 打包環境。"""
    if getattr(sys, "frozen", False):
        # PyInstaller 打包：資料檔在 sys._MEIPASS（onedir）或臨時目錄（onefile）
        return Path(sys._MEIPASS) / "models" / "manifest.json"  # type: ignore[attr-defined]
    # 開發環境：專案根目錄
    return Path(__file__).resolve().parent.parent.parent / "models" / "manifest.json"
