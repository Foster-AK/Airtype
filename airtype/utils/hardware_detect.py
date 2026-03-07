"""硬體偵測與推理路徑建議。

提供 HardwareDetector 偵測 GPU/CPU 能力，以及 recommend_inference_path
依據 PRD §10.4 決策樹自動建議最佳 ASR 推理路徑。

符合 specs/hardware-detection/spec.md。
"""

from __future__ import annotations

import logging
import platform
import shutil
import subprocess
import sys
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


def _hidden_subprocess_kwargs() -> dict:
    """Windows 上隱藏 subprocess console 視窗的額外參數。"""
    if sys.platform == "win32":
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        return {"creationflags": 0x08000000, "startupinfo": si}
    return {}


# ---------------------------------------------------------------------------
# 資料類別
# ---------------------------------------------------------------------------


@dataclass
class SystemCapabilities:
    """系統硬體能力快照。

    Attributes:
        gpu_vendor:      GPU 廠商（"nvidia" / "amd" / "intel" / None）
        gpu_model:       GPU 型號字串（偵測失敗時為 None）
        gpu_vram_mb:     GPU 顯存容量（MB），無 GPU 時為 0
        cpu_type:        CPU 架構字串（e.g., "x86_64", "arm64"）
        total_ram_mb:    系統總 RAM（MB）
        available_disk_mb: 模型目錄所在磁碟可用空間（MB）
    """

    gpu_vendor: Optional[str] = None
    gpu_model: Optional[str] = None
    gpu_vram_mb: int = 0
    cpu_type: str = ""
    total_ram_mb: int = 0
    available_disk_mb: int = 0


@dataclass
class InferencePath:
    """推理路徑建議結果。

    Attributes:
        engine: 推理引擎識別字串
        model:  推薦模型識別字串
    """

    engine: str
    model: str


@dataclass
class LlmRecommendation:
    """LLM 推理建議結果。

    Attributes:
        model:   推薦的 LLM 模型識別字串，None 表示停用 LLM。
        backend: 推理後端（"local" 或 "disabled"）。
        warning: 警示代碼，None 表示無警示。
                 "approaching_timeout_cpu" 表示 CPU-only 環境接近逾時。
    """

    model: Optional[str] = None
    backend: str = "disabled"
    warning: Optional[str] = None


# ---------------------------------------------------------------------------
# 硬體偵測器
# ---------------------------------------------------------------------------


