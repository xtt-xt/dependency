# CardRegistry API 说明

> 本模组专为外部模组提供设置界面卡片注册能力。
> **外部模组调用本 API 时务必遵循下方的「外部模组集成要求」**，否则可能因网易多 Addon 加载顺序导致 `ImportError`。

---

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

---

## 导入

### 推荐方式：组件工厂（统一入口）

只需导入 `CardRegistryApi` 即可获得全部公开 API，无需分别从 `CardRegistry` 和 `Client` 导入。

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
    # 回调机制
    SetCardChangedCallback,
    # 事件常量
    SettingsUIOpenEvent, SettingsUICloseEvent,
    # UI 构建器注册
    RegisterContentBuilder,
    # 导航 API
    OpenSettings,
    # 锁定 API
    SetLocked,
    # 折叠菜单注册表
    RegisterCollapsibleMenu, AddCollapsibleMenuCard,
    GetCollapsibleMenu, GetCollapsibleMenuCards,
    ShowCollapsibleMenu, CloseCollapsibleMenu,
)
```

也支持 `from CardRegistryApi import *` 一键导入全部。

### 分别导入（本包内部使用）

本包内部仍可分别从 `CardRegistry` 和 `Client` 导入：

```python
from CardRegistry import (
    RegisterMainCard, CreateContentInst, ...
)
from Client import RegisterContentBuilder
```

---

## 主卡片（左侧列表）<span style="float:right">`[客户端]`</span>

### RegisterMainCard(unique_id, name, icon=None) <span style="float:right">`[客户端]`</span>

注册一个左侧主卡片。

| 参数 | 类型 | 说明 |
|------|------|------|
| unique_id | str | 唯一标识符（全局唯一，不可重复） |
| name | str | 中文名称 |
| icon | str/None | 图标路径，传 None 使用默认图标 `textures/ui/icon_setting`。建议使用**方形**图标，否则可能因缩放导致显示异常。 |

返回 `True` 成功，`False` 失败（参数无效或 ID 已存在）。

```python
RegisterMainCard("basic_settings", "基础设置")
RegisterMainCard("my_mod", "我的模组", "textures/ui/sidebar_icons/realms")
```

> 注册后自动刷新 UI（若设置界面已打开），无需手动调用 `RebuildMainCards`。

### GetMainCard(unique_id) <span style="float:right">`[客户端]`</span>

获取已注册的主卡片信息。

返回 `{"name": str, "icon": str}` 或 `None`。

```python
info = GetMainCard("basic_settings")
print info["name"], info["icon"]
```

### GetAllMainCardIds() <span style="float:right">[客户端]</span>

按注册顺序返回所有主卡片的 unique_id 列表。

```python
for cardId in GetAllMainCardIds():
    info = GetMainCard(cardId)
    print info["name"]
```

### UnregisterMainCard(unique_id) <span style="float:right">[客户端]</span>

移除主卡片注册，**同时自动清除**该主卡片关联的所有中间卡片绑定（client 和 server）。

返回 `True` 成功，`False` 卡片不存在。

```python
UnregisterMainCard("volume")  # 注销后自动刷新 UI，无需手动调用 RebuildMainCards
```

### ClearAllCards() <span style="float:right">[客户端]</span>

清空所有注册的卡片（主卡片 + 中间卡片 + 右侧内容项），用于重置注册表。

```python
ClearAllCards()
```

### SetCardChangedCallback(callback) <span style="float:right">[客户端]</span>

设置主卡片注册变更回调。当 `RegisterMainCard` / `UnregisterMainCard` 成功执行后自动调用该回调。

> **本模组内部已自动注册**：`MyClientSystem` 在初始化时已设置回调，用于自动刷新 UI。**外部模组一般无需调用此方法**。

| 参数 | 类型 | 说明 |
|------|------|------|
| callback | function | 无参函数，主卡片注册/注销成功后被调用 |

```python
from CardRegistry import SetCardChangedCallback

def OnMainCardChanged():
    print "主卡片已变更，刷新 UI..."
    # 刷新逻辑...

SetCardChangedCallback(OnMainCardChanged)
```

---

## 中间卡片（子卡片面板内的选项）<span style="float:right">`[客户端]`</span>

### RegisterMiddleCard(main_card_id, key, card_id, name, icon=None) <span style="float:right">`[客户端]`</span>

注册中间卡片并绑定到指定主卡片 + 子卡片（一步到位）。

| 参数 | 类型 | 说明 |
|------|------|------|
| main_card_id | str | 主卡片 unique_id（须先通过 RegisterMainCard 注册） |
| key | str | `"client"` 或 `"server"` |
| card_id | str | 中间卡片唯一标识符 |
| name | str | 中文名称 |
| icon | str/None | 图标路径，传 None 使用默认图标 |

返回 `True` 成功，`False` 失败。

```python
RegisterMiddleCard("basic_settings", "server", "ts_card", "测试专用卡片", "textures/ui/sidebar_icons/realms")
RegisterMiddleCard("basic_settings", "client", "opt_a", "选项A", "textures/ui/sidebar_icons/addon")
RegisterMiddleCard("basic_settings", "client", "opt_b", "选项B")  # 默认图标
```

> 中间卡片在用户点击子卡片（client/server）时动态渲染，注册后无需额外刷新操作。

### GetMiddleCardBindings(main_card_id, key) <span style="float:right">`[客户端]`</span>

获取指定主卡片+子卡片的所有绑定中间卡片。

返回 `[(card_id, name, icon), ...]` 列表。

```python
bindings = GetMiddleCardBindings("basic_settings", "server")
for card_id, name, icon in bindings:
    print card_id, name, icon
