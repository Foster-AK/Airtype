"""音訊工具函式：環形緩衝區與 RMS 計算。

提供：
- RingBuffer：以 numpy 循環陣列實作的固定大小音訊緩衝區（執行緒安全）
- compute_rms：計算音訊幀的均方根音量
"""

from __future__ import annotations

import threading

import numpy as np


class RingBuffer:
    """固定大小的 numpy 循環環形緩衝區（執行緒安全）。

    使用 head 指標追蹤下一個寫入位置。緩衝區滿時，
    新資料會覆寫最舊的樣本（循環覆寫）。

    Args:
        capacity: 緩衝區最大樣本數（float32）
    """

    def __init__(self, capacity: int) -> None:
        self._capacity = capacity
        self._buf = np.zeros(capacity, dtype=np.float32)
        self._head = 0   # 下一個寫入位置
        self._count = 0  # 有效樣本數
        self._lock = threading.Lock()

    @property
    def capacity(self) -> int:
        """緩衝區容量（樣本數）。"""
        return self._capacity

    @property
    def count(self) -> int:
        """目前有效樣本數。"""
        with self._lock:
            return self._count

    def write(self, data: np.ndarray) -> None:
        """寫入音訊樣本至環形緩衝區。

        若資料量超過緩衝區容量，僅保留最新的 capacity 個樣本。
        若緩衝區已滿，新資料覆寫最舊資料。

        Args:
            data: 一維 float32 音訊樣本陣列
        """
        n = len(data)
        if n == 0:
            return

        with self._lock:
            if n >= self._capacity:
                # 資料量超過容量，僅保留最後 capacity 個樣本
                self._buf[:] = data[-self._capacity :]
                self._head = 0
                self._count = self._capacity
            else:
                end = self._head + n
                if end <= self._capacity:
                    self._buf[self._head : end] = data
                else:
                    # 跨越緩衝區邊界，分兩段寫入
                    first = self._capacity - self._head
                    self._buf[self._head :] = data[:first]
                    self._buf[: n - first] = data[first:]
                self._head = (self._head + n) % self._capacity
                self._count = min(self._count + n, self._capacity)

    def read_all(self) -> np.ndarray:
        """讀取緩衝區中所有有效樣本（按時間順序）。

        Returns:
            一維 float32 陣列，包含最多 capacity 個樣本，最舊的在前。
        """
        with self._lock:
            if self._count < self._capacity:
                return self._buf[: self._count].copy()
            # 緩衝區已滿：head 指向最舊樣本
            return np.concatenate([
                self._buf[self._head :],
                self._buf[: self._head],
            ])

    def clear(self) -> None:
        """清空緩衝區，重設所有指標。"""
        with self._lock:
            self._buf[:] = 0.0
            self._head = 0
            self._count = 0


def compute_rms(frame: np.ndarray) -> float:
    """計算音訊幀的 RMS（均方根）音量。

    使用 float64 中間計算以保留精度。

    Args:
        frame: 一維音訊樣本陣列（任意數值型別）

    Returns:
        RMS 值（float），靜音時接近 0.0，音量越大值越高。
    """
    if len(frame) == 0:
        return 0.0
    return float(np.sqrt(np.mean(frame.astype(np.float64) ** 2)))
