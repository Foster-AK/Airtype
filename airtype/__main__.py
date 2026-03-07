"""Airtype Python package 入口點。

執行方式：
    python -m airtype

啟動流程：
    1. 載入設定（~/.airtype/config.json）
    2. 初始化日誌與 i18n
    3. 建立 QApplication
    4. 依序初始化所有核心元件（含容錯降級）
    5. 建立 UI 元件並串接 Signal
    6. 啟動 Qt 事件迴圈
    7. 關閉時按正確順序清理資源
"""

import importlib
import logging
import sys

from airtype.config import AirtypeConfig
from airtype.logging_setup import setup_logging

# manifest inference_engine → 引擎模組映射
_ENGINE_MODULE_MAP: dict[str, str] = {
    "qwen3-openvino": "airtype.core.asr_qwen_openvino",
    "qwen3-pytorch-cuda": "airtype.core.asr_qwen_pytorch",
    "chatllm-vulkan": "airtype.core.asr_qwen_vulkan",
    "sherpa-onnx": "airtype.core.asr_sherpa",
    "faster-whisper": "airtype.core.asr_breeze",
    "breeze-asr-25": "airtype.core.asr_breeze",
}

# 全部引擎模組（後備，manifest 讀取失敗時使用）
_ALL_ASR_ENGINE_MODULES = list(_ENGINE_MODULE_MAP.values())


def _resolve_needed_engine_modules(asr_model: str) -> list[str]:
    """依 manifest 中已下載或設定的模型，決定需要載入的引擎模組。

    只載入設定中 asr_model 對應的引擎模組 + 已下載模型對應的模組。
    manifest 讀取失敗時回退到全部模組。
    """
    import json

    from airtype.utils.paths import get_manifest_path

    manifest_path = get_manifest_path()
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return list(_ALL_ASR_ENGINE_MODULES)

    needed: set[str] = set()
    models_dir = Path.home() / ".airtype" / "models"

    for entry in data.get("models", []):
        if entry.get("category") != "asr":
            continue
        engine_key = entry.get("inference_engine", "")
        module_path = _ENGINE_MODULE_MAP.get(engine_key)
        if not module_path:
            continue

        # 載入條件：是設定中的模型，或已下載
        if entry.get("id") == asr_model:
            needed.add(module_path)
            continue
        filename = entry.get("filename", "")
        if filename:
            dest = models_dir / filename
            dir_dest = models_dir / filename[:-4] if filename.endswith(".zip") else None
            if dest.exists() or (dir_dest and dir_dest.is_dir()):
                needed.add(module_path)

    return list(needed) if needed else list(_ALL_ASR_ENGINE_MODULES)


