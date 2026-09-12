# -*- coding: utf-8 -*-
"""
设置项状态系统
==============
基于官方 ConfigCompClient（本地存储）持久化开关/输入框内容。
存储 key 自动生成：主卡片id.子key.中间卡片id.item_id

官方接口（API文档/1-ModAPI/接口/通用/本地存储）：
    comp = clientApi.GetEngineCompFactory().CreateConfigClient(clientApi.GetLevelId())
    comp.GetConfigData(configName, isGlobal)  # 返回 dict
    comp.SetConfigData(configName, value, isGlobal)  # 返回 bool
"""
try:
    import mod.client.extraClientApi as clientApi
except ImportError:
    clientApi = None  # 防御：SDK 环境缺失时降级为内存字典

from CardRegistry import NormalizeMiddleCardId, GetContentItem, GetAllContentGroups, GetContentItems
from DebugLog import dlog

# 配置文件名：只能包含字母、数字和下划线，加 addon 命名空间前缀避免冲突
_CONFIG_NAME = "Script_NeteaseMod9sPMlz0K_setting_state"
_IS_GLOBAL = False  # False = 存档配置（重进世界保留，跨存档不共享）

# 内存缓存（启动时由 LoadSettingData 从本地配置加载；SDK 缺失时作为降级存储）
_memStore = {}

_uiChangedCallback = None  # API 修改后通知 UI 刷新的回调

_comp = None  # ConfigClient 组件（懒加载）


def _GetComp():
    """懒加载 ConfigClient 组件。"""
    global _comp
    if _comp is None and clientApi is not None:
        try:
            _comp = clientApi.GetEngineCompFactory().CreateConfigClient(
                clientApi.GetLevelId())
        except Exception:
            _comp = None
    return _comp


def MakeSettingKey(main_card_id, key, middle_card_id, item_id):
    """生成存储 key：主卡片id.子key.中间卡片id.item_id"""
    return "%s.%s.%s.%s" % (main_card_id, key,
                            NormalizeMiddleCardId(middle_card_id), item_id)


def LoadSettingData():
    """启动时从本地配置加载全部存储数据（UI 初始化完成后调用一次）。"""
    global _memStore
    comp = _GetComp()
    if comp is not None:
        try:
            data = comp.GetConfigData(_CONFIG_NAME, _IS_GLOBAL)
            if isinstance(data, dict):
                _memStore = dict(data)
                dlog.client_print("==== SettingState loaded %d entries ====" % len(_memStore))
        except Exception as e:
            dlog.client_print("==== SettingState load error: %s ====" % str(e))
    return _memStore


def _Read(key):
    """从内存缓存读取。"""
    return _memStore.get(key)


def _Write(key, value):
    """写内存缓存并持久化到本地配置（整包写入）。"""
    _memStore[key] = value
    comp = _GetComp()
    if comp is not None:
        try:
            comp.SetConfigData(_CONFIG_NAME, dict(_memStore), _IS_GLOBAL)
        except Exception as e:
            dlog.client_print("==== SettingState write error: %s ====" % str(e))
    return True


def _Coerce(item, value):
    """按内容项类型归一化读出的值（防御外部写入错误类型）。"""
    if item is None:
        return value
    if item.type_name == "switch":
        if isinstance(value, bool):
            return value
        return str(value).lower() in ("1", "true", "yes", "on")
    if item.type_name == "edit_box":
        return str(value) if value is not None else ""
    if item.type_name == "slider":
        try:
            return float(value)
        except Exception:
            return value
    if item.type_name == "collapsible_menu":
        return str(value) if value is not None else ""
    return value


def _FindItem(main_card_id, key, middle_card_id, item_id):
    return GetContentItem(main_card_id, key,
                          NormalizeMiddleCardId(middle_card_id), item_id)


# ────────────── 公共 API ──────────────

def GetSettingValue(main_card_id, key, middle_card_id, item_id, default=None):
    """
    读取设置值；无存储值时回退 item.default_value（switch=False / edit_box=""）。
    兼容默认参数：外部传 default 时优先使用该默认值。
    """
    if default is None:
        item = _FindItem(main_card_id, key, middle_card_id, item_id)
        if item is not None:
            default = getattr(item, "default_value", None)
    stored = _Read(MakeSettingKey(main_card_id, key, middle_card_id, item_id))
    if stored is None:
        return default
    return _Coerce(_FindItem(main_card_id, key, middle_card_id, item_id), stored)


