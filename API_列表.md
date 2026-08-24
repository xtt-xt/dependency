# API 列表（总览）

> 本模组专为外部模组提供设置界面卡片注册能力。所有公开 API 均通过 `CardRegistryApi` 统一导出。
> **外部模组调用本 API 时务必遵循下方「外部模组集成要求」**，否则可能因网易多 Addon 加载顺序导致 `ImportError`。

## 模块总览

| 模块文件 | 职责 | 详细文档 |
|----------|------|----------|
| `CardRegistry.py` | 纯注册表：主卡片 / 中间卡片 / 内容项 / 弹窗 / 折叠菜单 / 事件常量 | [API_客户端.md](API_客户端.md) |
| `CardRegistryApi.py` | 对外门面：再导出全部公开 API + 导航/锁定/弹窗/折叠菜单便捷封装 | [API_客户端.md](API_客户端.md) |
| `SettingState.py` | 设置项持久化（`ConfigCompClient` 本地存储） | [API_客户端.md](API_客户端.md#设置项状态系统-api) |
| `Toast.py` | Toast 提示系统（叠加层显示、排队播放） | [API_客户端.md](API_客户端.md#toast-提示-api) |
| `DebugLog.py` | 调试日志开关（客户端/服务端独立控制，单例 `dlog`） | [API_客户端.md](API_客户端.md#客户端调试日志开关) |
| `setting.py` | 框架自带"设置配置"卡片注册（含客户端/服务端"调试>日志输出"开关） | [API_服务端.md](API_服务端.md#服务端全局调试日志开关) |
| `Server.py` | 服务端系统：处理 `/setting_open` 自定义指令 + 全局日志开关（OP 鉴权/同步） | [API_服务端.md](API_服务端.md) |

## 导入方式

只需导入 `CardRegistryApi` 即可获得全部公开 API，无需分别从其他模块导入：

```python
from CardRegistryApi import (
    # 主卡片
    RegisterMainCard, GetMainCard, GetAllMainCardIds, UnregisterMainCard,
    # 中间卡片
    RegisterMiddleCard, GetMiddleCardBindings, UnregisterMiddleCard,
    ClearMiddleCardBindings,
    # 整体重置
    ClearAllCards,
    # 右侧内容项
    CreateContentInst, GetContentItems, GetContentItem, ClearContentItems,
    RegisterContentItemType, GetContentItemFactory,
    RegisterContentListener, UnregisterContentListener,
    # 辅助函数
    NormalizeMiddleCardId, GetAllContentGroups,
    # 回调机制
    SetCardChangedCallback,
    # 事件常量
    SettingsUIOpenEvent, SettingsUICloseEvent,
    # 弹窗
    RegisterPopUp, UnregisterPopUp, GetPopUp, GetAllPopUpIds,
    ShowPopUp, ClosePopUp,
    # 折叠菜单
    RegisterCollapsibleMenu, AddCollapsibleMenuCard,
    GetCollapsibleMenu, GetCollapsibleMenuCards,
    ShowCollapsibleMenu, CloseCollapsibleMenu,
    # 弹窗事件常量
    PopUpOpenEvent, PopUpCloseEvent,
    # 跳转事件常量 + 跳转拦截 API
    SettingsNavigateEvent,
    RegNavigateBlockCallback, UnregNavigateBlockCallback, IsNavigateBlocked,
    # UI 构建器注册
    RegisterContentBuilder,
    # 导航 API
    OpenSettings,
    # 锁定 API
    SetLocked,
    # 设置项状态系统
    MakeSettingKey, GetSettingValue, GetSettingLocked, SetSettingValue,
    ResetSettingValue, ResetAllSettings, ResetGroupSettings,
    SaveGroupSettings, SaveAllSettings,
    # Toast 提示
    ShowToast, ToastTop, ToastTopRight, ToastUnder,
)
```

也支持 `from CardRegistryApi import *` 一键导入全部。

## API 快速索引

### 客户端 API（详见 [API_客户端.md](API_客户端.md)）

| 分类 | API |
|------|-----|
| 主卡片 | `RegisterMainCard` `GetMainCard` `GetAllMainCardIds` `UnregisterMainCard` `ClearAllCards` `SetCardChangedCallback` |
| 中间卡片 | `RegisterMiddleCard` `GetMiddleCardBindings` `UnregisterMiddleCard` `ClearMiddleCardBindings` |
| 内容项（链式） | `CreateContentInst` `ForMiddleCard` `AddText` `AddButton` `AddSwitch` `AddEditBox` `AddResetButton` `AddCustom` `AddSlider` `AddCollapsibleMenu` `Clear` `Remove` |
| 内容项查询 | `GetContentItems` `GetContentItem` `ClearContentItems` `GetAllContentGroups` `NormalizeMiddleCardId` |
| 内容项扩展 | `RegisterContentItemType` `GetContentItemFactory` `RegisterContentBuilder` `RegisterContentListener` `UnregisterContentListener` |
| 弹窗 | `RegisterPopUp` `UnregisterPopUp` `GetPopUp` `GetAllPopUpIds` `ShowPopUp` `ClosePopUp` |
| 折叠菜单 | `RegisterCollapsibleMenu` `AddCollapsibleMenuCard` `GetCollapsibleMenu` `GetCollapsibleMenuCards` `ShowCollapsibleMenu` `CloseCollapsibleMenu` |
| 锁定 | `SetLocked` |
| 设置项状态 | `MakeSettingKey` `GetSettingValue` `GetSettingLocked` `SetSettingValue` `ResetSettingValue` `ResetAllSettings` `ResetGroupSettings` `SaveGroupSettings` `SaveAllSettings` |
| 导航 | `OpenSettings` |
| 跳转拦截 | `SettingsNavigateEvent` `RegNavigateBlockCallback` `UnregNavigateBlockCallback` `IsNavigateBlocked` |
| Toast | `ShowToast` `ToastTop` `ToastTopRight` `ToastUnder` |

### 服务端 API（详见 [API_服务端.md](API_服务端.md)）

| 分类 | API |
|------|-----|
| 自定义指令 | `/setting_open`（`setting_open`） |

### 事件（详见 [API_事件.md](API_事件.md)）

| 分类 | 事件常量 |
|------|----------|
| 设置界面 | `SettingsUIOpenEvent` `SettingsUICloseEvent` |
| 弹窗 | `PopUpOpenEvent` `PopUpCloseEvent` |
| 跳转 | `SettingsNavigateEvent`（`/setting_open` 跳转前） |
| 服务端→客户端 | `Script_NeteaseMod9sPMlz0K_OpenSettingsFromCommand`（指令打开设置） |

## 外部模组集成要求

### ⚠️ 禁止顶层 import

```python
# ❌ 错误：在脚本文件顶部直接 import
from Script_NeteaseMod9sPMlz0K.CardRegistry import RegisterMainCard
class MySystem(ClientSystem):
    ...
```

**原因**：网易客户端的多 Addon 加载**不保证顺序**。你的模组脚本被加载时，本模组的脚本可能尚未注册，顶层 import 会抛出 `ImportError`。

### ✅ 正确方式

在 `UiInitFinished` / `LoadClientAddonScriptsAfter` 事件中**延迟导入**，并防御性地处理 `ImportError`：

```python
class MyClientSystem(ClientSystem):

    def __init__(self, namespace, systemName):
        ClientSystem.__init__(self, namespace, systemName)
        self.ListenForEvent(
            clientApi.GetEngineNamespace(),
            clientApi.GetEngineSystemName(),
            'UiInitFinished',
            self,
            self.onUiReady
        )

    def onUiReady(self, args):
        # 延迟导入，防御对方模组未安装的情况
        try:
            from Script_NeteaseMod9sPMlz0K.CardRegistryApi import (
                RegisterMainCard, RegisterMiddleCard,
            )
        except ImportError:
            print "==== CardRegistryApi 模组未安装，跳过注册 ===="
            return

        # 注册主卡片 + 中间卡片（注册后自动刷新 UI，无需手动调用 RebuildMainCards）
        RegisterMainCard("my_mod", "我的模组", "textures/ui/sidebar_icons/addon")
        RegisterMiddleCard("my_mod", "server", "my_feat", "我的功能")
```

### 自动刷新机制

`RegisterMainCard` 和 `UnregisterMainCard` 成功执行后，`MyClientSystem` 内部会自动调用 `SettingsScreenNode.RebuildMainCards()` 刷新左侧卡片列表。

- **设置界面已打开时**：注册/注销主卡片后立即自动刷新，无需手动调用。
- **设置界面未打开时**：注册/注销操作仍然生效，下次玩家打开设置界面时（`OnActive`）会自动从注册表重建左侧卡片列表。

> 外部模组只需调用 `RegisterMainCard`/`UnregisterMainCard`，无需关心 UI 刷新逻辑。
