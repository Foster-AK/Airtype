"""音訊擷取模組測試。

涵蓋：
- RingBuffer 單元測試（累積、溢位、clear）
- compute_rms 單元測試（已知訊號）
- AudioCaptureService 整合測試（mock sounddevice）
"""

from __future__ import annotations

import queue
import unittest
from unittest.mock import MagicMock, patch

import numpy as np

from airtype.utils.audio_utils import RingBuffer, compute_rms


# ---------------------------------------------------------------------------
# 4.1 RingBuffer 單元測試
# ---------------------------------------------------------------------------

class TestRingBuffer(unittest.TestCase):
    """環形緩衝區單元測試：累積、溢位、邊界條件。"""

    def test_empty_buffer_returns_empty(self):
        buf = RingBuffer(100)
        result = buf.read_all()
        self.assertEqual(len(result), 0)
        self.assertEqual(buf.count, 0)

    def test_accumulate_below_capacity(self):
        """寫入少於容量的資料，read_all 回傳全部樣本。"""
        buf = RingBuffer(100)
        data = np.ones(50, dtype=np.float32)
        buf.write(data)
        result = buf.read_all()
        self.assertEqual(len(result), 50)
        np.testing.assert_array_almost_equal(result, data)

    def test_accumulate_to_capacity(self):
        """寫入恰好等於容量的資料，read_all 回傳全部 capacity 個樣本。"""
        buf = RingBuffer(100)
        data = np.arange(100, dtype=np.float32)
        buf.write(data)
        result = buf.read_all()
        self.assertEqual(len(result), 100)
        np.testing.assert_array_almost_equal(result, data)

    def test_overflow_overwrites_oldest(self):
        """緩衝區滿後繼續寫入，最舊資料應被覆寫。"""
        buf = RingBuffer(10)
        buf.write(np.zeros(10, dtype=np.float32))
        buf.write(np.ones(5, dtype=np.float32))
        result = buf.read_all()
        self.assertEqual(len(result), 10)
        # 最舊的 5 個零 → 已被覆寫，最新的 5 個零保留
        np.testing.assert_array_almost_equal(result[:5], np.zeros(5, dtype=np.float32))
        np.testing.assert_array_almost_equal(result[5:], np.ones(5, dtype=np.float32))

    def test_overflow_large_write_keeps_last_capacity(self):
        """一次寫入超過容量的資料，應只保留最後 capacity 個樣本。"""
        buf = RingBuffer(10)
        data = np.arange(25, dtype=np.float32)
        buf.write(data)
        result = buf.read_all()
        self.assertEqual(len(result), 10)
        np.testing.assert_array_almost_equal(result, data[-10:])

    def test_multiple_small_writes_with_overflow(self):
        """多次小量寫入，確認環形覆寫順序正確。"""
        buf = RingBuffer(6)
        for i in range(4):
            buf.write(np.full(3, float(i), dtype=np.float32))
        result = buf.read_all()
        self.assertEqual(len(result), 6)
        # 最後兩批 [2,2,2] 和 [3,3,3]
        np.testing.assert_array_almost_equal(
            result,
            np.array([2, 2, 2, 3, 3, 3], dtype=np.float32),
        )

    def test_clear_resets_buffer(self):
        """clear 後緩衝區應為空。"""
        buf = RingBuffer(10)
        buf.write(np.ones(10, dtype=np.float32))
        buf.clear()
        result = buf.read_all()
        self.assertEqual(len(result), 0)
        self.assertEqual(buf.count, 0)

    def test_ring_buffer_3sec_capacity(self):
        """驗證 3 秒環形緩衝區容量（16kHz = 48000 樣本）。"""
        buf = RingBuffer(48_000)
        self.assertEqual(buf.capacity, 48_000)

    def test_write_empty_array(self):
        """寫入空陣列不應影響緩衝區狀態。"""
        buf = RingBuffer(10)
        buf.write(np.zeros(5, dtype=np.float32))
        buf.write(np.array([], dtype=np.float32))
        self.assertEqual(buf.count, 5)


# ---------------------------------------------------------------------------
# 4.2 RMS 計算單元測試
# ---------------------------------------------------------------------------

