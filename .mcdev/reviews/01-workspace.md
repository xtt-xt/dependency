# Python 代码审查报告

> 审查完成：未发现必须修复项，发现 **1 项建议修复的问题**，另有 245 项需要人工确认。

## 扫描概览

| 扫描范围 | 解析状态 | 诊断分布 | 处理优先级 |
|---|---|---|---|
| **1** 包 · **13** 文件 | **13** 正常 | **246** 项 · **20** 警告 · **42** 风险 · **184** 提示 | **1** 建议修复 · **245** 人工确认 |

## 包概览

| 包 | 文件 | 解析状态 | 入口模块 |
|---|---:|---|---|
| `Script_NeteaseMod9sPMlz0K` | 13 | 13 正常 | `behavior_pack_GQ74TKax/Script_NeteaseMod9sPMlz0K/modMain.py` |

## 建议修复

这些问题具有明确风险，建议结合当前发布计划安排修复。

### 导入了违反平台安全规则的模块

**规则：** `platform.restricted-module-import`  |  **级别：** 警告  |  **数量：** 1

> **处理建议：** 仅可在本地自测代码中使用；线上产品应移除该模块或改用 ModSDK 安全 API。

| # | 级别 | 位置 | 所在符号 | 判断依据 |
|---:|---|---|---|---|
| 1 | 警告 | `behavior_pack_GQ74TKax/Script_NeteaseMod9sPMlz0K/SettingState.py:34` | `_SharedState` | 导入模块: __builtin__ |

## 需要人工确认

以下结果来自结构或规模启发式判断。它们不一定是缺陷，请核实业务意图后再修改。

### 单文件过大且逻辑单元过多（可能存在职责堆积）

**规则：** `logic-blob.large-file`  |  **级别：** 警告  |  **数量：** 1

> **处理建议：** 按职责把不相关的类/函数群拆分到独立模块，降低单文件认知负担；若确为数据/生成文件可忽略。

<details>
<summary>查看 1 处位置</summary>

| # | 级别 | 位置 | 所在符号 | 判断依据 |
|---:|---|---|---|---|
| 1 | 警告 | `behavior_pack_GQ74TKax/Script_NeteaseMod9sPMlz0K/Client.py:1` | - | 代码行 5254 ≥ 1200 |

</details>

### 单函数过长（逻辑堆积）

**规则：** `logic-blob.large-function`  |  **级别：** 警告 / 风险  |  **数量：** 24

> **处理建议：** 把独立的步骤/职责抽成子函数，降低单函数认知复杂度；事件分发类长函数可酌情忽略。

<details>
<summary>查看 24 处位置</summary>

