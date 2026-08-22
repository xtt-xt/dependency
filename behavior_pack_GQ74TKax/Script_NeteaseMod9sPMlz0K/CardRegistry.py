# -*- coding: utf-8 -*-
"""
卡片注册 API
============
统一注册主卡片、中间卡片和右侧内容项，支持运行时增删重建。

主卡片:
    RegisterMainCard("my_mod", "我的模组", "textures/ui/icon_setting")

中间卡片（一步注册 + 绑定）:
    RegisterMiddleCard("my_mod", "server", "my_feature", "我的功能")
    RegisterMiddleCard("my_mod", "server", "my_extra", "额外功能", "textures/ui/sidebar_icons/realms")

右侧内容项（链式注册，按 主卡片 + 子卡片 + 中间卡片 分组）:
    CreateContentInst("my_mod", "server", "my_feature")\
        .AddText("info", "功能说明")\
        .AddButton("btn", "启用功能", "启用")
"""

_cards = {}       # unique_id -> {"name": str, "icon": str}   (中间卡片信息)
_defaultIcon = "textures/ui/icon_setting"

# ────────────────── 主卡片 ──────────────────

_mainCards = {}      # unique_id -> {"name": str, "icon": str}
_mainCardOrder = []  # [unique_id, ...] 注册顺序


def RegisterMainCard(unique_id, name, icon=None):
    """
    注册一个左侧主卡片。
    注: 注册后自动刷新 UI（若设置界面已打开），无需手动调用 RebuildMainCards。
    """
    if not unique_id or not name:
        return False
    if unique_id in _mainCards:
        return False
    if icon is None:
        icon = _defaultIcon
    _mainCards[unique_id] = {"name": name, "icon": icon}
    if unique_id not in _mainCardOrder:
        _mainCardOrder.append(unique_id)
    _NotifyCardChanged()
    return True


def GetMainCard(unique_id):
    """获取主卡片信息 {"name": str, "icon": str} 或 None"""
    return _mainCards.get(unique_id)


def GetAllMainCardIds():
    """按注册顺序返回所有主卡片 unique_id 列表"""
    return list(_mainCardOrder)


def UnregisterMainCard(unique_id):
    """移除主卡片注册，同时自动清除关联的所有中间卡片绑定。"""
    if unique_id in _mainCards:
        del _mainCards[unique_id]
        if unique_id in _mainCardOrder:
            _mainCardOrder.remove(unique_id)
        # 自动清除关联的中间卡片绑定
        for key in ("client", "server"):
            bk = (unique_id, key)
            if bk in _middleCardBindings:
                del _middleCardBindings[bk]
        # 同时清除该主卡片下的所有右侧内容项
        _ClearContentItemsByMainCard(unique_id)
        _NotifyCardChanged()
        return True
    return False


# ────────────────── 中间卡片（统一 API） ──────────────────

# (main_card_id, key) -> [(card_id, name, icon), ...]
_middleCardBindings = {}


def RegisterMiddleCard(main_card_id, key, card_id, name, icon=None):
    """
    注册中间卡片并绑定到指定主卡片 + 子卡片。

    :param main_card_id:  主卡片 unique_id（须先通过 RegisterMainCard 注册）
    :param key:           "client" 或 "server"
    :param card_id:       中间卡片唯一标识符
    :param name:          中文名称
    :param icon:          图标路径，传 None 使用默认设置图标
    :returns:             True 成功；False 参数无效或 card_id 已存在
    """
    if not all([main_card_id, key in ("client", "server"), card_id, name]):
        return False
    if icon is None:
        icon = _defaultIcon
    bk = (main_card_id, key)
    if bk not in _middleCardBindings:
        _middleCardBindings[bk] = []
    for existing in _middleCardBindings[bk]:
        if existing[0] == card_id:
            return False  # 不重复注册
    _middleCardBindings[bk].append((card_id, name, icon))
    return True


def GetMiddleCardBindings(main_card_id, key):
    """
    获取指定主卡片+子卡片的所有绑定的中间卡片。
    返回 [(card_id, name, icon), ...]
    """
    return list(_middleCardBindings.get((main_card_id, key), []))


