"""VAD 引擎模組測試。

涵蓋：
- VAD 狀態機轉換單元測試（全部 4 個狀態、所有轉換）
- 可設定靜默逾時行為單元測試
- 整合測試：已知語音/靜默音訊 → 驗證狀態轉換
"""

from __future__ import annotations

import threading
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np


# ---------------------------------------------------------------------------
# 模組級輔助函式
# ---------------------------------------------------------------------------

def _named_mock(name: str) -> MagicMock:
    """建立具有 .name 屬性的 MagicMock（用於 ONNX session.get_inputs() mock）。"""
    m = MagicMock()
    m.name = name
    return m


# ---------------------------------------------------------------------------
# 輔助函式
# ---------------------------------------------------------------------------

def _make_engine(silence_timeout: float = 1.5, threshold: float = 0.5):
    """建立使用 mock VAD 模型的 VadEngine（不需真實 ONNX 模型）。"""
    from airtype.config import AirtypeConfig
    from airtype.core.vad import VadEngine

    config = AirtypeConfig()
    config.general.silence_timeout = silence_timeout
    mock_vad = MagicMock()
    mock_vad.reset_states.return_value = None
    engine = VadEngine(config=config, vad_model=mock_vad)
    engine.speech_threshold = threshold
    return engine


def _frame(prob: float) -> np.ndarray:
    """建立固定語音機率的 mock 幀（實際內容不重要，mock_vad 會回傳指定機率）。"""
    return np.zeros(512, dtype=np.float32)


def _feed(engine, probs: list[float]) -> None:
    """依序以指定語音機率驅動狀態機（直接設定 mock 回傳值）。"""
    for prob in probs:
        engine._vad_model.process_frame.return_value = prob
        engine.process_frame(_frame(prob))


# ---------------------------------------------------------------------------
# 4.1 VAD 狀態機轉換單元測試
# ---------------------------------------------------------------------------