| # | 级别 | 位置 | 所在符号 | 判断依据 |
|---:|---|---|---|---|
| 1 | 警告 | `behavior_pack_GQ74TKax/Script_NeteaseMod9sPMlz0K/Client.py:46` | `MyClientSystem.__init__` | 函数约 135 行 ≥ 60 |
| 2 | 风险 | `behavior_pack_GQ74TKax/Script_NeteaseMod9sPMlz0K/Client.py:197` | `MyClientSystem.OnPopScreen` | 函数约 60 行 ≥ 60 |
| 3 | 风险 | `behavior_pack_GQ74TKax/Script_NeteaseMod9sPMlz0K/Client.py:525` | `MyClientSystem.OnUIInitFinished` | 函数约 95 行 ≥ 60 |
| 4 | 风险 | `behavior_pack_GQ74TKax/Script_NeteaseMod9sPMlz0K/Client.py:1177` | `Test1ScreenNode.ShowSubCards` | 函数约 65 行 ≥ 60 |
| 5 | 警告 | `behavior_pack_GQ74TKax/Script_NeteaseMod9sPMlz0K/Client.py:1350` | `SettingsScreenNode.__init__` | 函数约 145 行 ≥ 60 |
| 6 | 风险 | `behavior_pack_GQ74TKax/Script_NeteaseMod9sPMlz0K/Client.py:1529` | `SettingsScreenNode.Create` | 函数约 85 行 ≥ 60 |
| 7 | 风险 | `behavior_pack_GQ74TKax/Script_NeteaseMod9sPMlz0K/Client.py:2020` | `SettingsScreenNode.AddCard` | 函数约 96 行 ≥ 60 |
| 8 | 风险 | `behavior_pack_GQ74TKax/Script_NeteaseMod9sPMlz0K/Client.py:2127` | `SettingsScreenNode.RebuildMainCards` | 函数约 97 行 ≥ 60 |
| 9 | 风险 | `behavior_pack_GQ74TKax/Script_NeteaseMod9sPMlz0K/Client.py:2414` | `SettingsScreenNode.ShowSubCards` | 函数约 73 行 ≥ 60 |
| 10 | 风险 | `behavior_pack_GQ74TKax/Script_NeteaseMod9sPMlz0K/Client.py:2630` | `SettingsScreenNode.CreateNextMiddleCard` | 函数约 77 行 ≥ 60 |
| 11 | 警告 | `behavior_pack_GQ74TKax/Script_NeteaseMod9sPMlz0K/Client.py:2887` | `SettingsScreenNode.OnTick` | 函数约 210 行 ≥ 60 |
| 12 | 警告 | `behavior_pack_GQ74TKax/Script_NeteaseMod9sPMlz0K/Client.py:3098` | `SettingsScreenNode._PollRightControlsUi` | 函数约 112 行 ≥ 60 |
| 13 | 警告 | `behavior_pack_GQ74TKax/Script_NeteaseMod9sPMlz0K/Client.py:3830` | `SettingsScreenNode.SetLocked` | 函数约 176 行 ≥ 60 |
| 14 | 风险 | `behavior_pack_GQ74TKax/Script_NeteaseMod9sPMlz0K/Client.py:4157` | `BuildButtonContent` | 函数约 78 行 ≥ 60 |
| 15 | 风险 | `behavior_pack_GQ74TKax/Script_NeteaseMod9sPMlz0K/Client.py:4237` | `BuildCollapsibleMenuContent` | 函数约 73 行 ≥ 60 |
| 16 | 风险 | `behavior_pack_GQ74TKax/Script_NeteaseMod9sPMlz0K/Client.py:4312` | `BuildItemPickerContent` | 函数约 76 行 ≥ 60 |
| 17 | 风险 | `behavior_pack_GQ74TKax/Script_NeteaseMod9sPMlz0K/Client.py:4390` | `BuildSwitchContent` | 函数约 80 行 ≥ 60 |
| 18 | 风险 | `behavior_pack_GQ74TKax/Script_NeteaseMod9sPMlz0K/Client.py:4483` | `BuildEditBoxContent` | 函数约 94 行 ≥ 60 |
| 19 | 警告 | `behavior_pack_GQ74TKax/Script_NeteaseMod9sPMlz0K/Client.py:4612` | `BuildSliderContent` | 函数约 118 行 ≥ 60 |
| 20 | 风险 | `behavior_pack_GQ74TKax/Script_NeteaseMod9sPMlz0K/Client.py:4732` | `_ApplySettingToOpenUI` | 函数约 83 行 ≥ 60 |

还有 **4** 处未展开；可使用 `--max-per-rule 0` 输出全部位置。

</details>

### 函数参数过多（可能存在职责过载）

**规则：** `signature.too-many-params`  |  **级别：** 警告 / 提示  |  **数量：** 8

> **处理建议：** 把相关参数聚合为一个对象/字典，或按职责拆分函数；引擎要求的固定签名可忽略或调 max_params。

<details>
<summary>查看 8 处位置</summary>