class TestComputeRms(unittest.TestCase):
    """RMS 音量計算單元測試：已知訊號 → 預期 RMS 值。"""

    def test_silence_rms_is_zero(self):
        """靜音（全零訊號）RMS 應等於 0。"""
        frame = np.zeros(512, dtype=np.float32)
        self.assertAlmostEqual(compute_rms(frame), 0.0, places=6)

    def test_sine_wave_rms(self):
        """正弦波 RMS = amplitude / sqrt(2) ≈ 0.7071（amplitude=1）。"""
        t = np.linspace(0, 2 * np.pi, 512, endpoint=False)
        frame = np.sin(t).astype(np.float32)
        rms = compute_rms(frame)
        self.assertAlmostEqual(rms, 1.0 / np.sqrt(2), places=2)

    def test_dc_signal_rms(self):
        """DC 訊號（常數值）RMS 應等於該常數的絕對值。"""
        frame = np.full(512, 0.5, dtype=np.float32)
        self.assertAlmostEqual(compute_rms(frame), 0.5, places=5)

    def test_negative_dc_signal_rms(self):
        """負 DC 訊號 RMS 與正數相同。"""
        frame = np.full(512, -0.3, dtype=np.float32)
        self.assertAlmostEqual(compute_rms(frame), 0.3, places=5)

    def test_empty_frame_rms_is_zero(self):
        """空幀 RMS 應為 0。"""
        frame = np.array([], dtype=np.float32)
        self.assertEqual(compute_rms(frame), 0.0)

    def test_voice_rms_greater_than_silence(self):
        """語音訊號 RMS 應大於靜音 RMS（符合 spec §語音期間 RMS 情境）。"""
        silence = np.zeros(512, dtype=np.float32)
        voice = np.random.default_rng(42).uniform(-0.5, 0.5, 512).astype(np.float32)
        self.assertGreater(compute_rms(voice), compute_rms(silence))

    def test_single_sample(self):
        """單樣本 RMS 應等於該樣本的絕對值。"""
        frame = np.array([0.8], dtype=np.float32)
        self.assertAlmostEqual(compute_rms(frame), 0.8, places=5)


# ---------------------------------------------------------------------------
# 4.3 AudioCaptureService 整合測試
# ---------------------------------------------------------------------------

