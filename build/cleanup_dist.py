#!/usr/bin/env python3
"""PyInstaller 產出裁剪腳本 — 移除 PySide6 未使用的 Qt 二進位。

用法：
    python build/cleanup_dist.py dist/airtype

PyInstaller 會複製整個 PySide6 套件的 .dll/.so/.dylib，
但 Airtype 只使用 QtCore、QtGui、QtWidgets。
此腳本刪除其他 Qt 模組的二進位，可節省 50-150MB。
"""
from __future__ import annotations

import glob
import os
import shutil
import sys

# ── Airtype 實際使用的 Qt 模組（保留清單）──────────────────────────────────
# 除了直接使用的 3 個模組外，也保留平台必要的模組
KEEP_QT_MODULES = frozenset({
    # 直接使用
    "Qt6Core",
    "Qt6Gui",
    "Qt6Widgets",
    # 平台必要（QtWidgets 需要）
    "Qt6DBus",          # Linux 桌面整合
    # ICU 國際化庫（Qt 需要）
    "icu",
})

# ── 確定要刪除的 Qt 模組前綴 ──────────────────────────────────────────────
REMOVE_PREFIXES = (
    "Qt6WebEngine",
    "Qt6Quick",
    "Qt6Qml",
    "Qt6Multimedia",
    "Qt6Network",
    "Qt6Svg",
    "Qt63D",
    "Qt6Bluetooth",
    "Qt6Nfc",
    "Qt6Sensors",
    "Qt6SerialPort",
    "Qt6Positioning",
    "Qt6PrintSupport",
    "Qt6Pdf",
    "Qt6Designer",
    "Qt6Help",
    "Qt6OpenGL",
    "Qt6Test",
    "Qt6Xml",
    "Qt6RemoteObjects",
    "Qt6HttpServer",
    "Qt6DataVisualization",
    "Qt6Charts",
    "Qt6StateMachine",
    "Qt6Scxml",
    "Qt6SpatialAudio",
    "Qt6Concurrent",
    "Qt6ShaderTools",
    "Qt6VirtualKeyboard",
    "Qt6LanguageServer",
    "Qt6JsonRpc",
)

# ── 確定要刪除的 PySide6 子目錄 ──────────────────────────────────────────
REMOVE_DIRS = (
    "QtWebEngine",
    "QtWebEngineCore",
    "QtWebEngineWidgets",
    "QtWebChannel",
    "QtNetwork",
    "QtSvg",
    "QtSvgWidgets",
    "QtMultimedia",
    "QtMultimediaWidgets",
    "Qt3DCore",
    "Qt3DRender",
    "Qt3DInput",
    "Qt3DExtras",
    "QtQuick",
    "QtQuickWidgets",
    "QtQml",
    "QtDesigner",
    "QtHelp",
    "QtOpenGL",
    "QtOpenGLWidgets",
    "QtTest",
    "QtXml",
    "QtRemoteObjects",
    "QtHttpServer",
    "QtDataVisualization",
    "QtCharts",
    "QtStateMachine",
    "QtScxml",
    "QtSpatialAudio",
    "QtPdf",
    "QtPdfWidgets",
    "QtBluetooth",
    "QtNfc",
    "QtSensors",
    "QtSerialPort",
    "QtPositioning",
    "QtPrintSupport",
    "QtConcurrent",
)


def _sizeof_fmt(num: float) -> str:
    """格式化檔案大小。"""
    for unit in ("B", "KB", "MB", "GB"):
        if abs(num) < 1024:
            return f"{num:.1f} {unit}"
        num /= 1024
    return f"{num:.1f} TB"


def _remove_path(path: str, dry_run: bool = False) -> int:
    """刪除檔案或目錄，回傳釋放的位元組數。"""
    if not os.path.exists(path):
        return 0
    if os.path.isdir(path):
        size = sum(
            os.path.getsize(os.path.join(dp, f))
            for dp, _, fns in os.walk(path)
            for f in fns
        )
        if not dry_run:
            shutil.rmtree(path, ignore_errors=True)
    else:
        size = os.path.getsize(path)
        if not dry_run:
            os.remove(path)
    return size


def cleanup(dist_dir: str, dry_run: bool = False) -> None:
    """裁剪 dist 目錄中未使用的 Qt 二進位。"""
    if not os.path.isdir(dist_dir):
        print(f"[cleanup] 目錄不存在：{dist_dir}")
        sys.exit(1)

    total_saved = 0
    removed_count = 0

    # 1. 刪除 Qt 動態庫（.dll / .so / .dylib）
    for pattern in ("*.dll", "*.so*", "*.dylib"):
        for filepath in glob.glob(os.path.join(dist_dir, "**", pattern), recursive=True):
            basename = os.path.basename(filepath)
            if any(basename.startswith(prefix) for prefix in REMOVE_PREFIXES):
                size = _remove_path(filepath, dry_run)
                total_saved += size
                removed_count += 1
                if dry_run:
                    print(f"  [DRY-RUN] 將刪除：{filepath} ({_sizeof_fmt(size)})")

    # 2. 刪除 PySide6 子目錄
    for root, dirs, _ in os.walk(dist_dir):
        if os.path.basename(root) == "PySide6":
            for dirname in REMOVE_DIRS:
                dirpath = os.path.join(root, dirname)
                if os.path.isdir(dirpath):
                    size = _remove_path(dirpath, dry_run)
                    total_saved += size
                    removed_count += 1
                    if dry_run:
                        print(f"  [DRY-RUN] 將刪除：{dirpath} ({_sizeof_fmt(size)})")

    # 3. 刪除 PySide6/Qt/translations（翻譯檔，Airtype 有自己的 i18n）
    for root, dirs, _ in os.walk(dist_dir):
        trans_dir = os.path.join(root, "PySide6", "Qt", "translations")
        if os.path.isdir(trans_dir):
            size = _remove_path(trans_dir, dry_run)
            total_saved += size
            removed_count += 1

    action = "將刪除" if dry_run else "已刪除"
    print(f"[cleanup] {action} {removed_count} 個項目，釋放 {_sizeof_fmt(total_saved)}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(f"用法：python {sys.argv[0]} <dist_dir> [--dry-run]")
        sys.exit(1)

    dist_path = sys.argv[1]
    is_dry_run = "--dry-run" in sys.argv
    cleanup(dist_path, dry_run=is_dry_run)
