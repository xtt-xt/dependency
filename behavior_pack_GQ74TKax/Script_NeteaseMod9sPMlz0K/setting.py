# -*- coding: utf-8 -*-
"""
设置配置页注册
==============
注册主卡片"设置配置"，供设置界面左侧列表展示。
图标使用本资源包内的 textures/ui/xtt_dependency（引擎纹理引用不带 .png 扩展名）。
"""

from CardRegistryApi import (
    RegisterMainCard,
    RegisterMiddleCard,
    CreateContentInst,
    RegisterCollapsibleMenu,
    RegisterPopUp,
    RegisterItemPicker,
    ResetGroupSettings,
    GetSettingValue,
    SetSettingValue,
    # 组合开关（开发者选项的演示用）
    RegisterCardToggle,
    AddCardToggleOption,
    AddCardToggleButton,
    RemoveCardToggleOption,
    GetCardToggleOptionIds,
    RemoveCardToggleState,
    RefreshCardToggle,
    OpenCardToggle,
)
from DebugLog import dlog

# 主卡片唯一标识（全局唯一，不可重复）
_MAIN_CARD_ID = "settings_config"

# "显示"分类下的开关项 id（供 FoldMenuProxy 读取）
DISPLAY_CATEGORY_ID = "display"
SWITCH_FOLD_MENU = "register_fold_menu"    # 注册到折叠菜单
# 加载速度滑块 id（档位 0~100，每 0.1 秒一级，即 0~10 秒）
SLIDER_MIDDLE_DELAY = "middle_card_load_delay"  # 中间卡片加载速度
SLIDER_RIGHT_DELAY = "right_content_load_delay" # 设置项加载速度

# 物品选择演示（临时演示用，正式使用时换成自己的物品表；不需要可整段删掉）
DEMO_PICKER_ID = "demo_item_picker"
DEMO_ITEM_ID = "demo_item_pick"

# "开发者选项"分类（客户端中间卡片）：测试卡片 / 测试弹窗 / 演示内容统一放这里。
# 发布正式版时，把 RegisterSettingsConfig 里带「开发者选项」横幅的那整块注释掉即可。
DEV_CATEGORY_ID = "dev_options"
DEV_NOTICE_ID = "dev_notice"           # 顶部开发版本提示（琥珀色文字内容项）
DEV_NOTICE_TITLE = "【开发版本】"
DEV_NOTICE_TEXT = ("你正在使用「通用模组前置」的开发版本。\n"
                   "本版本可能不稳定，其中包含尚未确定的功能与内容，随时可能改动或移除。\n"
                   "请不要以本版本作为开发基准，正式接入请以发布版本为准。")
DEV_NOTICE_COLOR = (1.0, 0.76, 0.35)   # 提示文字颜色（琥珀），AddText 的 color 参数

# 组合开关演示（开发者选项）：三种行控件 + 锁定行 + 底部按钮动态增删行
DEV_TOGGLE_ID = "dev_card_toggle"
DEV_TOGGLE_OPEN_ID = "dev_toggle_open"
_DEV_TOGGLE_SEQ = 0                    # 动态加行的序号（只增不减，避免与已有 option_id 撞车）


def _OnDemoItemPicked(screenNode, item_id, item_name, item_aux):
    """物品选择演示回调：把选中物品打到客户端日志。"""
    dlog.client_print("==== demo item picked: %s aux=%s (item_id=%s) ====" % (
        item_name, item_aux, item_id))


def RefreshDemoItemPicker(entries):
    """用「全部物品」重建演示数据集（Client 收到服务端下发后调用）。

    :param entries: [(item_name, item_aux, display_name), ...]
    """
    if not entries:
        return
    RegisterItemPicker(DEMO_PICKER_ID, "选择物品", items=entries)
    dlog.client_print("==== demo item picker refreshed: %d items ====" % len(entries))


def _DelayValueFormat(level):
    """滑块档位（0~100）转为秒显示文本：'X.X秒'。"""
    return "%.1f秒" % (float(level) / 10.0)