```

### UnregisterMiddleCard(main_card_id, key, card_id) <span style="float:right">`[客户端]`</span>

取消单个中间卡片绑定。

返回 `True` 成功，`False` 绑定不存在。

```python
UnregisterMiddleCard("basic_settings", "server", "ts_card")
```

### ClearMiddleCardBindings(main_card_id, key) <span style="float:right">`[客户端]`</span>

清空指定主卡片+子卡片的所有中间卡片绑定。

返回 `True` 成功。

```python
ClearMiddleCardBindings("basic_settings", "client")
```

---

## 右侧内容项（面板内容区）<span style="float:right">`[客户端]`</span>

右侧面板的内容项按 `(母卡片id, 子卡片key, 中间卡片id)` 三元组分组注册。点击中间卡片时自动显示该分类下的内容。支持链式调用。

### CreateContentInst(main_card_id, key, middle_card_id=None) <span style="float:right">`[客户端]`</span>

创建一个链式注册实例。

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| main_card_id | str | 是 | 母卡片 unique_id |
| key | str | 是 | `"client"` 或 `"server"` |
| middle_card_id | str | 否 | 中间卡片 unique_id；也可后续用 `ForMiddleCard` 指定 |

返回 `ContentSettingInst` 实例。

```python
from CardRegistry import CreateContentInst, GetContentItems, ClearContentItems

# 方式1：创建时指定中间卡片
CreateContentInst("basic_settings", "client", "client_opt_a")\
    .AddText("info", "功能说明", "这是功能的详细描述")\
    .AddButton("btn", "启用功能", "启用")

# 方式2：用 ForMiddleCard 链式指定
CreateContentInst("basic_settings", "client")\
    .ForMiddleCard("client_opt_a")\
    .AddText("info", "功能说明", "这是功能的详细描述")\
    .AddButton("btn", "启用功能", "启用")
```

### ContentSettingInst 方法

所有方法返回 `self`，支持链式调用。

#### ForMiddleCard(middle_card_id) <span style="float:right">`[客户端]`</span>

指定当前链式操作归属的中间卡片。

| 参数 | 类型 | 说明 |
|------|------|------|
| middle_card_id | str | 中间卡片 unique_id |

```python
inst.ForMiddleCard("client_opt_a").AddText("info", "标题", "说明文字")
```

#### AddText(item_id, title="", text="") <span style="float:right">`[客户端]`</span>

添加纯文本内容项，支持分标题和正文两部分显示。

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| item_id | str | 是 | 内容项唯一标识符 |
| title | str | 否 | 小标题（白色加大字体），默认为空字符串 |
| text | str | 否 | 正文内容（白色普通字体），默认为空字符串 |

```python
# 只有标题
inst.AddText("title_1", "功能说明")

# 只有内容
inst.AddText("desc_1", "", "这是一段很长的说明文字")

# 既有标题又有内容
inst.AddText("info", "功能说明", "这是功能的详细描述，可以有多行文字")
```

#### AddButton(item_id, desc, button_text, on_click=None, locked=False, litle="") <span style="float:right">`[客户端]`</span>

添加按钮内容项。按钮左侧显示描述文字，右侧显示按钮文字；点击后按钮文字隐藏并显示 `finish` 图标，切换到其他中间卡片后再切回会恢复为初始 `button_text`。

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| item_id | str | 是 | 内容项唯一标识符 |
| desc | str | 是 | 按钮左侧描述文字 |
| button_text | str | 是 | 按钮右侧显示的初始文字 |
| on_click | function | 否 | 点击后的回调函数，签名 `on_click(screenNode, item_id)` |
| locked | bool | 否 | 是否锁定，`True` 时显示锁图标覆盖层并禁止点击 |
| litle | str | 否 | 小标题（白色加大字体），默认为空字符串 |

```python
inst.AddButton("enable", "启用功能", "启用")
inst.AddButton("apply", "应用配置", "应用", on_click=OnApply)
inst.AddButton("locked_feat", "未解锁的功能", "锁定", locked=True)
inst.AddButton("with_title", "配置", "编辑", litle="功能设置")
```

> **`on_click` 回调签名**：`on_click(screenNode, item_id) -> None`  
> - `screenNode`: 当前 `SettingsScreenNode` 实例，可调用 `screenNode.SetLocked(id, locked)` 动态修改锁定状态  
> - `item_id`: 被点击按钮的内容项 ID

#### AddSwitch(item_id, desc, default_value=False, locked=False, on_toggle=None, litle="") <span style="float:right">`[客户端]`</span>

添加开关内容项。左侧显示描述文字，右侧显示开关控件。支持设置默认开关状态、锁定状态和切换回调。

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| item_id | str | 是 | 内容项唯一标识符 |
| desc | str | 是 | 开关左侧描述文字 |
| default_value | bool | 否 | 初始开关状态，`True` 为开，`False` 为关 |
| locked | bool | 否 | 是否锁定，`True` 时禁用开关交互 |
| on_toggle | function | 否 | 开关状态改变回调，签名 `on_toggle(screenNode, item_id, state)` |
| litle | str | 否 | 小标题（白色加大字体），默认为空字符串 |

```python
inst.AddSwitch("auto_save", "启用自动保存", default_value=True)
inst.AddSwitch("debug_mode", "调试模式", default_value=False, locked=True)
inst.AddSwitch("ctrl_lock", "控制另一个开关锁定", default_value=True,
               on_toggle=lambda sn, iid, state: sn.SetLocked("other_switch", not state))
