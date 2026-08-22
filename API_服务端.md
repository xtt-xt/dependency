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
| permission_level | `game_directors`（游戏管理员） |

### 参数

| 参数名 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| 目标 | target | `@s` | 打开设置的目标玩家选择器 |
| 主卡片id | str | `""` | 打开后选中的主卡片 unique_id |
| 中间卡片id | str | `""` | 打开后选中的中间卡片 unique_id |
| 子卡片key | str | `""` | 子卡片 key，`"client"` 或 `"server"` |

## 使用示例

```text
# 打开自己的设置界面
/setting_open

# 打开自己并导航到指定主卡片
/setting_open @s 基础设置

# 打开指定玩家并导航到主卡片 + 子卡片 + 中间卡片
/setting_open @p 基础设置 opt_a client

# 打开所有玩家
/setting_open @a
```

## 处理流程（Server.py）

1. `MyServerSystem` 监听引擎事件 `CustomCommandTriggerServerEvent`，当 `command == "setting_open"` 时处理。
2. 解析参数（按 `name` 匹配：目标 / 主卡片id / 中间卡片id / 子卡片key）。
3. 解析目标玩家：
   - 未传参：使用 `origin.entityId`（触发者自身）。
   - `tuple` 类型：引擎已解析（如 `@a` 返回多个玩家 ID）。
   - `str` 类型（默认值 `@s` 以字符串到达）：调用实体组件 `GetEntitiesBySelector` 手动解析（注意：须用 **Entity 组件**，不是 game 组件）；解析失败回退 `origin.entityId`。
4. 向每个目标客户端 `NotifyToClient` 发送自定义事件 `SettingsOpenFromCommandEvent`（事件名 `Script_NeteaseMod9sPMlz0K_OpenSettingsFromCommand`），事件数据：

```python
{
    "main_card_id": str,
    "middle_card_id": str,
    "sub_key": str,
}
```

5. 客户端 `MyClientSystem.OnOpenSettingsFromCommand` 监听该事件，调用 `OpenSettings` 打开设置界面并导航。

> 服务端 → 客户端事件的事件常量定义在 `Server.py`：`SettingsOpenFromCommandEvent`，但**默认不对外导出**（客户端监听时直接使用事件名字符串，见 [API_事件.md](API_事件.md)）。