def _OnMiddleDelayChange(screenNode, item_id, value):
    """中间卡片加载速度改变：写入存储并实时应用到界面。"""
    level = int(round(float(value)))
    SetSettingValue(_MAIN_CARD_ID, "client", DISPLAY_CATEGORY_ID, item_id, level)
    try:
        screenNode.SetMiddleCardDelaySec(level / 10.0)
    except Exception:
        pass


def _OnRightDelayChange(screenNode, item_id, value):
    """设置项加载速度改变：写入存储并实时应用到界面。"""
    level = int(round(float(value)))
    SetSettingValue(_MAIN_CARD_ID, "client", DISPLAY_CATEGORY_ID, item_id, level)
    try:
        screenNode.SetRightContentDelaySec(level / 10.0)
    except Exception:
        pass


def _OnDisplaySwitchToggle(screenNode, item_id, state):
    """开关值改变时打印提示。实际生效由对应菜单代理在打开界面时读取开关值决定。"""
    dlog.client_print("==== display switch %s => %s ====" % (item_id, state))

def _OnPickerArrowPageToggle(screenNode, item_id, state):
    """「左右方向键翻页」开关：关闭时把下面的「翻页需按住 Shift」一并锁定。"""
    locked = not bool(state)
    dlog.client_print("==== picker arrow page => %s, shift switch locked=%s ====" % (state, locked))
    if screenNode and hasattr(screenNode, "SetLocked"):
        screenNode.SetLocked(SWITCH_PICKER_ARROW_SHIFT, locked)

def _OnPickerArrowShiftToggle(screenNode, item_id, state):
    """「翻页需按住 Shift」开关：改完在底部提示需重新进入物品选择弹窗才生效。"""
    dlog.client_print("==== picker arrow shift => %s ====" % state)
    from CardRegistryApi import ShowToast, ToastUnder
    ShowToast(ToastUnder, "「翻页需按住 Shift」改动将在重新进入物品选择弹窗后生效")


def _OnSaveSyncToggle(screenNode, item_id, state):
    """开关1：本存档配置同步（权威值在存档内，交给 SyncControl 处理）。"""
    from SyncControl import OnToggleSaveSync
    return OnToggleSaveSync(screenNode, item_id, state)


def _OnNewSaveUseCrossToggle(screenNode, item_id, state):
    """开关2：新存档套用跨存档配置。"""
    from SyncControl import OnToggleNewSaveUseCross
    return OnToggleNewSaveUseCross(screenNode, item_id, state)


def _OnClearCrossClick(screenNode, item_id):
    """调试页：清空跨存档配置（仅用于测试）。"""
    from SyncControl import OnClickClearCross
    return OnClickClearCross(screenNode, item_id)


def _OnSyncInfoClick(screenNode, item_id):
    """调试页：把当前同步状态输出到调试日志。"""
    from SyncControl import OnClickSyncInfo
    return OnClickSyncInfo(screenNode, item_id)


def _OnResetClick(screenNode, item_id):
    """重置当前分类下所有设置项为默认值，并刷新右侧面板。

    服务端分组额外通知服务端重置权威默认值并广播全服（参考飞行之羽模组的
    "服务端权威重置 + 全局广播"方法），保证其他在线玩家 UI 同步。
    """
    group = getattr(screenNode, "mCurrentRightGroup", None)
    if not group or len(group) < 3:
        return
    main_card_id, sub_key, middle_card_id = group
    ResetGroupSettings(main_card_id, sub_key, middle_card_id)
    screenNode.RebuildRightContent(main_card_id, sub_key, middle_card_id)
    # 重置"显示"分组后，重新从存储读取加载速度并应用到界面（滑块不会触发 on_value_change）
    if middle_card_id == DISPLAY_CATEGORY_ID:
        try:
            screenNode.SetMiddleCardDelaySec(
                GetSettingValue(main_card_id, "client", DISPLAY_CATEGORY_ID,
                                SLIDER_MIDDLE_DELAY, default=0) / 10.0)
            screenNode.SetRightContentDelaySec(
                GetSettingValue(main_card_id, "client", DISPLAY_CATEGORY_ID,
                                SLIDER_RIGHT_DELAY, default=0) / 10.0)
        except Exception:
            pass
    if sub_key == "server":
        from CardRegistryApi import _g_ClientSystem
        if _g_ClientSystem:
            _g_ClientSystem.NotifyResetGroup(sub_key, middle_card_id)
    dlog.client_print("==== reset group %s/%s/%s ====" % (main_card_id, sub_key, middle_card_id))


