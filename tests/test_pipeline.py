"""辨識管線單元測試（TDD）。

使用模擬元件驗證批次管線與串流管線的端對端流程。

涵蓋：
- 任務 4.1：批次辨識管線（SPEECH 累積 → SPEECH_ENDED → ASR → 注入）
- 任務 4.2：串流辨識管線（逐幀串流 + 偽串流模式）
- 任務 3.1：管線可組合性（依賴注入 + mock 元件）
"""

from __future__ import annotations

import queue
import threading
import time
from typing import Callable, List, Optional

import numpy as np
import pytest

from airtype.core.asr_engine import ASRResult, PartialResult
from airtype.core.pipeline import BatchRecognitionPipeline, StreamingRecognitionPipeline
from airtype.core.vad import VadState


# ─────────────────────────────────────────────────────────────────────────────
# Mock 元件
# ─────────────────────────────────────────────────────────────────────────────


class MockAudioCapture:
    """可預設幀序列的模擬音訊擷取服務。"""

    def __init__(self, frames: Optional[List[np.ndarray]] = None) -> None:
        self._queue: queue.Queue[Optional[np.ndarray]] = queue.Queue()
        for f in frames or []:
            self._queue.put(f)

    def push(self, frame: np.ndarray) -> None:
        self._queue.put(frame)

    def get_frame(self, timeout: float = 0.05) -> Optional[np.ndarray]:
        try:
            return self._queue.get(timeout=timeout)
        except queue.Empty:
            return None


class MockVadEngine:
    """不執行真實 ONNX 推理的模擬 VadEngine。

    支援手動觸發狀態轉換，供測試驗證管線 callback 行為。
    """

    def __init__(self) -> None:
        self._callbacks: list[Callable] = []
        self._audio_source = None

    def on_state_change(self, callback: Callable) -> None:
        self._callbacks.append(callback)

    def start_consuming(self, audio_source) -> None:
        self._audio_source = audio_source

    def stop_consuming(self) -> None:
        pass

    def fire_state_change(self, prev: VadState, new: VadState) -> None:
        """手動觸發狀態轉換 callback（供測試使用）。"""
        for cb in self._callbacks:
            cb(prev, new)


class MockASREngine:
    """回傳預設辨識結果的模擬 ASR 引擎。"""

    def __init__(
        self,
        batch_text: str = "測試文字",
        stream_text: str = "串流測試",
        stream_is_final: bool = True,
    ) -> None:
        self.batch_text = batch_text
        self.stream_text = stream_text
        self.stream_is_final = stream_is_final
        self.recognize_calls: list[np.ndarray] = []
        self.recognize_stream_calls: list[np.ndarray] = []

    def recognize(self, audio: np.ndarray) -> ASRResult:
        self.recognize_calls.append(audio)
        return ASRResult(text=self.batch_text, language="zh-TW", confidence=0.99)

    def recognize_stream(self, chunk: np.ndarray) -> PartialResult:
        self.recognize_stream_calls.append(chunk)
        return PartialResult(text=self.stream_text, is_final=self.stream_is_final)

    def load_model(self, model_path, config) -> None:
        pass

    def set_hot_words(self, words) -> None:
        pass

    def set_context(self, context_text) -> None:
        pass

    def get_supported_languages(self) -> list[str]:
        return ["zh-TW"]

    def unload(self) -> None:
        pass


class MockTextInjector:
    """記錄注入文字的模擬文字注入器。"""

    def __init__(self) -> None:
        self.injected: list[str] = []
        self._event = threading.Event()

    def inject(self, text: str) -> None:
        self.injected.append(text)
        self._event.set()

    def wait_for_injection(self, timeout: float = 2.0) -> bool:
        """等待至少一次 inject() 呼叫，逾時回傳 False。"""
        return self._event.wait(timeout=timeout)

    def reset(self) -> None:
        self.injected.clear()
        self._event.clear()


# ─────────────────────────────────────────────────────────────────────────────
# 輔助：產生測試音訊幀
# ─────────────────────────────────────────────────────────────────────────────


def _make_frames(n: int = 5) -> list[np.ndarray]:
    """產生 n 個 512 樣本的 float32 幀（值各不相同以便驗證累積）。"""
    return [np.full(512, i * 0.01, dtype=np.float32) for i in range(n)]