inst.AddSwitch("with_title", "启用功能", litle="功能开关")
```

#### AddEditBox(item_id, desc, default_value="", placeholder="请输入内容", locked=False, litle="") <span style="float:right">`[客户端]`</span>

添加编辑框内容项。左侧显示描述文字，右侧显示输入框（`edit_box`）。支持自定义提示文字（placeholder）与初始内容，支持锁定。

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| item_id | str | 是 | 内容项唯一标识符 |
| desc | str | 是 | 编辑框左侧描述文字 |
| default_value | str | 否 | 输入框初始内容，默认为空字符串 |
| placeholder | str | 否 | 输入框提示文字，默认 `"请输入内容"`（对应 JSON 变量 `$place_holder_text`） |
| locked | bool | 否 | 是否锁定，`True` 时显示 lock 覆盖层并禁止输入 |
| litle | str | 否 | 小标题（白色加大字体），默认为空字符串 |

```python
inst.AddEditBox("server_ip", "服务器地址", default_value="127.0.0.1", placeholder="请输入IP")
inst.AddEditBox("readonly", "只读配置", default_value="固定值", locked=True)
inst.AddEditBox("with_title", "开启提示", litle="功能设置")
```

#### AddResetButton(item_id, popup_id=None, on_click=None) <span style="float:right">`[客户端]`</span>

添加重置按钮内容项。仅显示一个占满整行的按钮（无左侧描述文字），按钮文字固定为"重置分页数据"；点击按钮后弹出 `popup_id` 关联的确认弹窗（须先通过 `RegisterPopUp` 注册）。

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| item_id | str | 是 | 内容项唯一标识符 |
| popup_id | str | 否 | 关联的弹窗 ID（须先 `RegisterPopUp` 注册），传 `None` 则只触发 `on_click` |
| on_click | function | 否 | 额外点击回调，签名 `on_click(screenNode, item_id)` |

```python
RegisterPopUp("reset_confirm", "确认重置", "确定要重置所有设置吗？",
              [("取消", None), ("确认", OnConfirmReset)])
inst.AddResetButton("reset_all", popup_id="reset_confirm")
```

#### AddCustom(item_id, type_name, **kwargs) <span style="float:right">`[客户端]`</span>

扩展接口：注册自定义类型内容项。使用前先通过 `RegisterContentItemType` 注册对应工厂。

```python
RegisterContentItemType("slider", SliderContentFactory)
inst.AddCustom("sensitivity", "slider", min=0, max=100, value=50)
```

#### AddSlider(item_id, desc, min_val=0, max_val=100, value=50, steps=1, locked=False, litle="", on_value_change=None, slider_type="percent", value_formatter=None, value_labels=None) <span style="float:right">`[客户端]`</span>

添加滑块内容项（上方 `litle` + `desc` 文字 + 右侧数值显示，下方滑块）。滑块背景/进度用 `textures/ui/slider/` 贴图，滑块按钮用 button 同款贴图（正方形）。

| 参数 | 类型 | 说明 |
|------|------|------|
| item_id | str | 内容项唯一标识符 |
| desc | str | 描述文字 |
| min_val / max_val | int | 固定格类型的最小/最大值 |
| value | number | 当前值。percent 类型为 0~1 小数；steps 类型为档位整数（0~steps） |
| steps | int | >1 时固定格类型（值量化为 0~steps 档位）；<=1 时百分比类型（0~1） |
| locked | bool | 是否锁定 |
| litle | str | 小标题（可选） |
| on_value_change | function | 值变化回调，签名 `on_value_change(screenNode, item_id, value)` |
| slider_type | str | `"percent"`（百分比 0~1）或 `"steps"`（固定格 0~steps） |
| value_formatter | function | 数值显示自定义回调 `value_formatter(value) -> str`（可选） |
| value_labels | list[str] | 固定格类型数值显示标签，下标=档位，长度应=steps+1（可选） |

```python
inst.AddSlider("volume", "音量调节", value=0.5, steps=1, litle="音量")
inst.AddSlider("quality", "画质等级", value=2, steps=5, slider_type="steps", litle="画质",
               value_labels=["极低", "低", "中", "高", "极高", "极致"])
inst.AddSlider("custom", "自定义显示", value=30, steps=1,
               value_formatter=lambda v: "已用 %d%%" % int(round(v * 100)))
