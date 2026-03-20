"""__main__ 入口點單元測試（TDD）。

涵蓋：
- 任務 1.1：main() 初始化流程中 overlay appearance signals are connected at startup
  （驗證 settings_window.connect_overlay(overlay) 確實被呼叫）
- 任務 3.1：HotkeyManager 被正確建立並傳入 CoreController
- 任務 3.2：tray.toggle_voice_requested Signal 觸發時呼叫 hotkey_manager._handle_toggle

使用 unittest.mock 全面替換 Qt 與外部依賴，可在無 GUI 環境執行。
"""

from __future__ import annotations

from contextlib import ExitStack
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


def _early_test_patches(stack, mock_cfg, mock_app, new, **overrides):
    """在 ExitStack 上進入前 3 個測試共用的所有 patch，回傳各 mock。

    overrides 可傳入需要 as 變數的 patch（如 mock_ctrl_cls、mock_hkm_cls）。
    """
    mock_overlay = overrides.get("overlay", MagicMock())
    mock_sw = overrides.get("sw", MagicMock())
    mock_tray = overrides.get("tray", MagicMock())
    mock_ctrl = overrides.get("ctrl", MagicMock())
    mock_hkm = overrides.get("hkm", MagicMock())

    stack.enter_context(patch("airtype.config.AirtypeConfig.load", return_value=mock_cfg))
    stack.enter_context(patch("airtype.__main__.setup_logging"))
    stack.enter_context(patch("airtype.__main__._acquire_instance_lock", return_value=MagicMock()))
    stack.enter_context(patch("airtype.utils.i18n.set_language"))
    stack.enter_context(patch("airtype.ui.overlay.CapsuleOverlay", return_value=mock_overlay))
    stack.enter_context(patch("airtype.ui.settings_window.SettingsWindow", return_value=mock_sw))
    stack.enter_context(patch("airtype.ui.tray_icon.SystemTrayIcon", return_value=mock_tray))
    mock_ctrl_cls = stack.enter_context(
        patch("airtype.core.controller.CoreController", return_value=mock_ctrl)
    )
    stack.enter_context(patch("airtype.core.controller.init_controller"))
    mock_hkm_cls = stack.enter_context(
        patch("airtype.core.hotkey.HotkeyManager", return_value=mock_hkm)
    )
    stack.enter_context(patch("airtype.core.audio_capture.AudioCaptureService", return_value=new["audio"]))
    stack.enter_context(patch("airtype.core.vad.VadEngine", return_value=new["vad"]))
    stack.enter_context(patch("airtype.core.asr_engine.ASREngineRegistry", return_value=new["registry"]))
    stack.enter_context(patch("airtype.core.hotkey.FocusManager", return_value=new["focus_mgr"]))
    stack.enter_context(patch("airtype.core.text_injector.TextInjector", return_value=new["injector"]))
    stack.enter_context(patch("airtype.core.dictionary.DictionaryEngine", return_value=new["dict_engine"]))
    stack.enter_context(patch("airtype.core.pipeline.BatchRecognitionPipeline", return_value=new["pipeline"]))
    stack.enter_context(patch("airtype.__main__.importlib"))
    stack.enter_context(patch("PySide6.QtWidgets.QApplication", return_value=mock_app))
    stack.enter_context(patch("PySide6.QtGui.QIcon"))
    stack.enter_context(patch("PySide6.QtCore.QTimer"))
    stack.enter_context(patch("sys.exit"))

    return {
        "overlay": mock_overlay,
        "sw": mock_sw,
        "tray": mock_tray,
        "ctrl_cls": mock_ctrl_cls,
        "hkm_cls": mock_hkm_cls,
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
    new = _new_component_patches(mock_cfg, mock_app)

    with ExitStack() as stack:
        _early_test_patches(stack, mock_cfg, mock_app, new, overlay=mock_overlay, sw=mock_sw)
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
    mock_ctrl = MagicMock()
    mock_hkm = MagicMock()
    new = _new_component_patches(mock_cfg, mock_app)

    with ExitStack() as stack:
        refs = _early_test_patches(stack, mock_cfg, mock_app, new, ctrl=mock_ctrl, hkm=mock_hkm)
        from airtype.__main__ import main
        main()

    # HotkeyManager 必須以 cfg.shortcuts 建立
    refs["hkm_cls"].assert_called_once_with(mock_cfg.shortcuts)
    # CoreController 必須收到 hotkey_manager=mock_hkm（新版本有更多 kwargs）
    assert refs["ctrl_cls"].call_args.kwargs["hotkey_manager"] == mock_hkm
    assert refs["ctrl_cls"].call_args.kwargs["config"] == mock_cfg


def test_tray_toggle_voice_connected_to_handle_toggle():
    """tray.toggle_voice_requested Signal 觸發時呼叫 hotkey_manager._handle_toggle。

    main() 必須將 tray.toggle_voice_requested 連接至 hotkey_manager._handle_toggle，
    使系統匣選單「切換語音輸入」的行為與快捷鍵完全一致。
    """
    mock_cfg = MagicMock()
    mock_app = MagicMock()
    mock_app.exec.return_value = 0
    mock_tray = MagicMock()
    mock_hkm = MagicMock()
    new = _new_component_patches(mock_cfg, mock_app)

    with ExitStack() as stack:
        _early_test_patches(stack, mock_cfg, mock_app, new, tray=mock_tray, hkm=mock_hkm)
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


def _call_main_new(mocks):
    """執行 main() 並回傳 ctrl_cls mock。

    Note: setup_logging 以模組層級 import 引用，需 patch airtype.__main__.setup_logging。
    其他元件以函式內 import 引用，需 patch 其原始模組路徑。
    """
    with ExitStack() as stack:
        stack.enter_context(patch("airtype.config.AirtypeConfig.load", return_value=mocks["cfg"]))
        stack.enter_context(patch("airtype.__main__.setup_logging"))
        stack.enter_context(patch("airtype.__main__._acquire_instance_lock", return_value=MagicMock()))
        stack.enter_context(patch("airtype.utils.i18n.set_language"))
        stack.enter_context(patch("PySide6.QtWidgets.QApplication", return_value=mocks["app"]))
        stack.enter_context(patch("PySide6.QtGui.QIcon"))
        stack.enter_context(patch("PySide6.QtCore.QTimer"))
        stack.enter_context(patch("airtype.core.audio_capture.AudioCaptureService", return_value=mocks["audio"]))
        stack.enter_context(patch("airtype.core.vad.VadEngine", return_value=mocks["vad"]))
        stack.enter_context(patch("airtype.core.asr_engine.ASREngineRegistry", return_value=mocks["registry"]))
        stack.enter_context(patch("airtype.core.hotkey.FocusManager", return_value=mocks["focus_mgr"]))
        stack.enter_context(patch("airtype.core.text_injector.TextInjector", return_value=mocks["injector"]))
        stack.enter_context(patch("airtype.core.dictionary.DictionaryEngine", return_value=mocks["dict_engine"]))
        stack.enter_context(patch("airtype.core.pipeline.BatchRecognitionPipeline", return_value=mocks["pipeline"]))
        mock_ctrl_cls = stack.enter_context(
            patch("airtype.core.controller.CoreController", return_value=mocks["ctrl"])
        )
        stack.enter_context(patch("airtype.core.controller.init_controller"))
        stack.enter_context(patch("airtype.core.hotkey.HotkeyManager", return_value=mocks["hkm"]))
        stack.enter_context(patch("airtype.ui.overlay.CapsuleOverlay", return_value=mocks["overlay"]))
        stack.enter_context(patch("airtype.ui.settings_window.SettingsWindow", return_value=mocks["sw"]))
        stack.enter_context(patch("airtype.ui.tray_icon.SystemTrayIcon", return_value=mocks["tray"]))
        stack.enter_context(patch("airtype.__main__.importlib"))
        stack.enter_context(patch("sys.exit"))

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


# ---------------------------------------------------------------------------
# model_integrity_msg 對話框分支測試
# ---------------------------------------------------------------------------


def _call_main_with_integrity(mocks, validate_return):
    """執行 main()，並用 validate_return 覆寫 validate_model_files 回傳值。

    回傳 (mock_ctrl_cls, qtimer_mock)。
    """
    mock_mm = MagicMock()
    mock_mm.is_downloaded.return_value = True
    mock_mm.validate_model_files.return_value = validate_return

    # 讓 asr_engine 為 None，才會觸發對話框路徑
    mocks["registry"].active_engine = None

    with ExitStack() as stack:
        stack.enter_context(patch("airtype.config.AirtypeConfig.load", return_value=mocks["cfg"]))
        stack.enter_context(patch("airtype.__main__.setup_logging"))
        stack.enter_context(patch("airtype.__main__._acquire_instance_lock", return_value=MagicMock()))
        stack.enter_context(patch("airtype.utils.i18n.set_language"))
        stack.enter_context(patch("PySide6.QtWidgets.QApplication", return_value=mocks["app"]))
        stack.enter_context(patch("PySide6.QtGui.QIcon"))
        mock_qtimer = MagicMock()
        stack.enter_context(patch("PySide6.QtCore.QTimer", mock_qtimer))
        stack.enter_context(patch("airtype.core.audio_capture.AudioCaptureService", return_value=mocks["audio"]))
        stack.enter_context(patch("airtype.core.vad.VadEngine", return_value=mocks["vad"]))
        stack.enter_context(patch("airtype.core.asr_engine.ASREngineRegistry", return_value=mocks["registry"]))
        stack.enter_context(patch("airtype.core.hotkey.FocusManager", return_value=mocks["focus_mgr"]))
        stack.enter_context(patch("airtype.core.text_injector.TextInjector", return_value=mocks["injector"]))
        stack.enter_context(patch("airtype.core.dictionary.DictionaryEngine", return_value=mocks["dict_engine"]))
        stack.enter_context(patch("airtype.core.pipeline.BatchRecognitionPipeline", return_value=mocks["pipeline"]))
        stack.enter_context(patch("airtype.core.controller.CoreController", return_value=mocks["ctrl"]))
        stack.enter_context(patch("airtype.core.controller.init_controller"))
        stack.enter_context(patch("airtype.core.hotkey.HotkeyManager", return_value=mocks["hkm"]))
        stack.enter_context(patch("airtype.ui.overlay.CapsuleOverlay", return_value=mocks["overlay"]))
        stack.enter_context(patch("airtype.ui.settings_window.SettingsWindow", return_value=mocks["sw"]))
        stack.enter_context(patch("airtype.ui.tray_icon.SystemTrayIcon", return_value=mocks["tray"]))
        stack.enter_context(patch("airtype.__main__.importlib"))
        stack.enter_context(patch("airtype.utils.model_manager.ModelManager", return_value=mock_mm))
        stack.enter_context(patch("sys.exit"))

        from airtype.__main__ import main
        main()

    return mock_qtimer


def test_asr_warning_dialog_shows_missing_files():
    """asr_engine=None 且 validate 偵測 missing 時，QTimer.singleShot 應被呼叫（對話框觸發）。"""
    mocks = _make_new_mocks()
    mock_qtimer = _call_main_with_integrity(
        mocks,
        validate_return=(False, ["encoder.onnx OR encoder.int8.onnx"], []),
    )
    mock_qtimer.singleShot.assert_called_once()
    # 確認 callback 函式存在
    callback = mock_qtimer.singleShot.call_args[0][1]
    assert callable(callback)


def test_asr_warning_dialog_shows_tmp_incomplete():
    """asr_engine=None 且 validate 偵測 .tmp 時，QTimer.singleShot 應被呼叫（對話框觸發）。"""
    mocks = _make_new_mocks()
    mock_qtimer = _call_main_with_integrity(
        mocks,
        validate_return=(False, [], ["encoder.onnx.tmp"]),
    )
    mock_qtimer.singleShot.assert_called_once()


def test_asr_warning_dialog_missing_files_message_content():
    """missing 場景的 callback 內容應包含缺少的檔案名稱。"""
    mocks = _make_new_mocks()
    missing_entry = "encoder.onnx OR encoder.int8.onnx"
    mock_qtimer = _call_main_with_integrity(
        mocks,
        validate_return=(False, [missing_entry], []),
    )
    callback = mock_qtimer.singleShot.call_args[0][1]

    mock_msgbox = MagicMock()
    with patch("PySide6.QtWidgets.QMessageBox", return_value=mock_msgbox):
        callback()

    set_text_call = mock_msgbox.setText.call_args[0][0]
    assert "encoder.onnx OR encoder.int8.onnx" in set_text_call
    assert "不完整" in set_text_call


def test_asr_warning_dialog_tmp_message_content():
    """.tmp 場景的 callback 應顯示「下載未完成」訊息。"""
    mocks = _make_new_mocks()
    mock_qtimer = _call_main_with_integrity(
        mocks,
        validate_return=(False, [], ["model.onnx.tmp"]),
    )
    callback = mock_qtimer.singleShot.call_args[0][1]

    mock_msgbox = MagicMock()
    with patch("PySide6.QtWidgets.QMessageBox", return_value=mock_msgbox):
        callback()

    set_text_call = mock_msgbox.setText.call_args[0][0]
    assert "下載未完成" in set_text_call


def test_asr_warning_dialog_no_model_downloaded():
    """模型未下載時，callback 應顯示「尚未下載」訊息。"""
    mocks = _make_new_mocks()
    mocks["registry"].active_engine = None

    mock_mm = MagicMock()
    mock_mm.is_downloaded.return_value = False  # 未下載

    with ExitStack() as stack:
        stack.enter_context(patch("airtype.config.AirtypeConfig.load", return_value=mocks["cfg"]))
        stack.enter_context(patch("airtype.__main__.setup_logging"))
        stack.enter_context(patch("airtype.__main__._acquire_instance_lock", return_value=MagicMock()))
        stack.enter_context(patch("airtype.utils.i18n.set_language"))
        stack.enter_context(patch("PySide6.QtWidgets.QApplication", return_value=mocks["app"]))
        stack.enter_context(patch("PySide6.QtGui.QIcon"))
        mock_qtimer = MagicMock()
        stack.enter_context(patch("PySide6.QtCore.QTimer", mock_qtimer))
        stack.enter_context(patch("airtype.core.audio_capture.AudioCaptureService", return_value=mocks["audio"]))
        stack.enter_context(patch("airtype.core.vad.VadEngine", return_value=mocks["vad"]))
        stack.enter_context(patch("airtype.core.asr_engine.ASREngineRegistry", return_value=mocks["registry"]))
        stack.enter_context(patch("airtype.core.hotkey.FocusManager", return_value=mocks["focus_mgr"]))
        stack.enter_context(patch("airtype.core.text_injector.TextInjector", return_value=mocks["injector"]))
        stack.enter_context(patch("airtype.core.dictionary.DictionaryEngine", return_value=mocks["dict_engine"]))
        stack.enter_context(patch("airtype.core.pipeline.BatchRecognitionPipeline", return_value=mocks["pipeline"]))
        stack.enter_context(patch("airtype.core.controller.CoreController", return_value=mocks["ctrl"]))
        stack.enter_context(patch("airtype.core.controller.init_controller"))
        stack.enter_context(patch("airtype.core.hotkey.HotkeyManager", return_value=mocks["hkm"]))
        stack.enter_context(patch("airtype.ui.overlay.CapsuleOverlay", return_value=mocks["overlay"]))
        stack.enter_context(patch("airtype.ui.settings_window.SettingsWindow", return_value=mocks["sw"]))
        stack.enter_context(patch("airtype.ui.tray_icon.SystemTrayIcon", return_value=mocks["tray"]))
        stack.enter_context(patch("airtype.__main__.importlib"))
        stack.enter_context(patch("airtype.utils.model_manager.ModelManager", return_value=mock_mm))
        stack.enter_context(patch("sys.exit"))

        from airtype.__main__ import main
        main()

    callback = mock_qtimer.singleShot.call_args[0][1]
    mock_msgbox = MagicMock()
    with patch("PySide6.QtWidgets.QMessageBox", return_value=mock_msgbox):
        callback()

    set_text_call = mock_msgbox.setText.call_args[0][0]
    assert "尚未下載" in set_text_call