def GetSettingLocked(main_card_id, key, middle_card_id, item_id, default=False):
    """
    读取持久化的锁定状态；无存储值时回退 item.locked（或传入的 default）。
    供 Build* 内容项时恢复动态锁定状态。
    """
    stored = _Read(MakeSettingKey(main_card_id, key, middle_card_id, item_id) + "::locked")
    if stored is None:
        return default
    if isinstance(stored, bool):
        return stored
    return str(stored).lower() in ("1", "true", "yes", "on")


def ClearSettingLocked(main_card_id, key, middle_card_id, item_id):
    """清除指定设置项持久化的锁定状态（::locked 键）。

    用于服务端按玩家 OP 实时决定的鉴权项：避免 OP 曾解锁被保存成过期
    解锁态后，下次（哪怕是其他权限、包括非 OP）打开时误用旧状态而穿透鉴权。
    """
    mid = NormalizeMiddleCardId(middle_card_id)
    locked_key = MakeSettingKey(main_card_id, key, mid, item_id) + "::locked"
    if locked_key in _memStore:
        del _memStore[locked_key]
    comp = _GetComp()
    if comp is not None:
        try:
            comp.SetConfigData(_CONFIG_NAME, dict(_memStore), _IS_GLOBAL)
        except Exception as e:
            dlog.client_print("==== SettingState clear lock error: %s ====" % str(e))


def SetSettingValue(main_card_id, key, middle_card_id, item_id, value):
    """修改设置值：写存储 + 通知 UI 刷新（applier 幂等，UI 无变化时自动跳过）。"""
    _Write(MakeSettingKey(main_card_id, key, middle_card_id, item_id), value)
    if _uiChangedCallback:
        try:
            _uiChangedCallback(main_card_id, key, middle_card_id, item_id, value)
        except Exception as e:
            dlog.client_print("==== SettingState notify error: %s ====" % str(e))
    return True


def ResetSettingValue(main_card_id, key, middle_card_id, item_id):
    """重置为默认值（item.default_value），并同步刷新 UI。"""
    item = _FindItem(main_card_id, key, middle_card_id, item_id)
    default = ""
    if item is not None:
        default = getattr(item, "default_value", "")
    return SetSettingValue(main_card_id, key, middle_card_id, item_id, default)


def ResetAllSettings():
    """批量重置：遍历注册表所有设置项为默认值，并清除持久化锁定状态。"""
    count = 0
    for group in GetAllContentGroups():
        main_card_id, key, middle_card_id = group
        count += ResetGroupSettings(main_card_id, key, middle_card_id)
    return count


def ResetGroupSettings(main_card_id, key, middle_card_id):
    """重置指定分组（主卡片+子卡片+中间卡片）下所有设置项为默认值，并清除持久化锁定状态。"""
    mid = NormalizeMiddleCardId(middle_card_id)
    count = 0
    for item in GetContentItems(main_card_id, key, mid):
        if item.type_name in ("switch", "edit_box", "slider", "collapsible_menu"):
            ResetSettingValue(main_card_id, key, mid, item.item_id)
            # 同步 item 运行时 value 为默认值（供后续 SaveGroupSettings 不覆盖重置结果）
            default = getattr(item, "default_value", "")
            if hasattr(item, "SetValue"):
                item.SetValue(default)
            else:
                item.value = default
            count += 1
        if item.type_name in ("switch", "edit_box", "slider", "button", "reset", "collapsible_menu"):
            # 清除持久化锁定状态，恢复注册默认（item 构造时的 locked）
            _memStore.pop(MakeSettingKey(main_card_id, key, mid, item.item_id) + "::locked", None)
            default_locked = getattr(item, "_default_locked", False)
            if hasattr(item, "SetLocked"):
                item.SetLocked(default_locked)
            else:
                item.locked = default_locked
            count += 1
    comp = _GetComp()
    if comp is not None:
        try:
            comp.SetConfigData(_CONFIG_NAME, dict(_memStore), _IS_GLOBAL)
        except Exception as e:
            dlog.client_print("==== SettingState reset group error: %s ====" % str(e))
    return count


