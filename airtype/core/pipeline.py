"""辨識管線：連接音訊擷取 → VAD → ASR → 文字注入。

兩種管線：
- BatchRecognitionPipeline：VAD 偵測語音結束後整段批次辨識（準確度較高）
- StreamingRecognitionPipeline：逐幀串流辨識，支援即時部分結果；
  另提供偽串流模式（適用於不支援真實串流的引擎）

設計原則：
- 管線作為 VadEngine 的音訊來源代理（提供 ``get_frame()`` 介面）
- 所有元件透過建構子注入，便於測試與替換
- ASR 辨識與文字注入在獨立背景執行緒執行，不阻塞 VAD 消費迴圈

相依：03-vad-engine、05-text-injector、06-asr-abstraction
"""

from __future__ import annotations

import itertools
import logging
import queue
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Callable, Optional

import numpy as np

from airtype.core.vad import VadState

logger = logging.getLogger(__name__)

# 偽串流：預設每段幀數（50 幀 × 512 樣本 @ 16kHz ≈ 1.6 秒）
_DEFAULT_PSEUDO_SEGMENT_FRAMES: int = 50

# 批次 ASR 執行緒計數器（供唯一命名使用）
_batch_asr_seq = itertools.count(1)

# 批次管線 ASR 執行緒池大小（串列處理，避免多個辨識任務並行消耗資源）
_BATCH_ASR_MAX_WORKERS: int = 1

# 偽串流最終辨識哨兵：由 SPEECH_ENDED callback 送入 chunk_queue，
# 確保 worker 在消費完所有音訊幀後再執行最終批次辨識與注入。
_PSEUDO_FINAL: object = object()