def UnregisterMiddleCard(main_card_id, key, card_id):
    """取消单个中间卡片绑定。"""
    bk = (main_card_id, key)
    if bk in _middleCardBindings:
        for i, (cid, _, _) in enumerate(_middleCardBindings[bk]):
            if cid == card_id:
                _middleCardBindings[bk].pop(i)
                # 同时清除该中间卡片关联的右侧内容项
                _ClearContentItemsByMiddleCard(main_card_id, key, card_id)
                return True
    return False


def ClearMiddleCardBindings(main_card_id, key):
    """清空指定主卡片+子卡片的所有绑定。"""
    bk = (main_card_id, key)
    if bk in _middleCardBindings:
        # 清除这些中间卡片关联的右侧内容项
        for card_id, _, _ in _middleCardBindings[bk]:
            _ClearContentItemsByMiddleCard(main_card_id, key, card_id)
        del _middleCardBindings[bk]
        return True
    return False


def ClearAllCards():
    """清空所有注册的卡片（主卡片 + 中间卡片 + 右侧内容项），用于重置注册表。"""
    global _mainCards, _mainCardOrder, _middleCardBindings, _contentItems
    _mainCards.clear()
    del _mainCardOrder[:]
    _middleCardBindings.clear()
    _contentItems.clear()


# ────────────────── 右侧内容项（按 主卡片 + 子卡片 + 中间卡片 分组，支持链式注册） ──────────────────

_DEFAULT_MIDDLE = "__default__"


def NormalizeMiddleCardId(middle_card_id):
    """将 None 归一化为默认中间卡片 ID（__default__），保证存储 key 与注册分组一致。"""
    return middle_card_id or _DEFAULT_MIDDLE

# (main_card_id, key, middle_card_id) -> [BaseContentItem, ...]
_contentItems = {}

# 内容项类型工厂注册表：type_name -> factory class
_contentFactories = {}

# 内容项变更监听器列表：[(listener), ...]
_contentListeners = []

# 主卡片注册变动回调（注册/注销主卡片时自动调用，用于刷新 UI）
_cardChangedCallback = None


class BaseContentItem(object):
    """右侧内容项基类。"""
    def __init__(self, item_id, type_name):
        self.item_id = item_id
        self.type_name = type_name


class TextContentItem(BaseContentItem):
    """文本内容项（litle 小标题 + label 正文）。"""
    def __init__(self, item_id, title, text):
        super(TextContentItem, self).__init__(item_id, "text")
        self.title = title  # 小标题（对应 JSON 的 litle 控件，白色加大字体）
        self.text = text    # 正文内容（对应 JSON 的 label 控件）


class ButtonContentItem(BaseContentItem):
    """按钮内容项。"""
    def __init__(self, item_id, desc, button_text, on_click=None, locked=False, litle=""):
        super(ButtonContentItem, self).__init__(item_id, "button")
        self.desc = desc
        self.button_text = button_text
        self.on_click = on_click
        self.locked = locked
        self._default_locked = locked  # 注册默认锁定（重置时恢复）
        self.litle = litle  # 小标题

    def SetLocked(self, locked):
        """动态修改锁定状态。"""
        self.locked = locked


class SwitchContentItem(BaseContentItem):
    """开关内容项。"""
    def __init__(self, item_id, desc, default_value=False, locked=False, on_toggle=None, litle=""):
        super(SwitchContentItem, self).__init__(item_id, "switch")
        self.desc = desc
        self.default_value = default_value  # 初始开关状态，True=开，False=关
        self.value = default_value          # 当前开关状态（运行时保存，供 SaveGroupSettings 批量提交）
        self.locked = locked  # 是否锁定
        self._default_locked = locked  # 注册默认锁定（重置时恢复）
        self.on_toggle = on_toggle  # 开关状态改变回调，签名 on_toggle(screenNode, item_id, state)
        self.litle = litle  # 小标题

    def SetLocked(self, locked):
        """动态修改锁定状态。"""
        self.locked = locked

    def SetValue(self, value):
        """保存当前开关状态。"""
        self.value = value


