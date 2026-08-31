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
    ResetGroupSettings,
    GetSettingValue,
)
from DebugLog import dlog

# 主卡片唯一标识（全局唯一，不可重复）
_MAIN_CARD_ID = "settings_config"

# "显示"分类下的开关项 id（供 PauseScreenProxy / FoldMenuProxy 读取）
DISPLAY_CATEGORY_ID = "display"
SWITCH_FOLD_MENU = "register_fold_menu"    # 注册到折叠菜单
SWITCH_PAUSE_MENU = "register_pause_menu"  # 注册到暂停菜单


def _OnDisplaySwitchToggle(screenNode, item_id, state):
    """开关值改变时打印提示。实际生效由对应菜单代理在打开界面时读取开关值决定。"""
    dlog.client_print("==== display switch %s => %s ====" % (item_id, state))


def _OnResetClick(screenNode, item_id):
    """重置当前分类下所有设置项为默认值，并刷新右侧面板。"""
    group = getattr(screenNode, "mCurrentRightGroup", None)
    if not group or len(group) < 3:
        return
    main_card_id, sub_key, middle_card_id = group
    ResetGroupSettings(main_card_id, sub_key, middle_card_id)
    screenNode.RebuildRightContent(main_card_id, sub_key, middle_card_id)
    dlog.client_print("==== reset group %s/%s/%s ====" % (main_card_id, sub_key, middle_card_id))


# "调试"分类下的开关项 id
DEBUG_CATEGORY_ID = "debug"
SWITCH_LOG_OUTPUT = "log_output"    # 客户端日志输出
SWITCH_SERVER_LOG_OUTPUT = "server_log_output"  # 服务端全局日志输出

# "显示"分类下的缓入/缓出动画开关项 id
SWITCH_FADE_ANIM = "enable_fade_anim"  # 设置项与中间卡片的缓入/缓出动画

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
                      "版本：0.0.1  作者：星天xt")

# 日志导出（复制）相关项 id
CLIENT_COPY_COUNT = "copy_client_count"  # 客户端导出数量（折叠菜单）
CLIENT_COPY_BTN = "copy_client_log"      # 客户端复制按钮
SERVER_COPY_COUNT = "copy_server_count"  # 服务端导出数量（折叠菜单）
SERVER_COPY_BTN = "copy_server_log"      # 服务端复制按钮

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


def _OnInfoButtonClick(screenNode, item_id):
    """简介页自定义按钮：打开自定义普通（不滚动）弹窗。"""
    from CardRegistryApi import ShowPopUp
    ShowPopUp(INFO_POPUP_ID, force_scroll=False)


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
    INTRO_TEXT = "这里可以设置设置的入口位置和部分其他内容，如果你把入口设置项全部关闭，你可以使用以下方法进入\n1.点击主菜单模组按钮-选中通用模组前置-打开设置按钮\n2.输入命令/setting_open\n3.使用模组快捷键(默认U),快捷键可在原版设置自定义"

    # 内容项顺序：介绍(顶) -> 三个开关 -> 重置按钮(底，使用框架内置 reset 控件)
    # 注意：AddSwitch 参数顺序为 (item_id, desc, default_value, locked, on_toggle, litle)，
    #       说明文字请放在 litle 小标题，不要放在 default_value 位置。
    CreateContentInst(main_card_id, "client", DISPLAY_CATEGORY_ID) \
        .AddText("intro", "介绍", INTRO_TEXT) \
        .AddSwitch(SWITCH_FOLD_MENU, "注册到界面上方的折叠菜单，默认true",
                    default_value=True, on_toggle=_OnDisplaySwitchToggle,
                    litle="注册到折叠菜单") \
        .AddSwitch(SWITCH_PAUSE_MENU, "注册到暂停界面，默认true",
                    default_value=True, on_toggle=_OnDisplaySwitchToggle,
                    litle="注册到暂停菜单") \
        .AddSwitch(SWITCH_FADE_ANIM, "开启设置项与中间卡片的缓入/缓出动画，默认true",
                   default_value=True, on_toggle=_OnOptimizeSwitchToggle,
                   litle="缓入/缓出动画") \
        .AddResetButton("reset", on_click=_OnResetClick)

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
                   "复制日志", on_click=_OnCopyServerLog, locked=True)

    # 注册"复制数量"折叠菜单（供上述两个下拉项共用）
    RegisterCollapsibleMenu(EXPORT_COUNT_MENU, "导出数量", _EXPORT_COUNT_OPTIONS)

    # 初始化客户端日志开关为已存储的值（开关关闭时吞掉本框架的调试日志）
    dlog.set_client_enabled(
        GetSettingValue(main_card_id, "client", DEBUG_CATEGORY_ID, SWITCH_LOG_OUTPUT,
                        default=False)
    )
    return ok


if __name__ == "__main__":
    dlog.client_print("==== setting.py loaded, RegisterSettingsConfig ready ====")