"""硬體偵測模組測試。

涵蓋：
- GPU 偵測單元測試（mock subprocess 輸出，涵蓋 NVIDIA、AMD、僅 CPU）
- 系統能力評估測試
- 推理路徑建議邏輯測試（決策樹所有分支）
"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from airtype.utils.hardware_detect import (
    HardwareDetector,
    InferencePath,
    LlmRecommendation,
    SystemCapabilities,
    recommend_inference_path,
)


# ---------------------------------------------------------------------------
# 3.1 GPU 偵測單元測試
# ---------------------------------------------------------------------------


class TestGpuDetectionNvidia(unittest.TestCase):
    """NVIDIA GPU 偵測：mock nvidia-smi 輸出。"""

    def test_nvidia_gpu_detected(self):
        """nvidia-smi 輸出成功時應回傳 vendor=nvidia、型號與 VRAM。"""
        nvidia_smi_output = (
            "NVIDIA GeForce RTX 3080, 10240\n"
        )
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=nvidia_smi_output,
                stderr="",
            )
            detector = HardwareDetector()
            caps = detector.assess()

        self.assertEqual(caps.gpu_vendor, "nvidia")
        self.assertIn("3080", caps.gpu_model)
        self.assertEqual(caps.gpu_vram_mb, 10240)

    def test_nvidia_smi_not_found(self):
        """nvidia-smi 不存在時應退回到 None（不崩潰）。"""
        import subprocess

        def raise_not_found(*args, **kwargs):
            raise FileNotFoundError("nvidia-smi not found")

        with patch("subprocess.run", side_effect=raise_not_found):
            detector = HardwareDetector()
            caps = detector.assess()

        # gpu_vendor 應為 None 或 "amd"/"intel"（由其他偵測決定），不應是 "nvidia"
        self.assertNotEqual(caps.gpu_vendor, "nvidia")

    def test_nvidia_smi_returns_nonzero(self):
        """nvidia-smi 返回非零 exit code 時應視為無 NVIDIA GPU。"""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=1,
                stdout="",
                stderr="NVIDIA-SMI has failed",
            )
            detector = HardwareDetector()
            caps = detector.assess()

        self.assertNotEqual(caps.gpu_vendor, "nvidia")


class TestGpuDetectionNoGpu(unittest.TestCase):
    """無 GPU 情境：所有 GPU 偵測均失敗。"""

    def test_no_gpu_returns_none_vendor(self):
        """所有 GPU 偵測失敗時 gpu_vendor 應為 None。"""
        import subprocess

        def raise_not_found(*args, **kwargs):
            raise FileNotFoundError("command not found")

        with patch("subprocess.run", side_effect=raise_not_found):
            with patch("platform.system", return_value="Linux"):
                detector = HardwareDetector()
                caps = detector.assess()

        self.assertIsNone(caps.gpu_vendor)
        self.assertIsNone(caps.gpu_model)
        self.assertEqual(caps.gpu_vram_mb, 0)


# ---------------------------------------------------------------------------
# 3.1 系統能力評估測試
# ---------------------------------------------------------------------------


class TestSystemCapabilityAssessment(unittest.TestCase):
    """系統能力評估：CPU 類型、總 RAM、可用磁碟。"""

    def test_assess_returns_system_capabilities(self):
        """assess() 應回傳包含所有必要欄位的 SystemCapabilities。"""
        import subprocess

        with patch("subprocess.run", side_effect=FileNotFoundError()):
            detector = HardwareDetector()
            caps = detector.assess()

        self.assertIsInstance(caps, SystemCapabilities)
        self.assertIsInstance(caps.cpu_type, str)
        self.assertGreater(caps.total_ram_mb, 0)
        self.assertGreater(caps.available_disk_mb, 0)

    def test_assess_fields_positive(self):
        """RAM 和磁碟空間應為正整數。"""
        with patch("subprocess.run", side_effect=FileNotFoundError()):
            detector = HardwareDetector()
            caps = detector.assess()

        self.assertGreater(caps.total_ram_mb, 0)
        self.assertGreater(caps.available_disk_mb, 0)

    def test_system_capabilities_dataclass_fields(self):
        """SystemCapabilities dataclass 應包含必要欄位。"""
        caps = SystemCapabilities(
            gpu_vendor="nvidia",
            gpu_model="RTX 3080",
            gpu_vram_mb=10240,
            cpu_type="x86_64",
            total_ram_mb=16384,
            available_disk_mb=102400,
        )
        self.assertEqual(caps.gpu_vendor, "nvidia")
        self.assertEqual(caps.gpu_model, "RTX 3080")
        self.assertEqual(caps.gpu_vram_mb, 10240)
        self.assertEqual(caps.cpu_type, "x86_64")
        self.assertEqual(caps.total_ram_mb, 16384)
        self.assertEqual(caps.available_disk_mb, 102400)


# ---------------------------------------------------------------------------
# 3.2 推理路徑建議邏輯測試（決策樹所有分支）
# ---------------------------------------------------------------------------


class TestInferencePathRecommendation(unittest.TestCase):
    """推理路徑建議：驗證決策樹所有分支。"""

    def _make_caps(
        self,
        gpu_vendor=None,
        gpu_vram_mb=0,
        total_ram_mb=8192,
        gpu_model=None,
        available_disk_mb=102400,
        cpu_type="x86_64",
    ) -> SystemCapabilities:
        return SystemCapabilities(
            gpu_vendor=gpu_vendor,
            gpu_model=gpu_model,
            gpu_vram_mb=gpu_vram_mb,
            cpu_type=cpu_type,
            total_ram_mb=total_ram_mb,
            available_disk_mb=available_disk_mb,
        )

    # --- NVIDIA 分支 ---

    def test_nvidia_vram_ge_4gb_recommends_cuda_17b(self):
        """NVIDIA GPU VRAM≥4GB → qwen3-pytorch-cuda + qwen3-asr-1.7b。"""
        caps = self._make_caps(gpu_vendor="nvidia", gpu_vram_mb=8192)
        path = recommend_inference_path(caps)
        self.assertEqual(path.engine, "qwen3-pytorch-cuda")
        self.assertEqual(path.model, "qwen3-asr-1.7b")

    def test_nvidia_vram_exactly_4gb_recommends_cuda_17b(self):
        """NVIDIA GPU VRAM=4096MB（恰好4GB）→ qwen3-pytorch-cuda + 1.7b。"""
        caps = self._make_caps(gpu_vendor="nvidia", gpu_vram_mb=4096)
        path = recommend_inference_path(caps)
        self.assertEqual(path.engine, "qwen3-pytorch-cuda")
        self.assertEqual(path.model, "qwen3-asr-1.7b")

    def test_nvidia_vram_2gb_to_4gb_recommends_cuda_06b(self):
        """NVIDIA GPU VRAM≥2GB 且 <4GB → qwen3-pytorch-cuda + qwen3-asr-0.6b。"""
        caps = self._make_caps(gpu_vendor="nvidia", gpu_vram_mb=2048)
        path = recommend_inference_path(caps)
        self.assertEqual(path.engine, "qwen3-pytorch-cuda")
        self.assertEqual(path.model, "qwen3-asr-0.6b")

    def test_nvidia_vram_exactly_2gb_recommends_cuda_06b(self):
        """NVIDIA GPU VRAM=2048MB（恰好2GB）→ qwen3-pytorch-cuda + 0.6b。"""
        caps = self._make_caps(gpu_vendor="nvidia", gpu_vram_mb=2048)
        path = recommend_inference_path(caps)
        self.assertEqual(path.engine, "qwen3-pytorch-cuda")
        self.assertEqual(path.model, "qwen3-asr-0.6b")

    def test_nvidia_vram_below_2gb_falls_back_to_onnx(self):
        """NVIDIA GPU VRAM<2GB → 退回至 CPU 路徑。"""
        caps = self._make_caps(gpu_vendor="nvidia", gpu_vram_mb=1024, total_ram_mb=8192)
        path = recommend_inference_path(caps)
        # 應退回至 CPU 路徑（ONNX Runtime 或 sherpa-onnx）
        self.assertIn(path.engine, ["qwen3-onnx", "sherpa-onnx"])

    # --- AMD/Intel 分支 ---

    def test_amd_gpu_recommends_vulkan_06b(self):
        """AMD GPU → chatllm-vulkan + qwen3-asr-0.6b。"""
        caps = self._make_caps(gpu_vendor="amd", gpu_vram_mb=4096)
        path = recommend_inference_path(caps)
        self.assertEqual(path.engine, "chatllm-vulkan")
        self.assertEqual(path.model, "qwen3-asr-0.6b")

    def test_intel_gpu_recommends_vulkan_06b(self):
        """Intel GPU → chatllm-vulkan + qwen3-asr-0.6b。"""
        caps = self._make_caps(gpu_vendor="intel", gpu_vram_mb=2048)
        path = recommend_inference_path(caps)
        self.assertEqual(path.engine, "chatllm-vulkan")
        self.assertEqual(path.model, "qwen3-asr-0.6b")

    # --- CPU 分支 ---

    def test_cpu_only_ram_ge_6gb_recommends_onnx_06b(self):
        """無 GPU、RAM≥6GB → qwen3-onnx + qwen3-asr-0.6b。"""
        caps = self._make_caps(gpu_vendor=None, gpu_vram_mb=0, total_ram_mb=8192)
        path = recommend_inference_path(caps)
        self.assertEqual(path.engine, "qwen3-onnx")
        self.assertEqual(path.model, "qwen3-asr-0.6b")

    def test_cpu_only_ram_exactly_6gb_recommends_onnx(self):
        """無 GPU、RAM=6144MB（恰好6GB）→ qwen3-onnx + 0.6b。"""
        caps = self._make_caps(gpu_vendor=None, gpu_vram_mb=0, total_ram_mb=6144)
        path = recommend_inference_path(caps)
        self.assertEqual(path.engine, "qwen3-onnx")
        self.assertEqual(path.model, "qwen3-asr-0.6b")

    def test_cpu_only_ram_below_6gb_recommends_sherpa(self):
        """無 GPU、RAM<6GB → sherpa-onnx + sensevoice。"""
        caps = self._make_caps(gpu_vendor=None, gpu_vram_mb=0, total_ram_mb=4096)
        path = recommend_inference_path(caps)
        self.assertEqual(path.engine, "sherpa-onnx")
        self.assertIn("sensevoice", path.model.lower())

    # --- spec 明確場景 ---

    def test_spec_scenario_nvidia_8gb(self):
        """Spec §推理路徑建議：NVIDIA GPU 8GB VRAM → qwen3-pytorch-cuda + 1.7b。"""
        caps = self._make_caps(gpu_vendor="nvidia", gpu_vram_mb=8192)
        path = recommend_inference_path(caps)
        self.assertEqual(path.engine, "qwen3-pytorch-cuda")
        self.assertEqual(path.model, "qwen3-asr-1.7b")

    def test_spec_scenario_cpu_8gb_ram(self):
        """Spec §推理路徑建議：無 GPU + 8GB RAM → qwen3-onnx + 0.6b。"""
        caps = self._make_caps(gpu_vendor=None, gpu_vram_mb=0, total_ram_mb=8192)
        path = recommend_inference_path(caps)
        self.assertEqual(path.engine, "qwen3-onnx")
        self.assertEqual(path.model, "qwen3-asr-0.6b")

    def test_inference_path_dataclass(self):
        """InferencePath dataclass 應包含 engine 和 model 欄位。"""
        path = InferencePath(engine="qwen3-onnx", model="qwen3-asr-0.6b")
        self.assertEqual(path.engine, "qwen3-onnx")
        self.assertEqual(path.model, "qwen3-asr-0.6b")


# ---------------------------------------------------------------------------
# 5.1 recommend_llm() 單元測試（涵蓋五個分支）
# ---------------------------------------------------------------------------


class TestRecommendLlm(unittest.TestCase):
    """recommend_llm() 決策樹：驗證五個分支的回傳結果。"""

    def _make_detector_with_caps(self, caps: SystemCapabilities) -> HardwareDetector:
        """建立 HardwareDetector，並 mock assess() 回傳指定 caps。"""
        detector = HardwareDetector()
        detector.assess = lambda: caps
        return detector

    def _make_caps(self, gpu_vendor=None, gpu_vram_mb=0, total_ram_mb=8192) -> SystemCapabilities:
        return SystemCapabilities(
            gpu_vendor=gpu_vendor,
            gpu_vram_mb=gpu_vram_mb,
            gpu_model=None,
            cpu_type="x86_64",
            total_ram_mb=total_ram_mb,
            available_disk_mb=102400,
        )

    # --- 分支 1：NVIDIA VRAM ≥ 8GB ---

    def test_nvidia_vram_ge_8gb_recommends_7b(self):
        """NVIDIA GPU VRAM≥8GB → model=qwen2.5-7b-instruct-q4_k_m, backend=local。"""
        caps = self._make_caps(gpu_vendor="nvidia", gpu_vram_mb=8192)
        detector = self._make_detector_with_caps(caps)
        result = detector.recommend_llm()
        self.assertIsInstance(result, LlmRecommendation)
        self.assertEqual(result.model, "qwen2.5-7b-instruct-q4_k_m")
        self.assertEqual(result.backend, "local")
        self.assertIsNone(result.warning)

    def test_nvidia_vram_exactly_8gb_recommends_7b(self):
        """NVIDIA GPU VRAM=8192MB（恰好8GB）→ model=7b, backend=local。"""
        caps = self._make_caps(gpu_vendor="nvidia", gpu_vram_mb=8192)
        detector = self._make_detector_with_caps(caps)
        result = detector.recommend_llm()
        self.assertEqual(result.model, "qwen2.5-7b-instruct-q4_k_m")
        self.assertEqual(result.backend, "local")

    # --- 分支 2：NVIDIA VRAM ≥ 4GB 且 < 8GB ---

    def test_nvidia_vram_ge_4gb_lt_8gb_recommends_3b(self):
        """NVIDIA GPU 4GB≤VRAM<8GB → model=qwen2.5-3b-instruct-q4_k_m, backend=local。"""
        caps = self._make_caps(gpu_vendor="nvidia", gpu_vram_mb=4096)
        detector = self._make_detector_with_caps(caps)
        result = detector.recommend_llm()
        self.assertEqual(result.model, "qwen2.5-3b-instruct-q4_k_m")
        self.assertEqual(result.backend, "local")
        self.assertIsNone(result.warning)

    def test_nvidia_vram_6gb_recommends_3b(self):
        """NVIDIA GPU VRAM=6144MB → model=3b, backend=local。"""
        caps = self._make_caps(gpu_vendor="nvidia", gpu_vram_mb=6144)
        detector = self._make_detector_with_caps(caps)
        result = detector.recommend_llm()
        self.assertEqual(result.model, "qwen2.5-3b-instruct-q4_k_m")
        self.assertEqual(result.backend, "local")

    # --- 分支 3：AMD/Intel GPU ---

    def test_amd_gpu_recommends_1_5b(self):
        """AMD GPU → model=qwen2.5-1.5b-instruct-q4_k_m, backend=local。"""
        caps = self._make_caps(gpu_vendor="amd", gpu_vram_mb=4096)
        detector = self._make_detector_with_caps(caps)
        result = detector.recommend_llm()
        self.assertEqual(result.model, "qwen2.5-1.5b-instruct-q4_k_m")
        self.assertEqual(result.backend, "local")
        self.assertIsNone(result.warning)

    def test_intel_gpu_recommends_1_5b(self):
        """Intel GPU → model=qwen2.5-1.5b-instruct-q4_k_m, backend=local。"""
        caps = self._make_caps(gpu_vendor="intel", gpu_vram_mb=2048)
        detector = self._make_detector_with_caps(caps)
        result = detector.recommend_llm()
        self.assertEqual(result.model, "qwen2.5-1.5b-instruct-q4_k_m")
        self.assertEqual(result.backend, "local")

    # --- 分支 4：CPU-only RAM ≥ 8GB ---

    def test_cpu_only_ram_ge_8gb_recommends_1_5b_with_warning(self):
        """CPU-only RAM≥8GB → model=1.5b, backend=local, warning=approaching_timeout_cpu。"""
        caps = self._make_caps(gpu_vendor=None, gpu_vram_mb=0, total_ram_mb=8192)
        detector = self._make_detector_with_caps(caps)
        result = detector.recommend_llm()
        self.assertEqual(result.model, "qwen2.5-1.5b-instruct-q4_k_m")
        self.assertEqual(result.backend, "local")
        self.assertEqual(result.warning, "approaching_timeout_cpu")

    def test_cpu_only_ram_exactly_8gb_has_warning(self):
        """CPU-only RAM=8192MB → warning=approaching_timeout_cpu。"""
        caps = self._make_caps(gpu_vendor=None, gpu_vram_mb=0, total_ram_mb=8192)
        detector = self._make_detector_with_caps(caps)
        result = detector.recommend_llm()
        self.assertEqual(result.warning, "approaching_timeout_cpu")

    # --- 分支 5：CPU-only RAM < 8GB ---

    def test_cpu_only_ram_lt_8gb_recommends_disabled(self):
        """CPU-only RAM<8GB → model=None, backend=disabled。"""
        caps = self._make_caps(gpu_vendor=None, gpu_vram_mb=0, total_ram_mb=4096)
        detector = self._make_detector_with_caps(caps)
        result = detector.recommend_llm()
        self.assertIsNone(result.model)
        self.assertEqual(result.backend, "disabled")

    def test_cpu_only_ram_7gb_backend_disabled(self):
        """CPU-only RAM=7168MB（<8GB）→ backend=disabled。"""
        caps = self._make_caps(gpu_vendor=None, gpu_vram_mb=0, total_ram_mb=7168)
        detector = self._make_detector_with_caps(caps)
        result = detector.recommend_llm()
        self.assertEqual(result.backend, "disabled")

    # --- 資料類別驗證 ---

    def test_llm_recommendation_dataclass_fields(self):
        """LlmRecommendation 應包含 model, backend, warning 欄位。"""
        rec = LlmRecommendation(
            model="qwen2.5-7b-instruct-q4_k_m",
            backend="local",
            warning=None,
        )
        self.assertEqual(rec.model, "qwen2.5-7b-instruct-q4_k_m")
        self.assertEqual(rec.backend, "local")
        self.assertIsNone(rec.warning)

    def test_llm_recommendation_disabled_branch(self):
        """LlmRecommendation disabled 分支的 model 應為 None。"""
        rec = LlmRecommendation(model=None, backend="disabled", warning=None)
        self.assertIsNone(rec.model)
        self.assertEqual(rec.backend, "disabled")


# ---------------------------------------------------------------------------
# RAM 偵測單元測試（fix-ram-detection）
# ---------------------------------------------------------------------------


class TestRamDetectionViaPsutil(unittest.TestCase):
    """RAM Detection via psutil（Scenario: RAM Detection via psutil）。"""

    def test_psutil_returns_correct_ram_mb(self):
        """psutil 可用時應回傳正確 RAM 值且不觸發 WARNING。"""
        import sys

        mock_psutil = MagicMock()
        mock_psutil.virtual_memory.return_value.total = 16 * 1024 * 1024 * 1024  # 16 GB

        with patch.dict(sys.modules, {"psutil": mock_psutil}):
            detector = HardwareDetector()
            with self.assertNoLogs("airtype.utils.hardware_detect", level="WARNING"):
                ram_mb = detector._get_total_ram_mb()

        self.assertEqual(ram_mb, 16384)


class TestRamDetectionViaCtypesWindows(unittest.TestCase):
    """RAM Detection via ctypes on Windows（Scenario: RAM Detection via ctypes on Windows）。"""

    def test_ctypes_fallback_returns_correct_ram_when_psutil_unavailable(self):
        """psutil 不可用時，Windows ctypes 備案應回傳正確 RAM 值（非假設值 4096）。"""
        import sys
        import ctypes as _ctypes

        _captured_stat = []
        _original_byref = _ctypes.byref

        def _capturing_byref(obj, *args):
            if hasattr(type(obj), "_fields_") and any(
                name == "ullTotalPhys"
                for name, _ in getattr(type(obj), "_fields_", [])
            ):
                _captured_stat.append(obj)
            return _original_byref(obj, *args)

        def _mock_gms(_byref_arg):
            if _captured_stat:
                _captured_stat[0].ullTotalPhys = 32 * 1024 * 1024 * 1024  # 32 GB
            return 1

        mock_windll = MagicMock()
        mock_windll.kernel32.GlobalMemoryStatusEx.side_effect = _mock_gms

        with patch.dict(sys.modules, {"psutil": None}):
            with patch("platform.system", return_value="Windows"):
                with patch("subprocess.run", side_effect=Exception("no wmic")):
                    with patch("ctypes.windll", new=mock_windll, create=True):
                        with patch("ctypes.byref", side_effect=_capturing_byref):
                            detector = HardwareDetector()
                            ram_mb = detector._get_total_ram_mb()

        self.assertEqual(ram_mb, 32768)  # 32 GB = 32 * 1024 MB


class TestRamDetectionFallbackWarning(unittest.TestCase):
    """RAM Detection Fallback Warning（Scenario: RAM Detection Fallback Warning）。"""

    def test_warning_logged_and_4096_returned_when_all_methods_fail(self):
        """所有偵測方法均失敗時應記錄 WARNING 並回傳假設值 4096。"""
        import sys

        mock_windll = MagicMock()
        mock_windll.kernel32.GlobalMemoryStatusEx.side_effect = OSError("ctypes failed")

        with patch.dict(sys.modules, {"psutil": None}):
            with patch("platform.system", return_value="Windows"):
                with patch("subprocess.run", side_effect=Exception("wmic failed")):
                    with patch("ctypes.windll", new=mock_windll, create=True):
                        with self.assertLogs(
                            "airtype.utils.hardware_detect", level="WARNING"
                        ) as log:
                            detector = HardwareDetector()
                            ram_mb = detector._get_total_ram_mb()

        self.assertEqual(ram_mb, 4096)
        self.assertTrue(any("RAM" in msg for msg in log.output))


if __name__ == "__main__":
    unittest.main()
