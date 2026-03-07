"""效能基準測試套件。

使用 pytest-benchmark 量測關鍵路徑延遲並設定迴歸門檻，
符合 specs/performance-optimization/spec.md 所定義的效能目標。

效能目標（PRD §10.1）：
    - 快捷鍵響應      < 100 ms
    - 音波圖幀計算    ≤ 33 ms（≥ 30 FPS）
    - ASR 批次延遲    < 2 s（10 秒音訊，GPU）
    - 端到端（不含 LLM）< 3 s
    - 端到端（含 LLM） < 6 s
    - 閒置 CPU        < 1%
    - 閒置 RAM        < 150 MB

執行方式::

    # 僅執行基準測試
    pytest tests/test_performance.py --benchmark-only

    # 與上次結果比較
    pytest tests/test_performance.py --benchmark-compare

    # 存儲基準結果
    pytest tests/test_performance.py --benchmark-save=baseline
"""

from __future__ import annotations

import importlib.util

import numpy as np
import pytest

# ─── 可選相依 ────────────────────────────────────────────────────────────────

_PSUTIL_AVAILABLE = importlib.util.find_spec("psutil") is not None


# ─── 快捷鍵響應（< 100 ms）──────────────────────────────────────────────────


class TestHotkeyResponseBenchmark:
    """快捷鍵響應延遲 < 100 ms（PRD §10.1）。

    Requirements:
        - Performance Benchmark Suite
        - Hotkey Response Benchmark Scenario
    """

    def test_parse_key_combo(self, benchmark):
        """按鍵組合解析延遲 < 100 ms。

        ``parse_key_combo`` 為純 Python 字串處理，應在微秒級完成。
        此測試防止未來回歸至 100 ms 以上。
        """
        from airtype.core.hotkey import parse_key_combo

        result = benchmark(parse_key_combo, "ctrl+shift+space")

        assert result == "<ctrl>+<shift>+<space>"
        assert benchmark.stats.stats.mean < 0.1  # < 100 ms

    def test_handle_toggle_callback_dispatch(self, benchmark):
        """快捷鍵 toggle callback 派發延遲 < 100 ms。

        量測從快捷鍵事件到 on_start callback 被呼叫的純 Python 開銷。
        """
        from airtype.config import ShortcutsConfig
        from airtype.core.hotkey import HotkeyManager, HotkeyState

        mgr = HotkeyManager(ShortcutsConfig())
        mgr._state = HotkeyState.INACTIVE
        mgr.on_start(lambda: None)

        def toggle_and_reset() -> None:
            mgr._handle_toggle()
            mgr._state = HotkeyState.INACTIVE  # 重設供下一輪使用

        benchmark(toggle_and_reset)

        assert benchmark.stats.stats.mean < 0.1  # < 100 ms


# ─── 音波圖幀率（≥ 30 FPS）──────────────────────────────────────────────────


class TestWaveformFPSBenchmark:
    """音波圖幀計算延遲 ≤ 33 ms（≥ 30 FPS，PRD §10.1）。

    Requirements:
        - Performance Benchmark Suite
    """

    def test_compute_bar_heights_with_audio(self, benchmark):
        """有音訊時每幀計算延遲 ≤ 33 ms。

        ``compute_bar_heights`` 為純 Python 數學計算，
        應遠低於 33 ms 門檻。
        """
        from airtype.ui.waveform_widget import compute_bar_heights

        result = benchmark(compute_bar_heights, 0.7, 1.0)

        assert len(result) == 7
        assert all(h >= 2 for h in result)
        assert benchmark.stats.stats.mean < 0.033  # ≤ 33 ms = ≥ 30 FPS

    def test_compute_bar_heights_silent(self, benchmark):
        """靜音時每幀計算延遲 ≤ 33 ms。

        RMS = 0.0 時所有音波條應為最小高度（BAR_MIN_HEIGHT = 2）。
        """
        from airtype.ui.waveform_widget import BAR_MIN_HEIGHT, compute_bar_heights

        result = benchmark(compute_bar_heights, 0.0, 0.0)

        assert len(result) == 7
        assert all(h == BAR_MIN_HEIGHT for h in result)
        assert benchmark.stats.stats.mean < 0.033  # ≤ 33 ms


# ─── ASR 延遲（mock 管線開銷，目標 < 2s / 10 秒音訊）───────────────────────