| # | 级别 | 位置 | 所在符号 | 判断依据 |
|---:|---|---|---|---|
| 1 | 提示 | `behavior_pack_GQ74TKax/Script_NeteaseMod9sPMlz0K/CardRegistry.py:637` | `ContentSettingInst.AddButton` | 非 self 参数 6 个 > 5 |
| 2 | 提示 | `behavior_pack_GQ74TKax/Script_NeteaseMod9sPMlz0K/CardRegistry.py:652` | `ContentSettingInst.AddSwitch` | 非 self 参数 6 个 > 5 |
| 3 | 提示 | `behavior_pack_GQ74TKax/Script_NeteaseMod9sPMlz0K/CardRegistry.py:667` | `ContentSettingInst.AddEditBox` | 非 self 参数 7 个 > 5 |
| 4 | 警告 | `behavior_pack_GQ74TKax/Script_NeteaseMod9sPMlz0K/CardRegistry.py:696` | `ContentSettingInst.AddSlider` | 非 self 参数 12 个 > 5 |
| 5 | 提示 | `behavior_pack_GQ74TKax/Script_NeteaseMod9sPMlz0K/CardRegistry.py:723` | `ContentSettingInst.AddCollapsibleMenu` | 非 self 参数 7 个 > 5 |
| 6 | 警告 | `behavior_pack_GQ74TKax/Script_NeteaseMod9sPMlz0K/CardRegistry.py:746` | `ContentSettingInst.AddItemPicker` | 非 self 参数 8 个 > 5 |
| 7 | 警告 | `behavior_pack_GQ74TKax/Script_NeteaseMod9sPMlz0K/CardRegistry.py:1043` | `AddCardToggleOption` | 非 self 参数 9 个 > 5 |
| 8 | 警告 | `behavior_pack_GQ74TKax/Script_NeteaseMod9sPMlz0K/Toast.py:267` | `ShowToast` | 非 self 参数 12 个 > 5 |

</details>

### 过宽 except 吞掉异常（确认是否有意防御）

**规则：** `try.masking.broad-except-swallow`  |  **级别：** 警告 / 风险 / 提示  |  **数量：** 211

> **处理建议：** 确认是否为有意的环境/兼容防御（如 PC 独占 API 在服务器不存在）：若是则忽略；try 体越大越可能吞掉真实业务错误，此时应收窄异常类型或补上下文后重抛。

<details>
<summary>查看 211 处位置</summary>

| # | 级别 | 位置 | 所在符号 | 判断依据 |
|---:|---|---|---|---|
| 1 | 提示 | `behavior_pack_GQ74TKax/Script_NeteaseMod9sPMlz0K/CardRegistry.py:297` | `SliderContentItem.GetDisplayText` | except Exception 捕获过宽 |
| 2 | 提示 | `behavior_pack_GQ74TKax/Script_NeteaseMod9sPMlz0K/CardRegistry.py:877` | `_NotifyCardChanged` | except Exception as e 捕获过宽 |
| 3 | 提示 | `behavior_pack_GQ74TKax/Script_NeteaseMod9sPMlz0K/CardRegistry.py:886` | `_NotifyContentChanged` | except Exception as e 捕获过宽 |
| 4 | 提示 | `behavior_pack_GQ74TKax/Script_NeteaseMod9sPMlz0K/CardRegistry.py:1318` | `IsNavigateBlocked` | except Exception as e 捕获过宽 |
| 5 | 提示 | `behavior_pack_GQ74TKax/Script_NeteaseMod9sPMlz0K/Client.py:40` | `_OnSyncStoreEvent` | except Exception as e 捕获过宽 |
| 6 | 提示 | `behavior_pack_GQ74TKax/Script_NeteaseMod9sPMlz0K/Client.py:213` | `MyClientSystem.OnPopScreen` | except Exception as e 捕获过宽 |
| 7 | 提示 | `behavior_pack_GQ74TKax/Script_NeteaseMod9sPMlz0K/Client.py:219` | `MyClientSystem.OnPopScreen` | except Exception as e 捕获过宽 |
| 8 | 提示 | `behavior_pack_GQ74TKax/Script_NeteaseMod9sPMlz0K/Client.py:234` | `MyClientSystem.OnPopScreen` | except Exception as e 捕获过宽 |
| 9 | 提示 | `behavior_pack_GQ74TKax/Script_NeteaseMod9sPMlz0K/Client.py:307` | `MyClientSystem._CanPickerArrowPage` | except Exception 捕获过宽 |
| 10 | 提示 | `behavior_pack_GQ74TKax/Script_NeteaseMod9sPMlz0K/Client.py:352` | `MyClientSystem._CanOpenSettingsFromKey` | except Exception 捕获过宽 |
| 11 | 提示 | `behavior_pack_GQ74TKax/Script_NeteaseMod9sPMlz0K/Client.py:401` | `MyClientSystem.OnOpenSettingsFromCommand` | except Exception as e 捕获过宽 |
| 12 | 提示 | `behavior_pack_GQ74TKax/Script_NeteaseMod9sPMlz0K/Client.py:414` | `MyClientSystem.SendServerLogRequest` | except Exception as e 捕获过宽 |
| 13 | 提示 | `behavior_pack_GQ74TKax/Script_NeteaseMod9sPMlz0K/Client.py:424` | `MyClientSystem.SendServerLogEnabled` | except Exception as e 捕获过宽 |
| 14 | 提示 | `behavior_pack_GQ74TKax/Script_NeteaseMod9sPMlz0K/Client.py:446` | `MyClientSystem.NotifyResetGroup` | except Exception as e 捕获过宽 |
| 15 | 提示 | `behavior_pack_GQ74TKax/Script_NeteaseMod9sPMlz0K/Client.py:455` | `MyClientSystem.CopyClientLogToClipboard` | except Exception as e 捕获过宽 |
| 16 | 提示 | `behavior_pack_GQ74TKax/Script_NeteaseMod9sPMlz0K/Client.py:465` | `MyClientSystem.RequestServerLogDump` | except Exception as e 捕获过宽 |
| 17 | 提示 | `behavior_pack_GQ74TKax/Script_NeteaseMod9sPMlz0K/Client.py:481` | `MyClientSystem._WriteClipboard` | except Exception as e 捕获过宽 |
| 18 | 提示 | `behavior_pack_GQ74TKax/Script_NeteaseMod9sPMlz0K/Client.py:486` | `MyClientSystem._WriteClipboard` | except Exception as e 捕获过宽 |
| 19 | 提示 | `behavior_pack_GQ74TKax/Script_NeteaseMod9sPMlz0K/Client.py:522` | `MyClientSystem.OnGridComponentSizeChanged` | except Exception as e 捕获过宽 |
| 20 | 提示 | `behavior_pack_GQ74TKax/Script_NeteaseMod9sPMlz0K/Client.py:533` | `MyClientSystem.OnUIInitFinished` | except Exception as e 捕获过宽 |

