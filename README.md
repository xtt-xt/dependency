# 通用模组前置（CardRegistry）

网易我的世界（NetEase MC）Studio 前置模组，为其他模组提供一套**基于卡片的设置界面框架**（`CardRegistry`）。

## 功能特性

- **三层卡片结构**：左侧主卡片 → 子卡片（client/server）→ 中间卡片 → 右侧内容项
- **丰富内容项**：文字（可指定文字颜色）、按钮、开关、输入框、滑块、折叠菜单、重置按钮
- **弹窗系统**：通用确认弹窗（内容超长自动滚动，支持自定义按钮）
- **折叠菜单**：单选式下拉菜单，选中状态自动持久化
- **组合开关弹窗**：普通按钮打开弹窗，支持物品/纯文字/编辑框三种行控件混合、行级锁定（开关内置锁定贴图 / 编辑框 lock 覆盖层）、单选/多选、弹窗内容超出自动滚动，可注册底部自定义按钮，状态独立持久化
- **物品选择**：内容项右侧显示选中物品图标 + 箭头按钮，点开为 8 列网格弹窗（搜索框按 identifier / 显示名过滤、翻页、点「确定」才写回），可列出原版与模组全部物品，选中状态自动持久化
- **Toast 提示**：顶部 / 右上 / 底部轻量提示，支持物品与图片图层、自定义文字与颜色、同位置排队播放；可自定义入场/出场音效与背景贴图（九宫格剪裁）
- **设置持久化**：开关 / 输入框 / 锁定状态自动保存到本地存储
- **重置本页**：客户端重置本地存储；服务端分组额外重置服务端权威默认值并**广播全服**（OP 鉴权，参考 FlyArmor 方法）
- **外部接入**：通过 `CardRegistryApi` 统一导出全部公开 API

## 打开设置界面

| 方式 | 说明 |
|------|------|
| **U 键** | 默认打开方式（可在游戏设置中改键），**ESC 关闭** |
| **官方设置入口** | 暂停菜单 → 模组设置 → 选中本模组 → 点"打开设置"按钮，关闭官方界面并打开本模组设置界面 |
| **导航 API** | 外部模组可直接调用 `OpenSettings(main_card_id, sub_key, middle_card_id)` 打开并导航到指定卡片，详见[导航 API](docs/API_客户端.md#导航-api) |

> 本模组**不再向原生暂停界面注入按钮**：平台自 2026-12-01 起机审拦截开发者对原生 `pause_screen` / `settings_screen` 的修改，入口统一走网易官方「通用设置」接口注册。

> 若要在游戏内以指令方式打开/导航自己的设置界面，可使用 `/setting_open` 命令（对所有成员可用，但只作用于调用者自己），详见[服务端 API](docs/API_服务端.md)。

## 目录结构

```
.
├── behavior_pack_GQ74TKax/               # 行为包（模组代码）
│   ├── Script_NeteaseMod9sPMlz0K/        # 模组脚本（Python 2.7）
│   │   ├── modMain.py                    # 入口，绑定 MyServerSystem / MyClientSystem
│   │   ├── CardRegistry.py               # 纯注册表（卡片、内容项、弹窗、事件常量）
│   │   ├── CardRegistryApi.py            # 对外门面，再导出全部公开 API
│   │   ├── Client.py                     # MyClientSystem + 设置界面/弹窗/暂停界面等 UI 实现
│   │   ├── Server.py                     # 服务端系统：/setting_open 指令 + 全局日志开关 + 重置本页（服务端权威）
│   │   ├── SettingState.py               # 设置项持久化（ConfigCompClient 本地存储）
│   │   ├── DebugLog.py                   # 调试日志开关（客户端/服务端独立控制）
│   │   ├── setting.py                    # 框架自带"设置配置"卡片注册
│   │   └── Toast.py                      # Toast 提示系统
│   └── netease_commands/                 # 自定义指令定义（setting_open）
├── resource_pack_nka0OOhF/
│   └── ui/                               # JSON UI（setting / pop_up / toast / mod_settings_button ...）
├── README.md                             # 本文件
└── docs/                                 # 对外文档
    ├── API_列表.md                       # API 总览、导入方式、快速索引、外部模组集成要求
    ├── API_客户端.md                     # 客户端 API 详细文档
    ├── API_服务端.md                     # 服务端 API（/setting_open 指令）
    └── API_事件.md                       # 全部事件说明
```

## 快速开始（外部模组接入）

1. 在 `UiInitFinished` 事件中**延迟导入** `CardRegistryApi`（禁止顶层 import，详见 [API_列表.md](docs/API_列表.md#外部模组集成要求)）。
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

## 开发者选项分页（维护者）

框架自带的「设置配置」主卡片里有一个**开发者选项**中间分页，用于集中放置测试卡片、测试弹窗与演示内容（当前放了开发版本提示 + 物品选择弹窗演示）。发布正式版时，把 `behavior_pack_GQ74TKax/Script_NeteaseMod9sPMlz0K/setting.py` 中 `RegisterSettingsConfig` 里带「开发者选项」横幅的那一整块注释掉即可，该分页不再注册，其余分页与已存配置不受影响。以后新增的测试内容都往这一块里加。

## 文档导航

| 文档 | 内容 |
|------|------|
| [API_列表.md](docs/API_列表.md) | 模块总览、统一导入方式、API 快速索引、外部模组集成要求 |
| [API_客户端.md](docs/API_客户端.md) | 主/中间卡片、内容项、弹窗、折叠菜单、组合开关、Toast、锁定、设置状态、导航等客户端 API 详解 |
| [API_服务端.md](docs/API_服务端.md) | `/setting_open` 自定义指令参数与使用示例 |
| [API_事件.md](docs/API_事件.md) | 设置界面开关、弹窗、指令等事件常量与监听示例 |


## 开源协议
本项目采用 [GNU Lesser General Public License v3.0](LICENSE) 协议开源，该协议并入的 GPLv3 全文见 [COPYING](COPYING)。