class TestAudioCaptureServiceIntegration(unittest.TestCase):
    """整合測試：mock sounddevice，驗證擷取流程。"""

    def _make_mock_stream_class(self, callback_store: list):
        """建立 MockInputStream，捕獲 callback 函式。"""

        class MockInputStream:
            def __init__(self, **kwargs):
                callback_store.append(kwargs.get("callback"))

            def start(self):
                pass

            def stop(self):
                pass

            def close(self):
                pass

        return MockInputStream

    def test_start_stop_receives_frames(self):
        """啟動擷取 → 模擬 callback → 停止 → 驗證已接收幀。"""
        from airtype.config import AirtypeConfig
        from airtype.core.audio_capture import AudioCaptureService

        config = AirtypeConfig()
        config.voice.input_device = "default"

        callback_store: list = []
        MockStream = self._make_mock_stream_class(callback_store)

        with patch("sounddevice.InputStream", MockStream):
            service = AudioCaptureService(config)
            service.start()

            self.assertTrue(service.is_capturing)
            self.assertIsNotNone(callback_store[0])
            callback = callback_store[0]

            # 模擬 3 幀音訊資料
            for _ in range(3):
                indata = np.random.default_rng(0).uniform(
                    -0.1, 0.1, (512, 1)
                ).astype(np.float32)
                callback(indata, 512, None, None)

            # 驗證三幀均已進入 queue
            frames_received = 0
            for _ in range(3):
                frame = service.get_frame(timeout=0.5)
                self.assertIsNotNone(frame)
                self.assertEqual(frame.shape, (512,))
                frames_received += 1

            self.assertEqual(frames_received, 3)

            service.stop()
            self.assertFalse(service.is_capturing)

    def test_rms_updated_after_callback(self):
        """callback 執行後 rms 屬性應反映計算結果。"""
        from airtype.config import AirtypeConfig
        from airtype.core.audio_capture import AudioCaptureService

        config = AirtypeConfig()
        callback_store: list = []
        MockStream = self._make_mock_stream_class(callback_store)

        with patch("sounddevice.InputStream", MockStream):
            service = AudioCaptureService(config)
            service.start()
            callback = callback_store[0]

            indata = np.full((512, 1), 0.5, dtype=np.float32)
            callback(indata, 512, None, None)

            self.assertAlmostEqual(service.rms, 0.5, places=4)
            service.stop()

    def test_ring_buffer_populated_after_callback(self):
        """callback 執行後環形緩衝區應包含音訊樣本。"""
        from airtype.config import AirtypeConfig
        from airtype.core.audio_capture import AudioCaptureService

        config = AirtypeConfig()
        callback_store: list = []
        MockStream = self._make_mock_stream_class(callback_store)

        with patch("sounddevice.InputStream", MockStream):
            service = AudioCaptureService(config)
            service.start()
            callback = callback_store[0]

            indata = np.ones((512, 1), dtype=np.float32)
            callback(indata, 512, None, None)

            result = service.ring_buffer.read_all()
            self.assertEqual(len(result), 512)
            np.testing.assert_array_almost_equal(result, np.ones(512, dtype=np.float32))
            service.stop()

    def test_device_switch_restarts_capture(self):
        """set_device 應停止舊串流並以新裝置重新啟動。"""
        from airtype.config import AirtypeConfig
        from airtype.core.audio_capture import AudioCaptureService

        config = AirtypeConfig()
        config.voice.input_device = "default"

        start_call_count = [0]

        class MockStream:
            def __init__(self, **kwargs):
                start_call_count[0] += 1
                self.device = kwargs.get("device")

            def start(self):
                pass

            def stop(self):
                pass

            def close(self):
                pass

        with patch("sounddevice.InputStream", MockStream):
            service = AudioCaptureService(config)
            service.start()          # 第一次啟動
            self.assertEqual(start_call_count[0], 1)

            service.set_device(1)    # 切換裝置 → 停止 + 重新啟動
            self.assertEqual(start_call_count[0], 2)
            self.assertTrue(service.is_capturing)
            self.assertEqual(config.voice.input_device, 1)

            service.stop()

    def test_list_devices_returns_input_devices(self):
        """list_devices 應回傳只有輸入裝置的清單（名稱不重複）。"""
        from airtype.config import AirtypeConfig
        from airtype.core.audio_capture import AudioCaptureService, DeviceInfo

        config = AirtypeConfig()
        fake_devices = [
            {"name": "麥克風 A", "max_input_channels": 2, "max_output_channels": 0, "hostapi": 0},
            {"name": "喇叭 B", "max_input_channels": 0, "max_output_channels": 2, "hostapi": 0},
            {"name": "麥克風 C", "max_input_channels": 1, "max_output_channels": 0, "hostapi": 0},
        ]

        with patch("sounddevice.query_devices", return_value=fake_devices), \
             patch("sounddevice.query_hostapis", return_value=[]):
            service = AudioCaptureService(config)
            devices = service.list_devices()

        self.assertEqual(len(devices), 2)
        self.assertIsInstance(devices[0], DeviceInfo)
        self.assertEqual(devices[0].name, "麥克風 A")
        self.assertEqual(devices[1].name, "麥克風 C")

    def test_list_devices_no_input_returns_empty(self):
        """無輸入裝置時 list_devices 應回傳空清單。"""
        from airtype.config import AirtypeConfig
        from airtype.core.audio_capture import AudioCaptureService

        config = AirtypeConfig()
        fake_devices = [
            {"name": "喇叭", "max_input_channels": 0, "max_output_channels": 2, "hostapi": 0},
        ]

        with patch("sounddevice.query_devices", return_value=fake_devices), \
             patch("sounddevice.query_hostapis", return_value=[]):
            service = AudioCaptureService(config)
            devices = service.list_devices()

        self.assertEqual(devices, [])

    def test_list_devices_deduplicates_same_name_across_hostapis(self):
        """同名裝置跨 Host API 出現時，list_devices 應只回傳一個。"""
        from airtype.config import AirtypeConfig
        from airtype.core.audio_capture import AudioCaptureService

        config = AirtypeConfig()
        fake_devices = [
            {"name": "麥克風 A", "max_input_channels": 2, "max_output_channels": 0, "hostapi": 0},
            {"name": "麥克風 A", "max_input_channels": 2, "max_output_channels": 0, "hostapi": 1},
            {"name": "麥克風 C", "max_input_channels": 1, "max_output_channels": 0, "hostapi": 0},
        ]
        fake_hostapis = [
            {"name": "MME"},
            {"name": "DirectSound"},
        ]

        with patch("sounddevice.query_devices", return_value=fake_devices), \
             patch("sounddevice.query_hostapis", return_value=fake_hostapis), \
             patch("sys.platform", "win32"):
            service = AudioCaptureService(config)
            devices = service.list_devices()

        names = [d.name for d in devices]
        self.assertEqual(len(devices), 2)
        self.assertEqual(names.count("麥克風 A"), 1)


