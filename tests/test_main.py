"""__main__ 入口點單元測試（TDD）。

涵蓋：
- 任務 1.1：main() 初始化流程中 overlay appearance signals are connected at startup
  （驗證 settings_window.connect_overlay(overlay) 確實被呼叫）
- 任務 3.1：HotkeyManager 被正確建立並傳入 CoreController
- 任務 3.2：tray.toggle_voice_requested Signal 觸發時呼叫 hotkey_manager._handle_toggle

使用 unittest.mock 全面替換 Qt 與外部依賴，可在無 GUI 環境執行。
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch


def _new_component_patches(mock_cfg, mock_app):
    """回傳新元件鏈所需的 patch 字典（供既有測試複用）。"""
    mock_audio = MagicMock()
    mock_audio.rms = 0.0
    mock_registry = MagicMock()
    mock_registry.get_active_engine.return_value = MagicMock()
    return {
        "audio": mock_audio,
        "vad": MagicMock(),
        "registry": mock_registry,
        "focus_mgr": MagicMock(),
        "injector": MagicMock(),
        "dict_engine": MagicMock(),
        "pipeline": MagicMock(),
    }


def test_connect_overlay_called_during_startup():
    """overlay appearance signals are connected at startup.

    main() 初始化流程中必須呼叫 settings_window.connect_overlay(overlay)，
    使 opacity_changed / theme_changed / position_changed 三個 Signal 即時生效。
    """
    mock_cfg = MagicMock()
    mock_app = MagicMock()
    mock_app.exec.return_value = 0
    mock_overlay = MagicMock()
    mock_sw = MagicMock()
    mock_tray = MagicMock()
    mock_ctrl = MagicMock()
    mock_hkm = MagicMock()
    new = _new_component_patches(mock_cfg, mock_app)

    with (
        patch("airtype.config.AirtypeConfig.load", return_value=mock_cfg),
        patch("airtype.__main__.setup_logging"),
        patch("airtype.utils.i18n.set_language"),
        patch("airtype.ui.overlay.CapsuleOverlay", return_value=mock_overlay),
        patch("airtype.ui.settings_window.SettingsWindow", return_value=mock_sw),
        patch("airtype.ui.tray_icon.SystemTrayIcon", return_value=mock_tray),
        patch("airtype.core.controller.CoreController", return_value=mock_ctrl),
        patch("airtype.core.controller.init_controller"),
        patch("airtype.core.hotkey.HotkeyManager", return_value=mock_hkm),
        patch("airtype.core.audio_capture.AudioCaptureService", return_value=new["audio"]),
        patch("airtype.core.vad.VadEngine", return_value=new["vad"]),
        patch("airtype.core.asr_engine.ASREngineRegistry", return_value=new["registry"]),
        patch("airtype.core.hotkey.FocusManager", return_value=new["focus_mgr"]),
        patch("airtype.core.text_injector.TextInjector", return_value=new["injector"]),
        patch("airtype.core.dictionary.DictionaryEngine", return_value=new["dict_engine"]),
        patch("airtype.core.pipeline.BatchRecognitionPipeline", return_value=new["pipeline"]),
        patch("airtype.__main__.importlib"),
        patch("PySide6.QtWidgets.QApplication", return_value=mock_app),
        patch("PySide6.QtCore.QTimer"),
        patch("sys.exit"),
    ):
        from airtype.__main__ import main
        main()

    # connect_overlay 必須以正確的 overlay 實例呼叫一次
    mock_sw.connect_overlay.assert_called_once_with(mock_overlay)


def test_hotkey_manager_created_and_passed_to_controller():
    """HotkeyManager 被正確建立並傳入 CoreController。

    main() 必須以 cfg.shortcuts 建立 HotkeyManager 實例，
    並將該實例作為 hotkey_manager= 參數傳入 CoreController()。
    """
    mock_cfg = MagicMock()
    mock_app = MagicMock()
    mock_app.exec.return_value = 0
    mock_overlay = MagicMock()
    mock_sw = MagicMock()
    mock_tray = MagicMock()
    mock_ctrl = MagicMock()
    mock_hkm = MagicMock()
    new = _new_component_patches(mock_cfg, mock_app)

    with (
        patch("airtype.config.AirtypeConfig.load", return_value=mock_cfg),
        patch("airtype.__main__.setup_logging"),
        patch("airtype.utils.i18n.set_language"),
        patch("airtype.ui.overlay.CapsuleOverlay", return_value=mock_overlay),
        patch("airtype.ui.settings_window.SettingsWindow", return_value=mock_sw),
        patch("airtype.ui.tray_icon.SystemTrayIcon", return_value=mock_tray),
        patch("airtype.core.controller.CoreController", return_value=mock_ctrl) as mock_ctrl_cls,
        patch("airtype.core.controller.init_controller"),
        patch("airtype.core.hotkey.HotkeyManager", return_value=mock_hkm) as mock_hkm_cls,
        patch("airtype.core.audio_capture.AudioCaptureService", return_value=new["audio"]),
        patch("airtype.core.vad.VadEngine", return_value=new["vad"]),
        patch("airtype.core.asr_engine.ASREngineRegistry", return_value=new["registry"]),
        patch("airtype.core.hotkey.FocusManager", return_value=new["focus_mgr"]),
        patch("airtype.core.text_injector.TextInjector", return_value=new["injector"]),
        patch("airtype.core.dictionary.DictionaryEngine", return_value=new["dict_engine"]),
        patch("airtype.core.pipeline.BatchRecognitionPipeline", return_value=new["pipeline"]),
        patch("airtype.__main__.importlib"),
        patch("PySide6.QtWidgets.QApplication", return_value=mock_app),
        patch("PySide6.QtCore.QTimer"),
        patch("sys.exit"),
    ):
        from airtype.__main__ import main
        main()

    # HotkeyManager 必須以 cfg.shortcuts 建立
    mock_hkm_cls.assert_called_once_with(mock_cfg.shortcuts)
    # CoreController 必須收到 hotkey_manager=mock_hkm（新版本有更多 kwargs）
    assert mock_ctrl_cls.call_args.kwargs["hotkey_manager"] == mock_hkm
    assert mock_ctrl_cls.call_args.kwargs["config"] == mock_cfg


def test_tray_toggle_voice_connected_to_handle_toggle():
    """tray.toggle_voice_requested Signal 觸發時呼叫 hotkey_manager._handle_toggle。

    main() 必須將 tray.toggle_voice_requested 連接至 hotkey_manager._handle_toggle，
    使系統匣選單「切換語音輸入」的行為與快捷鍵完全一致。
    """
    mock_cfg = MagicMock()
    mock_app = MagicMock()
    mock_app.exec.return_value = 0
    mock_overlay = MagicMock()
    mock_sw = MagicMock()
    mock_tray = MagicMock()
    mock_ctrl = MagicMock()
    mock_hkm = MagicMock()
    new = _new_component_patches(mock_cfg, mock_app)

    with (
        patch("airtype.config.AirtypeConfig.load", return_value=mock_cfg),
        patch("airtype.__main__.setup_logging"),
        patch("airtype.utils.i18n.set_language"),
        patch("airtype.ui.overlay.CapsuleOverlay", return_value=mock_overlay),
        patch("airtype.ui.settings_window.SettingsWindow", return_value=mock_sw),
        patch("airtype.ui.tray_icon.SystemTrayIcon", return_value=mock_tray),
        patch("airtype.core.controller.CoreController", return_value=mock_ctrl),
        patch("airtype.core.controller.init_controller"),
        patch("airtype.core.hotkey.HotkeyManager", return_value=mock_hkm),
        patch("airtype.core.audio_capture.AudioCaptureService", return_value=new["audio"]),
        patch("airtype.core.vad.VadEngine", return_value=new["vad"]),
        patch("airtype.core.asr_engine.ASREngineRegistry", return_value=new["registry"]),
        patch("airtype.core.hotkey.FocusManager", return_value=new["focus_mgr"]),
        patch("airtype.core.text_injector.TextInjector", return_value=new["injector"]),
        patch("airtype.core.dictionary.DictionaryEngine", return_value=new["dict_engine"]),
        patch("airtype.core.pipeline.BatchRecognitionPipeline", return_value=new["pipeline"]),
        patch("airtype.__main__.importlib"),
        patch("PySide6.QtWidgets.QApplication", return_value=mock_app),
        patch("PySide6.QtCore.QTimer"),
        patch("sys.exit"),
    ):
        from airtype.__main__ import main
        main()

    # toggle_voice_requested.connect 必須以 hotkey_manager._handle_toggle 呼叫
    mock_tray.toggle_voice_requested.connect.assert_any_call(mock_hkm._handle_toggle)


# ─────────────────────────────────────────────────────────────────────────────
# 任務 4-6（23-main-wiring）：主程式元件鏈建立測試
# ─────────────────────────────────────────────────────────────────────────────


def _make_new_mocks():
    """建立新元件鏈測試所需的 mock 字典。"""
    mock_cfg = MagicMock()
    mock_cfg.general.language = "zh-TW"
    mock_cfg.general.log_level = "INFO"
    mock_cfg.general.notifications = False
    mock_cfg.llm.enabled = False
    mock_cfg.version = "2.0.0"

    mock_app = MagicMock()
    mock_app.exec.return_value = 0

    mock_audio = MagicMock()
    mock_audio.rms = 0.0
    mock_registry = MagicMock()
    mock_registry.active_engine = MagicMock()  # asr_engine 非 None（property）

    return {
        "cfg": mock_cfg,
        "app": mock_app,
        "overlay": MagicMock(),
        "sw": MagicMock(),
        "tray": MagicMock(),
        "ctrl": MagicMock(),
        "hkm": MagicMock(),
        "audio": mock_audio,
        "vad": MagicMock(),
        "registry": mock_registry,
        "focus_mgr": MagicMock(),
        "injector": MagicMock(),
        "dict_engine": MagicMock(),
        "pipeline": MagicMock(),
    }


def _new_main_ctx(mocks):
    """回傳所有新元件 patch 的 context manager 串列。"""
    return (
        patch("airtype.config.AirtypeConfig.load", return_value=mocks["cfg"]),
        patch("airtype.__main__.setup_logging"),           # patch 本地引用
        patch("airtype.__main__.set_language"),            # patch 本地引用
        patch("PySide6.QtWidgets.QApplication", return_value=mocks["app"]),
        patch("PySide6.QtCore.QTimer"),
        patch("airtype.__main__.AudioCaptureService", return_value=mocks["audio"]),
        patch("airtype.__main__.VadEngine", return_value=mocks["vad"]),
        patch("airtype.__main__.ASREngineRegistry", return_value=mocks["registry"]),
        patch("airtype.__main__.FocusManager", return_value=mocks["focus_mgr"]),
        patch("airtype.__main__.TextInjector", return_value=mocks["injector"]),
        patch("airtype.__main__.DictionaryEngine", return_value=mocks["dict_engine"]),
        patch("airtype.__main__.BatchRecognitionPipeline", return_value=mocks["pipeline"]),
        patch("airtype.core.controller.CoreController", return_value=mocks["ctrl"]),
        patch("airtype.core.controller.init_controller"),
        patch("airtype.core.hotkey.HotkeyManager", return_value=mocks["hkm"]),
        patch("airtype.ui.overlay.CapsuleOverlay", return_value=mocks["overlay"]),
        patch("airtype.ui.settings_window.SettingsWindow", return_value=mocks["sw"]),
        patch("airtype.ui.tray_icon.SystemTrayIcon", return_value=mocks["tray"]),
        patch("airtype.__main__.importlib"),               # 阻止 ASR 動態 import
        patch("sys.exit"),
    )


def _call_main_new(mocks):
    """執行 main() 並回傳 ctrl_cls mock。

    Note: setup_logging 以模組層級 import 引用，需 patch airtype.__main__.setup_logging。
    其他元件以函式內 import 引用，需 patch 其原始模組路徑。
    """
    with (
        patch("airtype.config.AirtypeConfig.load", return_value=mocks["cfg"]),
        patch("airtype.__main__.setup_logging"),                          # 模組層級 ref
        patch("airtype.utils.i18n.set_language"),                         # 函式內 from import
        patch("PySide6.QtWidgets.QApplication", return_value=mocks["app"]),
        patch("PySide6.QtCore.QTimer"),
        patch("airtype.core.audio_capture.AudioCaptureService", return_value=mocks["audio"]),
        patch("airtype.core.vad.VadEngine", return_value=mocks["vad"]),
        patch("airtype.core.asr_engine.ASREngineRegistry", return_value=mocks["registry"]),
        patch("airtype.core.hotkey.FocusManager", return_value=mocks["focus_mgr"]),
        patch("airtype.core.text_injector.TextInjector", return_value=mocks["injector"]),
        patch("airtype.core.dictionary.DictionaryEngine", return_value=mocks["dict_engine"]),
        patch("airtype.core.pipeline.BatchRecognitionPipeline", return_value=mocks["pipeline"]),
        patch("airtype.core.controller.CoreController", return_value=mocks["ctrl"]) as mock_ctrl_cls,
        patch("airtype.core.controller.init_controller"),
        patch("airtype.core.hotkey.HotkeyManager", return_value=mocks["hkm"]),
        patch("airtype.ui.overlay.CapsuleOverlay", return_value=mocks["overlay"]),
        patch("airtype.ui.settings_window.SettingsWindow", return_value=mocks["sw"]),
        patch("airtype.ui.tray_icon.SystemTrayIcon", return_value=mocks["tray"]),
        patch("airtype.__main__.importlib"),                               # 阻止 ASR 動態 import
        patch("sys.exit"),
    ):
        from airtype.__main__ import main
        main()
    return mock_ctrl_cls


def test_audio_capture_service_is_started():
    """AudioCaptureService 應被建立並呼叫 .start()。"""
    mocks = _make_new_mocks()
    _call_main_new(mocks)
    mocks["audio"].start.assert_called_once()


def test_audio_capture_graceful_degradation():
    """AudioCaptureService.start() 失敗時不應 crash（優雅降級）。"""
    mocks = _make_new_mocks()
    mocks["audio"].start.side_effect = RuntimeError("無麥克風")
    _call_main_new(mocks)  # 不應 raise


def test_controller_receives_pipeline_and_injector():
    """CoreController 建構子應收到 pipeline=、text_injector= 參數。"""
    mocks = _make_new_mocks()
    mock_ctrl_cls = _call_main_new(mocks)
    call_kwargs = mock_ctrl_cls.call_args.kwargs
    assert "pipeline" in call_kwargs
    assert "text_injector" in call_kwargs


def test_controller_receives_dictionary_engine():
    """CoreController 應收到 dictionary_engine= 參數。"""
    mocks = _make_new_mocks()
    mock_ctrl_cls = _call_main_new(mocks)
    call_kwargs = mock_ctrl_cls.call_args.kwargs
    assert "dictionary_engine" in call_kwargs


def test_resource_cleanup_audio_capture_stopped():
    """關閉時應呼叫 audio_capture.stop()。"""
    mocks = _make_new_mocks()
    _call_main_new(mocks)
    mocks["audio"].stop.assert_called_once()