class BatchRecognitionPipeline:
    """批次辨識管線。

    作為 VadEngine 的音訊來源代理（提供 ``get_frame()``），
    在 SPEECH / SILENCE_COUNTING 狀態期間累積音訊幀。當 VadEngine 發出
    SPEECH_ENDED 事件時，將完整音訊緩衝區送至 ASR 進行批次辨識，
    並將辨識結果注入文字。

    Args:
        audio_capture:    音訊擷取服務（需提供 ``get_frame(timeout)`` 方法）。
        vad_engine:       VAD 引擎（需提供 ``on_state_change``、
                          ``start_consuming``、``stop_consuming`` 方法）。
        asr_engine:       ASR 引擎（符合 ASREngine Protocol，需提供 ``recognize``）。
        text_injector:    文字注入器（需提供 ``inject(text)`` 方法）。
        dictionary_engine: 辭典引擎（可選），用於 ASR 後文字後處理。
    """

    def __init__(
        self,
        audio_capture,
        vad_engine,
        asr_engine,
        text_injector,
        dictionary_engine=None,
        on_asr_engine_used: Optional[Callable[[], None]] = None,
        asr_language: str = "zh-TW",
    ) -> None:
        self._audio_capture = audio_capture
        self._vad_engine = vad_engine
        self._asr_engine = asr_engine
        self._text_injector = text_injector
        self._dictionary_engine = dictionary_engine
        self._on_asr_engine_used = on_asr_engine_used

        self._audio_buffer: list[np.ndarray] = []
        self._accumulating: bool = False
        self._lock = threading.Lock()

        self._on_recognition_cb: Optional[Callable[[str], None]] = None
        self._on_error_cb: Optional[Callable[[str], None]] = None

        # 簡體→繁體轉換器（僅 zh-TW 啟用）
        self._s2t_converter = None
        if asr_language == "zh-TW":
            try:
                from opencc import OpenCC
                self._s2t_converter = OpenCC("s2t")
                logger.debug("已啟用簡→繁轉換（OpenCC s2t）")
            except ImportError:
                logger.warning("OpenCC 未安裝，無法進行簡繁轉換")

        # 使用固定大小執行緒池（max_workers=1）確保 ASR 任務串列執行，
        # 避免並行辨識消耗過多 CPU / RAM 資源（設計：audio=1, ASR=1, LLM=1 on-demand）
        self._asr_executor = ThreadPoolExecutor(
            max_workers=_BATCH_ASR_MAX_WORKERS,
            thread_name_prefix="batch-asr",
        )

        # 向 VadEngine 註冊狀態轉換 callback
        self._vad_engine.on_state_change(self._on_vad_state_change)

    # ------------------------------------------------------------------
    # 公開介面
    # ------------------------------------------------------------------

    def on_recognition_complete(self, callback: Callable[[str], None]) -> None:
        """註冊辨識完成事件 callback。

        Args:
            callback: 接受辨識文字字串的函式。
        """
        self._on_recognition_cb = callback

    def on_error(self, callback: Callable[[str], None]) -> None:
        """註冊管線錯誤事件 callback。

        Args:
            callback: 接受錯誤訊息字串的函式。
        """
        self._on_error_cb = callback

    def start(self) -> None:
        """啟動管線：立即開始累積音訊，VadEngine 開始消費。

        手動模式下（快捷鍵控制開始/結束），不依賴 VAD 偵測語音才累積，
        而是一啟動就開始累積所有音訊幀。VAD 狀態轉換仍可觸發
        SPEECH_ENDED 自動送出辨識。
        """
        # 清空音訊擷取的 frame queue，丟棄按下快捷鍵前的殘留幀
        self._drain_frame_queue()
        with self._lock:
            self._audio_buffer.clear()
            self._accumulating = True
        self._vad_engine.start_consuming(self)
        logger.info("批次辨識管線已啟動（已開始累積音訊）")

    def stop(self) -> None:
        """停止管線：通知 VadEngine 停止消費音訊並關閉執行緒池。"""
        self._vad_engine.stop_consuming()
        self._asr_executor.shutdown(wait=False, cancel_futures=True)
        logger.info("批次辨識管線已停止")

    def flush_and_recognize(self) -> None:
        """手動停止時強制觸發 ASR（Flush and Recognize on Manual Stop）。

        停止音訊累積，停止 VAD 消費，取出緩衝區送 ASR 背景執行緒。
        若緩衝區無音訊，直接呼叫 ``_on_recognition_cb("")``。
        """
        with self._lock:
            self._accumulating = False
            if self._audio_buffer:
                audio = np.concatenate(self._audio_buffer)
                self._audio_buffer.clear()
            else:
                audio = np.array([], dtype=np.float32)

        self._vad_engine.stop_consuming()

        if len(audio) > 0:
            self._asr_executor.submit(self._run_asr_and_inject, audio)
            logger.debug("批次管線：flush_and_recognize 送出 %d 樣本至 ASR", len(audio))
        else:
            logger.debug("批次管線：flush_and_recognize 無音訊，直接回傳空字串")
            if self._on_recognition_cb is not None:
                self._on_recognition_cb("")

    def get_frame(self, timeout: float = 0.05) -> Optional[np.ndarray]:
        """VadEngine 音訊來源代理。

        從真實音訊擷取服務取得幀，並在 SPEECH / SILENCE_COUNTING
        狀態期間將副本累積至緩衝區。

        Args:
            timeout: 等待逾時秒數（傳遞至底層 ``get_frame``）。

        Returns:
            音訊幀（1-D float32 ndarray），或逾時時回傳 None。
        """
        frame = self._audio_capture.get_frame(timeout=timeout)
        if frame is not None:
            with self._lock:
                if self._accumulating:
                    self._audio_buffer.append(frame.copy())
        return frame

    def _convert_s2t(self, text: str) -> str:
        """簡體中文→繁體中文轉換（若已啟用）。"""
        if self._s2t_converter and text:
            return self._s2t_converter.convert(text)
        return text

    def _drain_frame_queue(self) -> None:
        """清空音訊擷取的 frame queue，丟棄按下快捷鍵前的殘留幀。"""
        drained = 0
        while True:
            frame = self._audio_capture.get_frame(timeout=0)
            if frame is None:
                break
            drained += 1
        if drained > 0:
            logger.debug("已丟棄 %d 個殘留音訊幀", drained)

    # ------------------------------------------------------------------
    # 內部：VAD callback
    # ------------------------------------------------------------------

    def _on_vad_state_change(self, prev: VadState, new: VadState) -> None:
        """VAD 狀態轉換 callback（由 VadEngine 在其消費執行緒中呼叫）。

        - SPEECH 開始：清空緩衝區並開始累積。
        - SILENCE_COUNTING：繼續累積（靜默期間語音可能尚未結束）。
        - SPEECH_ENDED：停止累積，取出緩衝區，啟動 ASR 背景執行緒。
        - IDLE：無需操作。
        """
        if new == VadState.SPEECH:
            with self._lock:
                self._audio_buffer.clear()
                self._accumulating = True
            logger.debug("批次管線：開始累積音訊")

        elif new == VadState.SILENCE_COUNTING:
            # 保持累積，等待確認語音段是否真正結束
            pass

        elif new == VadState.SPEECH_ENDED:
            with self._lock:
                self._accumulating = False
                if self._audio_buffer:
                    audio = np.concatenate(self._audio_buffer)
                    self._audio_buffer.clear()
                else:
                    audio = np.array([], dtype=np.float32)

            if len(audio) > 0:
                self._asr_executor.submit(self._run_asr_and_inject, audio)
            else:
                logger.debug("批次管線：SPEECH_ENDED 但無累積音訊，略過辨識")

        elif new == VadState.IDLE:
            pass

    # ------------------------------------------------------------------
    # 內部：ASR 執行緒
    # ------------------------------------------------------------------

    def _run_asr_and_inject(self, audio: np.ndarray) -> None:
        """在背景執行緒中進行批次 ASR 辨識並注入結果。

        辭典後處理僅套用於直接注入路徑（standalone 使用）。
        若管線已連接至 CoreController callback，則傳遞原始 ASR 文字，
        由 controller 負責辭典後處理，避免雙重套用。
        """
        try:
            if self._on_asr_engine_used is not None:
                self._on_asr_engine_used()
            result = self._asr_engine.recognize(audio)
            raw_text = result.text.strip()
            # 簡體→繁體轉換（若 ASR 語言設定為 zh-TW）
            raw_text = self._convert_s2t(raw_text)
            if raw_text:
                if self._on_recognition_cb is not None:
                    # Controller 路徑：傳原始文字，由 controller 統一套用辭典 + LLM
                    logger.debug("批次管線：辨識完成（%d 字），交由 controller 處理", len(raw_text))
                    self._on_recognition_cb(raw_text)
                else:
                    # Standalone 路徑：pipeline 直接套用辭典並注入
                    inject_text = raw_text
                    if self._dictionary_engine is not None:
                        inject_text = self._dictionary_engine.apply_rules(raw_text)
                    logger.debug("批次管線：辨識完成（%d 字），直接注入", len(inject_text))
                    self._text_injector.inject(inject_text)
            else:
                logger.debug("批次管線：辨識結果為空，略過注入")
        except Exception as exc:
            logger.error("批次管線 ASR/注入失敗：%s", exc)
            if self._on_error_cb is not None:
                self._on_error_cb(str(exc))