class HardwareDetector:
    """偵測 GPU/CPU 能力並評估系統整體資源。

    透過 subprocess 呼叫平台工具（nvidia-smi、WMI、system_profiler、lspci）
    而不引入重量級依賴（如 pycuda、vulkan bindings）。

    使用方式::

        detector = HardwareDetector()
        caps = detector.assess()
        path = recommend_inference_path(caps)
    """

    def assess(self) -> SystemCapabilities:
        """評估系統硬體，回傳 SystemCapabilities。

        偵測順序：NVIDIA（nvidia-smi）→ AMD/Intel（平台相依工具）→ 退回無 GPU。
        CPU 資訊與 RAM / 磁碟空間透過 platform / psutil / shutil 取得。
        """
        gpu_vendor, gpu_model, gpu_vram_mb = self._detect_gpu()
        cpu_type = platform.machine() or sys.platform
        total_ram_mb = self._get_total_ram_mb()
        available_disk_mb = self._get_available_disk_mb()

        caps = SystemCapabilities(
            gpu_vendor=gpu_vendor,
            gpu_model=gpu_model,
            gpu_vram_mb=gpu_vram_mb,
            cpu_type=cpu_type,
            total_ram_mb=total_ram_mb,
            available_disk_mb=available_disk_mb,
        )
        logger.debug(
            "硬體評估完成：vendor=%s model=%s vram=%dMB ram=%dMB disk=%dMB",
            gpu_vendor,
            gpu_model,
            gpu_vram_mb,
            total_ram_mb,
            available_disk_mb,
        )
        return caps

    # ------------------------------------------------------------------
    # GPU 偵測（私有）
    # ------------------------------------------------------------------

    def _detect_gpu(self) -> tuple[Optional[str], Optional[str], int]:
        """偵測 GPU。回傳 (vendor, model, vram_mb)。"""
        # 1. 嘗試 NVIDIA
        result = self._detect_nvidia()
        if result[0] is not None:
            return result

        # 2. 嘗試 AMD / Intel（平台相依）
        result = self._detect_amd_intel()
        if result[0] is not None:
            return result

        # 3. 無 GPU
        return None, None, 0

    def _detect_nvidia(self) -> tuple[Optional[str], Optional[str], int]:
        """透過 nvidia-smi 偵測 NVIDIA GPU。

        nvidia-smi 輸出格式（CSV）：
            <name>, <memory.total [MiB]>
        例：NVIDIA GeForce RTX 3080, 10240 MiB
        """
        try:
            result = subprocess.run(
                [
                    "nvidia-smi",
                    "--query-gpu=name,memory.total",
                    "--format=csv,noheader,nounits",
                ],
                capture_output=True,
                text=True,
                timeout=10,
                **_hidden_subprocess_kwargs(),
            )
            if result.returncode != 0:
                logger.debug("nvidia-smi 返回非零：%s", result.stderr.strip())
                return None, None, 0

            line = result.stdout.strip().splitlines()[0] if result.stdout.strip() else ""
            if not line:
                return None, None, 0

            # 解析 "Name, VRAM"
            parts = [p.strip() for p in line.split(",")]
            if len(parts) < 2:
                return None, None, 0

            gpu_model = parts[0]
            try:
                vram_mb = int(parts[1])
            except ValueError:
                vram_mb = 0

            logger.info("偵測到 NVIDIA GPU：%s（%d MB）", gpu_model, vram_mb)
            return "nvidia", gpu_model, vram_mb

        except FileNotFoundError:
            logger.debug("nvidia-smi 未找到，跳過 NVIDIA 偵測")
            return None, None, 0
        except subprocess.TimeoutExpired:
            logger.warning("nvidia-smi 逾時")
            return None, None, 0
        except Exception as exc:  # noqa: BLE001
            logger.debug("nvidia-smi 偵測例外：%s", exc)
            return None, None, 0

    def _detect_amd_intel(self) -> tuple[Optional[str], Optional[str], int]:
        """偵測 AMD 或 Intel GPU（平台相依）。"""
        os_name = platform.system()
        if os_name == "Windows":
            return self._detect_wmi_gpu()
        elif os_name == "Darwin":
            return self._detect_macos_gpu()
        else:
            return self._detect_lspci_gpu()

    def _detect_wmi_gpu(self) -> tuple[Optional[str], Optional[str], int]:
        """Windows：透過 wmic 查詢 GPU 資訊。"""
        try:
            result = subprocess.run(
                ["wmic", "path", "Win32_VideoController", "get",
                 "Name,AdapterRAM", "/format:csv"],
                capture_output=True,
                text=True,
                timeout=15,
                **_hidden_subprocess_kwargs(),
            )
            if result.returncode != 0:
                return None, None, 0

            for line in result.stdout.splitlines():
                line = line.strip()
                if not line or line.startswith("Node"):
                    continue
                parts = line.split(",")
                if len(parts) < 3:
                    continue
                adapter_ram_str, name = parts[1].strip(), parts[2].strip()
                if not name:
                    continue
                name_lower = name.lower()
                vendor = None
                if "amd" in name_lower or "radeon" in name_lower:
                    vendor = "amd"
                elif "intel" in name_lower:
                    vendor = "intel"
                if vendor:
                    try:
                        vram_bytes = int(adapter_ram_str)
                        vram_mb = vram_bytes // (1024 * 1024)
                    except (ValueError, TypeError):
                        vram_mb = 0
                    logger.info("偵測到 %s GPU（WMI）：%s（%d MB）", vendor, name, vram_mb)
                    return vendor, name, vram_mb

        except FileNotFoundError:
            logger.debug("wmic 未找到")
        except subprocess.TimeoutExpired:
            logger.warning("wmic 查詢逾時")
        except Exception as exc:  # noqa: BLE001
            logger.debug("WMI GPU 偵測例外：%s", exc)
        return None, None, 0

    def _detect_macos_gpu(self) -> tuple[Optional[str], Optional[str], int]:
        """macOS：透過 system_profiler 查詢 GPU。"""
        try:
            result = subprocess.run(
                ["system_profiler", "SPDisplaysDataType"],
                capture_output=True,
                text=True,
                timeout=15,
                **_hidden_subprocess_kwargs(),
            )
            if result.returncode != 0:
                return None, None, 0

            output = result.stdout.lower()
            if "amd" in output or "radeon" in output:
                vendor = "amd"
            elif "intel" in output:
                vendor = "intel"
            else:
                return None, None, 0

            # 嘗試解析型號（取 Chipset Model 行）
            gpu_model = None
            for line in result.stdout.splitlines():
                if "chipset model" in line.lower():
                    gpu_model = line.split(":")[-1].strip()
                    break

            logger.info("偵測到 %s GPU（system_profiler）：%s", vendor, gpu_model)
            return vendor, gpu_model, 0  # macOS system_profiler 不易取得 VRAM

        except FileNotFoundError:
            logger.debug("system_profiler 未找到")
        except subprocess.TimeoutExpired:
            logger.warning("system_profiler 逾時")
        except Exception as exc:  # noqa: BLE001
            logger.debug("macOS GPU 偵測例外：%s", exc)
        return None, None, 0

    def _detect_lspci_gpu(self) -> tuple[Optional[str], Optional[str], int]:
        """Linux：透過 lspci 查詢 GPU。"""
        try:
            result = subprocess.run(
                ["lspci"],
                capture_output=True,
                text=True,
                timeout=10,
                **_hidden_subprocess_kwargs(),
            )
            if result.returncode != 0:
                return None, None, 0

            for line in result.stdout.splitlines():
                line_lower = line.lower()
                if "vga" not in line_lower and "3d" not in line_lower and "display" not in line_lower:
                    continue
                if "amd" in line_lower or "ati" in line_lower or "radeon" in line_lower:
                    gpu_model = line.split(":")[-1].strip() if ":" in line else line
                    logger.info("偵測到 AMD GPU（lspci）：%s", gpu_model)
                    return "amd", gpu_model, 0
                elif "intel" in line_lower:
                    gpu_model = line.split(":")[-1].strip() if ":" in line else line
                    logger.info("偵測到 Intel GPU（lspci）：%s", gpu_model)
                    return "intel", gpu_model, 0

        except FileNotFoundError:
            logger.debug("lspci 未找到")
        except subprocess.TimeoutExpired:
            logger.warning("lspci 逾時")
        except Exception as exc:  # noqa: BLE001
            logger.debug("lspci GPU 偵測例外：%s", exc)
        return None, None, 0

    # ------------------------------------------------------------------
    # 系統資源（私有）
    # ------------------------------------------------------------------

    def _get_total_ram_mb(self) -> int:
        """取得系統總 RAM（MB）。"""
        try:
            import psutil
            return psutil.virtual_memory().total // (1024 * 1024)
        except ImportError:
            logger.debug("psutil 不可用（ImportError），退回至平台備案")

        # 退回：各平台備案
        try:
            os_name = platform.system()
            if os_name == "Windows":
                # ctypes GlobalMemoryStatusEx 備案（不依賴 wmic，Windows 2000+ 支援）
                try:
                    import ctypes

                    class _MEMSTATUSEX(ctypes.Structure):
                        _fields_ = [
                            ("dwLength", ctypes.c_ulong),
                            ("dwMemoryLoad", ctypes.c_ulong),
                            ("ullTotalPhys", ctypes.c_ulonglong),
                            ("ullAvailPhys", ctypes.c_ulonglong),
                            ("ullTotalPageFile", ctypes.c_ulonglong),
                            ("ullAvailPageFile", ctypes.c_ulonglong),
                            ("ullTotalVirtual", ctypes.c_ulonglong),
                            ("ullAvailVirtual", ctypes.c_ulonglong),
                            ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
                        ]

                    stat = _MEMSTATUSEX()
                    stat.dwLength = ctypes.sizeof(stat)
                    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat))
                    ram_mb = stat.ullTotalPhys // (1024 * 1024)
                    if ram_mb > 0:
                        return ram_mb
                    logger.debug("ctypes GlobalMemoryStatusEx 回傳 0，無法取得 RAM")
                except Exception as exc:  # noqa: BLE001
                    logger.debug("ctypes GlobalMemoryStatusEx 失敗：%s", exc)
            elif os_name == "Darwin":
                try:
                    result = subprocess.run(
                        ["sysctl", "-n", "hw.memsize"],
                        capture_output=True, text=True, timeout=5,
                        **_hidden_subprocess_kwargs(),
                    )
                    if result.returncode == 0:
                        return int(result.stdout.strip()) // (1024 * 1024)
                    logger.debug("sysctl hw.memsize 回傳非零：%s", result.returncode)
                except Exception as exc:  # noqa: BLE001
                    logger.debug("sysctl hw.memsize 失敗：%s", exc)
            else:
                # Linux：讀取 /proc/meminfo
                try:
                    with open("/proc/meminfo", encoding="utf-8") as f:
                        for line in f:
                            if line.startswith("MemTotal:"):
                                kb = int(line.split()[1])
                                return kb // 1024
                    logger.debug("/proc/meminfo 未找到 MemTotal 欄位")
                except Exception as exc:  # noqa: BLE001
                    logger.debug("/proc/meminfo 讀取失敗：%s", exc)
        except Exception as exc:  # noqa: BLE001
            logger.debug("取得 RAM 失敗：%s", exc)

        # 最終退回：假設 4GB
        logger.warning("無法取得 RAM 資訊，假設 4096 MB")
        return 4096

    def _get_available_disk_mb(self) -> int:
        """取得模型目錄所在磁碟可用空間（MB）。"""
        import os

        try:
            model_dir = os.path.expanduser("~/.airtype/models")
            # 若目錄不存在，改用 home 目錄
            if not os.path.exists(model_dir):
                model_dir = os.path.expanduser("~")
            usage = shutil.disk_usage(model_dir)
            return usage.free // (1024 * 1024)
        except Exception as exc:  # noqa: BLE001
            logger.debug("取得磁碟空間失敗：%s", exc)
            return 0

    def recommend_llm(self) -> LlmRecommendation:
        """建議 LLM 推理環境，依五分支決策樹回傳模型、後端與警示資訊。

        決策樹（依優先順序）：
        1. NVIDIA GPU，VRAM≥8GB  → 大型模型（7B），後端 local，無警示
        2. NVIDIA GPU，VRAM≥4GB  → 中型模型（3B），後端 local，無警示
        3. AMD/Intel GPU（任意）  → 小型模型（1.5B），後端 local，無警示
        4. CPU-only，RAM≥8GB     → 小型模型（1.5B），後端 local，警示 approaching_timeout_cpu
        5. CPU-only，RAM<8GB     → 停用 LLM，後端 disabled，無警示

        NVIDIA GPU VRAM < 4GB 時視為 CPU-only，fallthrough 至步驟 4/5。
        """
        try:
            caps = self.assess()
            vendor = caps.gpu_vendor
            vram_mb = caps.gpu_vram_mb
            ram_mb = caps.total_ram_mb

            # 分支 1：NVIDIA GPU，VRAM ≥ 8GB
            if vendor == "nvidia" and vram_mb >= _LLM_VRAM_8GB:
                logger.info(
                    "LLM 建議：NVIDIA 大型模型（VRAM=%dMB ≥ 8GB）→ %s",
                    vram_mb,
                    _LLM_LARGE,
                )
                return LlmRecommendation(
                    model=_LLM_LARGE,
                    backend="local",
                    warning=None,
                )

            # 分支 2：NVIDIA GPU，VRAM ≥ 4GB（且 < 8GB）
            if vendor == "nvidia" and vram_mb >= _LLM_VRAM_4GB:
                logger.info(
                    "LLM 建議：NVIDIA 中型模型（VRAM=%dMB，4GB≤VRAM<8GB）→ %s",
                    vram_mb,
                    _LLM_MEDIUM,
                )
                return LlmRecommendation(
                    model=_LLM_MEDIUM,
                    backend="local",
                    warning=None,
                )

            # 分支 3：AMD/Intel GPU（任意 VRAM）
            if vendor in ("amd", "intel"):
                logger.info(
                    "LLM 建議：%s GPU 小型模型（VRAM=%dMB）→ %s",
                    vendor,
                    vram_mb,
                    _LLM_SMALL,
                )
                return LlmRecommendation(
                    model=_LLM_SMALL,
                    backend="local",
                    warning=None,
                )

            # 以下為 CPU-only 路徑（包含 NVIDIA VRAM < 4GB 的 fallthrough）
            if vendor == "nvidia":
                logger.info(
                    "NVIDIA VRAM 不足（%dMB < 4GB），退回 CPU-only LLM 路徑",
                    vram_mb,
                )

            # 分支 4：CPU-only，RAM ≥ 8GB
            if ram_mb >= _LLM_RAM_8GB:
                logger.info(
                    "LLM 建議：CPU-only 小型模型（RAM=%dMB ≥ 8GB）→ %s，警示逾時風險",
                    ram_mb,
                    _LLM_SMALL,
                )
                return LlmRecommendation(
                    model=_LLM_SMALL,
                    backend="local",
                    warning="approaching_timeout_cpu",
                )

            # 分支 5：CPU-only，RAM < 8GB → 停用 LLM
            logger.info(
                "LLM 建議：CPU-only RAM 不足（RAM=%dMB < 8GB），停用 LLM",
                ram_mb,
            )
            return LlmRecommendation(
                model=None,
                backend="disabled",
                warning=None,
            )

        except Exception as exc:  # noqa: BLE001
            logger.debug("recommend_llm 偵測失敗，忽略：%s", exc)
            return LlmRecommendation(model=None, backend="disabled", warning=None)