class TestVadStateMachineTransitions(unittest.TestCase):
    """VAD 狀態機轉換單元測試：全部 4 個狀態與所有轉換。"""

    def test_initial_state_is_idle(self):
        """初始狀態應為 IDLE。"""
        from airtype.core.vad import VadState
        engine = _make_engine()
        self.assertEqual(engine.state, VadState.IDLE)

    def test_idle_to_speech_on_high_prob(self):
        """IDLE 狀態下，語音機率 >= 閾值 → 轉換至 SPEECH。"""
        from airtype.core.vad import VadState
        engine = _make_engine(threshold=0.5)
        _feed(engine, [0.8])
        self.assertEqual(engine.state, VadState.SPEECH)

    def test_idle_stays_idle_on_low_prob(self):
        """IDLE 狀態下，語音機率 < 閾值 → 保持 IDLE。"""
        from airtype.core.vad import VadState
        engine = _make_engine(threshold=0.5)
        _feed(engine, [0.3])
        self.assertEqual(engine.state, VadState.IDLE)

    def test_idle_to_speech_at_exact_threshold(self):
        """IDLE 狀態下，語音機率 == 閾值 → 轉換至 SPEECH（>= 觸發）。"""
        from airtype.core.vad import VadState
        engine = _make_engine(threshold=0.5)
        _feed(engine, [0.5])
        self.assertEqual(engine.state, VadState.SPEECH)

    def test_speech_to_silence_counting_on_low_prob(self):
        """SPEECH 狀態下，語音機率 < 閾值 → 轉換至 SILENCE_COUNTING。"""
        from airtype.core.vad import VadState
        engine = _make_engine()
        _feed(engine, [0.8, 0.2])
        self.assertEqual(engine.state, VadState.SILENCE_COUNTING)

    def test_speech_stays_speech_on_high_prob(self):
        """SPEECH 狀態下，語音機率 >= 閾值 → 保持 SPEECH。"""
        from airtype.core.vad import VadState
        engine = _make_engine()
        _feed(engine, [0.8, 0.9])
        self.assertEqual(engine.state, VadState.SPEECH)

    def test_silence_counting_to_speech_on_high_prob(self):
        """SILENCE_COUNTING 狀態下，語音機率 >= 閾值 → 轉換回 SPEECH。"""
        from airtype.core.vad import VadState
        engine = _make_engine(silence_timeout=10.0)
        _feed(engine, [0.8, 0.2, 0.8])
        self.assertEqual(engine.state, VadState.SPEECH)

    def test_silence_counting_to_speech_ended_on_timeout(self):
        """SILENCE_COUNTING 狀態下，靜默達逾時 → 轉換至 SPEECH_ENDED。"""
        from airtype.core.vad import VadState

        with patch("airtype.core.vad.time") as mock_time:
            # t=0: 進入 SILENCE_COUNTING；t=2.0: 超過 1.5s 逾時
            mock_time.monotonic.side_effect = [0.0, 0.0, 2.0]
            engine = _make_engine(silence_timeout=1.5)
            _feed(engine, [0.8, 0.2, 0.2])
            self.assertEqual(engine.state, VadState.SPEECH_ENDED)

    def test_speech_ended_resets_to_idle_on_next_frame(self):
        """SPEECH_ENDED 後的下一幀 → 自動重置至 IDLE（或 SPEECH 若有語音）。"""
        from airtype.core.vad import VadState

        with patch("airtype.core.vad.time") as mock_time:
            mock_time.monotonic.side_effect = [0.0, 0.0, 2.0, 3.0]
            engine = _make_engine(silence_timeout=1.5)
            _feed(engine, [0.8, 0.2, 0.2])  # → SPEECH_ENDED
            self.assertEqual(engine.state, VadState.SPEECH_ENDED)

            _feed(engine, [0.1])  # 重置後低機率 → IDLE
            self.assertEqual(engine.state, VadState.IDLE)

    def test_speech_ended_then_new_speech_detected(self):
        """SPEECH_ENDED 重置後立即偵測到語音 → 轉換至 SPEECH。"""
        from airtype.core.vad import VadState

        with patch("airtype.core.vad.time") as mock_time:
            mock_time.monotonic.side_effect = [0.0, 0.0, 2.0, 3.0]
            engine = _make_engine(silence_timeout=1.5)
            _feed(engine, [0.8, 0.2, 0.2])  # → SPEECH_ENDED
            _feed(engine, [0.9])             # → 重置 + SPEECH
            self.assertEqual(engine.state, VadState.SPEECH)

    def test_reset_states_called_on_speech_ended(self):
        """SPEECH_ENDED 後重置時，vad_model.reset_states() 應被呼叫。"""
        with patch("airtype.core.vad.time") as mock_time:
            mock_time.monotonic.side_effect = [0.0, 0.0, 2.0, 3.0]
            engine = _make_engine(silence_timeout=1.5)
            _feed(engine, [0.8, 0.2, 0.2])  # → SPEECH_ENDED
            _feed(engine, [0.1])              # 觸發重置
            engine._vad_model.reset_states.assert_called()

    def test_multiple_speech_segments(self):
        """完整兩段語音周期：IDLE→SPEECH→SILENCE_COUNTING→SPEECH_ENDED→IDLE→SPEECH。"""
        from airtype.core.vad import VadState

        with patch("airtype.core.vad.time") as mock_time:
            mock_time.monotonic.side_effect = [
                0.0,   # 第一次進 SILENCE_COUNTING 時記錄
                0.0,   # 第一次幀 (0.2)
                2.0,   # 第二次幀 (0.2) → 超過逾時
                3.0,   # 第三次幀 (0.9) 自動重置後
            ]
            engine = _make_engine(silence_timeout=1.5)
            _feed(engine, [0.8])       # → SPEECH
            _feed(engine, [0.2])       # → SILENCE_COUNTING
            _feed(engine, [0.2])       # → SPEECH_ENDED
            _feed(engine, [0.9])       # 重置 → SPEECH
            self.assertEqual(engine.state, VadState.SPEECH)


# ---------------------------------------------------------------------------
# 4.2 可設定靜默逾時行為單元測試
# ---------------------------------------------------------------------------

