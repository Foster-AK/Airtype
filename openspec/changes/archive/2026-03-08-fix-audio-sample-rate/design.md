## Context

目前 `AudioCaptureService.start()` 硬編碼 `samplerate=16000` 開啟 `sd.InputStream`。在 Windows WASAPI 共享模式下，部分裝置（USB 麥克風、虛擬音訊裝置）不支援 16kHz，導致 `PortAudioError -9997 (Invalid sample rate)`。現有 fallback 僅切換至預設裝置（仍以 16kHz 開啟），使用者選定的麥克風無法正常使用。

`sounddevice >= 0.4.7` 提供 `sd.WasapiSettings(auto_convert=True)`，可在 Windows WASAPI 共享模式下啟用 `AUDCLNT_STREAMFLAGS_AUTOCONVERTPCM` 旗標，讓 OS 音訊引擎在驅動層自動處理取樣率轉換。

## Goals / Non-Goals

**Goals:**

- 讓不原生支援 16kHz 的 WASAPI 裝置能正常開啟串流
- 零應用層 CPU 開銷（轉換在 OS 驅動層完成）
- 最小程式碼改動、不破壞現有行為
- 麥克風測試功能同步修復

**Non-Goals:**

- 不實作應用層重採樣邏輯（soxr / scipy）
- 不修改 macOS / Linux 音訊路徑
- 不變更音訊格式（仍為 16kHz / float32 / mono / 512 blocksize）

## Decisions

### WASAPI auto_convert 平台特定設定

在 Windows 上建立 `sd.InputStream` 時傳入 `extra_settings=sd.WasapiSettings(auto_convert=True)`。

**替代方案考量：**
- **soxr 手動重採樣**：需在 callback 中做 numpy 運算、增加 ~100 行程式碼、累積器邏輯複雜 → 不採用
- **嘗試多個取樣率清單**：需要迴圈嘗試、增加啟動延遲 → 不採用
- **切換 Host API（DirectSound/MME）**：犧牲低延遲特性 → 不採用

**選擇理由：** WASAPI auto_convert 是 OS 層級轉換，零 CPU 開銷、2 行程式碼、不影響 callback 邏輯。

### 抽取 `_build_extra_settings()` 輔助方法

為避免主路徑和 fallback 路徑重複程式碼，抽取一個靜態方法：

```python
@staticmethod
def _build_extra_settings():
    if sys.platform == "win32":
        try:
            return sd.WasapiSettings(auto_convert=True)
        except Exception:
            return None
    return None
```

### 麥克風測試同步修復

`_MicTestWorker.run()` 中的 `sd.InputStream` 也需加入 `extra_settings`，確保設定頁面的裝置測試能正常使用 WASAPI auto_convert。

## Risks / Trade-offs

- **[WASAPI 獨占模式不適用]** → `auto_convert` 僅在共享模式生效。Airtype 使用預設的共享模式，無影響。
- **[非 WASAPI Host API]** → 若 sounddevice 使用非 WASAPI 的 Host API（如 DirectSound），`WasapiSettings` 建構可能失敗 → 已用 try/except 包裹，回退為 `None`。
- **[sounddevice 版本]** → `WasapiSettings` 需 `>= 0.4.7`，`pyproject.toml` 已指定此版本，無風險。
- **[OS 層重採樣品質]** → Windows Audio Engine 的重採樣品質足夠語音辨識使用，不影響 ASR 準確率。