# ---------------------------------------------------------------------------
# 推理路徑建議（PRD §10.4 決策樹）
# ---------------------------------------------------------------------------

# VRAM 閾值（MB）
_VRAM_4GB = 4 * 1024   # 4096 MB
_VRAM_2GB = 2 * 1024   # 2048 MB

# RAM 閾值（MB）
_RAM_6GB = 6 * 1024    # 6144 MB

# ---------------------------------------------------------------------------
# LLM 推理建議（五分支決策樹）
# ---------------------------------------------------------------------------

# LLM VRAM 閾值（MB）
_LLM_VRAM_8GB = 8 * 1024   # 8192 MB
_LLM_VRAM_4GB = 4 * 1024   # 4096 MB

# LLM RAM 閾值（MB）
_LLM_RAM_8GB = 8 * 1024    # 8192 MB

# LLM 模型常數
_LLM_LARGE = "qwen2.5-7b-instruct-q4_k_m"
_LLM_MEDIUM = "qwen2.5-3b-instruct-q4_k_m"
_LLM_SMALL = "qwen2.5-1.5b-instruct-q4_k_m"


def recommend_inference_path(caps: SystemCapabilities) -> InferencePath:
    """依 PRD §10.4 決策樹建議最佳 ASR 推理路徑。

    決策樹（依優先順序）：
    1. NVIDIA GPU，VRAM≥4GB  → qwen3-pytorch-cuda + qwen3-asr-1.7b
    2. NVIDIA GPU，VRAM≥2GB  → qwen3-pytorch-cuda + qwen3-asr-0.6b
    3. AMD/Intel GPU          → chatllm-vulkan + qwen3-asr-0.6b
    4. CPU，RAM≥6GB           → qwen3-openvino + qwen3-asr-0.6b
    5. CPU，RAM<6GB            → sherpa-onnx + sensevoice-small

    Args:
        caps: 由 HardwareDetector.assess() 回傳的系統能力資料。

    Returns:
        InferencePath 包含推薦的 engine 與 model 字串。
    """
    vendor = caps.gpu_vendor
    vram_mb = caps.gpu_vram_mb
    ram_mb = caps.total_ram_mb

    if vendor == "nvidia":
        if vram_mb >= _VRAM_4GB:
            logger.info("建議路徑：NVIDIA CUDA 1.7B（VRAM=%dMB）", vram_mb)
            return InferencePath(engine="qwen3-pytorch-cuda", model="qwen3-asr-1.7b")
        elif vram_mb >= _VRAM_2GB:
            logger.info("建議路徑：NVIDIA CUDA 0.6B（VRAM=%dMB）", vram_mb)
            return InferencePath(engine="qwen3-pytorch-cuda", model="qwen3-asr-0.6b")
        else:
            logger.info("NVIDIA VRAM 不足（%dMB），退回 CPU 路徑", vram_mb)
            # 退回至 CPU 路徑

    elif vendor in ("amd", "intel"):
        logger.info("建議路徑：Vulkan 0.6B（vendor=%s）", vendor)
        return InferencePath(engine="chatllm-vulkan", model="qwen3-asr-0.6b")

    # CPU 路徑
    if ram_mb >= _RAM_6GB:
        logger.info("建議路徑：OpenVINO INT8 0.6B（RAM=%dMB）", ram_mb)
        return InferencePath(engine="qwen3-openvino", model="qwen3-asr-0.6b")
    else:
        logger.info("建議路徑：sherpa-onnx SenseVoice（RAM=%dMB）", ram_mb)
        return InferencePath(engine="sherpa-onnx", model="sensevoice-small")