class TestVadConfigurableTimeout(unittest.TestCase):
    """可設定靜默逾時行為單元測試。"""

    def test_default_silence_timeout_is_1_5_seconds(self):
        """預設 silence_timeout 應為 1.5 秒（從設定讀取）。"""
        engine = _make_engine(silence_timeout=1.5)
        self.assertAlmostEqual(engine.silence_timeout, 1.5)

    def test_custom_silence_timeout_3_seconds(self):
        """設定 silence_timeout=3.0 時，VAD 等待 3.0 秒才轉換至 SPEECH_ENDED。"""
        from airtype.core.vad import VadState

        with patch("airtype.core.vad.time") as mock_time:
            # 靜默 2.9 秒時不應觸發（< 3.0）
            mock_time.monotonic.side_effect = [0.0, 0.0, 2.9]
            engine = _make_engine(silence_timeout=3.0)
            _feed(engine, [0.8, 0.2, 0.2])
            self.assertEqual(engine.state, VadState.SILENCE_COUNTING)

    def test_custom_timeout_triggers_at_3_seconds(self):
        """靜默達 3.0 秒時應轉換至 SPEECH_ENDED。"""
        from airtype.core.vad import VadState

        with patch("airtype.core.vad.time") as mock_time:
            mock_time.monotonic.side_effect = [0.0, 0.0, 3.0]
            engine = _make_engine(silence_timeout=3.0)
            _feed(engine, [0.8, 0.2, 0.2])
            self.assertEqual(engine.state, VadState.SPEECH_ENDED)

    def test_minimum_silence_timeout_0_5_seconds(self):
        """最小 silence_timeout = 0.5 秒，0.4 秒時不觸發。"""
        from airtype.core.vad import VadState

        with patch("airtype.core.vad.time") as mock_time:
            mock_time.monotonic.side_effect = [0.0, 0.0, 0.4]
            engine = _make_engine(silence_timeout=0.5)
            _feed(engine, [0.8, 0.2, 0.2])
            self.assertEqual(engine.state, VadState.SILENCE_COUNTING)

    def test_minimum_silence_timeout_triggers_at_0_5_seconds(self):
        """最小 silence_timeout = 0.5 秒，0.5 秒時觸發。"""
        from airtype.core.vad import VadState

        with patch("airtype.core.vad.time") as mock_time:
            mock_time.monotonic.side_effect = [0.0, 0.0, 0.5]
            engine = _make_engine(silence_timeout=0.5)
            _feed(engine, [0.8, 0.2, 0.2])
            self.assertEqual(engine.state, VadState.SPEECH_ENDED)

    def test_timeout_reset_when_speech_resumes(self):
        """SILENCE_COUNTING 期間語音恢復 → 回到 SPEECH → 靜默計時器重置。"""
        from airtype.core.vad import VadState

        with patch("airtype.core.vad.time") as mock_time:
            # _update_state 每幀都呼叫 time.monotonic()，共 6 幀 = 6 個值
            # 幀 1 [0.8]: IDLE→SPEECH, t=0.0
            # 幀 2 [0.2]: SPEECH→SILENCE_COUNTING, silence_start=0.0, t=0.0
            # 幀 3 [0.2]: 靜默 0.8s < 1.5s, t=0.8
            # 幀 4 [0.8]: SILENCE_COUNTING→SPEECH, t=1.0
            # 幀 5 [0.2]: SPEECH→SILENCE_COUNTING, silence_start=1.0, t=1.0
            # 幀 6 [0.2]: 靜默 1.4s < 1.5s, t=2.4 → 保持 SILENCE_COUNTING
            mock_time.monotonic.side_effect = [0.0, 0.0, 0.8, 1.0, 1.0, 2.4]
            engine = _make_engine(silence_timeout=1.5)
            _feed(engine, [0.8])  # IDLE→SPEECH
            _feed(engine, [0.2])  # SPEECH→SILENCE_COUNTING (t=0.0)
            _feed(engine, [0.2])  # t=0.8s，未逾時
            _feed(engine, [0.8])  # 語音恢復 → SPEECH
            _feed(engine, [0.2])  # SPEECH→SILENCE_COUNTING (t=1.0)
            _feed(engine, [0.2])  # t=2.4s，1.4s 靜默，未逾時
            self.assertEqual(engine.state, VadState.SILENCE_COUNTING)

    def test_threshold_configurable(self):
        """自訂閾值 0.7：語音機率 0.6 時不觸發，0.7 時觸發。"""
        from airtype.core.vad import VadState
        engine_strict = _make_engine(threshold=0.7)
        _feed(engine_strict, [0.6])
        self.assertEqual(engine_strict.state, VadState.IDLE)

        engine_strict2 = _make_engine(threshold=0.7)
        _feed(engine_strict2, [0.7])
        self.assertEqual(engine_strict2.state, VadState.SPEECH)

    def test_config_general_silence_timeout_applied(self):
        """VadEngine 應從 config.general.silence_timeout 讀取逾時值。"""
        from airtype.config import AirtypeConfig
        from airtype.core.vad import VadEngine

        config = AirtypeConfig()
        config.general.silence_timeout = 2.5
        engine = VadEngine(config=config, vad_model=MagicMock())
        self.assertAlmostEqual(engine.silence_timeout, 2.5)