def main() -> None:
    setup_logging("INFO")

    cfg = AirtypeConfig.load()
    setup_logging(cfg.general.log_level)

    logger = logging.getLogger(__name__)
    logger.info("Airtype v%s 啟動中…", cfg.version)

    # ── 建立 QApplication ──────────────────────────────────────────────
    try:
        from PySide6.QtWidgets import QApplication
        from PySide6.QtCore import QTimer
    except ImportError:
        logger.error("PySide6 未安裝，無法啟動 UI")
        sys.exit(1)

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)  # 關閉視窗時隱藏到系統匣

    # ── 4.2 I18n 語言初始化 ────────────────────────────────────────────
    from airtype.utils.i18n import set_language
    set_language(cfg.general.language)

    # ── 4.3 AudioCaptureService（容錯：無麥克風 → None） ───────────────
    from airtype.core.audio_capture import AudioCaptureService
    audio_capture = AudioCaptureService(cfg)
    try:
        audio_capture.start()
        logger.info("AudioCaptureService 已啟動")
    except Exception as exc:
        logger.error("AudioCaptureService 啟動失敗（無麥克風？）：%s — 音訊擷取停用", exc)
        audio_capture = None

    # ── 4.4 VadEngine ──────────────────────────────────────────────────
    from airtype.core.vad import VadEngine
    vad_engine = VadEngine(cfg)

    # ── 4.5 ASR 引擎動態登錄（Dynamic Registration） ──────────────────
    from airtype.core.asr_engine import ASREngineRegistry
    asr_registry = ASREngineRegistry()

    # 只載入 manifest 中存在的引擎模組，避免不必要的 import
    needed_modules = _resolve_needed_engine_modules(cfg.voice.asr_model)
    for module_path in needed_modules:
        try:
            mod = importlib.import_module(module_path)
            mod.register(asr_registry)
            logger.debug("ASR 引擎模組已載入：%s", module_path)
        except Exception as exc:
            logger.debug("ASR 引擎模組略過：%s（%s）", module_path, exc)

    try:
        asr_registry.load_default_engine(cfg)
        logger.info("預設 ASR 引擎已載入")
    except Exception as exc:
        logger.warning("無法載入預設 ASR 引擎（未下載模型？）：%s", exc)

    asr_engine = asr_registry.active_engine

    # ── 4.6 FocusManager 與 TextInjector ──────────────────────────────
    from airtype.core.hotkey import FocusManager
    from airtype.core.text_injector import TextInjector
    focus_manager = FocusManager()
    text_injector = TextInjector(cfg, focus_manager)

    # ── 4.7 DictionaryEngine（容錯：Optional） ─────────────────────────
    from airtype.core.dictionary import DictionaryEngine
    dictionary_engine = DictionaryEngine(cfg)
    try:
        dictionary_engine.load_sets()
        logger.info("DictionaryEngine 已載入")
    except Exception as exc:
        logger.warning("DictionaryEngine 載入失敗：%s — 辭典功能停用", exc)
        dictionary_engine = None

    # ── 4.8 PolishEngine（無條件初始化，運行時由 config.llm.enabled 控制）──
    polish_engine = None
    try:
        from airtype.core.llm_polish import PolishEngine
        polish_engine = PolishEngine(cfg)
        logger.info("PolishEngine 已初始化")
    except Exception as exc:
        logger.warning("PolishEngine 初始化失敗：%s — LLM 潤飾停用", exc)

    # ── 4.9 RecognitionPipeline（依 recognition_mode 選擇批次或串流） ──
    pipeline = None
    if audio_capture is not None and asr_engine is not None:
        if cfg.voice.recognition_mode == "stream":
            from airtype.core.pipeline import StreamingRecognitionPipeline
            # 判斷是否需要偽串流（引擎 recognize_stream 回傳空結果則用偽串流）
            use_pseudo = True  # 預設偽串流，目前引擎皆不支援真實串流
            pipeline = StreamingRecognitionPipeline(
                audio_capture=audio_capture,
                vad_engine=vad_engine,
                asr_engine=asr_engine,
                text_injector=text_injector,
                use_pseudo_streaming=use_pseudo,
                dictionary_engine=dictionary_engine,
                on_asr_engine_used=asr_registry.notify_used,
                asr_language=cfg.voice.asr_language,
            )
            logger.info("StreamingRecognitionPipeline 已建立（偽串流=%s）", use_pseudo)
        else:
            from airtype.core.pipeline import BatchRecognitionPipeline
            pipeline = BatchRecognitionPipeline(
                audio_capture=audio_capture,
                vad_engine=vad_engine,
                asr_engine=asr_engine,
                text_injector=text_injector,
                dictionary_engine=dictionary_engine,
                on_asr_engine_used=asr_registry.notify_used,
                asr_language=cfg.voice.asr_language,
            )
            logger.info("BatchRecognitionPipeline 已建立")
    else:
        logger.warning("RecognitionPipeline 未建立（audio_capture=%s, asr_engine=%s）",
                       audio_capture, asr_engine)

    # ── 4.10 CoreController（含所有元件） ──────────────────────────────
    from airtype.core.controller import CoreController, init_controller
    from airtype.core.hotkey import HotkeyManager

    hotkey_manager = HotkeyManager(cfg.shortcuts)
    controller = CoreController(
        config=cfg,
        hotkey_manager=hotkey_manager,
        pipeline=pipeline,
        text_injector=text_injector,
        polish_engine=polish_engine,
        dictionary_engine=dictionary_engine,
        focus_manager=focus_manager,
    )
    init_controller(controller)

    # ── 建立 UI 元件 ───────────────────────────────────────────────────
    from airtype.ui.overlay import CapsuleOverlay
    from airtype.ui.tray_icon import SystemTrayIcon
    from airtype.ui.settings_window import SettingsWindow

    overlay = CapsuleOverlay(config=cfg)
    overlay.connect_controller(controller)
    overlay.show_animated()

    settings_window = SettingsWindow(config=cfg, dictionary_engine=dictionary_engine)
    settings_window.connect_overlay(overlay)

    # 快捷鍵設定變更 → 重新載入 HotkeyManager
    if hasattr(settings_window, "_page_shortcuts") and hasattr(settings_window._page_shortcuts, "shortcuts_changed"):
        settings_window._page_shortcuts.shortcuts_changed.connect(hotkey_manager.reload)

    tray = SystemTrayIcon(config=cfg)
    tray.connect_controller(controller)
    tray.open_settings_requested.connect(settings_window.show)
    tray.toggle_voice_requested.connect(hotkey_manager._handle_toggle)
    tray.show()

    # ── 5.1 RMS 輪詢（33ms QTimer） ────────────────────────────────────
    rms_timer = None
    if audio_capture is not None:
        rms_timer = QTimer()
        rms_timer.setInterval(33)
        rms_timer.timeout.connect(lambda: overlay.update_rms(audio_capture.rms))
        rms_timer.start()

    # ── 5.2 裝置選擇器 Signal 連接 ─────────────────────────────────────
    if audio_capture is not None and hasattr(overlay, "_device_selector"):
        overlay._device_selector.device_changed.connect(audio_capture.set_device)

    # ── 5.3 Settings Window 整合 ───────────────────────────────────────
    # 注意：connect_rms_feed 期望 Qt Signal，但 RMS 採用 QTimer 輪詢架構，
    # 不適用 Signal 連接。SettingsWindow 透過 dictionary_engine 參數整合辭典功能。

    # ── 啟動控制器 ─────────────────────────────────────────────────────
    controller.startup()
    logger.info("Airtype 啟動完成")

    # ── Qt 事件迴圈 ────────────────────────────────────────────────────
    exit_code = app.exec()

    # ── 6.1 資源清理（反向順序） ───────────────────────────────────────
    if rms_timer is not None:
        rms_timer.stop()
    if audio_capture is not None:
        try:
            audio_capture.stop()
        except Exception as exc:
            logger.debug("停止 AudioCaptureService 時發生例外：%s", exc)
    try:
        asr_registry.shutdown()
    except Exception as exc:
        logger.debug("停止 ASREngineRegistry 時發生例外：%s", exc)
    controller.shutdown()

    logger.info("Airtype 已關閉")
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