class EditBoxContentItem(BaseContentItem):
    """编辑框内容项。"""
    def __init__(self, item_id, desc, default_value="", placeholder="请输入内容", locked=False, litle="", on_value_change=None):
        super(EditBoxContentItem, self).__init__(item_id, "edit_box")
        self.desc = desc
        self.default_value = default_value  # 输入框初始内容
        self.value = default_value          # 当前输入内容（运行时保存，切换卡片/重建时恢复）
        self.placeholder = placeholder      # 提示文字（JSON 变量 $place_holder_text）
        self.locked = locked
        self._default_locked = locked  # 注册默认锁定（重置时恢复）
        self.litle = litle
        self.on_value_change = on_value_change  # 输入内容变化回调，签名 on_value_change(screenNode, item_id, value)

    def SetLocked(self, locked):
        """动态修改锁定状态。"""
        self.locked = locked

    def SetValue(self, value):
        """保存当前输入内容。"""
        self.value = value


class ResetContentItem(BaseContentItem):
    """重置按钮内容项（仅显示按钮，点击后弹出关联的确认弹窗，文字固定为"重置分页数据"）。"""
    def __init__(self, item_id, popup_id=None, on_click=None):
        super(ResetContentItem, self).__init__(item_id, "reset")
        self.button_text = "重置分页数据"  # 按钮文字固定，不可自定义
        self.popup_id = popup_id    # 关联的弹窗 ID（须先 RegisterPopUp 注册）
        self.on_click = on_click    # 额外点击回调，签名 on_click(screenNode, item_id)（可选）

    def SetPopupId(self, popup_id):
        """动态修改关联的弹窗 ID。"""
        self.popup_id = popup_id


class SliderContentItem(BaseContentItem):
    """滑块内容项。

    steps > 1 时为固定格类型（滑动范围 0~steps），steps <= 1 时为百分比类型（0~1）。
    """
    def __init__(self, item_id, desc, min_val=0, max_val=100, value=50, steps=1,
                 locked=False, litle="", on_value_change=None, slider_type="percent",
                 value_formatter=None, value_labels=None):
        super(SliderContentItem, self).__init__(item_id, "slider")
        self.desc = desc            # 左侧描述文字
        self.litle = litle          # 小标题
        self.min = min_val          # 最小值（固定格类型）
        self.max = max_val          # 最大值（固定格类型）
        self.value = value          # 当前值（percent: 0~1 float；steps: 0~steps）
        self.default_value = value  # 初始值
        self.steps = steps          # 总步长：>1 固定格，<=1 百分比
        self.slider_type = slider_type  # "percent" 或 "steps"
        self.locked = locked
        self._default_locked = locked  # 注册默认锁定（重置时恢复）
        self.on_value_change = on_value_change  # 值变化回调，签名 on_value_change(screenNode, item_id, value)
        # 数值显示自定义：
        #   value_formatter(value) -> str 回调，返回自定义显示文本（无则默认数字/百分比）
        #   value_labels: 固定格类型时 [str,...] 列表，下标=档位，长度应=steps+1，显示对应文字
        self.value_formatter = value_formatter
        self.value_labels = value_labels

    def GetDisplayText(self):
        """获取数值显示文本（支持自定义，默认数字/百分比）。"""
        if self.value_formatter:
            try:
                return self.value_formatter(self.value)
            except Exception:
                pass
        steps = float(self.steps or 1)
        if steps > 1:
            label_idx = int(round(float(self.value)))
            if self.value_labels and 0 <= label_idx < len(self.value_labels):
                return self.value_labels[label_idx]
            return "%d" % label_idx
        return "%.0f%%" % (float(self.value) * 100)

    def SetLocked(self, locked):
        """动态修改锁定状态。"""
        self.locked = locked

    def SetValue(self, value):
        """保存当前滑块值。"""
        self.value = value


class TextContentFactory(object):
    """文本内容项工厂。"""
    @staticmethod
    def CreateItem(item_id, **kwargs):
        return TextContentItem(
            item_id,
            kwargs.get("title", ""),
            kwargs.get("text", "")
        )


