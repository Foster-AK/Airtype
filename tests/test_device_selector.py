"""裝置選擇器測試。

涵蓋 list_input_devices() 的偏好 Host API 過濾與名稱去重邏輯。
"""

from __future__ import annotations

import unittest
from unittest.mock import patch


class TestListInputDevices(unittest.TestCase):
    """list_input_devices() 單元測試。"""

    _DEVICES_WITH_HOSTAPI = [
        # index 0: MME 版麥克風 A
        {"name": "麥克風 A", "max_input_channels": 2, "max_output_channels": 0, "hostapi": 0},
        # index 1: WASAPI 版麥克風 A（同名，不同 hostapi）
        {"name": "麥克風 A", "max_input_channels": 2, "max_output_channels": 0, "hostapi": 1},
        # index 2: 喇叭（輸出裝置，應排除）
        {"name": "喇叭 B", "max_input_channels": 0, "max_output_channels": 2, "hostapi": 1},
        # index 3: WASAPI 版麥克風 C
        {"name": "麥克風 C", "max_input_channels": 1, "max_output_channels": 0, "hostapi": 1},
    ]

    _HOSTAPIS_WITH_WASAPI = [
        {"name": "MME"},
        {"name": "Windows WASAPI"},
    ]

    def test_wasapi_preferred_on_windows(self):
        """Windows 上 WASAPI 可用時，應只回傳 WASAPI 裝置且不重複。"""
        from airtype.ui.device_selector import list_input_devices

        with patch("sounddevice.query_devices", return_value=self._DEVICES_WITH_HOSTAPI), \
             patch("sounddevice.query_hostapis", return_value=self._HOSTAPIS_WITH_WASAPI), \
             patch("sys.platform", "win32"):
            devices = list_input_devices()

        names = [d["name"] for d in devices]
        # 只回傳 WASAPI (hostapi=1) 的輸入裝置，麥克風 A 不重複
        self.assertEqual(len(devices), 2)
        self.assertIn("麥克風 A", names)
        self.assertIn("麥克風 C", names)
        # 確認使用的是 WASAPI 版的 index（index=1，不是 MME 的 index=0）
        mic_a = next(d for d in devices if d["name"] == "麥克風 A")
        self.assertEqual(mic_a["index"], 1)

    def test_fallback_deduplication_when_no_preferred_api(self):
        """找不到偏好 Host API 時，應以名稱去重（保留 index 最小的第一個）。"""
        from airtype.ui.device_selector import list_input_devices

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
            devices = list_input_devices()

        names = [d["name"] for d in devices]
        self.assertEqual(len(devices), 2)
        self.assertEqual(names.count("麥克風 A"), 1)
        # 保留第一個出現的（index=0，MME 版）
        mic_a = next(d for d in devices if d["name"] == "麥克風 A")
        self.assertEqual(mic_a["index"], 0)

    def test_empty_device_list_returns_empty(self):
        """無任何裝置時應回傳空清單。"""
        from airtype.ui.device_selector import list_input_devices

        with patch("sounddevice.query_devices", return_value=[]), \
             patch("sounddevice.query_hostapis", return_value=[]):
            devices = list_input_devices()

        self.assertEqual(devices, [])

    def test_query_devices_exception_returns_empty(self):
        """query_devices 拋出例外時應回傳空清單而不崩潰。"""
        from airtype.ui.device_selector import list_input_devices

        with patch("sounddevice.query_devices", side_effect=OSError("no audio")):
            devices = list_input_devices()

        self.assertEqual(devices, [])

    def test_output_devices_excluded(self):
        """純輸出裝置（max_input_channels=0）不應出現在結果中。"""
        from airtype.ui.device_selector import list_input_devices

        fake_devices = [
            {"name": "喇叭", "max_input_channels": 0, "max_output_channels": 2, "hostapi": 0},
            {"name": "麥克風", "max_input_channels": 1, "max_output_channels": 0, "hostapi": 0},
        ]

        with patch("sounddevice.query_devices", return_value=fake_devices), \
             patch("sounddevice.query_hostapis", return_value=[]):
            devices = list_input_devices()

        self.assertEqual(len(devices), 1)
        self.assertEqual(devices[0]["name"], "麥克風")


if __name__ == "__main__":
    unittest.main()