```

> 固定格类型（steps>1）采用"视觉连续滑动 + 取值量化"：滑块 UI 连续拖动，值自动吸附到最近档位。
> 数值显示支持自定义：`value_formatter(value) -> str` 回调返回任意文本，或 `value_labels` 列表（固定格每档对应文字，长度 = steps+1）。无自定义时默认固定格显示整数档位、百分比显示 `xx%`。

#### AddCollapsibleMenu(item_id, desc, menu_id, litle="", on_select=None, default_selected_id=None, locked=False) <span style="float:right">`[客户端]`</span>

添加折叠菜单内容项：上方 `litle`（小标题）+ `desc`（描述文字），下方一个按钮（文字左对齐实时显示当前选中项，右侧带箭头图标）。点击按钮弹出关联的 `collapsible_menu` 弹窗，弹窗中间垂直排列可选卡片，卡片之间互斥，选中后自动关闭弹窗并更新按钮文字。

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| item_id | str | 是 | 内容项唯一标识符 |
| desc | str | 是 | 描述文字（按钮上方） |
| menu_id | str | 是 | 关联折叠菜单 ID（须先 `RegisterCollapsibleMenu` / `AddCollapsibleMenuCard` 注册卡片） |
| litle | str | 否 | 小标题（可选，空则隐藏） |
| on_select | function | 否 | 选择回调，签名 `on_select(screenNode, item_id, card_id)` |
| default_selected_id | str | 否 | 默认选中卡片 ID（可选） |
| locked | bool | 否 | 初始锁定状态，`True` 时按钮显示锁覆盖层并禁止点击（可选，默认 `False`） |

```python
inst.AddCollapsibleMenu(
    "resolution", "选择游戏分辨率，点击下方按钮弹出菜单选择",
    "resolution_menu", litle="分辨率",
    default_selected_id="r_1080p",
    on_select=lambda sn, item_id, card_id: print "selected", card_id
)
```

> 按钮文字为左对齐，实时显示当前选中项名称；未选择时显示"请选择"。**选中状态自动持久化**：选择/切换卡片/退出设置界面时随 `SaveGroupSettings`/`SaveAllSettings` 保存到本地存储，下次打开自动恢复；`ResetGroupSettings`/`ResetAllSettings` 会恢复为 `default_selected_id`。锁定状态（`locked` 参数或运行时 `SetLocked`）同样随 `::locked` 键持久化。

#### Clear() <span style="float:right">`[客户端]`</span>

清除当前分组的所有内容项。

```python
inst.Clear()  # 等价于 ClearContentItems("basic_settings", "client", "client_opt_a")
```

#### Remove(item_id) <span style="float:right">`[客户端]`</span>

移除当前分组下的单个内容项。

```python
inst.Remove("enable")
```

### GetContentItems(main_card_id, key, middle_card_id="__default__") <span style="float:right">`[客户端]`</span>

获取指定分组的全部内容项列表。

```python
items = GetContentItems("basic_settings", "client", "client_opt_a")
for item in items:
    print item.item_id, item.type_name
```

### GetContentItem(main_card_id, key, middle_card_id, item_id) <span style="float:right">`[客户端]`</span>

获取指定分组中指定 ID 的单个内容项，未找到返回 `None`。

```python
item = GetContentItem("basic_settings", "client", "client_opt_a", "enable_btn")
if item:
    print item.item_id, item.type_name, getattr(item, "locked", False)
```

> 常用于在 `on_click` 回调中读取按钮的当前锁定状态，配合 `SetLocked` 使用。

### ClearContentItems(main_card_id=None, key=None, middle_card_id=None) <span style="float:right">`[客户端]`</span>

清空内容项。不传参清空全部；传参只清空指定分组。

```python
ClearContentItems()                                                   # 清空全部
ClearContentItems("basic_settings", "client", "client_opt_a")        # 清空指定中间卡片
ClearContentItems("basic_settings", "client")                         # 清空指定子卡片下所有中间卡片
```

### RegisterContentItemType(type_name, factory) <span style="float:right">`[客户端]`</span>

注册自定义内容项类型，用于扩展右侧面板可显示的内容类型。

| 参数 | 类型 | 说明 |
|------|------|------|
| type_name | str | 类型名称，如 `"slider"` |
| factory | class | 工厂类，需实现 `CreateItem(item_id, **kwargs)` 返回 `BaseContentItem` 子类 |

```python
class SliderContentItem(BaseContentItem):
    def __init__(self, item_id, min_val, max_val, value):
        super(SliderContentItem, self).__init__(item_id, "slider")
        self.min = min_val
        self.max = max_val
        self.value = value

class SliderContentFactory(object):
    @staticmethod
    def CreateItem(item_id, **kwargs):
        return SliderContentItem(
            item_id,
            kwargs.get("min", 0),
            kwargs.get("max", 100),
            kwargs.get("value", 50)
        )

RegisterContentItemType("slider", SliderContentFactory)
```

### GetContentItemFactory(type_name) <span style="float:right">`[客户端]`</span>

获取已注册的指定类型内容项工厂。

```python
factory = GetContentItemFactory("slider")
```

### RegisterContentBuilder(type_name, builder) <span style="float:right">`[客户端]`</span>

注册内容项的 UI 构建器（在 `Client.py` 中）。Builder 负责在右侧面板中创建实际的 UI 控件。

| 参数 | 类型 | 说明 |
|------|------|------|
| type_name | str | 类型名称，与 `RegisterContentItemType` 一致 |
| builder | function | 构建函数，签名 `builder(screenNode, parent, item) -> None` |

```python
from Client import RegisterContentBuilder

def BuildSliderContent(screenNode, parent, item):
    # 创建 UI 控件...
    pass

RegisterContentBuilder("slider", BuildSliderContent)
```

> 内置类型 `"text"` 和 `"button"` 的 builder 已自动注册，无需手动调用。

### RegisterContentListener(listener) <span style="float:right">`[客户端]`</span>

注册内容项变更监听器。当右侧内容项被增删时，会通知所有监听器，可用于动态刷新 UI。

| 参数 | 类型 | 说明 |
|------|------|------|
| listener | function | 签名 `listener(group_tuple) -> None`，`group_tuple = (main_card_id, key, middle_card_id)` |

```python
def OnContentChanged(group):
    main_card_id, key, middle_card_id = group
    print "content changed for %s/%s/%s" % (main_card_id, key, middle_card_id)