class TestASRLatencyBenchmark:
    """ASR 批次辨識延遲 < 2 s（10 秒音訊，PRD §10.1）。

    此類別使用模擬引擎量測管線資料傳遞開銷，不含真實模型推理。
    真實 GPU 延遲測試需在目標硬體上手動執行（見 test_asr_real_gpu_latency）。

    Requirements:
        - Performance Benchmark Suite
    """

    def test_asr_pipeline_overhead(self, benchmark):
        """ASR 管線開銷（不含模型推理）應遠小於 2 s 目標。

        量測音訊陣列傳遞 + ASRResult 物件建立開銷。
        實際 GPU 推理時間由真實硬體測試涵蓋。
        """
        from airtype.core.asr_engine import ASRResult, ASRSegment

        audio = np.zeros(16000 * 10, dtype=np.float32)  # 10 秒音訊

        def mock_asr_recognize(audio_data: np.ndarray) -> ASRResult:
            _ = audio_data[:1]  # 最小存取以量測陣列傳遞開銷
            return ASRResult(
                text="測試辨識文字",
                language="zh-TW",
                confidence=0.95,
                segments=[ASRSegment(text="測試辨識文字", start=0.0, end=2.0)],
            )

        result = benchmark(mock_asr_recognize, audio)

        assert result.text == "測試辨識文字"
        assert benchmark.stats.stats.mean < 2.0  # 管線開銷遠小於 2 s 目標

    @pytest.mark.skip(reason="需要 GPU 硬體與已下載 ASR 模型，請在目標硬體手動執行")
    def test_asr_real_gpu_latency(self, benchmark):
        """真實 ASR GPU 延遲 < 2 s（10 秒音訊）。

        驗證 ASR 引擎在 GPU 上處理 10 秒音訊的實際延遲。
        此測試需要：
            1. 已安裝 GPU 驅動與 CUDA/OpenVINO
            2. 已下載 ASR 模型至 ~/.airtype/models/
        """
        from airtype.config import AirtypeConfig
        from airtype.core.asr_engine import ASREngineRegistry

        config = AirtypeConfig()
        registry = ASREngineRegistry()
        registry.load_default_engine(config)
        engine = registry.active_engine

        audio = np.zeros(16000 * 10, dtype=np.float32)

        result = benchmark(engine.recognize, audio)

        assert result.text is not None
        assert benchmark.stats.stats.mean < 2.0  # < 2 s on GPU


# ─── 端到端延遲（< 3 s 不含 LLM，< 6 s 含 LLM）─────────────────────────────


class TestEndToEndLatencyBenchmark:
    """端到端延遲：不含 LLM < 3 s，含 LLM < 6 s（PRD §10.1）。

    此類別使用模擬引擎量測管線路徑開銷（資料結構建立、函式呼叫等），
    不含真實模型推理。

    Requirements:
        - Performance Benchmark Suite
    """

    def test_e2e_pipeline_overhead_without_llm(self, benchmark):
        """端到端管線開銷（不含 LLM）應遠小於 3 s 目標。

        模擬完整路徑：音訊陣列 → ASRResult 建立 → 文字後處理 → 輸出。
        """
        from airtype.core.asr_engine import ASRResult, ASRSegment

        audio = np.zeros(16000 * 10, dtype=np.float32)

        def e2e_no_llm() -> str:
            _ = audio[:1]  # 模擬音訊傳遞開銷
            result = ASRResult(
                text="頂新 Workflow 測試文字",
                language="zh-TW",
                confidence=0.9,
                segments=[ASRSegment(text="頂新 Workflow 測試文字", start=0.0, end=3.0)],
            )
            return result.text.strip()

        text = benchmark(e2e_no_llm)

        assert text is not None
        assert benchmark.stats.stats.mean < 3.0  # < 3 s 不含 LLM

    def test_e2e_pipeline_overhead_with_llm(self, benchmark):
        """端到端管線開銷（含 LLM mock）應遠小於 6 s 目標。

        模擬含 LLM 路徑：ASRResult → mock LLM 輸出 → 最終文字。
        """
        from airtype.core.asr_engine import ASRResult, ASRSegment

        audio = np.zeros(16000 * 10, dtype=np.float32)

        def e2e_with_llm() -> str:
            _ = audio[:1]
            result = ASRResult(
                text="今天天氣很好呢",
                language="zh-TW",
                confidence=0.88,
                segments=[ASRSegment(text="今天天氣很好呢", start=0.0, end=2.5)],
            )
            # 模擬 LLM 輸出（不含推理延遲）
            return result.text.strip()

        text = benchmark(e2e_with_llm)

        assert text is not None
        assert benchmark.stats.stats.mean < 6.0  # < 6 s 含 LLM

    @pytest.mark.skip(reason="需要已下載的本機 LLM 模型，請在目標硬體手動執行")
    def test_e2e_real_llm_latency(self, benchmark):
        """真實含 LLM 端到端延遲 < 6 s。

        驗證含本機 LLM 推理的完整端到端延遲。
        此測試需要：
            1. 已安裝 llama-cpp-python
            2. 已下載 GGUF 格式 LLM 模型至 ~/.airtype/models/
        """
        from airtype.config import AirtypeConfig
        from airtype.core.llm_polish import PolishEngine

        config = AirtypeConfig()
        engine = PolishEngine(config)

        asr_text = "今天天氣很好，我想要去公園散步。"

        result = benchmark(engine.polish, asr_text)

        assert result is not None
        assert isinstance(result, str)
        assert benchmark.stats.stats.mean < 6.0  # < 6 s 含 LLM 推理