# ─────────────────────────────────────────────────────────────────────────────
# 任務 4.1：批次辨識管線單元測試
# ─────────────────────────────────────────────────────────────────────────────


class TestBatchRecognitionPipeline:
    """驗證批次辨識管線：SPEECH 累積 → SPEECH_ENDED → ASR → 注入。"""

    def _make_pipeline(self, frames=None, batch_text="辨識結果"):
        audio = MockAudioCapture(frames)
        vad = MockVadEngine()
        asr = MockASREngine(batch_text=batch_text)
        injector = MockTextInjector()
        pipeline = BatchRecognitionPipeline(audio, vad, asr, injector)
        return pipeline, audio, vad, asr, injector

    def test_audio_accumulated_during_speech(self):
        """SPEECH 狀態期間的幀應被累積至內部緩衝區。"""
        frames = _make_frames(5)
        pipeline, audio, vad, asr, injector = self._make_pipeline(frames)

        vad.fire_state_change(VadState.IDLE, VadState.SPEECH)
        for _ in frames:
            pipeline.get_frame(timeout=0.1)
        vad.fire_state_change(VadState.SPEECH, VadState.SPEECH_ENDED)

        assert injector.wait_for_injection(timeout=2.0), "SPEECH_ENDED 後應觸發 ASR 並注入文字"
        assert len(asr.recognize_calls) == 1
        audio_sent = asr.recognize_calls[0]
        assert len(audio_sent) == 5 * 512, f"預期 {5 * 512} 樣本，實際 {len(audio_sent)}"

    def test_asr_called_on_speech_ended(self):
        """SPEECH_ENDED 事件時應呼叫 ASR.recognize 一次。"""
        frames = _make_frames(3)
        pipeline, audio, vad, asr, injector = self._make_pipeline(frames)

        vad.fire_state_change(VadState.IDLE, VadState.SPEECH)
        for _ in frames:
            pipeline.get_frame(timeout=0.1)
        vad.fire_state_change(VadState.SPEECH, VadState.SPEECH_ENDED)

        assert injector.wait_for_injection(timeout=2.0)
        assert len(asr.recognize_calls) == 1

    def test_text_injected_after_asr(self):
        """ASR 完成後應以辨識文字呼叫文字注入器。"""
        pipeline, audio, vad, asr, injector = self._make_pipeline(
            frames=_make_frames(2), batch_text="注入測試"
        )

        vad.fire_state_change(VadState.IDLE, VadState.SPEECH)
        for _ in range(2):
            pipeline.get_frame(timeout=0.1)
        vad.fire_state_change(VadState.SPEECH, VadState.SPEECH_ENDED)

        assert injector.wait_for_injection(timeout=2.0)
        assert injector.injected == ["注入測試"]

    def test_empty_audio_not_injected(self):
        """SPEECH_ENDED 前無累積音訊時不應呼叫 ASR 或注入。"""
        pipeline, audio, vad, asr, injector = self._make_pipeline()

        # 不觸發 SPEECH，直接觸發 SPEECH_ENDED
        vad.fire_state_change(VadState.IDLE, VadState.SPEECH_ENDED)

        time.sleep(0.3)
        assert len(injector.injected) == 0
        assert len(asr.recognize_calls) == 0

    def test_silence_counting_continues_accumulation(self):
        """SILENCE_COUNTING 狀態期間應繼續累積音訊（不重置緩衝區）。"""
        frames_a = _make_frames(3)
        frames_b = _make_frames(2)
        pipeline, audio, vad, asr, injector = self._make_pipeline(
            frames=frames_a + frames_b
        )

        vad.fire_state_change(VadState.IDLE, VadState.SPEECH)
        for _ in frames_a:
            pipeline.get_frame(timeout=0.1)
        vad.fire_state_change(VadState.SPEECH, VadState.SILENCE_COUNTING)
        for _ in frames_b:
            pipeline.get_frame(timeout=0.1)
        vad.fire_state_change(VadState.SILENCE_COUNTING, VadState.SPEECH_ENDED)

        assert injector.wait_for_injection(timeout=2.0)
        audio_sent = asr.recognize_calls[0]
        assert len(audio_sent) == 5 * 512, "SPEECH + SILENCE_COUNTING 的幀均應累積"

    def test_buffer_reset_on_new_speech(self):
        """每次新的 SPEECH 開始時應重置緩衝區，不混入前段音訊。"""
        pipeline, audio, vad, asr, injector = self._make_pipeline(
            frames=_make_frames(4)
        )

        # 第一段語音（2 幀）
        vad.fire_state_change(VadState.IDLE, VadState.SPEECH)
        for _ in range(2):
            pipeline.get_frame(timeout=0.1)
        vad.fire_state_change(VadState.SPEECH, VadState.SPEECH_ENDED)
        assert injector.wait_for_injection(timeout=2.0)
        injector.reset()

        # 第二段語音（2 幀），緩衝區應已重置
        vad.fire_state_change(VadState.IDLE, VadState.SPEECH)
        for _ in range(2):
            pipeline.get_frame(timeout=0.1)
        vad.fire_state_change(VadState.SPEECH, VadState.SPEECH_ENDED)
        assert injector.wait_for_injection(timeout=2.0)

        audio_sent_2 = asr.recognize_calls[1]
        assert len(audio_sent_2) == 2 * 512, "第二段應只有 2 幀，不含第一段殘留"