# "调试"分类下的开关项 id
DEBUG_CATEGORY_ID = "debug"
SWITCH_LOG_OUTPUT = "log_output"    # 客户端日志输出
SWITCH_SERVER_LOG_OUTPUT = "server_log_output"  # 服务端全局日志输出
SERVER_RESET_ID = "reset_server_debug"  # 服务端调试页"重置本页"按钮（重置服务端权威默认值）

# "显示"分类下的缓入/缓出动画开关项 id
SWITCH_FADE_ANIM = "enable_fade_anim"  # 设置项与中间卡片的缓入/缓出动画
SWITCH_ENTER_ANIM = "enable_enter_anim"  # 中间/右边面板的滑入进入动画
SWITCH_PICKER_ARROW_PAGE = "picker_arrow_page"    # 物品选择弹窗左右方向键翻页（默认开）
SWITCH_PICKER_ARROW_SHIFT = "picker_arrow_shift"  # 翻页需按住 Shift（默认关）
SWITCH_SAVE_SYNC = "save_config_sync"      # 本存档配置同步（每个存档独立）
SWITCH_NEW_SAVE_USE_CROSS = "new_save_use_cross"  # 新存档套用跨存档配置（跨存档保存）

# "简介"分类下的项 id（内容由用户自行填写）
INFO_CATEGORY_ID = "info"

# 简介正文：请在此自行填写（支持 \n 换行）
INFO_TEXT = "感谢使用通用模组前置\n本模组前置仅为其他模组提供基础功能，不包含任何游戏内容\n点击其他卡片开始配置吧\n\n如果觉得这个模组有用，不妨打个五星好评?"

# 简介页自定义按钮与弹窗（弹窗内容请自行修改）
INFO_BUTTON_ID = "info_btn"                  # 自定义按钮 id
INFO_POPUP_ID = "info_popup"                 # 弹窗 id
INFO_POPUP_TITLE = "关于通用模组前置"
INFO_POPUP_CONTENT = ("本模组是开源模组\n"
                      "开源链接https://github.com/xtt-xt/dependency\n"
                      "开源协议参见仓库内LICENSE文件\n"
                      "本模组前置仅为其他模组提供基础功能，不包含任何游戏内容。\n"
                      "版本：0.0.2  作者：星天xt")

# 日志导出（复制）相关项 id
CLIENT_COPY_COUNT = "copy_client_count"  # 客户端导出数量（折叠菜单）
CLIENT_COPY_BTN = "copy_client_log"      # 客户端复制按钮
SERVER_COPY_COUNT = "copy_server_count"  # 服务端导出数量（折叠菜单）
SERVER_COPY_BTN = "copy_server_log"             # 服务端复制按钮
CLIENT_CLEAR_CROSS_BTN = "clear_cross_config"  # 调试页：清空跨存档配置（测试用）
CLIENT_SYNC_INFO_BTN = "sync_state_info"       # 调试页：输出同步状态

# 导出数量选择菜单：共享同一个菜单，各分类项各自的选中值独立存储
EXPORT_COUNT_MENU = "export_log_count"
_EXPORT_COUNT_OPTIONS = (
    ("50", "50条"),
    ("100", "100条"),
    ("200", "200条"),
    ("500", "500条"),
)
_DEFAULT_EXPORT_COUNT = "200"


