# 通用模组前置（CardRegistry）

网易我的世界（NetEase MC）Studio 前置模组，为其他模组提供一套**基于卡片的设置界面框架**（`CardRegistry`）。

## 功能特性

- **三层卡片结构**：左侧主卡片 → 子卡片（client/server）→ 中间卡片 → 右侧内容项
- **丰富内容项**：文字、按钮、开关、输入框、滑块、折叠菜单、重置按钮
- **弹窗系统**：通用确认弹窗（内容超长自动滚动，支持自定义按钮）
- **折叠菜单**：单选式下拉菜单，选中状态自动持久化
- **Toast 提示**：顶部 / 右上 / 底部轻量提示，支持物品与图片图层、自定义文字与颜色、同位置排队播放
- **设置持久化**：开关 / 输入框 / 锁定状态自动保存到本地存储
- **外部接入**：通过 `CardRegistryApi` 统一导出全部公开 API

## 打开设置界面

| 方式 | 说明 |
|------|------|
| **U 键** | 默认打开方式（可在游戏设置中改键），**ESC 关闭** |
| **暂停菜单 → 模组设置按钮** | 向暂停界面注入"模组设置"按钮 |
| **官方设置入口** | 暂停菜单 → 模组 → 本模组 → 点"打开设置"按钮，关闭官方界面并打开本模组设置界面 |
| **导航 API** | 外部模组可直接调用 `OpenSettings(main_card_id, sub_key, middle_card_id)` 打开并导航到指定卡片，详见[导航 API](API_客户端.md#导航-api) |

> 若要在游戏内以指令方式打开/导航（如给指定玩家或管理员操作），仍可使用 `/setting_open` 命令，详见[服务端 API](API_服务端.md)。

## 目录结构

```
.
├── behavior_pack_GQ74TKax/               # 行为包（模组代码）
│   ├── Script_NeteaseMod9sPMlz0K/        # 模组脚本（Python 2.7）
│   │   ├── modMain.py                    # 入口，绑定 MyServerSystem / MyClientSystem
│   │   ├── CardRegistry.py               # 纯注册表（卡片、内容项、弹窗、事件常量）
│   │   ├── CardRegistryApi.py            # 对外门面，再导出全部公开 API
│   │   ├── Client.py                     # MyClientSystem + 设置界面/弹窗/暂停界面等 UI 实现
│   │   ├── Server.py                     # 服务端系统，处理 /setting_open 指令
│   │   ├── SettingState.py               # 设置项持久化（ConfigCompClient 本地存储）
│   │   └── Toast.py                      # Toast 提示系统
│   └── netease_commands/                 # 自定义指令定义（setting_open）
├── resource_pack_nka0OOhF/
│   └── ui/                               # JSON UI（setting / pop_up / toast / pause_screen ...）
├── README.md                             # 本文件
├── API_列表.md                           # API 总览、导入方式、快速索引、外部模组集成要求
├── API_客户端.md                         # 客户端 API 详细文档
├── API_服务端.md                         # 服务端 API（/setting_open 指令）
└── API_事件.md                           # 全部事件说明
```

## 快速开始（外部模组接入）

1. 在 `UiInitFinished` 事件中**延迟导入** `CardRegistryApi`（禁止顶层 import，详见 [API_列表.md](API_列表.md#外部模组集成要求)）。
2. 注册主卡片、中间卡片、内容项：
   ```python
   from Script_NeteaseMod9sPMlz0K.CardRegistryApi import (
       RegisterMainCard, RegisterMiddleCard, CreateContentInst,
   )
   RegisterMainCard("my_mod", "我的模组", "textures/ui/icon_setting")
   RegisterMiddleCard("my_mod", "client", "my_feat", "我的功能")
   CreateContentInst("my_mod", "client", "my_feat")\
       .AddButton("btn", "启用功能", "启用")\
       .AddSwitch("auto", "自动保存", default_value=True)
   ```

## 文档导航

| 文档 | 内容 |
|------|------|
| [API_列表.md](API_列表.md) | 模块总览、统一导入方式、API 快速索引、外部模组集成要求 |
| [API_客户端.md](API_客户端.md) | 主/中间卡片、内容项、弹窗、折叠菜单、Toast、锁定、设置状态、导航等客户端 API 详解 |
| [API_服务端.md](API_服务端.md) | `/setting_open` 自定义指令参数与使用示例 |
| [API_事件.md](API_事件.md) | 设置界面开关、弹窗、指令等事件常量与监听示例 |

## 开发说明

- 模组脚本为 **Python 2.7**（网易 Mod SDK），禁止 Python 3 语法。
- 本机无法直接运行脚本，验证方式 = 启动测试世界（`.mcdev.json` 已开启模组/UI 自动热重载），调试输出在客户端控制台。
- 模组命名空间：`Script_NeteaseMod9sPMlz0K`（用于 `modMain.py` 绑定、`RegisterSystem` 名称及所有自定义事件名前缀）。