RegisterContentListener(OnContentChanged)
```

### UnregisterContentListener(listener) <span style="float:right">`[客户端]`</span>

注销之前注册的内容项变更监听器。

```python
UnregisterContentListener(OnContentChanged)
```

---

## 事件与导航 API <span style="float:right">`[客户端]`</span>

### 事件常量 <span style="float:right">`[客户端]`</span>

当玩家打开或关闭设置 UI 时，`MyClientSystem` 会向引擎抛出事件，外部模块可通过 `ListenForEvent` 监听。

| 常量 | 事件名 | 抛出时机 | 事件数据 |
|------|--------|----------|----------|
| `SettingsUIOpenEvent` | `Script_NeteaseMod9sPMlz0K_SettingsUIOpen` | 玩家打开设置界面 | `{"playerId": str}` |
| `SettingsUICloseEvent` | `Script_NeteaseMod9sPMlz0K_SettingsUIClose` | 玩家关闭设置界面 | `{"playerId": str}` |

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

> 监听时 `namespace` 和 `systemName` 固定填写 `"Script_NeteaseMod9sPMlz0K"` 和 `"client"`。

### OpenSettings（导航 API） <span style="float:right">`[客户端]`</span>

通过 `CardRegistryApi.OpenSettings` 打开设置 UI，并可选导航到指定卡片。

```python
from CardRegistryApi import OpenSettings

# 仅打开设置（默认行为）
OpenSettings()

# 选中主卡片
OpenSettings(main_card_id="basic_settings")

# 选中主卡片 + 子卡片
OpenSettings("basic_settings", "client")

# 选中主卡片 + 子卡片 + 中间卡片（右侧内容自动显示）
OpenSettings("basic_settings", "client", "client_opt_a")
```

#### 参数说明

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| main_card_id | str | 否 | 主卡片 ID（如 `"basic_settings"`），传 `None` 则不导航 |
| sub_key | str | 否 | 子卡片 key，可选 `"client"` 或 `"server"` |
| middle_card_id | str | 否 | 中间卡片 ID（如 `"client_opt_a"`），需在 `sub_key` 指定后生效 |

#### 行为说明

- **设置界面未打开时**：`PushScreen` 打开设置，UI 就绪后自动导航到指定卡片
- **设置界面已打开时**：直接导航到新卡片，不会重复 `PushScreen`
- **不传任何参数**：仅打开设置界面，保持当前卡片状态
- **中间卡片导航**：由于中间卡片是异步懒加载的，选中操作会在卡片创建完成后自动执行

---

## 锁定 API <span style="float:right">`[客户端]`</span>

### SetLocked(item_id_or_path, locked) <span style="float:right">`[客户端]`</span>

统一设置指定内容项（按钮/开关/edit_box 内容项）或 `edit_box` 输入框的锁定状态。自动根据传入参数判断类型：

- 若是右侧面板内容项 ID（`AddButton`/`AddSwitch`/`AddEditBox` 时传入的 `item_id`），执行对应内容项锁定逻辑
- 若是以 `/` 开头的控件完整路径，则按 `edit_box` 路径处理

**按钮锁定**：显示锁图标覆盖层，点击无响应；解锁后恢复可点击。
**开关锁定**：禁用开关控件交互，无法点击切换；解锁后恢复可操作。
**edit_box 内容项/输入框锁定**：显示 `lock` 子控件覆盖层，并禁用输入框交互；解锁后恢复可输入。

| 参数 | 类型 | 说明 |
|------|------|------|
| item_id_or_path | str | 内容项 ID（`AddButton`/`AddSwitch`/`AddEditBox` 时传入的 `item_id`）或 `edit_box` 完整控件路径 |
| locked | bool | `True` 锁定，`False` 解锁 |

```python
from CardRegistryApi import SetLocked, GetContentItem

# 锁定按钮/开关
SetLocked("enable_btn", True)
SetLocked("auto_save", True)

# 解锁按钮/开关
SetLocked("enable_btn", False)
SetLocked("auto_save", False)

# 锁定/解锁 edit_box 内容项（按 item_id）
SetLocked("server_ip", True)
SetLocked("server_ip", False)

# 锁定 edit_box（传入完整控件路径）
SetLocked("/variables_button_mappings_and_controls/.../my_edit", True)

# 读取当前锁定状态后切换
item = GetContentItem("basic_settings", "client", "client_opt_a", "enable_btn")
if item and hasattr(item, "locked"):
    SetLocked("enable_btn", not item.locked)