class StreamingRecognitionPipeline:
    """串流辨識管線。

    支援兩種子模式：

    **真實串流** (``use_pseudo_streaming=False``，預設)：
    SPEECH 狀態期間，每個音訊幀透過 ``asr_engine.recognize_stream()``
    送入引擎取得部分結果；``is_final=True`` 時注入最終文字。

    **偽串流** (``use_pseudo_streaming=True``)：
    每累積 ``pseudo_segment_frames`` 幀，呼叫 ``asr_engine.recognize()``
    批次辨識並以 ``on_partial`` 回報部分結果（``is_final=False``）。
    適用於不支援真實串流的引擎（例如 OpenVINO、Breeze-ASR）。

    Args:
        audio_capture:        音訊擷取服務。
        vad_engine:           VAD 引擎。
        asr_engine:           ASR 引擎。
        text_injector:        文字注入器。
        on_partial:           部分結果 callback：``(text: str, is_final: bool) → None``。
        use_pseudo_streaming: True 則使用偽串流模式。
        pseudo_segment_frames: 偽串流每段幀數（預設 50 ≈ 1.6 秒）。
        dictionary_engine:    辭典引擎（可選），用於 ASR 後文字後處理。
    """

    def __init__(
        self,
        audio_capture,
        vad_engine,
        asr_engine,
        text_injector,
        on_partial: Optional[Callable[[str, bool], None]] = None,
        use_pseudo_streaming: bool = False,
        pseudo_segment_frames: int = _DEFAULT_PSEUDO_SEGMENT_FRAMES,
        dictionary_engine=None,
        on_asr_engine_used: Optional[Callable[[], None]] = None,
        asr_language: str = "zh-TW",
    ) -> None:
        self._audio_capture = audio_capture
        self._vad_engine = vad_engine
        self._asr_engine = asr_engine
        self._text_injector = text_injector
        self._on_partial = on_partial
        self._use_pseudo = use_pseudo_streaming
        self._pseudo_segment_frames = pseudo_segment_frames
        self._dictionary_engine = dictionary_engine
        self._on_asr_engine_used = on_asr_engine_used

        self._on_recognition_cb: Optional[Callable[[str], None]] = None
        self._on_error_cb: Optional[Callable[[str], None]] = None

        # 簡體→繁體轉換器（僅 zh-TW 啟用）
        self._s2t_converter = None
        if asr_language == "zh-TW":
            try:
                from opencc import OpenCC
                self._s2t_converter = OpenCC("s2t")
            except ImportError:
                pass

        self._streaming_active: bool = False
        self._chunk_queue: queue.Queue = queue.Queue(maxsize=200)
        self._pseudo_buffer: list[np.ndarray] = []
        self._lock = threading.Lock()
        self._worker_thread: Optional[threading.Thread] = None

        self._vad_engine.on_state_change(self._on_vad_state_change)

    # ------------------------------------------------------------------
    # 公開介面
    # ------------------------------------------------------------------

    def on_recognition_complete(self, callback: Callable[[str], None]) -> None:
        """註冊辨識完成事件 callback（走 controller 路徑）。"""
        self._on_recognition_cb = callback

    def on_error(self, callback: Callable[[str], None]) -> None:
        """註冊管線錯誤事件 callback。"""
        self._on_error_cb = callback

    def start(self) -> None:
        """啟動串流管線：清空殘留幀、開啟工作執行緒並啟動 VAD 消費。"""
        self._drain_frame_queue()
        # 清空 chunk queue 殘留項目
        while not self._chunk_queue.empty():
            try:
                self._chunk_queue.get_nowait()
            except queue.Empty:
                break
        with self._lock:
            self._pseudo_buffer.clear()
            self._streaming_active = True
        self._worker_thread = threading.Thread(
            target=self._stream_worker,
            daemon=True,
            name="stream-asr",
        )
        self._worker_thread.start()
        self._vad_engine.start_consuming(self)
        logger.info("串流辨識管線已啟動（偽串流=%s）", self._use_pseudo)

    def stop(self) -> None:
        """停止串流管線：終止工作執行緒並停止 VAD 消費。"""
        self._vad_engine.stop_consuming()
        # 送入哨兵值（None）以終止工作執行緒
        self._chunk_queue.put(None)
        if self._worker_thread is not None and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=2.0)
        logger.info("串流辨識管線已停止")

    def flush_and_recognize(self) -> None:
        """手動停止時強制觸發最終辨識（與批次管線介面一致）。"""
        with self._lock:
            self._streaming_active = False
        self._vad_engine.stop_consuming()
        # 送入停止哨兵終止 worker，並等待它結束（避免 ASR 並行衝突）
        self._chunk_queue.put(None)
        if self._worker_thread is not None and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=5.0)

        # worker 結束後才安全取出 buffer 做最終辨識
        with self._lock:
            if self._pseudo_buffer:
                audio = np.concatenate(self._pseudo_buffer)
                self._pseudo_buffer.clear()
            else:
                audio = np.array([], dtype=np.float32)

        if len(audio) > 0:
            # 在背景執行緒做 ASR，避免阻塞 hotkey thread
            t = threading.Thread(
                target=self._run_final_recognize,
                args=(audio,),
                daemon=True,
                name="stream-final-asr",
            )
            t.start()
        else:
            logger.debug("串流管線：flush_and_recognize 無音訊")
            if self._on_recognition_cb is not None:
                self._on_recognition_cb("")

    def _drain_frame_queue(self) -> None:
        """清空音訊擷取的 frame queue。"""
        drained = 0
        while True:
            frame = self._audio_capture.get_frame(timeout=0)
            if frame is None:
                break
            drained += 1
        if drained > 0:
            logger.debug("已丟棄 %d 個殘留音訊幀", drained)

    def _convert_s2t(self, text: str) -> str:
        """簡體中文→繁體中文轉換（若已啟用）。"""
        if self._s2t_converter and text:
            return self._s2t_converter.convert(text)
        return text

    def get_frame(self, timeout: float = 0.05) -> Optional[np.ndarray]:
        """VadEngine 音訊來源代理。

        從音訊擷取服務取得幀；若處於 SPEECH 活躍狀態，
        將幀副本加入串流工作 queue 供工作執行緒處理。

        Args:
            timeout: 等待逾時秒數。

        Returns:
            音訊幀（1-D float32 ndarray），或逾時時回傳 None。
        """
        frame = self._audio_capture.get_frame(timeout=timeout)
        if frame is not None:
            with self._lock:
                active = self._streaming_active
            if active:
                try:
                    self._chunk_queue.put_nowait(frame.copy())
                except queue.Full:
                    logger.warning("串流 queue 已滿，丟棄音訊幀")
        return frame

    # ------------------------------------------------------------------
    # 內部：VAD callback
    # ------------------------------------------------------------------

    def _on_vad_state_change(self, prev: VadState, new: VadState) -> None:
        if new == VadState.SPEECH:
            with self._lock:
                self._pseudo_buffer.clear()
                self._streaming_active = True
            logger.debug("串流管線：開始串流辨識")

        elif new == VadState.SPEECH_ENDED:
            with self._lock:
                self._streaming_active = False
            if self._use_pseudo:
                # 將哨兵送至 queue 末端，確保 worker 在消費完所有音訊幀
                # 後才執行最終批次辨識，避免擷取 _pseudo_buffer 的競態條件。
                try:
                    self._chunk_queue.put(_PSEUDO_FINAL, timeout=1.0)
                except queue.Full:
                    logger.warning("串流 queue 已滿，偽串流最終辨識哨兵遺失")
            logger.debug("串流管線：串流辨識段落結束")

        elif new in (VadState.SILENCE_COUNTING, VadState.IDLE):
            pass

    # ------------------------------------------------------------------
    # 內部：串流工作執行緒
    # ------------------------------------------------------------------

    def _stream_worker(self) -> None:
        """串流 ASR 工作執行緒主迴圈。

        持續從 chunk_queue 取出項目並處理：
        - ``None``：停止哨兵，終止執行緒。
        - ``_PSEUDO_FINAL``：偽串流最終辨識哨兵，執行最終 ASR 並注入。
        - ``np.ndarray``：音訊幀，依模式送至串流或偽串流處理。
        """
        while True:
            item = self._chunk_queue.get()
            if item is None:
                break  # 停止哨兵，終止執行緒
            if item is _PSEUDO_FINAL:
                self._run_pseudo_final()
                continue
            chunk: np.ndarray = item  # type: ignore[assignment]
            if self._use_pseudo:
                self._process_pseudo_chunk(chunk)
            else:
                self._process_stream_chunk(chunk)

    def _process_stream_chunk(self, chunk: np.ndarray) -> None:
        """真實串流：呼叫 recognize_stream() 處理單一音訊幀。"""
        try:
            result = self._asr_engine.recognize_stream(chunk)
            if result.text:
                text = self._convert_s2t(result.text)
                if self._on_partial is not None:
                    self._on_partial(text, result.is_final)
                if result.is_final and text.strip():
                    self._run_final_recognize_text(text.strip())
        except Exception as exc:
            logger.error("串流管線 recognize_stream 失敗：%s", exc)
            if self._on_error_cb is not None:
                self._on_error_cb(str(exc))

    def _process_pseudo_chunk(self, chunk: np.ndarray) -> None:
        """偽串流：累積幀，每達 pseudo_segment_frames 幀執行一次批次辨識。"""
        with self._lock:
            self._pseudo_buffer.append(chunk)
            count = len(self._pseudo_buffer)

        if count % self._pseudo_segment_frames == 0:
            with self._lock:
                audio = np.concatenate(self._pseudo_buffer)
            try:
                if self._on_asr_engine_used is not None:
                    self._on_asr_engine_used()
                result = self._asr_engine.recognize(audio)
                if result.text:
                    text = self._convert_s2t(result.text)
                    if self._on_partial is not None:
                        self._on_partial(text, False)
            except Exception as exc:
                logger.error("偽串流管線批次辨識失敗：%s", exc)

    def _run_pseudo_final(self) -> None:
        """偽串流最終辨識：對完整 _pseudo_buffer 執行批次 ASR。"""
        with self._lock:
            if not self._pseudo_buffer:
                return
            audio = np.concatenate(self._pseudo_buffer)
        self._run_final_recognize(audio)

    def _run_final_recognize(self, audio: np.ndarray) -> None:
        """對音訊執行最終 ASR 辨識，走 controller 路徑或直接注入。"""
        try:
            if self._on_asr_engine_used is not None:
                self._on_asr_engine_used()
            result = self._asr_engine.recognize(audio)
            text = self._convert_s2t(result.text.strip())
            if text:
                self._run_final_recognize_text(text)
            else:
                logger.debug("串流管線：最終辨識結果為空")
                if self._on_recognition_cb is not None:
                    self._on_recognition_cb("")
        except Exception as exc:
            logger.error("串流管線最終辨識失敗：%s", exc)
            if self._on_error_cb is not None:
                self._on_error_cb(str(exc))

    def _run_final_recognize_text(self, text: str) -> None:
        """處理最終辨識文字：走 controller 路徑或直接注入。"""
        if self._on_partial is not None:
            self._on_partial(text, True)
        if self._on_recognition_cb is not None:
            logger.debug("串流管線：辨識完成（%d 字），交由 controller 處理", len(text))
            self._on_recognition_cb(text)
        else:
            if self._dictionary_engine is not None:
                text = self._dictionary_engine.apply_rules(text)
            logger.debug("串流管線：辨識完成（%d 字），直接注入", len(text))
            self._text_injector.inject(text)
