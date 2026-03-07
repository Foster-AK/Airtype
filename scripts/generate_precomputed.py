#!/usr/bin/env python3
"""生成預先計算的 Mel 濾波器組與提示模板佔位檔案。

使用方法：
    python scripts/generate_precomputed.py

輸出：
    models/precomputed/mel_filters.npy        — (128, 201) float32 Mel 濾波器組矩陣
    models/precomputed/prompt_template.json   — BPE 提示 token ID 佔位檔案

Mel 濾波器組規格（與 Qwen3-ASR / Whisper 相容）：
    - n_fft = 400, hop_length = 160, sample_rate = 16000
    - n_mels = 128, f_min = 0 Hz, f_max = 8000 Hz
    - Mel 刻度：HTK；正規化：Slaney（面積正規化）
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

# ── Qwen3-ASR 設定（與 processor_numpy.py 一致）──────────────────────────────
N_FFT = 400
N_MELS = 128
SAMPLE_RATE = 16000
F_MIN = 0.0
F_MAX = 8000.0  # SAMPLE_RATE / 2


# ── 輔助函式 ──────────────────────────────────────────────────────────────────

def _hz_to_mel(hz: float | np.ndarray) -> float | np.ndarray:
    """HTK Mel 刻度轉換：mel = 2595 × log10(1 + hz / 700)。"""
    return 2595.0 * np.log10(1.0 + hz / 700.0)


def _mel_to_hz(mel: float | np.ndarray) -> float | np.ndarray:
    """HTK Mel 刻度反轉換：hz = 700 × (10^(mel/2595) − 1)。"""
    return 700.0 * (10.0 ** (mel / 2595.0) - 1.0)


def create_mel_filterbank(
    n_fft: int,
    n_mels: int,
    sr: int,
    f_min: float = 0.0,
    f_max: float | None = None,
) -> np.ndarray:
    """建立 Mel 濾波器組矩陣（HTK 刻度，Slaney 面積正規化）。

    演算法與 librosa.filters.mel(norm='slaney') 相同，無需 librosa 依賴。

    Args:
        n_fft:   FFT 點數（必須為偶數）
        n_mels:  Mel 濾波器數量
        sr:      取樣率（Hz）
        f_min:   最低頻率（Hz）
        f_max:   最高頻率（Hz，預設為 sr / 2）

    Returns:
        float32 ndarray，shape (n_mels, n_fft // 2 + 1)
    """
    if f_max is None:
        f_max = sr / 2.0

    n_freqs = n_fft // 2 + 1

    # FFT 線性頻率（0 到 sr/2）
    fft_freqs = np.linspace(0.0, sr / 2.0, n_freqs)

    # Mel 等間距點（HTK 刻度）
    mel_min = _hz_to_mel(f_min)
    mel_max = _hz_to_mel(f_max)
    mel_points = np.linspace(mel_min, mel_max, n_mels + 2)
    hz_points = _mel_to_hz(mel_points)  # 長度 n_mels + 2

    fdiff = np.diff(hz_points)  # 長度 n_mels + 1

    # ramps[i, k] = hz_points[i] - fft_freqs[k]
    ramps = hz_points[:, np.newaxis] - fft_freqs[np.newaxis, :]  # (n_mels+2, n_freqs)

    weights = np.zeros((n_mels, n_freqs), dtype=np.float64)
    for i in range(n_mels):
        lower = -ramps[i] / fdiff[i]           # 上升斜坡
        upper = ramps[i + 2] / fdiff[i + 1]    # 下降斜坡
        weights[i] = np.maximum(0.0, np.minimum(lower, upper))

    # Slaney 面積正規化：2 / (f_right - f_left)
    enorm = 2.0 / (hz_points[2: n_mels + 2] - hz_points[:n_mels])
    weights *= enorm[:, np.newaxis]

    return weights.astype(np.float32)


# ── 主程式 ────────────────────────────────────────────────────────────────────

def main() -> None:
    root = Path(__file__).parent.parent
    out_dir = root / "models" / "precomputed"
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1. Mel 濾波器組
    mel_path = out_dir / "mel_filters.npy"
    filters = create_mel_filterbank(N_FFT, N_MELS, SAMPLE_RATE, F_MIN, F_MAX)
    np.save(mel_path, filters)
    print(f"已儲存 {mel_path}  shape={filters.shape}  dtype={filters.dtype}")

    # 2. 提示模板佔位檔案（僅在不存在時建立）
    prompt_path = out_dir / "prompt_template.json"
    if not prompt_path.exists():
        placeholder = {
            "_comment": (
                "佔位檔案 — 從 Qwen3-ASR 模型設定產生。"
                "使用 scripts/extract_prompt_tokens.py 更新此檔案。"
            ),
            "prompt_token_ids": [],
        }
        prompt_path.write_text(
            json.dumps(placeholder, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"已建立佔位檔案 {prompt_path}")
    else:
        print(f"已存在，跳過 {prompt_path}")


if __name__ == "__main__":
    main()
