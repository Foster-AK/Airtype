# -*- mode: python ; coding: utf-8 -*-
"""Airtype PyInstaller spec — onedir 模式，只打包核心功能。

打包前請使用乾淨 venv，只安裝核心依賴：
    pip install -e .
    pip install tokenizers>=0.15 pyinstaller>=6.0

不要安裝 [full] extras，否則 torch/transformers 等巨型套件會被打包。
"""
from PyInstaller.utils.hooks import collect_data_files

block_cipher = None

# 收集 tokenizers 的 Rust 動態庫（BPE tokenizer 需要）
try:
    tokenizers_datas = collect_data_files("tokenizers")
except Exception:
    tokenizers_datas = []

a = Analysis(
    ["airtype/__main__.py"],
    pathex=[],
    binaries=[],
    datas=[
        ("models/manifest.json", "models"),
        ("models/precomputed", "models/precomputed"),
        ("locales", "locales"),
        ("resources/icons", "resources/icons"),
    ]
    + tokenizers_datas,
    hiddenimports=[
        # ── 核心推理 ──
        "onnxruntime",
        "tokenizers",
        # ── Qt 模組（只用到這 3 個）──
        "PySide6.QtCore",
        "PySide6.QtGui",
        "PySide6.QtWidgets",
        # ── 標準庫中被動態使用的模組 ──
        "json",
        "logging",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # ══════════════════════════════════════════════════════════════════
        # 巨型 ML 套件（程式碼中為 lazy import，打包不需要）
        # ══════════════════════════════════════════════════════════════════
        "torch",
        "torchvision",
        "torchaudio",
        "transformers",
        "faster_whisper",
        "ctranslate2",
        "sherpa_onnx",
        "llama_cpp",
        "llama_cpp_python",
        "openvino",
        "tensorflow",
        "keras",
        "scipy",
        "pandas",
        "matplotlib",
        "sympy",
        "IPython",
        "notebook",
        "jupyterlab",
        # ══════════════════════════════════════════════════════════════════
        # PySide6 未使用模組（Airtype 只用 QtCore / QtGui / QtWidgets）
        # ══════════════════════════════════════════════════════════════════
        "PySide6.QtWebEngine",
        "PySide6.QtWebEngineCore",
        "PySide6.QtWebEngineWidgets",
        "PySide6.QtWebChannel",
        "PySide6.QtNetwork",
        "PySide6.QtSvg",
        "PySide6.QtSvgWidgets",
        "PySide6.QtMultimedia",
        "PySide6.QtMultimediaWidgets",
        "PySide6.Qt3DCore",
        "PySide6.Qt3DRender",
        "PySide6.Qt3DInput",
        "PySide6.Qt3DExtras",
        "PySide6.QtBluetooth",
        "PySide6.QtNfc",
        "PySide6.QtSensors",
        "PySide6.QtSerialPort",
        "PySide6.QtPositioning",
        "PySide6.QtPrintSupport",
        "PySide6.QtPdf",
        "PySide6.QtPdfWidgets",
        "PySide6.QtQuick",
        "PySide6.QtQuickWidgets",
        "PySide6.QtQml",
        "PySide6.QtDesigner",
        "PySide6.QtHelp",
        "PySide6.QtOpenGL",
        "PySide6.QtOpenGLWidgets",
        "PySide6.QtTest",
        "PySide6.QtXml",
        "PySide6.QtRemoteObjects",
        "PySide6.QtHttpServer",
        "PySide6.QtDataVisualization",
        "PySide6.QtCharts",
        "PySide6.QtStateMachine",
        "PySide6.QtScxml",
        "PySide6.QtSpatialAudio",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

import sys as _sys

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,  # onedir 模式
    name="airtype",
    debug=False,
    bootloader_ignore_signals=False,
    strip=not _sys.platform.startswith("win"),  # strip 僅 Unix 有效
    upx=True,
    console=False,
    icon="resources/icons/airtype_icon_486.ico",
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=not _sys.platform.startswith("win"),  # strip 僅 Unix 有效
    upx=True,
    upx_exclude=[],
    name="airtype",
)