# ─── 資源用量（閒置 CPU < 1%，閒置 RAM < 150 MB）───────────────────────────


class TestResourceUsageBenchmark:
    """閒置資源用量目標（PRD §10.1）。

    Requirements:
        - Resource Usage Targets
        - Measure Idle Resource Usage Scenario
    """

    @pytest.mark.skipif(not _PSUTIL_AVAILABLE, reason="需要 psutil（pip install psutil）")
    def test_idle_memory_below_threshold(self):
        """量測當前進程記憶體用量並驗證未超過門檻。

        生產目標：閒置 RAM < 150 MB。
        此測試在測試環境中量測（含 pytest 框架），
        門檻放寬至 500 MB 以容納測試框架開銷。
        """
        import os

        import psutil

        process = psutil.Process(os.getpid())
        mem_mb = process.memory_info().rss / (1024 * 1024)

        # 測試環境門檻（生產目標：< 150 MB）
        assert mem_mb < 500, (
            f"進程 RAM 用量 {mem_mb:.1f} MB 過高（測試環境門檻 500 MB）。"
            " 生產目標為閒置 < 150 MB。"
        )

    @pytest.mark.skipif(not _PSUTIL_AVAILABLE, reason="需要 psutil（pip install psutil）")
    def test_idle_cpu_below_threshold(self):
        """量測當前進程 CPU 用量並驗證未超過門檻。

        生產目標：閒置 CPU < 1%。
        此測試量測 1 秒平均 CPU 用量。
        門檻放寬至 50% 以容納測試框架開銷。
        """
        import os

        import psutil

        process = psutil.Process(os.getpid())
        cpu_percent = process.cpu_percent(interval=1.0)

        # 測試環境門檻（生產目標：< 1%）
        assert cpu_percent < 50.0, (
            f"進程 CPU 用量 {cpu_percent:.1f}% 過高（測試環境門檻 50%）。"
            " 生產目標為閒置 < 1%。"
        )


# ─── 懶加載與閒置卸載 ────────────────────────────────────────────────────────


class TestIdleUnloaderBenchmark:
    """懶加載與閒置卸載機制驗證。

    Requirements:
        - Lazy Loading and On-Demand Model Management
        - Unload Model After Idle Timeout Scenario
    """

    def test_idle_unloader_mark_used_latency(self, benchmark):
        """``mark_used()`` 呼叫延遲 < 1 ms（每次使用引擎時呼叫）。"""
        from airtype.utils.idle_unloader import IdleUnloader

        calls: list[int] = []
        unloader = IdleUnloader(lambda: calls.append(1), timeout_sec=300.0)
        unloader.start()

        try:
            benchmark(unloader.mark_used)
        finally:
            unloader.stop()

        assert benchmark.stats.stats.mean < 0.001  # < 1 ms

    def test_idle_unloader_triggers_unload_after_timeout(self):
        """閒置逾時後應自動呼叫 unload_fn 並標記為未載入狀態。"""
        import threading

        from airtype.utils.idle_unloader import IdleUnloader

        unloaded = threading.Event()
        unloader = IdleUnloader(
            unload_fn=lambda: unloaded.set(),
            timeout_sec=0.1,       # 極短逾時供測試使用
            check_interval_sec=0.05,
        )
        unloader.mark_used()
        unloader.start()

        triggered = unloaded.wait(timeout=2.0)
        unloader.stop()

        assert triggered, "IdleUnloader 應在逾時後呼叫 unload_fn"
        assert not unloader.is_loaded(), "卸載後 is_loaded() 應回傳 False"

    def test_idle_unloader_mark_used_resets_timer(self):
        """mark_used() 應重設閒置計時器，防止提前卸載。"""
        import time
        import threading

        from airtype.utils.idle_unloader import IdleUnloader

        unloaded = threading.Event()
        unloader = IdleUnloader(
            unload_fn=lambda: unloaded.set(),
            timeout_sec=0.3,
            check_interval_sec=0.05,
        )
        unloader.mark_used()
        unloader.start()

        # 持續 mark_used 直到 0.5 秒
        deadline = time.monotonic() + 0.5
        while time.monotonic() < deadline:
            unloader.mark_used()
            time.sleep(0.05)

        # 在持續使用期間不應觸發卸載
        # （逾時 0.3s，但每 0.05s 重設一次）
        assert not unloaded.is_set(), "持續使用期間不應觸發卸載"

        unloader.stop()