def SaveGroupSettings(main_card_id, key, middle_card_id):
    """
    批量保存指定分组（主卡片+子卡片+中间卡片）下所有 switch/edit_box 的
    运行时 value 到本地存储（整包写一次，不触发逐项 UI 刷新回调）。

    :returns: 实际写入的设置项数量
    """
    mid = NormalizeMiddleCardId(middle_card_id)
    changes = {}
    for item in GetContentItems(main_card_id, key, mid):
        if item.type_name in ("switch", "edit_box", "slider", "collapsible_menu"):
            # 仅保存已从存储加载/UI 初始化过的 item，避免用 default_value 覆盖已有存储
            if not getattr(item, "_loaded", False):
                continue
            base_key = MakeSettingKey(main_card_id, key, mid, item.item_id)
            value = getattr(item, "value", getattr(item, "default_value", None))
            changes[base_key] = value
            # 一并保存锁定状态（动态锁定恢复用）
            changes[base_key + "::locked"] = bool(getattr(item, "locked", False))
        elif item.type_name in ("button", "reset"):
            # 按钮/重置项无值概念，仅保存锁定状态
            if not getattr(item, "_loaded", False):
                continue
            base_key = MakeSettingKey(main_card_id, key, mid, item.item_id)
            changes[base_key + "::locked"] = bool(getattr(item, "locked", False))
    if not changes:
        return 0
    _memStore.update(changes)
    comp = _GetComp()
    if comp is not None:
        try:
            comp.SetConfigData(_CONFIG_NAME, dict(_memStore), _IS_GLOBAL)
        except Exception as e:
            dlog.client_print("==== SettingState save group error: %s ====" % str(e))
    return len(changes)


def SaveAllSettings():
    """
    批量保存注册表中所有 switch/edit_box 的运行时 value 到本地存储。
    供"保存全部设置"场景使用（整包写一次，不触发逐项 UI 刷新回调）。

    :returns: 实际写入的设置项数量
    """
    count = 0
    for group in GetAllContentGroups():
        main_card_id, key, middle_card_id = group
        count += SaveGroupSettings(main_card_id, key, middle_card_id)
    return count


def SetSettingChangedCallback(cb):
    """
    注册设置值变更回调（供 Client.py 注入 UI 刷新函数）。
    签名: cb(main_card_id, key, middle_card_id, item_id, value)
    """
    global _uiChangedCallback
    _uiChangedCallback = cb


# ────────────────── CardToggle（组合开关）状态持久化 ──────────────────
# 独立于内容项/分组的存储，按 toggle_id 存一份 {option_id: bool} 字典。
# key = "cardtoggle.<toggle_id>"。

def _CardToggleKey(toggle_id):
    return "cardtoggle.%s" % toggle_id


def GetCardToggleState(toggle_id, option_id, default_on=False):
    """读取某选项状态；无存储或未记录时返回 default_on。

    开关选项返回 bool，编辑框选项返回文本字符串（原样存储，不做类型转换）。
    """
    states = _Read(_CardToggleKey(toggle_id))
    if isinstance(states, dict):
        val = states.get(option_id)
        if val is not None:
            return val
    return default_on


def SetCardToggleState(toggle_id, option_id, state):
    """写入某选项状态并持久化整个 toggle 状态字典。

    开关选项传 bool，编辑框选项传文本字符串（原样存储）。
    """
    key = _CardToggleKey(toggle_id)
    states = _Read(key)
    if not isinstance(states, dict):
        states = {}
    states[option_id] = state
    return _Write(key, states)


def ResetCardToggleStates(toggle_id):
    """清除该 toggle 的全部持久化状态（回退各选项 default_on）。"""
    key = _CardToggleKey(toggle_id)
    if key in _memStore:
        del _memStore[key]
    comp = _GetComp()
    if comp is not None:
        try:
            comp.SetConfigData(_CONFIG_NAME, dict(_memStore), _IS_GLOBAL)
        except Exception as e:
            dlog.client_print("==== SettingState reset cardtoggle error: %s ====" % str(e))
    return True
