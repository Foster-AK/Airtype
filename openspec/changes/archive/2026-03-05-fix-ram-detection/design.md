## Context

`HardwareDetector._get_total_ram_mb()` 偵測 RAM 時依序嘗試 psutil → wmic → sysctl → /proc/meminfo → 假設 4096 MB。在使用者環境中，psutil 未安裝（未列為正式依賴），且 Windows 11 22H2+ 已廢棄 wmic，導致所有方法均失敗並觸發 WARNING。

## Goals / Non-Goals

**Goals:**

- 確保 RAM 值在所有目標平台（Windows / macOS / Linux）均能正確取得
- 不依賴已廢棄的 wmic 命令即可在 Windows 上取得 RAM
- 將 psutil 列為正式依賴，使首選方法可靠運作

**Non-Goals:**

- 不修改 RAM 以外的其他硬體偵測邏輯
- 不改變 `SystemCapabilities` 資料結構或 `assess()` 的對外介面

## Decisions

### 將 psutil 加入正式依賴

psutil 已廣泛用於跨平台系統資源查詢，且在 `_get_total_ram_mb()` 中已有完整的使用邏輯，只差未列入 `pyproject.toml`。直接加入依賴是最低成本、最高可靠性的修正。

替代方案：改為 optional dependency → 拒絕，因 RAM 偵測是核心功能，不應設為可選。

### 加入 ctypes GlobalMemoryStatusEx 作為 Windows 備案

ctypes 是 Python 標準函式庫，呼叫 `kernel32.GlobalMemoryStatusEx` 可直接從 Windows API 取得實體記憶體大小，不依賴任何外部程序（wmic 已 deprecated）。此備案在 psutil 不可用時保障 Windows 環境仍能正常取得 RAM。

替代方案：保留 wmic → 拒絕，wmic 在 Windows 11 22H2+ 已移除，不可靠。

替代方案：使用 `winreg` 讀取登錄檔 → 拒絕，登錄檔路徑因 Windows 版本差異可能不穩定。

### 強化各 fallback 層的 debug log

每層失敗時記錄具體原因（ImportError / 指令不存在 / 解析錯誤），不改變 WARNING 訊息格式，只在 DEBUG 層提供更詳細的診斷資訊。

## Risks / Trade-offs

- [風險] ctypes struct 定義若與 Windows 版本不符 → 緩解：`GlobalMemoryStatusEx` 自 Windows 2000 起穩定，結構體定義無版本差異
- [風險] psutil 加入依賴後增加安裝體積（~約 1MB）→ 可接受，psutil 在其他模組（效能監控）也可能用到

## Migration Plan

1. 更新 `pyproject.toml`，加入 `psutil>=5.9`
2. 修改 `_get_total_ram_mb()`，在 Windows wmic fallback 之前插入 ctypes 備案
3. 強化各層 debug log
4. 重新安裝專案（`pip install -e .`）後驗證 WARNING 消失