class ButtonContentFactory(object):
    """按钮内容项工厂。"""
    @staticmethod
    def CreateItem(item_id, **kwargs):
        return ButtonContentItem(
            item_id,
            kwargs.get("desc", ""),
            kwargs.get("button_text", ""),
            kwargs.get("on_click", None),
            kwargs.get("locked", False),
            kwargs.get("litle", "")
        )


class SwitchContentFactory(object):
    """开关内容项工厂。"""
    @staticmethod
    def CreateItem(item_id, **kwargs):
        return SwitchContentItem(
            item_id,
            kwargs.get("desc", ""),
            kwargs.get("default_value", False),
            kwargs.get("locked", False),
            kwargs.get("on_toggle", None),
            kwargs.get("litle", "")
        )


class EditBoxContentFactory(object):
    """编辑框内容项工厂。"""
    @staticmethod
    def CreateItem(item_id, **kwargs):
        return EditBoxContentItem(
            item_id,
            kwargs.get("desc", ""),
            kwargs.get("default_value", ""),
            kwargs.get("placeholder", "请输入内容"),
            kwargs.get("locked", False),
            kwargs.get("litle", ""),
            kwargs.get("on_value_change", None)
        )


class ResetContentFactory(object):
    """重置按钮内容项工厂。"""
    @staticmethod
    def CreateItem(item_id, **kwargs):
        return ResetContentItem(
            item_id,
            kwargs.get("popup_id", None),
            kwargs.get("on_click", None)
        )


class SliderContentFactory(object):
    """滑块内容项工厂。"""
    @staticmethod
    def CreateItem(item_id, **kwargs):
        return SliderContentItem(
            item_id,
            kwargs.get("desc", ""),
            kwargs.get("min", 0),
            kwargs.get("max", 100),
            kwargs.get("value", 50),
            kwargs.get("steps", 1),
            kwargs.get("locked", False),
            kwargs.get("litle", ""),
            kwargs.get("on_value_change", None),
            kwargs.get("slider_type", "percent"),
            kwargs.get("value_formatter", None),
            kwargs.get("value_labels", None)
        )


class CollapsibleMenuContentItem(BaseContentItem):
    """折叠菜单内容项：litle/desc + 按钮(左对齐显示当前选择+右侧箭头)，点击弹出 collapsible_menu。"""
    def __init__(self, item_id, desc, menu_id, litle="", on_select=None,
                 default_selected_id=None, locked=False):
        super(CollapsibleMenuContentItem, self).__init__(item_id, "collapsible_menu")
        self.desc = desc
        self.menu_id = menu_id          # 关联的折叠菜单 ID（RegisterCollapsibleMenu 注册）
        self.litle = litle
        self.on_select = on_select      # 选择回调，签名 on_select(screenNode, item_id, card_id)
        self.default_selected_id = default_selected_id  # 默认选中卡
        self.default_value = default_selected_id        # 存储默认值（同默认选中卡，重置时恢复）
        self.selected_id = default_selected_id          # 当前选中卡（运行时）
        self.selected_name = self._NameOf(default_selected_id)
        self.value = default_selected_id                # 运行时值（=选中卡 id，SaveGroupSettings 批量提交）
        self.locked = locked
        self._default_locked = locked  # 注册默认锁定（重置时恢复）
        self._loaded = False

    def _NameOf(self, card_id):
        """根据 card_id 查名称；查不到返回空串。"""
        menu = GetCollapsibleMenu(self.menu_id) if card_id else None
        for cid, name in (menu.get("cards", []) if menu else []):
            if cid == card_id:
                return name
        return ""

    def SetSelected(self, card_id, card_name):
        """更新选中状态（供弹窗点击回调调用）。"""
        self.selected_id = card_id
        self.selected_name = card_name
        self.value = card_id

    def SetValue(self, value):
        """从存储/外部写入选中状态（card_id 字符串）。"""
        self.selected_id = value
        self.selected_name = self._NameOf(value)
        self.value = value

    def SetLocked(self, locked):
        """动态修改锁定状态。"""
        self.locked = locked

    def GetDisplayText(self):
        """按钮上实时显示的文本（选中项名称；未选择时提示占位）。"""
        return self.selected_name or "请选择"