# ─────────────────────────────────────────────────────────────────────────────
# 任務 4.2：串流辨識管線單元測試
# ─────────────────────────────────────────────────────────────────────────────


class TestStreamingRecognitionPipeline:
    """驗證串流辨識管線：逐幀串流 ASR + 偽串流模式。"""

    def _make_pipeline(
        self,
        frames=None,
        stream_text="串流結果",
        stream_is_final=True,
        batch_text="批次結果",
        on_partial=None,
        use_pseudo=False,
        pseudo_segment_frames=50,
    ):
        audio = MockAudioCapture(frames)
        vad = MockVadEngine()
        asr = MockASREngine(
            batch_text=batch_text,
            stream_text=stream_text,
            stream_is_final=stream_is_final,
        )
        injector = MockTextInjector()
        pipeline = StreamingRecognitionPipeline(
            audio,
            vad,
            asr,
            injector,
            on_partial=on_partial,
            use_pseudo_streaming=use_pseudo,
            pseudo_segment_frames=pseudo_segment_frames,
        )
        return pipeline, audio, vad, asr, injector

    def test_chunks_fed_to_recognize_stream_during_speech(self):
        """SPEECH 狀態期間的每幀應傳送至 recognize_stream。"""
        frames = _make_frames(3)
        pipeline, audio, vad, asr, injector = self._make_pipeline(frames=frames)
        pipeline.start()

        vad.fire_state_change(VadState.IDLE, VadState.SPEECH)
        for _ in frames:
            pipeline.get_frame(timeout=0.1)

        time.sleep(0.5)
        assert len(asr.recognize_stream_calls) == 3

        pipeline.stop()

    def test_recognize_stream_not_called_outside_speech(self):
        """SPEECH 以外狀態取出的幀不應送至 recognize_stream。"""
        frames = _make_frames(3)
        pipeline, audio, vad, asr, injector = self._make_pipeline(frames=frames)
        pipeline.start()

        # 不觸發 SPEECH，直接取幀
        for _ in frames:
            pipeline.get_frame(timeout=0.1)

        time.sleep(0.3)
        assert len(asr.recognize_stream_calls) == 0

        pipeline.stop()

    def test_partial_callback_called(self):
        """on_partial callback 應於每次部分結果時被呼叫。"""
        partial_calls: list[tuple[str, bool]] = []

        def on_partial(text: str, is_final: bool) -> None:
            partial_calls.append((text, is_final))

        frames = _make_frames(2)
        pipeline, audio, vad, asr, injector = self._make_pipeline(
            frames=frames,
            stream_text="部分文字",
            stream_is_final=False,
            on_partial=on_partial,
        )
        pipeline.start()

        vad.fire_state_change(VadState.IDLE, VadState.SPEECH)
        for _ in frames:
            pipeline.get_frame(timeout=0.1)

        time.sleep(0.5)
        assert len(partial_calls) == 2
        assert all(text == "部分文字" for text, _ in partial_calls)
        assert all(not is_final for _, is_final in partial_calls)

        pipeline.stop()

    def test_final_result_injected(self):
        """recognize_stream 回傳 is_final=True 時應注入文字。"""
        frames = _make_frames(2)
        pipeline, audio, vad, asr, injector = self._make_pipeline(
            frames=frames, stream_text="最終文字", stream_is_final=True
        )
        pipeline.start()

        vad.fire_state_change(VadState.IDLE, VadState.SPEECH)
        for _ in frames:
            pipeline.get_frame(timeout=0.1)

        assert injector.wait_for_injection(timeout=2.0)
        assert "最終文字" in injector.injected

        pipeline.stop()

    def test_stream_worker_stops_on_stop(self):
        """stop() 後串流工作執行緒應正常終止。"""
        pipeline, audio, vad, asr, injector = self._make_pipeline()
        pipeline.start()
        pipeline.stop()
        # 測試若工作執行緒未正常終止將逾時，故無需額外斷言

    def test_pseudo_streaming_batch_recognition_on_segment(self):
        """偽串流模式：每達 pseudo_segment_frames 幀應呼叫批次 ASR 並觸發 on_partial。"""
        partial_calls: list[tuple[str, bool]] = []

        frames = _make_frames(3)
        pipeline, audio, vad, asr, injector = self._make_pipeline(
            frames=frames,
            on_partial=lambda t, f: partial_calls.append((t, f)),
            use_pseudo=True,
            pseudo_segment_frames=2,  # 每 2 幀觸發一次偽串流批次辨識
        )
        pipeline.start()

        vad.fire_state_change(VadState.IDLE, VadState.SPEECH)
        for _ in frames:
            pipeline.get_frame(timeout=0.1)

        time.sleep(0.5)
        # 3 幀 / 每段 2 幀 → 至少 1 次 partial callback
        assert len(partial_calls) >= 1
        assert asr.recognize_calls, "偽串流應呼叫 recognize() 進行批次辨識"

        pipeline.stop()

    def test_pseudo_streaming_injects_on_speech_ended(self):
        """偽串流模式：SPEECH_ENDED 時應對完整緩衝區執行最終 ASR 並注入文字。"""
        frames = _make_frames(3)
        pipeline, audio, vad, asr, injector = self._make_pipeline(
            frames=frames,
            batch_text="最終偽串流結果",
            use_pseudo=True,
            pseudo_segment_frames=100,  # 超過幀數，確保不觸發中途辨識
        )
        pipeline.start()

        vad.fire_state_change(VadState.IDLE, VadState.SPEECH)
        for _ in frames:
            pipeline.get_frame(timeout=0.1)
        vad.fire_state_change(VadState.SPEECH, VadState.SPEECH_ENDED)

        assert injector.wait_for_injection(timeout=2.0), "偽串流 SPEECH_ENDED 後應執行最終注入"
        assert "最終偽串流結果" in injector.injected
        assert len(asr.recognize_calls) == 1

        pipeline.stop()

    def test_pseudo_streaming_final_partial_callback_is_final_true(self):
        """偽串流最終辨識時，on_partial callback 的 is_final 應為 True。"""
        partial_calls: list[tuple[str, bool]] = []
        frames = _make_frames(2)
        pipeline, audio, vad, asr, injector = self._make_pipeline(
            frames=frames,
            batch_text="最終結果",
            on_partial=lambda t, f: partial_calls.append((t, f)),
            use_pseudo=True,
            pseudo_segment_frames=100,
        )
        pipeline.start()

        vad.fire_state_change(VadState.IDLE, VadState.SPEECH)
        for _ in frames:
            pipeline.get_frame(timeout=0.1)
        vad.fire_state_change(VadState.SPEECH, VadState.SPEECH_ENDED)

        assert injector.wait_for_injection(timeout=2.0)
        # 最終辨識的 on_partial 應以 is_final=True 呼叫
        final_calls = [(t, f) for t, f in partial_calls if f]
        assert len(final_calls) == 1
        assert final_calls[0][0] == "最終結果"

        pipeline.stop()