def _GetExportCount(sub_key, item_id):
    """读取导出数量下拉框当前选中的条数（取不到回退 200）。"""
    from CardRegistryApi import GetContentItem
    item = GetContentItem(_MAIN_CARD_ID, sub_key, DEBUG_CATEGORY_ID, item_id)
    if item is not None:
        try:
            return int(item.value)
        except Exception:
            pass
    return 200


def _OnCopyClientLog(screenNode, item_id):
    """复制最近 N 条客户端调试日志到本机剪贴板。"""
    from CardRegistryApi import _g_ClientSystem
    if _g_ClientSystem:
        _g_ClientSystem.CopyClientLogToClipboard(
            _GetExportCount("client", CLIENT_COPY_COUNT))


def _OnCopyServerLog(screenNode, item_id):
    """请求服务端最近 N 条服务端日志并复制到本机剪贴板。"""
    from CardRegistryApi import _g_ClientSystem
    if _g_ClientSystem:
        _g_ClientSystem.RequestServerLogDump(
            _GetExportCount("server", SERVER_COPY_COUNT))


def _OnDebugSwitchToggle(screenNode, item_id, state):
    """客户端"日志输出"开关回调：立即切换客户端调试日志输出。"""
    dlog.set_client_enabled(state)


def _OnServerLogSwitchToggle(screenNode, item_id, state):
    """服务端全局"日志输出"开关回调：通知服务端修改（服务端自行鉴权 OP）。"""
    from CardRegistryApi import _g_ClientSystem
    if _g_ClientSystem:
        _g_ClientSystem.SendServerLogEnabled(bool(state))


def _OnOptimizeSwitchToggle(screenNode, item_id, state):
    """优化开关回调：立即启用/禁用设置项与中间卡片的缓入/缓出动画。"""
    if screenNode and hasattr(screenNode, "SetFadeAnimEnabled"):
        screenNode.SetFadeAnimEnabled(bool(state))


def _OnEnterAnimToggle(screenNode, item_id, state):
    """面板滑入动画开关回调。

    开启：立即生效并写存储。
    关闭：运行时切换动画会导致面板停在动画初始位，故弹确认框——
    取消则恢复开启；确认退出设置则关闭动画并立即关闭设置界面（下次打开生效）。
    """
    if state:
        if screenNode and hasattr(screenNode, "SetEnterAnimEnabled"):
            screenNode.SetEnterAnimEnabled(True)
        SetSettingValue("settings_config", "client", DISPLAY_CATEGORY_ID,
                        SWITCH_ENTER_ANIM, True)
        return
    _ConfirmDisableEnterAnim(screenNode, item_id)


def _ConfirmDisableEnterAnim(screenNode, item_id):
    """关闭"面板滑入动画"的确认弹窗：取消恢复开启；确认则关闭动画并关闭设置界面。"""
    from CardRegistryApi import (RegisterPopUp, ShowPopUp, GetContentItem,
                                 _g_ClientSystem)

    def _OnCancel():
        # 恢复为开启：item 值 + 存储 + 重建当前分组（弹窗打开时设置界面在后台，
        # 直接 SetToggleState 不刷新，重建从存储读回 True 才可靠）
        item = GetContentItem(_MAIN_CARD_ID, "client", DISPLAY_CATEGORY_ID, item_id)
        if item is not None:
            item.value = True
        SetSettingValue(_MAIN_CARD_ID, "client", DISPLAY_CATEGORY_ID, item_id, True)
        group = getattr(screenNode, "mCurrentRightGroup", None)
        if group and len(group) == 3:
            try:
                screenNode.RebuildRightContent(*group)
            except Exception as e:
                dlog.client_print("==== confirm cancel rebuild error: %s ====" % str(e))
        return True

    def _OnConfirmClose():
        # 关闭动画 + 写存储 + 标记关闭设置界面（OnActive 时 PopScreen）
        if screenNode and hasattr(screenNode, "SetEnterAnimEnabled"):
            screenNode.SetEnterAnimEnabled(False)
        item = GetContentItem(_MAIN_CARD_ID, "client", DISPLAY_CATEGORY_ID, item_id)
        if item is not None:
            item.value = False
        SetSettingValue(_MAIN_CARD_ID, "client", DISPLAY_CATEGORY_ID, item_id, False)
        if _g_ClientSystem:
            _g_ClientSystem.mPendingCloseSettings = True
        return True

    RegisterPopUp("confirm_disable_enter_anim", "关闭面板滑入动画",
                  "关闭面板滑入动画需要重启设置界面才能生效\n"
                  "确定后设置界面将立即关闭，下次打开设置时生效",
                  buttons=[("取消", _OnCancel), ("退出设置", _OnConfirmClose)])
    ShowPopUp("confirm_disable_enter_anim", force_scroll=False)