class CollapsibleMenuContentFactory(object):
    """折叠菜单内容项工厂。"""
    @staticmethod
    def CreateItem(item_id, **kwargs):
        return CollapsibleMenuContentItem(
            item_id,
            kwargs.get("desc", ""),
            kwargs.get("menu_id", ""),
            kwargs.get("litle", ""),
            kwargs.get("on_select", None),
            kwargs.get("default_selected_id", None),
            kwargs.get("locked", False)
        )


def RegisterContentItemType(type_name, factory):
    """
    注册自定义内容项类型。

    :param type_name: 类型名称，如 "slider"
    :param factory:   工厂类，需要实现静态/类方法：
                          CreateItem(item_id, **kwargs) -> BaseContentItem
    """
    _contentFactories[type_name] = factory


# 注册内置类型
RegisterContentItemType("text", TextContentFactory)
RegisterContentItemType("button", ButtonContentFactory)
RegisterContentItemType("switch", SwitchContentFactory)
RegisterContentItemType("edit_box", EditBoxContentFactory)
RegisterContentItemType("reset", ResetContentFactory)
RegisterContentItemType("slider", SliderContentFactory)
RegisterContentItemType("collapsible_menu", CollapsibleMenuContentFactory)


def GetContentItemFactory(type_name):
    """获取指定类型的内容项工厂。"""
    return _contentFactories.get(type_name)