# ---------------------------------------------------------------------------
# 4.3 狀態轉換事件與 callback 整合測試
# ---------------------------------------------------------------------------

class TestVadStateTransitionEvents(unittest.TestCase):
    """狀態轉換事件與 callback 整合測試。"""

    def test_callback_called_on_idle_to_speech(self):
        """IDLE→SPEECH 轉換時，callback 應以 (IDLE, SPEECH) 呼叫。"""
        from airtype.core.vad import VadState

        engine = _make_engine()
        events: list[tuple] = []
        engine.on_state_change(lambda prev, curr: events.append((prev, curr)))

        _feed(engine, [0.8])
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0], (VadState.IDLE, VadState.SPEECH))

    def test_callback_called_on_speech_to_silence_counting(self):
        """SPEECH→SILENCE_COUNTING 轉換時，callback 應以 (SPEECH, SILENCE_COUNTING) 呼叫。"""
        from airtype.core.vad import VadState

        engine = _make_engine()
        events: list[tuple] = []
        engine.on_state_change(lambda prev, curr: events.append((prev, curr)))

        _feed(engine, [0.8, 0.2])
        self.assertIn((VadState.SPEECH, VadState.SILENCE_COUNTING), events)

    def test_callback_called_on_silence_counting_to_speech(self):
        """SILENCE_COUNTING→SPEECH 轉換時，callback 以 (SILENCE_COUNTING, SPEECH) 呼叫。"""
        from airtype.core.vad import VadState

        engine = _make_engine(silence_timeout=10.0)
        events: list[tuple] = []
        engine.on_state_change(lambda prev, curr: events.append((prev, curr)))

        _feed(engine, [0.8, 0.2, 0.8])
        self.assertIn((VadState.SILENCE_COUNTING, VadState.SPEECH), events)

    def test_callback_called_on_speech_ended(self):
        """SILENCE_COUNTING→SPEECH_ENDED 轉換時，callback 以 (SILENCE_COUNTING, SPEECH_ENDED) 呼叫。"""
        from airtype.core.vad import VadState

        with patch("airtype.core.vad.time") as mock_time:
            mock_time.monotonic.side_effect = [0.0, 0.0, 2.0]
            engine = _make_engine(silence_timeout=1.5)
            events: list[tuple] = []
            engine.on_state_change(lambda prev, curr: events.append((prev, curr)))
            _feed(engine, [0.8, 0.2, 0.2])
            self.assertIn((VadState.SILENCE_COUNTING, VadState.SPEECH_ENDED), events)

    def test_multiple_callbacks_all_called(self):
        """多個 callback 均應在狀態轉換時被呼叫。"""
        from airtype.core.vad import VadState

        engine = _make_engine()
        calls_a: list = []
        calls_b: list = []
        engine.on_state_change(lambda p, c: calls_a.append((p, c)))
        engine.on_state_change(lambda p, c: calls_b.append((p, c)))

        _feed(engine, [0.8])
        self.assertEqual(len(calls_a), 1)
        self.assertEqual(len(calls_b), 1)

    def test_callback_exception_does_not_stop_processing(self):
        """callback 拋出例外時，不應阻斷狀態機繼續處理後續幀。"""
        from airtype.core.vad import VadState

        engine = _make_engine()

        def bad_callback(prev, curr):
            raise ValueError("測試例外")

        engine.on_state_change(bad_callback)

        # 不應拋出例外，而是繼續處理
        _feed(engine, [0.8])
        self.assertEqual(engine.state, VadState.SPEECH)

    def test_no_callback_when_state_unchanged(self):
        """狀態未改變時，callback 不應被呼叫。"""
        engine = _make_engine()
        events: list = []
        engine.on_state_change(lambda p, c: events.append((p, c)))

        # 持續在 IDLE（低機率）
        _feed(engine, [0.1, 0.2, 0.3])
        self.assertEqual(len(events), 0)

    def test_full_speech_cycle_events(self):
        """完整語音周期：驗證所有狀態轉換事件依序發生。"""
        from airtype.core.vad import VadState

        with patch("airtype.core.vad.time") as mock_time:
            mock_time.monotonic.side_effect = [0.0, 0.0, 2.0]
            engine = _make_engine(silence_timeout=1.5)
            events: list[tuple] = []
            engine.on_state_change(lambda p, c: events.append((p, c)))

            _feed(engine, [0.8])  # IDLE→SPEECH
            _feed(engine, [0.2])  # SPEECH→SILENCE_COUNTING
            _feed(engine, [0.2])  # SILENCE_COUNTING→SPEECH_ENDED

            expected = [
                (VadState.IDLE, VadState.SPEECH),
                (VadState.SPEECH, VadState.SILENCE_COUNTING),
                (VadState.SILENCE_COUNTING, VadState.SPEECH_ENDED),
            ]
            self.assertEqual(events, expected)