def _OnInfoButtonClick(screenNode, item_id):
    """简介页自定义按钮：打开自定义普通（不滚动）弹窗。"""
    from CardRegistryApi import ShowPopUp
    ShowPopUp(INFO_POPUP_ID, force_scroll=False)


# ==================== 组合开关演示（开发者选项用，发布时随该块一起注释） ====================

def _OnDevToggleOpen(screenNode, item_id):
    """打开组合开关演示弹窗（普通 button 触发）。"""
    OpenCardToggle(DEV_TOGGLE_ID)


def _OnDevTogglePrint(screenNode, toggle_id, state_dict):
    """底部按钮：打印当前所有行的状态（开关行 bool，编辑框行文本）。"""
    dlog.client_print("==== dev card_toggle '%s' states: %s ====" % (toggle_id, state_dict))


def _OnDevToggleAddRow(screenNode, toggle_id, state_dict):
    """底部按钮：动态追加一行并刷新弹窗（RefreshCardToggle 下一帧重建）。"""
    global _DEV_TOGGLE_SEQ
    _DEV_TOGGLE_SEQ += 1
    n = _DEV_TOGGLE_SEQ
    palette = (("minecraft:gold_ingot", "金锭"),
               ("minecraft:redstone", "红石"),
               ("minecraft:book", "书"),
               ("minecraft:coal", "煤炭"))
    item_name, label = palette[(n - 1) % len(palette)]
    AddCardToggleOption(DEV_TOGGLE_ID, "extra_%d" % n, item_name,
                        desc="动态新增第%d行（%s）" % (n, label))
    RefreshCardToggle(DEV_TOGGLE_ID)
    dlog.client_print("==== dev card_toggle add: extra_%d ====" % n)


def _OnDevToggleRemoveRow(screenNode, toggle_id, state_dict):
    """底部按钮：删除最后一行并刷新弹窗（顺带清掉该行已存状态）。"""
    ids = GetCardToggleOptionIds(DEV_TOGGLE_ID)
    if not ids:
        return
    removed = ids[-1]
    if RemoveCardToggleOption(DEV_TOGGLE_ID, removed):
        RemoveCardToggleState(DEV_TOGGLE_ID, removed)
        RefreshCardToggle(DEV_TOGGLE_ID)
        dlog.client_print("==== dev card_toggle remove: %s ====" % removed)


def _RegisterDevToggleDemo():
    """注册组合开关演示数据集：混合三种行控件 + 锁定行 + 底部增删/打印按钮。"""
    RegisterCardToggle(DEV_TOGGLE_ID, "组合开关演示", mode="multi")
    # 默认 ctrl_type="toggle"：物品图标 + 文字 + 开关
    AddCardToggleOption(DEV_TOGGLE_ID, "demo_toggle", "minecraft:diamond",
                        desc="开关行：物品图标 + 文字 + 开关", default_on=True)
    # ctrl_type="toggle_text"：纯文字 + 开关（item_name 传 ""）
    AddCardToggleOption(DEV_TOGGLE_ID, "demo_text", "",
                        desc="纯文字行：没有物品图标", ctrl_type="toggle_text")
    # ctrl_type="toggle_edit_box"：物品图标 + 文字 + 输入框（default_value 为初始文本）
    AddCardToggleOption(DEV_TOGGLE_ID, "demo_edit", "minecraft:paper",
                        desc="输入框行：文字可编辑", ctrl_type="toggle_edit_box",
                        default_value="16")
    # 锁定行：开关不可交互，显示 switch 内置锁定贴图
    AddCardToggleOption(DEV_TOGGLE_ID, "demo_locked", "minecraft:emerald",
                        desc="锁定行：开关不可点", locked=True)
    AddCardToggleButton(DEV_TOGGLE_ID, "加一行", _OnDevToggleAddRow)
    AddCardToggleButton(DEV_TOGGLE_ID, "删末尾一行", _OnDevToggleRemoveRow)
    AddCardToggleButton(DEV_TOGGLE_ID, "打印状态", _OnDevTogglePrint)


