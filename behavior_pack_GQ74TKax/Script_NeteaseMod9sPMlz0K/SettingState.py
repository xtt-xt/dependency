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

import time

from CardRegistry import NormalizeMiddleCardId, GetContentItem, GetAllContentGroups, GetContentItems
from DebugLog import dlog

# 配置文件名：只能包含字母、数字和下划线，加 addon 命名空间前缀避免冲突
_CONFIG_NAME = "Script_NeteaseMod9sPMlz0K_setting_state"
_IS_GLOBAL = True   # 跨存档配置（存在应用内，所有存档共用；清除应用数据即丢）

# 内存缓存（启动时由 LoadSettingData 从本地配置加载；SDK 缺失时作为降级存储）
# 注意：同一个文件可能被两条导入路径加载成两个模块对象
# （扁平 `SettingState` 与带包名的 `Script_NeteaseModXXX.SettingState`）。
# 若各自持有一份 _memStore，"整包写入"就会把对方存的数据抹掉，
# 因此把可变状态统一挂到共享槽位，两条路径看到同一份数据。
def _SharedState():
    try:
        import __builtin__ as _b          # Python 2
    except ImportError:
        import builtins as _b             # Python 3
    key = "_XTT_DEP_SETTING_STATE"
    st = getattr(_b, key, None)
    if st is None:
        st = {
            "memStore": {},         # 内存缓存（整包写入的唯一数据源）
            "comp": None,           # ConfigClient 组件
            "external": {},         # 外部键 item_id -> (provider, persist)
            "afterPersist": None,   # 写入成功回调
            "uiChanged": None,      # 设置值变更回调
        }
        setattr(_b, key, st)
    return st


_SHARED = _SharedState()

_memStore = _SHARED["memStore"]

_uiChangedCallback = None  # API 修改后通知 UI 刷新的回调（实际存在 _SHARED["uiChanged"]）

_comp = None  # ConfigClient 组件（懒加载，实际存在 _SHARED["comp"]）


def _GetComp(force=False):
    """懒加载 ConfigClient 组件（跨存档配置）；force=True 可丢弃缓存重取。

    组件缓存在共享槽位里，保证不同导入路径下的模块对象用同一个组件。
    """
    if force:
        _SHARED["comp"] = None
    if _SHARED.get("comp") is None and clientApi is not None:
        try:
            _SHARED["comp"] = clientApi.GetEngineCompFactory().CreateConfigClient(
                clientApi.GetLevelId())
        except Exception:
            _SHARED["comp"] = None
    return _SHARED.get("comp")


def _Persist(tag):
    """整包写入跨存档配置，并立即回读校验，返回是否真正写成功。

    仅在写入失败或回读不一致时打日志（成功路径不打，避免高频刷屏）。
    """
    comp = _GetComp()
    if comp is None:
        dlog.client_print("==== SettingState %s: comp is None ====" % tag)
        return False
    try:
        # 读-改-写：先取磁盘上的最新副本，再合并本实例的改动后写回。
        # 这样任何"过期实例"（例如另一条导入路径下的模块对象、其它模组）
        # 都只能新增/覆盖它自己知道的键，不会把别人存的数据整体清空。
        base = comp.GetConfigData(_CONFIG_NAME, _IS_GLOBAL)
        base = dict(base) if isinstance(base, dict) else {}
        base.update(_memStore)
        ok = comp.SetConfigData(_CONFIG_NAME, base, _IS_GLOBAL)
        back = comp.GetConfigData(_CONFIG_NAME, _IS_GLOBAL)
        if isinstance(back, dict):
            # 回填内存，保证与磁盘一致
            _memStore.clear()
            _memStore.update(back)
        full = bool(ok) and isinstance(back, dict) and len(back) == len(base)
        if not full:
            dlog.client_print(
                "==== SettingState %s: write=%s readback=%s want=%d ====" % (
                    tag, ok,
                    (len(back) if isinstance(back, dict) else back), len(base)))
        elif _SHARED.get("afterPersist") is not None:
            try:
                _SHARED["afterPersist"](tag)
            except Exception as e2:
                dlog.client_print(
                    "==== SettingState persist callback error: %s ====" % str(e2))
        return full
    except Exception as e:
        dlog.client_print("==== SettingState %s error: %s ====" % (tag, str(e)))
        return False


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
            dlog.client_print("==== SettingState load raw: %r ====" % (data,))
            if isinstance(data, dict):
                # 就地更新（不能重绑，否则会脱离共享槽位）
                _memStore.clear()
                _memStore.update(data)
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
    _Persist("write")
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
    provider = _ExternalProvider(item_id)
    if provider is not None:
        try:
            val = provider()
            if val is not None:
                return _Coerce(_FindItem(main_card_id, key,
                                         NormalizeMiddleCardId(middle_card_id), item_id),
                               val)
        except Exception as e:
            dlog.client_print("==== SettingState external provider error: %s ====" % str(e))
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
    _Persist("clear lock")


