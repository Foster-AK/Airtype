## Context

Airtype 的外觀設定面板（`settings_appearance.py`）已實作 `opacity_changed`、`theme_changed`、`position_changed` 三個 Qt Signal，並在 `settings_window.py` 提供 `connect_overlay()` 方法負責將這些 Signal 連接至 `CapsuleOverlay`。

然而，`airtype/__main__.py` 在初始化流程中建立兩個物件後，**從未呼叫** `connect_overlay()`，導致 Signal 與 Slot 之間的連線始終不存在。

## Goals / Non-Goals

**Goals:**

- 在 App 啟動流程中呼叫 `settings_window.connect_overlay(overlay)`，使三個外觀 Signal 正式連上膠囊視窗。
- 不透明度、主題切換、膠囊位置三項調整均能即時生效。

**Non-Goals:**

- 不修改 `connect_overlay()` 的實作邏輯。
- 不修改任何 Signal 或 paintEvent 的行為。
- 不涉及其他 UI 設定頁（語音、快捷鍵等）。

## Decisions

### Connect overlay after both objects are initialized

在 `__main__.py` 的 UI 初始化區塊中，`CapsuleOverlay` 先建立（第 51 行），`SettingsWindow` 隨後建立（第 55 行）。`connect_overlay()` 需要兩者都存在，因此必須在第 55 行之後立即呼叫：

```python
settings_window = SettingsWindow(config=cfg)
settings_window.connect_overlay(overlay)  # 連接外觀 Signal → 膠囊即時更新
```

此位置確保：
1. `overlay` 已完成初始化且已呼叫 `connect_controller()`
2. `settings_window` 已完成初始化且 `_page_appearance` 已存在

## Risks / Trade-offs

- [風險] `connect_overlay()` 內部以 `hasattr` 判斷是否連接，若 `settings_window` 在非 PySide6 環境下為 stub class（`else` 分支），`connect_overlay` 方法不存在 → **緩解**：`settings_window.py` 的 else 分支為空 class，不會有 AttributeError，但 signal 也不會連接（可接受，因為無 Qt 環境就沒有 overlay）。