还有 **191** 处未展开；可使用 `--max-per-rule 0` 输出全部位置。

</details>

### XXX 无 owner/原因

**规则：** `comment-doc.unowned-todo`  |  **级别：** 提示  |  **数量：** 1

> **处理建议：** 为 TODO 标注负责人与原因，或转为 issue 跟踪，避免长期腐烂。

<details>
<summary>查看 1 处位置</summary>

| # | 级别 | 位置 | 所在符号 | 判断依据 |
|---:|---|---|---|---|
| 1 | 提示 | `behavior_pack_GQ74TKax/Script_NeteaseMod9sPMlz0K/SettingState.py:29` | - | # （扁平 `SettingState` 与带包名的 `Script_NeteaseModXXX.SettingState`�… |

</details>

## 诊断热点

| 文件 | 诊断数 |
|---|---:|
| `behavior_pack_GQ74TKax/Script_NeteaseMod9sPMlz0K/Client.py` | 193 |
| `behavior_pack_GQ74TKax/Script_NeteaseMod9sPMlz0K/CardRegistry.py` | 11 |
| `behavior_pack_GQ74TKax/Script_NeteaseMod9sPMlz0K/SyncControl.py` | 10 |
| `behavior_pack_GQ74TKax/Script_NeteaseMod9sPMlz0K/SettingState.py` | 9 |
| `behavior_pack_GQ74TKax/Script_NeteaseMod9sPMlz0K/Server.py` | 8 |
| `behavior_pack_GQ74TKax/Script_NeteaseMod9sPMlz0K/PlayerStore.py` | 7 |
| `behavior_pack_GQ74TKax/Script_NeteaseMod9sPMlz0K/setting.py` | 6 |
| `behavior_pack_GQ74TKax/Script_NeteaseMod9sPMlz0K/Toast.py` | 2 |

## 技术详情

<details>
<summary>查看扫描路径、发现方式、配置与忽略目录</summary>

- **扫描路径：** `d:/MCStudioDownload/work/xt11451489@163.com/Cpp/AddOn/6a5b659d03644ac3bfd4d9211b6031ed`
- **包发现方式：** `modMain`
- **配置来源：** 内置默认值
- **单规则展示上限：** 20
- **忽略目录：**
  - `d:/MCStudioDownload/work/xt11451489@163.com/Cpp/AddOn/6a5b659d03644ac3bfd4d9211b6031ed/.git`

</details>
