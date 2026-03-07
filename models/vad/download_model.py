"""下載 Silero VAD v5 ONNX 模型至 models/vad/ 目錄。

用法：
    python models/vad/download_model.py

模型來源：snakers4/silero-vad（HuggingFace Hub / GitHub）
模型大小：約 2MB
"""

from __future__ import annotations

import hashlib
import os
import sys
import urllib.request
from pathlib import Path

MODEL_FILENAME = "silero_vad_v5.onnx"
MODEL_DIR = Path(__file__).parent
MODEL_PATH = MODEL_DIR / MODEL_FILENAME

# Silero VAD ONNX 模型下載 URL（GitHub raw）
MODEL_URL = (
    "https://github.com/snakers4/silero-vad/raw/master/src/silero_vad/data/silero_vad.onnx"
)


def download(url: str, dest: Path) -> None:
    """從 URL 下載檔案至 dest，並顯示進度。"""
    print(f"下載中：{url}")
    print(f"目的地：{dest}")

    def _reporthook(block_num: int, block_size: int, total_size: int) -> None:
        downloaded = block_num * block_size
        if total_size > 0:
            pct = min(100, downloaded * 100 // total_size)
            bar = "#" * (pct // 5) + "-" * (20 - pct // 5)
            print(f"\r  [{bar}] {pct:3d}%  ({downloaded:,}/{total_size:,} bytes)", end="")
        else:
            print(f"\r  Downloaded {downloaded:,} bytes", end="")

    urllib.request.urlretrieve(url, dest, reporthook=_reporthook)
    print()


def main() -> None:
    if MODEL_PATH.exists():
        print(f"模型已存在：{MODEL_PATH}（略過下載）")
        sys.exit(0)

    MODEL_DIR.mkdir(parents=True, exist_ok=True)

    try:
        download(MODEL_URL, MODEL_PATH)
        size = MODEL_PATH.stat().st_size
        print(f"下載完成：{MODEL_PATH}（{size:,} bytes）")
    except Exception as exc:
        print(f"下載失敗：{exc}", file=sys.stderr)
        if MODEL_PATH.exists():
            MODEL_PATH.unlink()
        sys.exit(1)


if __name__ == "__main__":
    main()