# ---------------------------------------------------------------------------
# 4.3 整合測試：連接 AudioCaptureService queue
# ---------------------------------------------------------------------------

class TestVadEngineAudioIntegration(unittest.TestCase):
    """整合測試：VadEngine 從 AudioCaptureService queue 消費音訊幀。"""

    def test_start_consuming_processes_frames_from_queue(self):
        """start_consuming 應從 audio_service 取幀並呼叫 process_frame。"""
        from airtype.core.vad import VadState

        engine = _make_engine()

        # 準備 mock audio service，返回幾幀後停止
        frames_sent = [np.zeros(512, dtype=np.float32)] * 3
        frame_iter = iter(frames_sent + [None] * 20)

        mock_audio = MagicMock()
        mock_audio.get_frame.side_effect = lambda timeout=0.05: next(frame_iter, None)

        # mock VAD model 持續回傳語音
        engine._vad_model.process_frame.return_value = 0.8

        engine.start_consuming(mock_audio)
        time.sleep(0.2)  # 讓背景執行緒運行
        engine.stop_consuming()

        # 驗證至少呼叫了 process_frame
        self.assertGreater(engine._vad_model.process_frame.call_count, 0)

    def test_stop_consuming_stops_background_thread(self):
        """stop_consuming 後，背景執行緒應停止運行。"""
        engine = _make_engine()

        mock_audio = MagicMock()
        mock_audio.get_frame.return_value = None

        engine.start_consuming(mock_audio)
        self.assertTrue(engine._thread.is_alive())

        engine.stop_consuming()
        self.assertFalse(engine._thread.is_alive())

    def test_none_frames_are_skipped(self):
        """audio_service.get_frame 回傳 None 時，不應呼叫 process_frame。"""
        engine = _make_engine()

        mock_audio = MagicMock()
        mock_audio.get_frame.return_value = None

        engine.start_consuming(mock_audio)
        time.sleep(0.1)
        engine.stop_consuming()

        engine._vad_model.process_frame.assert_not_called()


# ---------------------------------------------------------------------------
# 4.3 SileroVAD ONNX 整合（mock onnxruntime）
# ---------------------------------------------------------------------------