# ─────────────────────────────────────────────────────────────────────────────
# 任務 3.1：管線可組合性測試
# ─────────────────────────────────────────────────────────────────────────────


class TestPipelineComposability:
    """驗證管線以依賴注入方式接受任意符合介面的元件。"""

    def test_batch_pipeline_accepts_mock_components(self):
        """BatchRecognitionPipeline 應能以任何 mock 元件建構。"""
        pipeline = BatchRecognitionPipeline(
            MockAudioCapture(),
            MockVadEngine(),
            MockASREngine(),
            MockTextInjector(),
        )
        assert pipeline is not None

    def test_streaming_pipeline_accepts_mock_components(self):
        """StreamingRecognitionPipeline 應能以任何 mock 元件建構。"""
        pipeline = StreamingRecognitionPipeline(
            MockAudioCapture(),
            MockVadEngine(),
            MockASREngine(),
            MockTextInjector(),
        )
        assert pipeline is not None

    def test_batch_pipeline_start_registers_self_as_audio_source(self):
        """BatchRecognitionPipeline.start() 後管線本身應成為 VadEngine 的音訊來源。"""
        vad = MockVadEngine()
        pipeline = BatchRecognitionPipeline(
            MockAudioCapture(), vad, MockASREngine(), MockTextInjector()
        )
        pipeline.start()
        assert vad._audio_source is pipeline

    def test_streaming_pipeline_start_registers_self_as_audio_source(self):
        """StreamingRecognitionPipeline.start() 後管線本身應成為 VadEngine 的音訊來源。"""
        vad = MockVadEngine()
        pipeline = StreamingRecognitionPipeline(
            MockAudioCapture(), vad, MockASREngine(), MockTextInjector()
        )
        pipeline.start()
        assert vad._audio_source is pipeline
        pipeline.stop()