class TestInvalidDeviceFallback(unittest.TestCase):
    """fix-device-name-collision: invalid device index fallback 測試。"""

    def test_invalid_int_index_falls_back_to_default(self):
        """傳入不存在的 int device index 時，應 fallback 至系統預設裝置。"""
        import sounddevice as sd

        from airtype.config import AirtypeConfig
        from airtype.core.audio_capture import AudioCaptureService

        config = AirtypeConfig()
        call_log: list = []

        class MockInputStream:
            def __init__(self, **kwargs):
                device = kwargs.get("device")
                call_log.append(device)
                if device == 9999:
                    raise sd.PortAudioError("Invalid device")

            def start(self):
                pass

            def stop(self):
                pass

            def close(self):
                pass

        with patch("sounddevice.InputStream", MockInputStream):
            service = AudioCaptureService(config)
            # 不應拋異常
            service.start(device=9999)
            self.assertTrue(service.is_capturing)
            # 應該先嘗試 9999，失敗後 fallback 至 None（預設）
            self.assertEqual(call_log, [9999, None])
            service.stop()

    def test_valid_int_index_no_fallback(self):
        """傳入有效 int device index 時，不應 fallback。"""
        from airtype.config import AirtypeConfig
        from airtype.core.audio_capture import AudioCaptureService

        config = AirtypeConfig()
        call_log: list = []

        class MockInputStream:
            def __init__(self, **kwargs):
                call_log.append(kwargs.get("device"))

            def start(self):
                pass

            def stop(self):
                pass

            def close(self):
                pass

        with patch("sounddevice.InputStream", MockInputStream):
            service = AudioCaptureService(config)
            service.start(device=3)
            self.assertTrue(service.is_capturing)
            self.assertEqual(call_log, [3])
            service.stop()

    def test_default_string_works_normally(self):
        """device="default" 應正常啟動（sd_device=None）。"""
        from airtype.config import AirtypeConfig
        from airtype.core.audio_capture import AudioCaptureService

        config = AirtypeConfig()
        call_log: list = []

        class MockInputStream:
            def __init__(self, **kwargs):
                call_log.append(kwargs.get("device"))

            def start(self):
                pass

            def stop(self):
                pass

            def close(self):
                pass

        with patch("sounddevice.InputStream", MockInputStream):
            service = AudioCaptureService(config)
            service.start(device="default")
            self.assertTrue(service.is_capturing)
            self.assertEqual(call_log, [None])
            service.stop()


# ---------------------------------------------------------------------------
# WASAPI auto_convert extra_settings 測試
# ---------------------------------------------------------------------------

class TestWasapiExtraSettings(unittest.TestCase):
    """WASAPI auto_convert 平台特定設定測試。"""

    def test_extra_settings_wasapi_on_windows(self):
        """3.1: Windows 上 extra_settings 包含 WasapiSettings(auto_convert=True)。"""
        from airtype.core.audio_capture import AudioCaptureService

        mock_wasapi_instance = MagicMock()
        with patch("sys.platform", "win32"), \
             patch("sounddevice.WasapiSettings", return_value=mock_wasapi_instance) as mock_cls:
            result = AudioCaptureService._build_extra_settings()
            mock_cls.assert_called_once_with(auto_convert=True)
            self.assertEqual(result, mock_wasapi_instance)

    def test_extra_settings_none_on_non_windows(self):
        """3.2: 非 Windows 上 extra_settings 為 None。"""
        from airtype.core.audio_capture import AudioCaptureService

        with patch("sys.platform", "linux"):
            result = AudioCaptureService._build_extra_settings()
            self.assertIsNone(result)

    def test_fallback_path_passes_extra_settings(self):
        """3.3: fallback 路徑也正確傳遞 extra_settings。"""
        import sounddevice as sd

        from airtype.config import AirtypeConfig
        from airtype.core.audio_capture import AudioCaptureService

        config = AirtypeConfig()
        call_kwargs: list = []

        class MockInputStream:
            def __init__(self, **kwargs):
                call_kwargs.append(kwargs)
                if kwargs.get("device") == 9999:
                    raise sd.PortAudioError("Invalid device")

            def start(self):
                pass

            def stop(self):
                pass

            def close(self):
                pass

        mock_extra = MagicMock()
        with patch("sounddevice.InputStream", MockInputStream), \
             patch.object(AudioCaptureService, "_build_extra_settings", return_value=mock_extra):
            service = AudioCaptureService(config)
            service.start(device=9999)
            # 主路徑和 fallback 路徑都應傳遞 extra_settings
            self.assertEqual(len(call_kwargs), 2)
            self.assertEqual(call_kwargs[0]["extra_settings"], mock_extra)
            self.assertEqual(call_kwargs[1]["extra_settings"], mock_extra)
            service.stop()

    def test_extra_settings_fallback_when_wasapi_unavailable(self):
        """3.4: WasapiSettings 不可用時回退至 None。"""
        from airtype.core.audio_capture import AudioCaptureService

        with patch("sys.platform", "win32"), \
             patch("sounddevice.WasapiSettings", side_effect=AttributeError("no WasapiSettings")):
            result = AudioCaptureService._build_extra_settings()
            self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