def RegisterSettingsConfig(main_card_id=_MAIN_CARD_ID, name="设置配置",
                           icon="textures/ui/xtt_dependency"):
    """注册"设置配置"主卡片及其"显示"分类下的开关项，返回主卡片是否注册成功。

    重复调用会自动失败（注册表去重），不会重复添加。
    """
    ok = RegisterMainCard(main_card_id, name, icon)

    # "简介"分类（客户端中间卡片）：内容由用户自行填写（改 INFO_TEXT 即可）
    RegisterMiddleCard(main_card_id, "client", INFO_CATEGORY_ID, "简介",
                       icon="textures/ui/bookshelf_flat")
    CreateContentInst(main_card_id, "client", INFO_CATEGORY_ID) \
        .AddText("info_text", "简介", INFO_TEXT) \
        .AddButton(INFO_BUTTON_ID, "查看模组信息", "关于", on_click=_OnInfoButtonClick)
    # 注册简介自定义弹窗（普通不滚动版，底部"确定"按钮点击即关闭）
    RegisterPopUp(INFO_POPUP_ID, INFO_POPUP_TITLE, INFO_POPUP_CONTENT,
                  buttons=[("确定", None)])

    # "显示"分类（中间卡片），挂到 主卡片 + client 子卡片下
    RegisterMiddleCard(main_card_id, "client", DISPLAY_CATEGORY_ID, "显示",
                       icon="textures/ui/icon_alex")

    # 顶部介绍（测试文字，可自行填充）
    INTRO_TEXT = "这里可以设置设置的入口位置和部分其他内容。如果你把入口设置项全部关闭，你可以使用以下方法进入\n1.暂停菜单点官方「模组设置」-选中通用模组前置-点「打开设置」\n2.输入命令/setting_open\n3.使用模组快捷键(默认U),快捷键可在原版设置自定义"

    # 内容项顺序：介绍(顶) -> 开关/滑块 -> 重置按钮(底，使用框架内置 reset 控件)
    # 注意：AddSwitch 参数顺序为 (item_id, desc, default_value, locked, on_toggle, litle)，
    #       说明文字请放在 litle 小标题，不要放在 default_value 位置。
    CreateContentInst(main_card_id, "client", DISPLAY_CATEGORY_ID) \
        .AddText("intro", "介绍", INTRO_TEXT) \
        .AddSwitch(SWITCH_FOLD_MENU, "注册到界面上方的折叠菜单，默认true",
                    default_value=True, on_toggle=_OnDisplaySwitchToggle,
                    litle="注册到折叠菜单") \
        .AddSwitch(SWITCH_FADE_ANIM, "开启设置项与中间卡片的缓入/缓出动画，默认true",
                   default_value=True, on_toggle=_OnOptimizeSwitchToggle,
                   litle="缓入/缓出动画") \
        .AddSwitch(SWITCH_ENTER_ANIM, "开启切换子卡片时中间/右边面板的滑入进入动画，默认true\n关闭需重启设置界面生效",
                   default_value=True, on_toggle=_OnEnterAnimToggle,
                   litle="面板滑入动画") \
        .AddSwitch(SWITCH_PICKER_ARROW_PAGE, "开启后，物品选择弹窗里按键盘←/→可切换页码，默认true\n搜索框里有文字时不翻页（此时方向键用于移动光标）",
                   default_value=True, on_toggle=_OnPickerArrowPageToggle,
                   litle="左右方向键翻页") \
        .AddSwitch(SWITCH_PICKER_ARROW_SHIFT, "开启后必须按住 Shift 再按←/→才切换页码，默认false\n适合习惯用方向键在搜索框里移动光标的情况",
                   default_value=False, on_toggle=_OnPickerArrowShiftToggle,
                   litle="翻页需按住 Shift") \
        .AddSlider(SLIDER_MIDDLE_DELAY, "中间卡片每多少秒加载一张（0为每帧加载一张），默认0\n调整后立即生效",
                   min_val=0, max_val=100, value=0, steps=100, litle="中间卡片加载速度",
                   on_value_change=_OnMiddleDelayChange, slider_type="steps",
                   value_formatter=_DelayValueFormat) \
        .AddSlider(SLIDER_RIGHT_DELAY, "右侧设置项每多少秒加载一项（0为每帧加载一项），默认0\n调整后立即生效",
                   min_val=0, max_val=100, value=0, steps=100, litle="设置项加载速度",
                   on_value_change=_OnRightDelayChange, slider_type="steps",
                   value_formatter=_DelayValueFormat) \
        .AddResetButton("reset", on_click=_OnResetClick)

    # ---------------------------------------------------------------
    # 跨存档同步：功能未稳定，暂时不开放。
    # 重新启用时：把下面两行接回上面的链式调用，并把 SyncControl._ENABLED 置为 True。
    # .AddSwitch(SWITCH_SAVE_SYNC, "开启后本存档的设置与跨存档配置双向保持一致",
    #            default_value=False, on_toggle=_OnSaveSyncToggle,
    #            litle="本存档配置同步") \
    # .AddSwitch(SWITCH_NEW_SAVE_USE_CROSS, "进入新存档时自动套用跨存档配置，并自动打开上一项",
    #            default_value=False, on_toggle=_OnNewSaveUseCrossToggle,
    #            litle="新存档套用跨存档配置") \
    # ---------------------------------------------------------------

    # "调试"分类（客户端中间卡片，图标 debug）
    RegisterMiddleCard(main_card_id, "client", DEBUG_CATEGORY_ID, "调试",
                       icon="textures/ui/icon/debug")
    CreateContentInst(main_card_id, "client", DEBUG_CATEGORY_ID) \
        .AddText("debug_intro", "简介",
                 "调试相关设置，用于排查问题\n可能会影响性能，谨慎开启") \
        .AddSwitch(SWITCH_LOG_OUTPUT, "在客户端控制台输出调试日志，默认false",
                    default_value=False, on_toggle=_OnDebugSwitchToggle,
                    litle="日志输出") \
        .AddCollapsibleMenu(CLIENT_COPY_COUNT, "选择要复制到剪贴板的日志条数",
                            EXPORT_COUNT_MENU, litle="复制数量",
                            default_selected_id=_DEFAULT_EXPORT_COUNT) \
        .AddButton(CLIENT_COPY_BTN, "复制客户端调试日志到剪贴板",
                   "复制日志", on_click=_OnCopyClientLog)

    # ---------------------------------------------------------------
    # 跨存档同步：功能未稳定，暂时不开放。
    # 重新启用时：把下面两行接回上面的链式调用。
    # .AddButton(CLIENT_CLEAR_CROSS_BTN, "清空跨存档配置与时间戳，仅用于测试",
    #            "清空跨存档配置", on_click=_OnClearCrossClick) \
    # .AddButton(CLIENT_SYNC_INFO_BTN, "把当前同步状态输出到调试日志",
    #            "查看同步状态", on_click=_OnSyncInfoClick)
    # ---------------------------------------------------------------

    # "调试"分类（服务端中间卡片）：全局开关，默认锁定。
    # 由服务端下发的 OP 状态决定是否解锁：OP 可改，非 OP 查看时保持锁定。
    RegisterMiddleCard(main_card_id, "server", DEBUG_CATEGORY_ID, "调试",
                       icon="textures/ui/icon/debug")
    CreateContentInst(main_card_id, "server", DEBUG_CATEGORY_ID) \
        .AddText("debug_intro", "简介",
                 "服务端调试相关设置，全局生效，仅管理员(OP)可修改\n可能会影响性能，谨慎开启") \
        .AddSwitch(SWITCH_SERVER_LOG_OUTPUT, "全局服务端调试日志输出，非管理员锁定，默认false",
                    default_value=False, locked=True,
                    on_toggle=_OnServerLogSwitchToggle,
                    litle="日志输出") \
        .AddCollapsibleMenu(SERVER_COPY_COUNT, "选择要复制到剪贴板的日志条数",
                            EXPORT_COUNT_MENU, litle="复制数量",
                            default_selected_id=_DEFAULT_EXPORT_COUNT, locked=True) \
        .AddButton(SERVER_COPY_BTN, "复制服务端调试日志到剪贴板",
                   "复制日志", on_click=_OnCopyServerLog, locked=True) \
        .AddResetButton(SERVER_RESET_ID, on_click=_OnResetClick)

    # 注册"复制数量"折叠菜单（供上述两个下拉项共用）
    RegisterCollapsibleMenu(EXPORT_COUNT_MENU, "导出数量", _EXPORT_COUNT_OPTIONS)

    # 初始化客户端日志开关为已存储的值（开关关闭时吞掉本框架的调试日志）
    dlog.set_client_enabled(
        GetSettingValue(main_card_id, "client", DEBUG_CATEGORY_ID, SWITCH_LOG_OUTPUT,
                        default=False)
    )

    # ══════════════════════════════════════════════════════════════════
    # 开发者选项（测试内容集中区）
    #   - 以后新增的测试卡片 / 测试弹窗 / 演示内容都往这里加，照下面物品选择、
    #     组合开关两个演示的写法（RegisterMiddleCard + CreateContentInst）追加即可。
    #   - 顶部提示用 AddText(..., color=(r,g,b)) 上琥珀色，不需要额外内容项类型。
    #   - 发布正式版时：把本块（从下面的 RegisterMiddleCard 到 return ok 之前）
    #     整块注释掉，该分页就不再注册；其余分页与已存配置不受影响。
    # ══════════════════════════════════════════════════════════════════
    RegisterMiddleCard(main_card_id, "client", DEV_CATEGORY_ID, "开发者选项",
                       icon="textures/ui/icon/advanced-icon")

    # 物品选择弹窗演示：数据集不写死，运行时由服务端下发的「全部已加载物品」
    # （原版 + 各模组自定义物品）填充，见 Client.OnAllItems -> RefreshDemoItemPicker。
    # 这里先注册空数据集占位，数据到达前后弹窗都能正常打开。
    RegisterItemPicker(DEMO_PICKER_ID, "选择物品", items=[])

    # 组合开关演示：混合三种行控件 + 锁定行，弹窗底部按钮可动态加/删行。
    _RegisterDevToggleDemo()

    CreateContentInst(main_card_id, "client", DEV_CATEGORY_ID) \
        .AddText(DEV_NOTICE_ID, DEV_NOTICE_TITLE, DEV_NOTICE_TEXT,
                 color=DEV_NOTICE_COLOR) \
        .AddItemPicker(DEMO_ITEM_ID, "演示：点右侧箭头从列表中选择一个物品，用于测试物品选择弹窗",
                       DEMO_PICKER_ID, litle="物品选择",
                       on_select=_OnDemoItemPicked) \
        .AddButton(DEV_TOGGLE_OPEN_ID,
                   "演示：弹窗里可动态加行 / 删行 / 打印状态，用于测试组合开关与 RefreshCardToggle",
                   "打开组合开关演示", on_click=_OnDevToggleOpen)

    return ok


if __name__ == "__main__":
    dlog.client_print("==== setting.py loaded, RegisterSettingsConfig ready ====")