```

#### 工作原理

- **数据层**：调用 `item.SetLocked(locked)` 更新内存中的锁定状态（仅右侧面板内容项）
- **UI 层（按钮）**：显示/隐藏 `lock` 控件（锁图标覆盖层），并注册/移除按钮点击回调；图层顺序 `lock`(4) → `finish`(5) → `text`(6)
- **UI 层（开关）**：锁定状态时调用 `SetTouchEnable(False)` 禁用开关控件交互，解锁时恢复 `SetTouchEnable(True)`
- **UI 层（edit_box 内容项）**：按内容项 ID 查 `mRightEditBoxCtrlMap`，显示/隐藏 `lock` 子控件，并调用 `SetTouchEnable(False/True)` 禁用/启用输入框交互
- **UI 层（edit_box 路径）**：按完整控件路径走 `GetBaseUIControl`，同样显示/隐藏 `lock` 子控件并调用 `SetTouchEnable(False/True)`

#### 创建时锁定

在 `AddButton`、`AddSwitch` 或 `AddEditBox` 时设置 `locked=True` 可使内容项初始即为锁定状态，无需额外调用 `SetLocked`：

```python
# 按钮初始锁定
CreateContentInst("basic_settings", "client", "client_opt_a")\
    .AddButton("locked_btn", "此功能未解锁", "锁定", locked=True)\
    .AddButton("toggle_btn", "点击切换上方按钮锁定状态", "切换锁定",
               on_click=lambda sn, iid: sn.SetLocked(
                   "locked_btn",
                   not GetContentItem("basic_settings", "client", "client_opt_a", "locked_btn").locked
               ))

# 开关初始锁定
CreateContentInst("basic_settings", "client", "client_opt_a")\
    .AddSwitch("locked_switch", "此功能已锁定", default_value=True, locked=True)

# edit_box 初始锁定
CreateContentInst("basic_settings", "client", "client_opt_a")\
    .AddEditBox("readonly_ip", "只读地址", default_value="127.0.0.1", locked=True)
```

> `on_click` 回调可通过 `sn.SetLocked(...)` 或模块级 `SetLocked(...)` 动态修改任意按钮/开关/edit_box 的锁定状态。

> **`on_toggle` 回调签名**：`on_toggle(screenNode, item_id, state) -> None`  
> - `screenNode`: 当前 `SettingsScreenNode` 实例，可调用 `screenNode.SetLocked(id, locked)` 动态修改锁定状态  
> - `item_id`: 被切换的开关内容项 ID  
> - `state`: 开关当前状态（`True` 开，`False` 关）


## 设置项状态系统 API <span style="float:right">`[客户端]`</span>

开关（switch）与输入框（edit_box）的设置值会自动持久化到本地存储，并在设置界面重开、重进世界后恢复。

存储实现基于官方接口 `ConfigCompClient`（API文档/1-ModAPI/接口/通用/本地存储）：`comp.GetConfigData(configName, isGlobal)` / `comp.SetConfigData(configName, value, isGlobal)`，配置名为 `Script_NeteaseMod9sPMlz0K_setting_state`（存档配置，`isGlobal=False`，跨存档不共享）。

**存储 key 自动生成**：`主卡片id.子key.中间卡片id.item_id`

```python
# 例如：
CreateContentInst("basic_settings", "client", "opt_a")\
    .AddSwitch("auto_save", "自动保存", default_value=True)
# 存储 key = "basic_settings.client.opt_a.auto_save"
```

- 无存储值时回退注册时的 `default_value`（开关默认 `False`，输入框默认 `""`）。
- UI 与存储双向联动：构建时读存储值初始化；用户在 UI 上的改动自动写回存储；API 修改时若设置界面已打开会即时刷新对应控件。
- API 修改开关值**不会**触发 `on_toggle` 回调（仅用户操作触发）。
- 所有设置项数据以整个 dict 存于一个配置名内，SDK 环境异常时自动降级为内存存储，不崩溃。

### MakeSettingKey(main_card_id, key, middle_card_id, item_id) <span style="float:right">`[客户端]`</span>

生成存储 key（`主卡片id.子key.中间卡片id.item_id`）。

### GetSettingValue(main_card_id, key, middle_card_id, item_id, default=None) <span style="float:right">`[客户端]`</span>

读取设置值。

| 参数 | 类型 | 说明 |
|------|------|------|
| main_card_id | str | 主卡片 ID |
| key | str | 子卡片 key（`"client"` / `"server"`） |
| middle_card_id | str | 中间卡片 ID |
| item_id | str | 内容项 ID（AddSwitch/AddEditBox 的 item_id） |
| default | 任意 | 可选；不传时无存储值回退 `default_value` |

返回存储值；无存储值返回 `default` 或注册默认值。

```python
state = GetSettingValue("basic_settings", "client", "opt_a", "auto_save")
text  = GetSettingValue("basic_settings", "client", "opt_a", "server_ip")
```

### SetSettingValue(main_card_id, key, middle_card_id, item_id, value) <span style="float:right">`[客户端]`</span>

修改设置值并写入本地存储。若设置界面已打开且正显示该分组，对应控件即时刷新。

```python
SetSettingValue("basic_settings", "client", "opt_a", "auto_save", False)
SetSettingValue("basic_settings", "client", "opt_a", "server_ip", "127.0.0.1")
```

### ResetSettingValue(main_card_id, key, middle_card_id, item_id) <span style="float:right">`[客户端]`</span>

将单个设置项重置为默认值（`default_value`），并同步刷新 UI。

```python
ResetSettingValue("basic_settings", "client", "opt_a", "auto_save")
```

### ResetAllSettings() <span style="float:right">`[客户端]`</span>

将注册表中所有开关与输入框重置为默认值，返回重置数量。

```python
count = ResetAllSettings()
print "已重置 %d 个设置项" % count
```

### SaveGroupSettings(main_card_id, key, middle_card_id) <span style="float:right">`[客户端]`</span>

批量保存指定分组（主卡片 + 子卡片 + 中间卡片）下所有开关/输入框的运行时值到本地存储，同时保存各内容项当前的**锁定状态**（`locked`）。整包写一次，不触发逐项 UI 刷新回调。返回实际写入数量。

```python
count = SaveGroupSettings("basic_settings", "client", "opt_a")
```

> 锁定状态说明：`AddButton`/`AddSwitch`/`AddEditBox` 的 `locked` 参数为注册默认值；运行时通过 `SetLocked` 动态修改后，保存时会持久化当前锁定状态，下次打开设置界面自动恢复。`ResetGroupSettings`/`ResetAllSettings` 会清除持久化锁定，恢复注册默认。

### SaveAllSettings() <span style="float:right">`[客户端]`</span>

批量保存注册表中所有开关/输入框的运行时值到本地存储。整包写一次，不触发逐项 UI 刷新回调。返回实际写入数量。

> 说明：设置界面内的开关/输入框改动默认**不会实时写入存储**（仅在内存中更新，避免高频写存储造成卡顿）。切换卡片时自动 `SaveGroupSettings` 保存当前分组，设置界面关闭时自动调用 `SaveAllSettings()` 提交全部改动。外部模组如需主动提交，可调用 `SaveGroupSettings`/`SaveAllSettings`。

```python
count = SaveAllSettings()
print "已保存 %d 个设置项" % count
```

### ResetGroupSettings(main_card_id, key, middle_card_id) <span style="float:right">`[客户端]`</span>

重置指定分组（主卡片 + 子卡片 + 中间卡片）下所有开关与输入框为默认值，返回重置数量。用于"重置本页设置"场景。

```python
# 重置 basic_settings/client/opt_a 分组下所有设置项
count = ResetGroupSettings("basic_settings", "client", "opt_a")
```


## 完整使用示例

```python
from CardRegistryApi import (
    RegisterMainCard, UnregisterMainCard,
    RegisterMiddleCard, UnregisterMiddleCard,
    GetAllMainCardIds, GetMainCard,
)

