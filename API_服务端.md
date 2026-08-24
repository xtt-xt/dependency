# 服务端 API 详解

> 覆盖：`/setting_open` 自定义指令。服务端系统在 `Server.py`（`MyServerSystem`）中实现。
> 客户端 API 见 [API_客户端.md](API_客户端.md)，事件见 [API_事件.md](API_事件.md)，总览见 [API_列表.md](API_列表.md)。

> **提示**：本指令仅用于游戏内/管理侧触发。外部模组若需打开/导航本设置界面，应**直接调用 `OpenSettings` API**（见 [客户端 API](API_客户端.md#导航-api)），无需依赖本指令。

## 指令定义

指令定义文件：`behavior_pack_GQ74TKax/netease_commands/craftStudio_Script_NeteaseMod9sPMlz0K_setting_open.json`

| 字段 | 值 |
|------|-----|
| name | `setting_open` |
| description | 打开模组设置界面，可选导航到指定卡片 |
| permission_level | `any`（所有成员可用） |

### 参数

| 参数名 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| 目标 | target | `@s` | 目标玩家选择器。**仅对调用者自己生效**，`@a`/指定他人会被忽略（仅作用于触发者） |
| 主卡片id | str | `""` | 打开后选中的主卡片 unique_id |
| 中间卡片id | str | `""` | 打开后选中的中间卡片 unique_id |
| 子卡片key | str | `""` | 子卡片 key，`"client"` 或 `"server"` |

> **安全约束**：命令对所有成员可用，但服务端强制只作用于**调用者自己**，即使传入 `@a`、`@p` 或指定玩家也无法强制他人弹出设置界面（防止骚扰/DoS）。

## 使用示例

```text
# 打开自己的设置界面
/setting_open

# 打开自己并导航到指定主卡片
/setting_open @s 基础设置

# 打开自己并导航到主卡片 + 子卡片 + 中间卡片
/setting_open @s 基础设置 opt_a client

# 打开自己（@a / 指定他人亦被忽略，仅作用于调用者）
/setting_open @a
```

## 处理流程（Server.py）

1. `MyServerSystem` 监听引擎事件 `CustomCommandTriggerServerEvent`，当 `command == "setting_open"` 时处理。
2. 解析参数（按 `name` 匹配：目标 / 主卡片id / 中间卡片id / 子卡片key）。
3. **安全收窄**：无论命令携带的目标参数如何，强制把目标设为 `origin.entityId`（调用者自己，即触发命令的玩家）；缺少 `origin.entityId` 则直接返回，不发送任何事件。`@a`、`@p`、指定玩家都会被忽略，只作用于调用者本人，防止低权限玩家强制他人弹出设置界面。
4. 向该目标客户端 `NotifyToClient` 发送自定义事件 `SettingsOpenFromCommandEvent`（事件名 `Script_NeteaseMod9sPMlz0K_OpenSettingsFromCommand`），事件数据：

```python
{
    "main_card_id": str,
    "middle_card_id": str,
    "sub_key": str,
}
```

5. 客户端 `MyClientSystem.OnOpenSettingsFromCommand` 监听该事件，调用 `OpenSettings` 打开设置界面并导航。

> 服务端 → 客户端事件的事件常量定义在 `Server.py`：`SettingsOpenFromCommandEvent`，但**默认不对外导出**（客户端监听时直接使用事件名字符串，见 [API_事件.md](API_事件.md)）。

## 服务端全局调试日志开关

> 对应设置界面「设置配置 >(服务端) 调试 > 日志输出」开关，**全局生效，仅 OP 可改**。
> 客户端侧的个人 `日志输出` 开关见 [API_客户端.md](API_客户端.md#客户端调试日志开关)，外部模组若需直接控制本框架日志，可读取/写入 `DebugLog` 单例 `dlog`。

- **存储**：服务端全局配置文件（`ModAttrComponentServer`），键 `Script_NeteaseMod9sPMlz0K_server_log_enabled`，`needRestore=True` + `SaveAttr` 持久化。
- **鉴权**：`IsOperator(playerId)` 通过 `PlayerCompServer.GetPlayerOperation() >= 2` 判断是否为 OP。
- **同步事件**（均定义在 `Server.py`）：
  - `ReqServerLogEvent`（client → server）：客户端请求当前全局值 + 自身 OP 状态。
  - `SetServerLogEvent`（client → server）：客户端请求修改全局值；**非 OP 的修改会被忽略**，并向该客户端回发当前值纠正 UI。
  - `ServerLogSyncEvent`（server → client）：服务端下发当前全局值 + 该客户端各自的 OP 状态（用于 UI 锁定）。
