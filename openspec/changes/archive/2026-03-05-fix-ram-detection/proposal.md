## Why

啟動時 `HardwareDetector._get_total_ram_mb()` 無法取得真實 RAM 值，退回假設 4096 MB 並觸發 WARNING，導致硬體能力評估不準確、推理路徑建議可能錯誤。主因是 `psutil` 未列為正式依賴，且 Windows 11 22H2+ 已廢棄 `wmic`，使所有備案方法均失敗。

## What Changes

- 將 `psutil>=5.9` 加入 `pyproject.toml` 的正式 `dependencies`
- 在 `_get_total_ram_mb()` 的 Windows fallback 鏈中，於 `wmic` 之前插入 ctypes `GlobalMemoryStatusEx` 備案（純 Windows API，無外部依賴）
- 強化各 fallback 層的 debug log，區分每層失敗原因以便後續排查

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `hardware-detection`: RAM 偵測需求新增：應優先使用 `psutil`（需列為正式依賴），Windows 環境需提供不依賴 `wmic` 的備案方法（ctypes GlobalMemoryStatusEx）

## Impact

- Affected code: `airtype/utils/hardware_detect.py` — `_get_total_ram_mb()`
- Affected code: `pyproject.toml` — 加入 psutil 依賴
- Affected specs: `hardware-detection`