# ─────────────────────────────────────────────────────────────────────────────
# 任務 1.1（23-main-wiring）：flush_and_recognize 測試
# ─────────────────────────────────────────────────────────────────────────────


class TestBatchPipelineFlushAndRecognize:
    """驗證 BatchRecognitionPipeline.flush_and_recognize() 行為。"""

    def _make_pipeline_started(self, frames=None, batch_text="辨識結果"):
        audio = MockAudioCapture(frames or [])
        vad = MockVadEngine()
        asr = MockASREngine(batch_text=batch_text)
        injector = MockTextInjector()
        pipeline = BatchRecognitionPipeline(audio, vad, asr, injector)
        pipeline.start()
        return pipeline, audio, vad, asr, injector

    def test_flush_with_audio_calls_asr(self):
        """flush_and_recognize() 有音訊時應呼叫 ASR 並觸發 on_recognition_complete callback。"""
        results: list[str] = []
        pipeline, audio, vad, asr, injector = self._make_pipeline_started()
        pipeline.on_recognition_complete(results.append)

        # 先模擬 SPEECH 開始累積
        vad.fire_state_change(VadState.IDLE, VadState.SPEECH)
        frame = np.zeros(512, dtype=np.float32)
        pipeline.get_frame.__func__  # 確保 get_frame 存在
        # 直接向 buffer 放入音訊
        with pipeline._lock:
            pipeline._audio_buffer.append(frame.copy())
            pipeline._accumulating = True

        pipeline.flush_and_recognize()

        # 等待 ASR 背景執行緒完成
        pipeline._asr_executor.shutdown(wait=True)
        assert len(results) == 1
        assert results[0] == "辨識結果"

    def test_flush_without_audio_calls_callback_with_empty(self):
        """flush_and_recognize() 無音訊時應呼叫 on_recognition_complete("") callback。"""
        results: list[str] = []
        pipeline, audio, vad, asr, injector = self._make_pipeline_started()
        pipeline.on_recognition_complete(results.append)

        # buffer 為空
        pipeline.flush_and_recognize()

        assert results == [""]

    def test_flush_sets_accumulating_false(self):
        """flush_and_recognize() 應將 _accumulating 設為 False（停止累積）。"""
        pipeline, _, vad, _, _ = self._make_pipeline_started()
        vad.fire_state_change(VadState.IDLE, VadState.SPEECH)
        with pipeline._lock:
            pipeline._accumulating = True

        pipeline.flush_and_recognize()

        with pipeline._lock:
            assert pipeline._accumulating is False

    def test_flush_stops_vad_consuming(self):
        """flush_and_recognize() 應呼叫 vad.stop_consuming()。"""
        pipeline, _, vad, _, _ = self._make_pipeline_started()
        stopped = []
        vad.stop_consuming = lambda: stopped.append(True)

        pipeline.flush_and_recognize()

        assert stopped, "flush_and_recognize 應呼叫 vad.stop_consuming()"