class ContentSettingInst(object):
    """
    链式注册实例。

    用法:
        inst = CreateContentInst("basic_settings", "client", "client_opt_a")
        inst.AddText("info", "说明").AddButton("btn", "启用功能", "启用")

    也可以中途切换中间卡片:
        CreateContentInst("basic_settings", "client")\
            .ForMiddleCard("client_opt_a")\
            .AddText("info", "说明")\
            .ForMiddleCard("client_opt_b")\
            .AddText("info_b", "说明B")
    """

    def __init__(self, main_card_id, key, middle_card_id=None):
        self._main_card_id = main_card_id
        self._key = key
        self._middle_card_id = middle_card_id or _DEFAULT_MIDDLE
        self._lst = self._GetList()

    def _GetList(self):
        bk = (self._main_card_id, self._key, self._middle_card_id)
        if bk not in _contentItems:
            _contentItems[bk] = []
        return _contentItems[bk]

    def ForMiddleCard(self, middle_card_id):
        """指定该内容项归属的中间卡片，返回 self 继续链式调用。"""
        self._middle_card_id = middle_card_id or _DEFAULT_MIDDLE
        self._lst = self._GetList()
        return self

    def AddText(self, item_id, title="", text=""):
        """
        添加文本内容项。
        :param item_id: 内容项唯一标识符
        :param title:   标题（可空字符串）
        :param text:    正文内容
        """
        return self._AddItem("text", item_id, title=title, text=text)

    def AddButton(self, item_id, desc, button_text, on_click=None, locked=False, litle=""):
        """
        添加按钮内容项。
        :param item_id:     内容项唯一标识符
        :param desc:        左侧描述文字
        :param button_text: 按钮上显示的文字
        :param on_click:    点击后的回调函数（可选）
        :param locked:      是否锁定（True 时显示 lock 图层并禁止点击）
        :param litle:       小标题（可选）
        """
        return self._AddItem(
            "button", item_id,
            desc=desc, button_text=button_text, on_click=on_click, locked=locked, litle=litle
        )

    def AddSwitch(self, item_id, desc, default_value=False, locked=False, on_toggle=None, litle=""):
        """
        添加开关内容项。
        :param item_id:      内容项唯一标识符
        :param desc:         左侧描述文字
        :param default_value: 初始开关状态，True=开，False=关
        :param locked:       是否锁定（True 时禁用开关交互）
        :param on_toggle:    开关状态改变回调，签名 on_toggle(screenNode, item_id, state)
        :param litle:        小标题（可选）
        """
        return self._AddItem(
            "switch", item_id,
            desc=desc, default_value=default_value, locked=locked, on_toggle=on_toggle, litle=litle
        )

    def AddEditBox(self, item_id, desc, default_value="", placeholder="请输入内容", locked=False, litle="", on_value_change=None):
        """
        添加编辑框内容项。
        :param item_id:       内容项唯一标识符
        :param desc:          左侧描述文字
        :param default_value: 输入框初始内容（可选，默认为空）
        :param placeholder:   输入框提示文字（可选，默认"请输入内容"）
        :param locked:        是否锁定（True 时显示 lock 图层并禁止输入）
        :param litle:         小标题（可选）
        :param on_value_change: 输入内容变化回调，签名 on_value_change(screenNode, item_id, value)（可选）
        """
        return self._AddItem(
            "edit_box", item_id,
            desc=desc, default_value=default_value, placeholder=placeholder, locked=locked, litle=litle,
            on_value_change=on_value_change
        )

    def AddResetButton(self, item_id, popup_id=None, on_click=None):
        """
        添加重置按钮内容项（仅显示按钮，无左侧描述，按钮文字固定为"重置分页数据"）。
        :param item_id:      内容项唯一标识符
        :param popup_id:     关联的弹窗 ID（须先 RegisterPopUp 注册），传 None 则只触发 on_click
        :param on_click:     额外点击回调，签名 on_click(screenNode, item_id)（可选）
        """
        return self._AddItem(
            "reset", item_id,
            popup_id=popup_id, on_click=on_click
        )

    def AddSlider(self, item_id, desc, min_val=0, max_val=100, value=50, steps=1,
                  locked=False, litle="", on_value_change=None, slider_type="percent",
                  value_formatter=None, value_labels=None):
        """
        添加滑块内容项（上面文字，下面滑块）。

        :param item_id:         内容项唯一标识符
        :param desc:            左侧描述文字
        :param min_val:         最小值（仅固定格类型有效）
        :param max_val:         最大值（仅固定格类型有效）
        :param value:           当前值。percent 类型为 0~1 小数；steps 类型为 0~steps 整数
        :param steps:           总步长：>1 时固定格类型（滑动范围 0~steps），<=1 时百分比类型（0~1）
        :param locked:          是否锁定
        :param litle:           小标题（可选）
        :param on_value_change: 值变化回调，签名 on_value_change(screenNode, item_id, value)（可选）
        :param slider_type:     "percent"（百分比 0~1）或 "steps"（固定格 0~steps）
        :param value_formatter: 数值显示自定义回调 value_formatter(value) -> str（可选，返回自定义文本）
        :param value_labels:    固定格类型数值显示标签 [str, ...]，下标=档位，长度应=steps+1（可选）
        """
        return self._AddItem(
            "slider", item_id,
            desc=desc, min=min_val, max=max_val, value=value, steps=steps,
            locked=locked, litle=litle, on_value_change=on_value_change,
            slider_type=slider_type,
            value_formatter=value_formatter, value_labels=value_labels
        )

    def AddCollapsibleMenu(self, item_id, desc, menu_id, litle="", on_select=None,
                           default_selected_id=None, locked=False):
        """
        添加折叠菜单内容项。
        :param item_id:             内容项唯一标识符
        :param desc:                左侧描述文字
        :param menu_id:             关联折叠菜单 ID（须先 RegisterCollapsibleMenu /
                                   AddCollapsibleMenuCard 注册卡片）
        :param litle:               小标题（可选）
        :param on_select:           选择回调，签名 on_select(screenNode, item_id, card_id)（可选）
        :param default_selected_id: 默认选中卡片 ID（可选）
        :param locked:              初始锁定状态（可选，默认 False）
        """
        return self._AddItem(
            "collapsible_menu", item_id,
            desc=desc, menu_id=menu_id, litle=litle, on_select=on_select,
            default_selected_id=default_selected_id, locked=locked
        )

    def AddCustom(self, item_id, type_name, **kwargs):
        """扩展接口：新增类型只需先 RegisterContentItemType，然后这里调用。"""
        return self._AddItem(type_name, item_id, **kwargs)

    def _AddItem(self, type_name, item_id, **kwargs):
        if item_id in [it.item_id for it in self._lst]:
            return self
        factory = _contentFactories.get(type_name)
        if factory is None:
            print "==== ContentItem type '%s' not registered ====" % type_name
            return self
        self._lst.append(factory.CreateItem(item_id, **kwargs))
        _NotifyContentChanged((self._main_card_id, self._key, self._middle_card_id))
        return self

    def Clear(self):
        """清除当前分组的所有内容项。"""
        del self._lst[:]
        _NotifyContentChanged((self._main_card_id, self._key, self._middle_card_id))
        return self

    def Remove(self, item_id):
        """移除当前分组下的一个内容项。"""
        for i, it in enumerate(self._lst):
            if it.item_id == item_id:
                self._lst.pop(i)
                break
        _NotifyContentChanged((self._main_card_id, self._key, self._middle_card_id))
        return self


