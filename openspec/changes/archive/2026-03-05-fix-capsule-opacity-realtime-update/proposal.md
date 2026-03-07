## Why

調整外觀設定面板的膠囊不透明度滑桿時，膠囊視窗不會即時反映變化，必須重新啟動 App 才會套用。此問題導致使用者無法在調整時即時預覽效果，體驗明顯不足。

## What Changes

- 在 `airtype/__main__.py` 的 UI 初始化流程中，補上 `settings_window.connect_overlay(overlay)` 的呼叫，使已實作完成的 Signal 連接正式生效。

## Capabilities

### New Capabilities

- `overlay-settings-wiring`: 定義設定面板外觀 Signal（opacity_changed、theme_changed、position_changed）須於啟動時連接至膠囊視窗，確保所有外觀調整即時生效，不需重啟 App。

### Modified Capabilities

（無）

## Impact

- **Affected code**: `airtype/__main__.py`（第 55–56 行，新增一行呼叫）
- **Side effect（正向）**：`connect_overlay()` 同時連接了 `theme_changed`、`opacity_changed`、`position_changed` 三個 Signal，因此主題切換與膠囊位置調整也將同步獲得即時生效能力。