class TestSileroVadOnnxIntegration(unittest.TestCase):
    """SileroVAD ONNX 模型封裝測試（mock onnxruntime.InferenceSession）。"""

    def setUp(self):
        """建立臨時 ONNX 模型檔案（不需真實內容，session 為 mock）。"""
        import tempfile
        tmp = tempfile.NamedTemporaryFile(suffix=".onnx", delete=False)
        self._model_path = Path(tmp.name)
        tmp.close()

    def tearDown(self):
        try:
            self._model_path.unlink()
        except FileNotFoundError:
            pass

    def _make_mock_session(self, speech_prob: float = 0.8):
        """建立回傳指定語音機率的 mock ONNX session（含正確的 get_inputs）。

        Silero VAD v5 介面：
        - 輸入：input (1, 512), state (2, 1, 128), sr (int64)
        - 輸出：output (1, 1), stateN (2, 1, 128)
        """
        mock_session = MagicMock()

        # get_inputs() 必須回傳具 .name 屬性的物件清單（v5 格式）
        mock_session.get_inputs.return_value = [
            _named_mock("input"), _named_mock("state"), _named_mock("sr"),
        ]

        state_out = np.zeros((2, 1, 128), dtype=np.float32)
        mock_session.run.return_value = [
            np.array([[speech_prob]], dtype=np.float32),  # shape (1, 1)
            state_out,
        ]
        return mock_session

    def _make_vad(self, speech_prob: float = 0.8):
        """建立使用 mock session 的 SileroVAD。"""
        import sys
        from airtype.core.vad import SileroVAD

        mock_session = self._make_mock_session(speech_prob)
        mock_ort = MagicMock()
        mock_ort.InferenceSession.return_value = mock_session
        with patch.dict(sys.modules, {"onnxruntime": mock_ort}):
            vad = SileroVAD(model_path=self._model_path)
        # 替換已建立的 _session，讓後續呼叫也用同一個 mock
        vad._session = mock_session
        return vad

    def test_process_frame_returns_speech_prob(self):
        """process_frame 應回傳語音機率 [0, 1]。"""
        vad = self._make_vad(0.85)
        frame = np.zeros(512, dtype=np.float32)
        prob = vad.process_frame(frame)

        self.assertAlmostEqual(prob, 0.85, places=5)
        self.assertGreaterEqual(prob, 0.0)
        self.assertLessEqual(prob, 1.0)

    def test_process_frame_updates_hidden_states(self):
        """process_frame 後，LSTM state 張量應更新（不再是零矩陣）。"""
        import sys
        from airtype.core.vad import SileroVAD

        state_out = np.ones((2, 1, 128), dtype=np.float32) * 0.5

        mock_session = MagicMock()
        mock_session.get_inputs.return_value = [
            _named_mock("input"), _named_mock("state"), _named_mock("sr"),
        ]
        mock_session.run.return_value = [np.array([[0.7]], dtype=np.float32), state_out]
        mock_ort = MagicMock()
        mock_ort.InferenceSession.return_value = mock_session
        with patch.dict(sys.modules, {"onnxruntime": mock_ort}):
            vad = SileroVAD(model_path=self._model_path)
        vad._session = mock_session
        vad.process_frame(np.zeros(512, dtype=np.float32))

        np.testing.assert_array_equal(vad._state, state_out)

    def test_reset_states_clears_hidden_states(self):
        """reset_states 應將 LSTM state 張量重置為零。"""
        vad = self._make_vad(0.5)
        vad._state = np.ones((2, 1, 128), dtype=np.float32)
        vad.reset_states()

        np.testing.assert_array_equal(vad._state, np.zeros((2, 1, 128), dtype=np.float32))

    def test_silence_frame_returns_low_prob(self):
        """靜音幀（全零）應回傳低語音機率（< 0.3，透過 mock）。"""
        vad = self._make_vad(0.05)
        frame = np.zeros(512, dtype=np.float32)
        prob = vad.process_frame(frame)
        self.assertLess(prob, 0.3)

    def test_speech_frame_returns_high_prob(self):
        """語音幀應回傳高語音機率（> 0.5，透過 mock）。"""
        vad = self._make_vad(0.92)
        t = np.linspace(0, 2 * np.pi, 512, endpoint=False)
        speech_frame = np.sin(t * 440).astype(np.float32)
        prob = vad.process_frame(speech_frame)
        self.assertGreater(prob, 0.5)

    def test_model_missing_raises_helpful_error(self):
        """模型檔案不存在時應拋出 FileNotFoundError，並包含路徑資訊。"""
        from airtype.core.vad import SileroVAD

        with self.assertRaises(FileNotFoundError):
            SileroVAD(model_path=Path("/nonexistent/path/model.onnx"))


if __name__ == "__main__":
    unittest.main()