def CreateContentInst(main_card_id, key, middle_card_id=None):
    """创建一个链式注册实例，关联到指定主卡片 + 子卡片 + 中间卡片。"""
    return ContentSettingInst(main_card_id, key, middle_card_id)


def GetContentItems(main_card_id, key, middle_card_id=_DEFAULT_MIDDLE):
    """获取指定分组的所有内容项列表。"""
    bk = (main_card_id, key, middle_card_id)
    return list(_contentItems.get(bk, []))


def GetContentItem(main_card_id, key, middle_card_id, item_id):
    """获取指定分组中指定 ID 的内容项，未找到返回 None。"""
    for item in GetContentItems(main_card_id, key, middle_card_id):
        if item.item_id == item_id:
            return item
    return None


def GetAllContentGroups():
    """返回所有已注册内容项分组 [(main_card_id, key, middle_card_id), ...]（供批量重置遍历）。"""
    return list(_contentItems.keys())


def ClearContentItems(main_card_id=None, key=None, middle_card_id=None):
    """
    清空内容项。
    不传参数清空全部；传参只清空指定分组。
    """
    global _contentItems
    if main_card_id is not None and key is not None:
        if middle_card_id is not None:
            _contentItems.pop((main_card_id, key, middle_card_id), None)
        else:
            for bk in list(_contentItems.keys()):
                if bk[0] == main_card_id and bk[1] == key:
                    del _contentItems[bk]
    else:
        _contentItems.clear()


def _ClearContentItemsByMainCard(main_card_id):
    """清空指定主卡片下的所有内容项。"""
    for bk in list(_contentItems.keys()):
        if bk[0] == main_card_id:
            del _contentItems[bk]


def _ClearContentItemsByMiddleCard(main_card_id, key, middle_card_id):
    """清空指定中间卡片关联的内容项。"""
    _contentItems.pop((main_card_id, key, middle_card_id), None)


def RegisterContentListener(listener):
    """
    注册内容项变更监听器。
    listener 签名: listener(group_tuple) -> None
    group_tuple = (main_card_id, key, middle_card_id)
    """
    if listener not in _contentListeners:
        _contentListeners.append(listener)


def UnregisterContentListener(listener):
    """注销内容项变更监听器。"""
    if listener in _contentListeners:
        _contentListeners.remove(listener)


def SetCardChangedCallback(callback):
    """
    设置主卡片注册变更回调。
    当 RegisterMainCard / UnregisterMainCard 成功执行后自动调用该回调。
    通常由 MyClientSystem 在初始化时设置，用于自动刷新 UI。
    """
    global _cardChangedCallback
    _cardChangedCallback = callback


def _NotifyCardChanged():
    """通知主卡片注册变更。"""
    if _cardChangedCallback:
        try:
            _cardChangedCallback()
        except Exception as e:
            print "==== card changed callback error: %s ====" % str(e)


def _NotifyContentChanged(group):
    """通知所有监听器内容项已变更。"""
    for listener in list(_contentListeners):
        try:
            listener(group)
        except Exception as e:
            print "==== content listener error: %s ====" % str(e)


# ============================================================
# 事件常量定义
# ============================================================

# 设置 UI 打开事件，由 MyClientSystem 在 PushScreen 时抛出
# 事件数据: {"playerId": str}
SettingsUIOpenEvent = "Script_NeteaseMod9sPMlz0K_SettingsUIOpen"

# 设置 UI 关闭事件，由 MyClientSystem 在 PopScreen 时抛出
# 事件数据: {"playerId": str}
SettingsUICloseEvent = "Script_NeteaseMod9sPMlz0K_SettingsUIClose"