def SetSettingValue(main_card_id, key, middle_card_id, item_id, value):
    """修改设置值：写存储 + 通知 UI 刷新（applier 幂等，UI 无变化时自动跳过）。"""
    _Write(MakeSettingKey(main_card_id, key, middle_card_id, item_id), value)
    _cb = _SHARED.get("uiChanged")
    if _cb:
        try:
            _cb(main_card_id, key, middle_card_id, item_id, value)
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
    _Persist("reset group")
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
        # 外部键（值由服务端下发的本存档配置提供）不写进跨存档配置
        if _IsExternal(item.item_id):
            continue
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
    if not _Persist("save group"):
        return 0
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
    _SHARED["uiChanged"] = cb


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
    _Persist("reset cardtoggle")
    return True


# ────────────────── 跨存档同步支撑 ──────────────────
# 外部键：值由外部（服务端下发的本存档配置）提供，不写进跨存档配置。
# item_id -> (provider, persist)
_externalProviders = _SHARED["external"]
# 保留键前缀：不参与同步的内部数据（如时间戳）
_RESERVED_PREFIX = "__"
_CROSS_STAMP_KEY = "__cross_stamp__"

# 每次成功写入跨存档配置后的回调（供同步模块防抖上报，存在 _SHARED["afterPersist"]）


def SetPersistCallback(cb):
    """注册"写入跨存档配置成功"回调，签名 cb(tag)。"""
    _SHARED["afterPersist"] = cb
    return True


def RegisterExternalKey(item_id, provider=None, persist=False):
    """
    注册外部键。

    :param item_id:  内容项 id
    :param provider: 取值函数 provider() -> value（返回 None 表示无值，走默认）
    :param persist:  True 表示该键仍写入跨存档配置
    """
    if not item_id:
        return False
    _externalProviders[item_id] = (provider, bool(persist))
    dlog.client_print("==== SettingState external key: %s persist=%s ====" % (
        item_id, persist))
    return True


def _ExternalProvider(item_id):
    entry = _externalProviders.get(item_id)
    return entry[0] if entry else None


def _IsExternal(item_id, persistOnly=True):
    entry = _externalProviders.get(item_id)
    if not entry:
        return False
    return (not entry[1]) if persistOnly else True


def _IsReservedKey(key):
    return str(key).startswith(_RESERVED_PREFIX)


def _FilterExternal(data):
    """剔除不写入跨存档配置的外部键与保留键。"""
    skip = [k for k in _externalProviders if not _externalProviders[k][1]]
    out = {}
    for k in (data or {}):
        if _IsReservedKey(k):
            continue
        hit = False
        for sid in skip:
            if k == sid or str(k).endswith("." + sid) or str(k).endswith("." + sid + "::locked"):
                hit = True
                break
        if not hit:
            out[k] = data[k]
    return out


def GetAllData():
    """导出跨存档配置（剔除外部键与保留键），用于同步上报。"""
    return _FilterExternal(_memStore)


def ApplyAllData(data, persist=True):
    """整包应用（用跨存档配置覆盖本存档 / 用本存档配置更新跨存档）。"""
    if not isinstance(data, dict):
        return False
    count = 0
    for k in data:
        if _IsReservedKey(k):
            continue
        _memStore[k] = data[k]
        count += 1
    if persist:
        PersistNow("apply all")
    dlog.client_print("==== SettingState ApplyAllData: %d keys ====" % count)
    return True


def GetCrossStamp():
    """跨存档配置的写入时间戳（用于判断是否需要同步）。"""
    try:
        return int(_memStore.get(_CROSS_STAMP_KEY, 0) or 0)
    except Exception:
        return 0


def SetCrossStamp(ts=None):
    _memStore[_CROSS_STAMP_KEY] = int(ts if ts is not None else time.time())
    return True


def PersistNow(tag="manual"):
    """立即把当前内存缓存整包写入跨存档配置。"""
    return _Persist(tag)


def ClearCrossData():
    """清空跨存档配置与时间戳（调试用）。"""
    _memStore.clear()
    PersistNow("clear cross")
    dlog.client_print("==== SettingState ClearCrossData ====")
    return True
