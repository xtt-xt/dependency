# -*- coding: utf-8 -*-
"""
CardRegistry API 组件工厂
========================
统一导入入口，只需 from CardRegistryApi import * 即可获得全部公开 API。

用法:
    from CardRegistryApi import (
        RegisterMainCard, RegisterMiddleCard, CreateContentInst,
        SettingsUIOpenEvent, OpenSettings, RegisterContentBuilder,
        ...
    )
    
    或直接:
    from CardRegistryApi import *
"""

# ────────────────── CardRegistry（卡片注册、内容项、事件常量） ──────────────────

from CardRegistry import (
    # 主卡片
    RegisterMainCard,
    GetMainCard,
    GetAllMainCardIds,
    UnregisterMainCard,
    # 中间卡片
    RegisterMiddleCard,
    GetMiddleCardBindings,
    UnregisterMiddleCard,
    ClearMiddleCardBindings,
    # 整体重置
    ClearAllCards,
    # 右侧内容项
    CreateContentInst,
    GetContentItems,
    GetContentItem,
    ClearContentItems,
    RegisterContentItemType,
    GetContentItemFactory,
    RegisterContentListener,
    UnregisterContentListener,
    # 回调机制
    SetCardChangedCallback,
    # 辅助函数
    NormalizeMiddleCardId,
    GetAllContentGroups,
    # 事件常量
    SettingsUIOpenEvent,
    SettingsUICloseEvent,
    # 弹窗注册表
    RegisterPopUp,
    UnregisterPopUp,
    GetPopUp,
    GetAllPopUpIds,
    # 折叠菜单注册表
    RegisterCollapsibleMenu,
    AddCollapsibleMenuCard,
    GetCollapsibleMenu,
    GetCollapsibleMenuCards,
    # 组合开关注册表
    RegisterCardToggle,
    AddCardToggleOption,
    AddCardToggleButton,
    GetCardToggle,
    GetCardToggleOptions,
    GetCardToggleOptionIds,
    # 弹窗事件常量
    PopUpOpenEvent,
    PopUpCloseEvent,
    # 跳转标准事件常量 + 跳转拦截 API
    SettingsNavigateEvent,
    RegNavigateBlockCallback,
    UnregNavigateBlockCallback,
    IsNavigateBlocked,
)

from DebugLog import dlog

# ────────────────── Client（UI 构建器注册、导航 API） ──────────────────

from Client import (
    RegisterContentBuilder,
    _g_ClientSystem,
)

# ────────────────── 设置项状态系统（level_data 持久化） ──────────────────

from SettingState import (
    MakeSettingKey,
    GetSettingValue,
    GetSettingLocked,
    SetSettingValue,
    ResetSettingValue,
    ResetAllSettings,
    ResetGroupSettings,
    SaveGroupSettings,
    SaveAllSettings,
    # 组合开关状态
    GetCardToggleState,
    SetCardToggleState,
    ResetCardToggleStates,
)

# ────────────────── Toast 提示系统 ──────────────────

from Toast import (
    ShowToast,
    ToastTop,
    ToastTopRight,
    ToastUnder,
)


def OpenSettings(main_card_id=None, sub_key=None, middle_card_id=None):
    """
    打开设置 UI，可选导航到指定卡片。
    便捷封装，等效于 _g_ClientSystem.OpenSettings(...)。

    :param main_card_id:  主卡片 ID（如 "basic_settings"），传 None 则不导航
    :param sub_key:       子卡片 key，可选 "client" 或 "server"
    :param middle_card_id: 中间卡片 ID（如 "client_opt_a"）
    """
    if _g_ClientSystem:
        _g_ClientSystem.OpenSettings(main_card_id, sub_key, middle_card_id)
    else:
        dlog.client_print("==== CardRegistryApi.OpenSettings: ClientSystem not ready ====")

def SetLocked(item_id_or_path, locked):
    """
    统一设置指定内容项（按钮/开关/edit_box）的锁定状态。
    便捷封装，等效于 _g_ClientSystem.SetLocked(...)。
    自动根据传入参数判断类型：
      - 若是右侧面板内容项 ID（按钮/开关），执行已有锁定逻辑
      - 若是 edit_box 完整控件路径，显示/隐藏 lock 子控件并禁用/启用输入

    :param item_id_or_path: 内容项 ID 或 edit_box 控件完整路径
    :param locked:   True 锁定，False 解锁
    """
    if _g_ClientSystem:
        _g_ClientSystem.SetLocked(item_id_or_path, locked)
    else:
        dlog.client_print("==== CardRegistryApi.SetLocked: ClientSystem not ready ====")


def OpenCardToggle(toggle_id):
    """
    打开组合开关弹窗。供普通按钮 on_click / 外部模组调用。
    数据集须先用 RegisterCardToggle/AddCardToggleOption 注册。

    :param toggle_id: 组合开关唯一标识
    :returns:         True 打开成功；False 未注册或 ClientSystem 未就绪
    """
    if _g_ClientSystem:
        return bool(_g_ClientSystem.OpenCardToggle(toggle_id))
    dlog.client_print("==== CardRegistryApi.OpenCardToggle: ClientSystem not ready ====")
    return False


def CloseCardToggle():
    """关闭当前组合开关弹窗（若打开）。"""
    if _g_ClientSystem:
        _g_ClientSystem.CloseCardToggle()


def ShowPopUp(popup_id, force_scroll=None):
    """
    打开指定 ID 的弹窗（须先 RegisterPopUp 注册）。
    便捷封装，等效于 _g_ClientSystem.ShowPopUp(...)。

    :param popup_id:    弹窗唯一标识符
    :param force_scroll: True 强制使用滚动版；False 强制普通版；
                         None 自动根据内容长度决定（默认）
    :returns:           True 打开成功；False 弹窗未注册或 ClientSystem 未就绪
    """
    if _g_ClientSystem:
        return _g_ClientSystem.ShowPopUp(popup_id, force_scroll)
    dlog.client_print("==== CardRegistryApi.ShowPopUp: ClientSystem not ready ====")
    return False


def ClosePopUp():
    """关闭当前弹窗，便捷封装，等效于 _g_ClientSystem.ClosePopUp()。"""
    if _g_ClientSystem:
        _g_ClientSystem.ClosePopUp()
    else:
        dlog.client_print("==== CardRegistryApi.ClosePopUp: ClientSystem not ready ====")


def ShowCollapsibleMenu(menu_id, item):
    """
    打开指定菜单的折叠菜单弹窗。
    便捷封装，等效于 _g_ClientSystem.ShowCollapsibleMenu(...)。

    :param menu_id: 折叠菜单 ID（须先 RegisterCollapsibleMenu 注册）
    :param item:    关联的 CollapsibleMenuContentItem（用于读取/更新选中状态）
    :returns:       True 打开成功；False 菜单未注册或 ClientSystem 未就绪
    """
    if _g_ClientSystem:
        return _g_ClientSystem.ShowCollapsibleMenu(menu_id, item)
    dlog.client_print("==== CardRegistryApi.ShowCollapsibleMenu: ClientSystem not ready ====")
    return False


def CloseCollapsibleMenu():
    """关闭当前折叠菜单弹窗，便捷封装，等效于 _g_ClientSystem.CloseCollapsibleMenu()。"""
    if _g_ClientSystem:
        _g_ClientSystem.CloseCollapsibleMenu()
    else:
        dlog.client_print("==== CardRegistryApi.CloseCollapsibleMenu: ClientSystem not ready ====")