# ============================================================
# 弹窗（PopUp）注册表
# ============================================================

# popup_id -> {"title": str, "content": str, "buttons": [(text, callback|None), ...]}
_popUps = {}


def RegisterPopUp(popup_id, title, content, buttons=None):
    """
    注册一个自定义弹窗。

    :param popup_id: 弹窗唯一标识符（全局唯一，重复注册会覆盖旧数据）
    :param title:    弹窗标题文字
    :param content:  弹窗正文内容（支持换行 \\n，超长自动滚动）
    :param buttons:  底部按钮列表 [(按钮文字, 点击回调|None), ...]，
                     回调签名 f()，返回 True 时弹窗自动关闭；传 None 表示无底部按钮
    :returns:        True 成功；False 参数无效
    """
    if not popup_id or not title:
        return False
    btnList = []
    if buttons:
        for btn in buttons:
            if not isinstance(btn, (tuple, list)) or len(btn) < 1:
                continue
            text = str(btn[0])
            cb = btn[1] if len(btn) > 1 else None
            btnList.append((text, cb))
    _popUps[popup_id] = {"title": title, "content": content, "buttons": btnList}
    return True


def UnregisterPopUp(popup_id):
    """注销指定弹窗，返回 True 成功，False 弹窗不存在。"""
    if popup_id in _popUps:
        del _popUps[popup_id]
        return True
    return False


def GetPopUp(popup_id):
    """获取弹窗数据 {"title": str, "content": str, "buttons": [(text, callback), ...]} 或 None。"""
    return _popUps.get(popup_id)


def GetAllPopUpIds():
    """返回所有已注册的弹窗 ID 列表。"""
    return list(_popUps.keys())


# ============================================================
# 折叠菜单（CollapsibleMenu）注册表
# ============================================================

# menu_id -> {"title": str, "cards": [(card_id, name), ...]}
_collapsibleMenus = {}


def RegisterCollapsibleMenu(menu_id, title, cards=None):
    """
    注册一个折叠菜单。

    :param menu_id: 折叠菜单唯一标识符
    :param title:   弹窗标题文字
    :param cards:   卡片列表 [(card_id, name), ...]，也可后续用 AddCollapsibleMenuCard 追加
    :returns:       True 成功；False 参数无效
    """
    if not menu_id or not title:
        return False
    _collapsibleMenus[menu_id] = {"title": title, "cards": list(cards or [])}
    return True


def AddCollapsibleMenuCard(menu_id, card_id, name):
    """
    向已注册的折叠菜单追加一张卡片；菜单不存在时自动创建（标题为空串，需再 RegisterCollapsibleMenu 设标题）。

    :param menu_id: 折叠菜单 ID
    :param card_id: 卡片唯一标识符
    :param name:    卡片显示文字
    :returns:       True 成功；False 参数无效或卡片重复
    """
    if not menu_id or not card_id or not name:
        return False
    menu = _collapsibleMenus.setdefault(menu_id, {"title": "", "cards": []})
    for cid, _ in menu["cards"]:
        if cid == card_id:
            return False  # 重复卡不追加
    menu["cards"].append((card_id, name))
    return True


def GetCollapsibleMenu(menu_id):
    """获取折叠菜单 {"title": str, "cards": [(card_id, name), ...]} 或 None。"""
    return _collapsibleMenus.get(menu_id)


def GetCollapsibleMenuCards(menu_id):
    """获取卡片列表 [(card_id, name), ...]，菜单不存在返回 []。"""
    menu = _collapsibleMenus.get(menu_id)
    return menu["cards"] if menu else []


# ============================================================
# 弹窗事件常量
# ============================================================

# 弹窗打开事件，由 MyClientSystem 在 PushScreen 时抛出
# 事件数据: {"playerId": str, "popupId": str}
PopUpOpenEvent = "Script_NeteaseMod9sPMlz0K_PopUpOpen"

# 弹窗关闭事件，由 MyClientSystem 在 PopScreen 时抛出
# 事件数据: {"playerId": str}
PopUpCloseEvent = "Script_NeteaseMod9sPMlz0K_PopUpClose"