# ===== 初始化 =====
RegisterMainCard("mod_main", "主模组", "textures/ui/icon_setting")
RegisterMainCard("mod_extra", "扩展模组", "textures/ui/sidebar_icons/realms")

# 注册中间卡片，按主卡片 ID + 子卡片 key 绑定
RegisterMiddleCard("mod_main", "server", "srv_feature", "服务端功能", "textures/ui/sidebar_icons/realms")
RegisterMiddleCard("mod_main", "client", "cli_option", "客户端选项", "textures/ui/sidebar_icons/addon")
RegisterMiddleCard("mod_extra", "server", "extra_srv", "额外服务端", "textures/ui/icon_setting")

# 创建 UI（SettingsScreenNode 内部调用）
for cardId in GetAllMainCardIds():
    info = GetMainCard(cardId)
    if info:
        screenNode.AddCard(info["name"], info["icon"], cardId)

# ===== 运行时增删（自动刷新 UI，无需手动调用 RebuildMainCards） =====
# 删除主卡片（中间绑定自动清除）
UnregisterMainCard("mod_extra")

# 添加新主卡片
RegisterMainCard("new_mod", "新模组", "textures/ui/sidebar_icons/addon")
RegisterMiddleCard("new_mod", "server", "new_feature", "新功能")

# 删除单个中间卡片（不清除主卡片）
UnregisterMiddleCard("mod_main", "server", "srv_feature")
```


## 弹窗 API <span style="float:right">`[客户端]`</span>

通用确认弹窗系统：`RegisterPopUp` 注册弹窗，`ShowPopUp` 打开，弹窗显示标题 + 正文（超长自动滚动，总高最多 80% 屏高）+ 底部按钮区（按钮间带间距）。

### RegisterPopUp(popup_id, title, content, buttons=None) <span style="float:right">`[客户端]`</span>

注册一个自定义弹窗。

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| popup_id | str | 是 | 弹窗唯一标识符（重复注册会覆盖旧数据） |
| title | str | 是 | 弹窗标题文字 |
| content | str | 是 | 弹窗正文内容（支持换行 `\n`，超长自动滚动） |
| buttons | list | 否 | 底部按钮列表 `[(按钮文字, 点击回调\|None), ...]`，回调签名 `f() -> bool`，返回 `True` 时弹窗自动关闭；传 `None` 表示无底部按钮 |

返回 `True` 成功，`False` 参数无效。

```python
def OnConfirmReset():
    # 执行重置逻辑...
    ResetAllSettings()
    return True  # 返回 True 自动关闭弹窗

