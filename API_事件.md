# 事件说明

> 本模组通过引擎事件系统抛出多种自定义事件。外部模组可用 `ListenForEvent` 监听。
> 客户端 API 见 [API_客户端.md](API_客户端.md)，服务端 API 见 [API_服务端.md](API_服务端.md)，总览见 [API_列表.md](API_列表.md)。

## 事件总览

| 事件常量 | 事件名字符串 | 方向 | 触发时机 | 事件数据 |
|----------|--------------|------|----------|----------|
| `SettingsUIOpenEvent` | `Script_NeteaseMod9sPMlz0K_SettingsUIOpen` | 客户端 | 玩家打开设置界面 | `{"playerId": str}` |
| `SettingsUICloseEvent` | `Script_NeteaseMod9sPMlz0K_SettingsUIClose` | 客户端 | 玩家关闭设置界面 | `{"playerId": str}` |
| `PopUpOpenEvent` | `Script_NeteaseMod9sPMlz0K_PopUpOpen` | 客户端 | 弹窗压栈打开时 | `{"playerId": str, "popupId": str, "useScroll": bool}` |
| `PopUpCloseEvent` | `Script_NeteaseMod9sPMlz0K_PopUpClose` | 客户端 | 弹窗出栈关闭时 | `{"playerId": str}` |
| `SettingsOpenFromCommandEvent` | `Script_NeteaseMod9sPMlz0K_OpenSettingsFromCommand` | 服务端→客户端 | `/setting_open` 指令触发 | `{"main_card_id": str, "middle_card_id": str, "sub_key": str}` |

> 客户端事件常量均可从 `CardRegistryApi` 导入：`SettingsUIOpenEvent`、`SettingsUICloseEvent`、`PopUpOpenEvent`、`PopUpCloseEvent`。
> `SettingsOpenFromCommandEvent` 定义在 `Server.py`，默认不对外导出；客户端监听时直接使用事件名字符串即可。

## 监听说明

所有客户端事件均通过 `ListenForEvent("Script_NeteaseMod9sPMlz0K", "client", ...)` 监听；`namespace` 和 `systemName` 固定为 `"Script_NeteaseMod9sPMlz0K"` 和 `"client"`。

## 设置界面事件

当玩家打开或关闭设置 UI 时，`MyClientSystem` 会向引擎抛出事件。

```python
from CardRegistryApi import SettingsUIOpenEvent, SettingsUICloseEvent

class MyExternalSystem(ClientSystem):
    def __init__(self, namespace, systemName):
        ClientSystem.__init__(self, namespace, systemName)
        self.ListenForEvent(
            "Script_NeteaseMod9sPMlz0K", "client",
            SettingsUIOpenEvent, self, self.OnSettingsOpen
        )
        self.ListenForEvent(
            "Script_NeteaseMod9sPMlz0K", "client",
            SettingsUICloseEvent, self, self.OnSettingsClose
        )

    def OnSettingsOpen(self, args):
        playerId = args.get("playerId", "")
        print "==== Player %s opened settings UI ====" % playerId

    def OnSettingsClose(self, args):
        playerId = args.get("playerId", "")
        print "==== Player %s closed settings UI ====" % playerId
```

## 弹窗事件

```python
from CardRegistryApi import PopUpOpenEvent, PopUpCloseEvent

class MyExternalSystem(ClientSystem):
    def __init__(self, namespace, systemName):
        ClientSystem.__init__(self, namespace, systemName)
        self.ListenForEvent(
            "Script_NeteaseMod9sPMlz0K", "client",
            PopUpOpenEvent, self, self.OnPopUpOpen
        )
        self.ListenForEvent(
            "Script_NeteaseMod9sPMlz0K", "client",
            PopUpCloseEvent, self, self.OnPopUpClose
        )

    def OnPopUpOpen(self, args):
        # args = {"playerId": str, "popupId": str, "useScroll": bool}
        print "==== popup opened: %s scroll=%s ====" % (
            args.get("popupId", ""), args.get("useScroll", False))

    def OnPopUpClose(self, args):
        print "==== popup closed for %s ====" % args.get("playerId", "")
```

## 指令打开设置事件（服务端 → 客户端）

由 `/setting_open` 指令触发（见 [API_服务端.md](API_服务端.md)），`MyServerSystem` 将 `NotifyToClient` 到目标客户端。外部模组如需在指令打开设置时做额外处理，可监听：

```python
class MyClientSystem(ClientSystem):
    def __init__(self, namespace, systemName):
        ClientSystem.__init__(self, namespace, systemName)
        self.ListenForEvent(
            "Script_NeteaseMod9sPMlz0K", "client",
            "Script_NeteaseMod9sPMlz0K_OpenSettingsFromCommand",
            self, self.OnOpenSettingsFromCommand
        )

    def OnOpenSettingsFromCommand(self, args):
        main_card_id = args.get("main_card_id", "")
        middle_card_id = args.get("middle_card_id", "")
        sub_key = args.get("sub_key", "")
        print "==== open settings via command: main=%s sub=%s middle=%s ====" % (
            main_card_id, sub_key, middle_card_id)
```