RegisterPopUp(
    "reset_confirm",
    "确认重置",
    "确定要重置所有设置吗？\n此操作不可撤销。",
    [("取消", None), ("确认重置", OnConfirmReset)]
)
```

### ShowPopUp(popup_id, force_scroll=None) <span style="float:right">`[客户端]`</span>

打开指定 ID 的弹窗（须先 `RegisterPopUp` 注册）。若弹窗已在场景栈中，则复用现有弹窗界面刷新内容。

- `force_scroll`：`True` 强制使用滚动版；`False` 强制普通版；`None`（默认）自动判断——当内容估算行数超过 4 行时使用滚动版（滚动区固定高度 100px，上下各留 10px 空隙）。

返回 `True` 打开成功，`False` 弹窗未注册或系统未就绪。

```python
from CardRegistryApi import ShowPopUp
ShowPopUp("reset_confirm")
ShowPopUp("long_notice", force_scroll=True)   # 强制滚动版
ShowPopUp("short_notice", force_scroll=False) # 强制普通版
```

### ClosePopUp() <span style="float:right">`[客户端]`</span>

关闭当前弹窗（`PopScreen` 返回上一层，设置界面不受影响）。

### UnregisterPopUp(popup_id) <span style="float:right">`[客户端]`</span>

注销指定弹窗，返回 `True` 成功，`False` 弹窗不存在。

### GetPopUp(popup_id) <span style="float:right">`[客户端]`</span>

获取弹窗数据 `{"title": str, "content": str, "buttons": [(text, callback), ...]}` 或 `None`。

### GetAllPopUpIds() <span style="float:right">`[客户端]`</span>

返回所有已注册的弹窗 ID 列表。

### 弹窗事件常量 <span style="float:right">`[客户端]`</span>

| 常量 | 触发时机 | 事件数据 |
|------|----------|----------|
| `PopUpOpenEvent` | 弹窗压栈打开时 | `{"playerId": str, "popupId": str, "useScroll": bool}` |
| `PopUpCloseEvent` | 弹窗出栈关闭时 | `{"playerId": str}` |

```python
from CardRegistryApi import PopUpOpenEvent
# 在 ClientSystem 中监听:
# self.ListenForEvent("Script_NeteaseMod9sPMlz0K", "client", PopUpOpenEvent, self, self.OnPopUpOpen)
```

### 与 AddResetButton 配合 <span style="float:right">`[客户端]`</span>

设置界面右侧通过 `AddResetButton` 注册重置项，点击后自动打开关联弹窗：

```python
from CardRegistryApi import (
    RegisterMainCard, RegisterMiddleCard, CreateContentInst,
    RegisterPopUp,
)

RegisterMainCard("basic_settings", "基础设置")
RegisterMiddleCard("basic_settings", "client", "opt_main", "主要选项")

RegisterPopUp("reset_confirm", "确认重置", "确定要重置所有设置吗？",
              [("取消", None), ("确认重置", lambda: True)])

CreateContentInst("basic_settings", "client", "opt_main")\
    .AddResetButton("reset_all", popup_id="reset_confirm")
```

## 折叠菜单 API <span style="float:right">`[客户端]`</span>

折叠菜单选择系统：先注册菜单（含标题与卡片列表），再通过 `AddCollapsibleMenu` 添加右侧内容项。点击内容项按钮弹出菜单弹窗，弹窗中间垂直排列可选卡片，卡片之间互斥（只能选一个），选中后触发 `on_select` 回调并自动关闭弹窗，按钮文字同步为选中项名称。

### RegisterCollapsibleMenu(menu_id, title, cards=None) <span style="float:right">`[客户端]`</span>

注册一个折叠菜单。

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| menu_id | str | 是 | 折叠菜单唯一标识符 |
| title | str | 是 | 弹窗标题文字 |
| cards | list | 否 | 卡片列表 `[(card_id, name), ...]`，也可后续用 `AddCollapsibleMenuCard` 追加 |

返回 `True` 成功，`False` 参数无效（menu_id 或 title 为空）。

### AddCollapsibleMenuCard(menu_id, card_id, name) <span style="float:right">`[客户端]`</span>

向已注册的折叠菜单追加一张卡片；菜单不存在时自动创建（此时标题为空串，需再调 `RegisterCollapsibleMenu` 设置标题）。

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| menu_id | str | 是 | 折叠菜单 ID |
| card_id | str | 是 | 卡片唯一标识符（重复不追加） |
| name | str | 是 | 卡片显示文字 |

返回 `True` 成功，`False` 参数无效或卡片重复。

### GetCollapsibleMenu(menu_id) <span style="float:right">`[客户端]`</span>

获取折叠菜单数据 `{"title": str, "cards": [(card_id, name), ...]}` 或 `None`。

### GetCollapsibleMenuCards(menu_id) <span style="float:right">`[客户端]`</span>

获取卡片列表 `[(card_id, name), ...]`，菜单不存在返回 `[]`。

### 完整示例 <span style="float:right">`[客户端]`</span>

```python
from CardRegistryApi import RegisterCollapsibleMenu, CreateContentInst

def OnSelect(sn, item_id, card_id):
    print "选中:", item_id, card_id
    # 可在此持久化：SetSettingValue("basic_settings", "client", "opt_main", item_id, card_id)

# 1. 注册菜单（标题 + 卡片）
RegisterCollapsibleMenu(
    "resolution_menu", "选择分辨率",
    [("r_720p", "720p"), ("r_1080p", "1080p"),
     ("r_1440p", "1440p"), ("r_2160p", "2160p")]
)

# 2. 追加卡片（可选）
AddCollapsibleMenuCard("resolution_menu", "r_4k", "4K")

# 3. 注册右侧内容项，点击按钮弹出菜单
CreateContentInst("basic_settings", "client", "opt_main")\
    .AddCollapsibleMenu(
        "resolution", "选择游戏分辨率",
        "resolution_menu", litle="分辨率",
        default_selected_id="r_1080p",
        on_select=OnSelect
    )
```

> 打开/关闭菜单由框架自动处理（`ShowCollapsibleMenu` / `CloseCollapsibleMenu` 为内部便捷封装，通常无需外部直接调用）。菜单弹窗打开时，设置界面的 ESC 行为自动调整为"先关菜单、再关弹窗、最后关设置界面"。
