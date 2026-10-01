# -*- coding: utf-8 -*-
"""
跨存档同步 · 客户端控制器
==========================
两个开关（注册在「设置配置 > 客户端 > 显示」页）：
    save_config_sync   本存档配置同步   ——权威值在存档内（B 层），每个存档独立
    new_save_use_cross 新存档套用跨存档配置 ——权威值在跨存档配置（C 层）

进世界流程：
    RequestStore() 向服务端要「本存档配置 + 存档标签」，OnSyncStore() 里决策：
      没有标签（该存档第一次跑）：
          开关2 开 -> 自动打开开关1 + 用跨存档配置覆盖本存档 + 打标签(applied=True)
          开关2 关 -> 只打标签(applied=False)
      已有标签：
          开关1 开 -> 拉取跨存档配置覆盖本存档
          开关1 关 -> 不动跨存档配置为空/默认 -> 弹窗提示开关1 的方向选择弹窗：未选择直接关闭 -> 开关1 自动回关
"""

import time

import mod.client.extraClientApi as clientApi

from DebugLog import dlog
from CardRegistry import RegisterPopUp
from StoreEvents import REQ_STORE, SAVE_STORE, SET_TAG, SYNC_STORE

import SettingState as SS

# ────────────────── 注册位置 / 唯一 ID ──────────────────
MAIN_CARD = "settings_config"
SUB_KEY = "client"
MID_DISPLAY = "display"
MID_DEBUG = "debug"

ITEM_SAVE_SYNC = "save_config_sync"
ITEM_NEW_SAVE_USE_CROSS = "new_save_use_cross"

POPUP_SYNC_CHOICE = "sync_choice"
POPUP_CROSS_EMPTY = "cross_empty"
POPUP_CLEAR_CROSS = "clear_cross_confirm"
POPUP_ID_INFO = "cross_sync_info"

# ---------------------------------------------------------------
# 总开关：跨存档同步功能未稳定，暂时关闭。
# 置 True 即恢复全部行为（同时要取消 setting.py 里四个新项的注释）。
# ---------------------------------------------------------------
_ENABLED = False

_system = None

# 跨存档配置的本地时间戳缓存（存在 SettingState 的保留键里）
_remote = {
    "loaded": False,
    "save_sync": False,
    "store_ts": 0,
    "tag": {"handled": False, "applied": False, "app_stamp": 0},
    "cross_stamp": 0,
}

_awaitingChoice = False   # 方向选择弹窗是否在等待用户选择
_pushTimer = None         # 防抖上报计时器
_retryTimer = None        # 进世界后的重试计时器
_retryLeft = 3
_lastSyncedSaveSync = None


# ────────────────── 初始化 ──────────────────

def Init(system):
    """由 MyClientSystem 在 UI 初始化时调用一次。"""
    if not _ENABLED:
        dlog.client_print("==== SyncControl disabled (cross-save sync off) ====")
        return False
    global _system, _retryLeft
    _system = system
    _retryLeft = 3
    # 开关1 的权威值来自本存档（B 层），不写进跨存档配置
    SS.RegisterExternalKey(ITEM_SAVE_SYNC, _ProviderSaveSync, persist=False)
    SS.SetPersistCallback(_OnPersisted)
    _RegisterPopUps()
    dlog.client_print("==== SyncControl init ====")


def _ProviderSaveSync():
    """供 SettingState 读取开关1（本存档值，由服务端下发）。"""
    return bool(_remote["save_sync"])


def _RegisterPopUps():
    RegisterPopUp(
        POPUP_SYNC_CHOICE, "选择同步方向",
        "本存档配置与跨存档配置将保持一致。\n跨存档配置保存在应用内，所有存档共用。",
        buttons=[
            ("用跨存档配置覆盖本存档", _OnChoiceUseCross),
            ("用本存档配置更新跨存档", _OnChoiceWriteCross),
        ])
    RegisterPopUp(
        POPUP_CROSS_EMPTY, "跨存档配置为空",
        "跨存档配置为空或已重置（可能因清除应用数据），"
        "当前存档的配置尚未保存到跨存档。是否仍要启用同步？",
        buttons=[
            ("用本存档配置初始化跨存档", _OnChoiceWriteCross),
            ("仅本存档使用", _OnChoiceLocalOnly),
        ])
    RegisterPopUp(
        POPUP_CLEAR_CROSS, "清空跨存档配置",
        "将清空跨存档配置与时间戳，且无法恢复。\n"
        "清空后进入存档会提示「跨存档配置为空」。",
        buttons=[
            ("取消", None),
            ("确认清空", _OnConfirmClearCross),
        ])


# ────────────────── 与服务端通信 ──────────────────

def _Send(eventName, data):
    if _system is None:
        dlog.client_print("==== SyncControl send %s: system is None ====" % eventName)
        return False
    try:
        payload = _system.CreateEventData()
        for k in (data or {}):
            payload[k] = data[k]
        payload["playerId"] = clientApi.GetLocalPlayerId()
        _system.NotifyToServer(eventName, payload)
        return True
    except Exception as e:
        dlog.client_print("==== SyncControl send %s error: %s ====" % (eventName, str(e)))
        return False


def RequestStore(reason="init"):
    """向服务端请求本存档配置 + 存档标签。"""
    if not _ENABLED:
        return False
    dlog.client_print("==== SyncControl RequestStore (%s) ====" % reason)
    return _Send(REQ_STORE, {})


def OnSyncStore(args):
    """服务端下发本存档配置与标签后的决策入口。"""
    if not _ENABLED:
        return False
    global _lastSyncedSaveSync

    settings = args.get("store_settings") or {}
    store_ts = int(args.get("updated_at", 0) or 0)
    tag = args.get("tag") or {}

    if not isinstance(settings, dict):
        settings = {}
    if not isinstance(tag, dict):
        tag = {"handled": False, "applied": False, "app_stamp": 0}

    _remote["loaded"] = True
    _remote["store_ts"] = store_ts
    _remote["tag"] = tag
    _remote["save_sync"] = bool(settings.get(_SaveSyncKey(), False))
    _remote["cross_stamp"] = SS.GetCrossStamp()

    dlog.client_print(
        "==== SyncControl OnSyncStore: keys=%d ts=%d save_sync=%s tag=%s ====" % (
            len(settings), store_ts, _remote["save_sync"], tag))

    cross_empty = IsCrossEmptyOrDefault()

    if not tag.get("handled", False):
        # 该存档第一次跑
        if bool(SS.GetSettingValue(MAIN_CARD, SUB_KEY, MID_DISPLAY,
                                   ITEM_NEW_SAVE_USE_CROSS, default=False)):
            dlog.client_print("==== SyncControl: new save -> auto enable & apply cross ====")
            _SetSaveSync(True)
            if cross_empty:
                _ShowPopup(POPUP_CROSS_EMPTY)
            else:
                PullCrossToSave()
            SetTag(applied=not cross_empty, app_stamp=_remote["cross_stamp"])
        else:
            dlog.client_print("==== SyncControl: new save -> skip (switch2 off) ====")
            SetTag(applied=False, app_stamp=0)
    else:
        # 老存档：开关1 开着就每次进入都拉一次（幂等）
        if _remote["save_sync"]:
            PullCrossToSave()
            if cross_empty:
                _ShowPopup(POPUP_CROSS_EMPTY)
        elif cross_empty:
            # 开关1 关着且跨存档配置为空：只在"曾经开过"时提示（标签里 applied 为真）
            if tag.get("applied", False):
                _ShowPopup(POPUP_CROSS_EMPTY)

    # 开关1 的值有变化才重建界面，避免闪烁
    if _lastSyncedSaveSync is None or _lastSyncedSaveSync != _remote["save_sync"]:
        _lastSyncedSaveSync = _remote["save_sync"]
        RefreshUI()
    return True


def SetTag(applied=False, app_stamp=0):
    return _Send(SET_TAG, {"applied": bool(applied), "app_stamp": int(app_stamp or 0)})


# ────────────────── 同步动作 ──────────────────

def _SaveSyncKey():
    return SS.MakeSettingKey(MAIN_CARD, SUB_KEY, MID_DISPLAY, ITEM_SAVE_SYNC)


def _NewSaveUseKey():
    return SS.MakeSettingKey(MAIN_CARD, SUB_KEY, MID_DISPLAY, ITEM_NEW_SAVE_USE_CROSS)


def _BuildPayload():
    """上报给 B 层的整包 = 跨存档配置 + 开关1 自身。"""
    data = SS.GetAllData()
    data[_SaveSyncKey()] = bool(_remote["save_sync"])
    return data


def _PushToSave(ts=None):
    """把当前配置整包写进本存档（B 层）。"""
    return _Send(SAVE_STORE, {
        "settings": _BuildPayload(),
        "updated_at": int(ts if ts is not None else time.time()),
    })


def PullCrossToSave():
    """用跨存档配置覆盖本存档：把跨存档配置整包写进 B 层，并把时间戳带过去。"""
    stamp = SS.GetCrossStamp()
    ok = _PushToSave(stamp)
    dlog.client_print("==== SyncControl PullCrossToSave: ok=%s stamp=%d ====" % (ok, stamp))
    return ok


def PushSaveToCross():
    """用本存档配置更新跨存档：把 B 层整包写进跨存档配置，并刷新时间戳。"""
    settings = _BuildPayload()
    SS.ApplyAllData(settings, persist=False)
    stamp = int(time.time())
    SS.SetCrossStamp(stamp)
    SS.PersistNow("push to cross")
    _PushToSave(stamp)
    dlog.client_print("==== SyncControl PushSaveToCross: keys=%d stamp=%d ====" % (
        len(settings), stamp))
    RefreshUI()
    return True


# ────────────────── 开关回调（由 setting.py 挂到 on_toggle） ──────────────────

def OnToggleSaveSync(screenNode, item_id, state):
    """开关1：本存档配置同步。"""
    global _awaitingChoice
    state = bool(state)
    dlog.client_print("==== display switch %s => %s ====" % (item_id, state))
    if state:
        _awaitingChoice = True
        _ShowPopup(POPUP_SYNC_CHOICE)
    else:
        _awaitingChoice = False
        _SetSaveSync(False)


def OnToggleNewSaveUseCross(screenNode, item_id, state):
    """开关2：新存档套用跨存档配置（值始终存在跨存档配置里）。"""
    dlog.client_print("==== display switch %s => %s ====" % (item_id, state))
    try:
        SS.SetSettingValue(MAIN_CARD, SUB_KEY, MID_DISPLAY, item_id, bool(state))
    except Exception as e:
        dlog.client_print("==== SyncControl switch2 persist error: %s ====" % str(e))
    # 关闭时顺手清掉"曾开过"的提示资格，避免以后反复弹窗
    if not state:
        SetTag(applied=False, app_stamp=0)


def _SetSaveSync(on, force=False):
    """写开关1（B 层权威值），必要时重建界面。"""
    global _lastSyncedSaveSync
    on = bool(on)
    if not force and bool(_remote["save_sync"]) == on:
        return on
    _remote["save_sync"] = on
    _lastSyncedSaveSync = on
    _PushToSave()
    RefreshUI()
    dlog.client_print("==== SyncControl save_config_sync -> %s ====" % on)
    return on


# ────────────────── 弹窗回调 ──────────────────

def _ClearAwaiting():
    global _awaitingChoice
    _awaitingChoice = False


def _OnChoiceUseCross():
    _ClearAwaiting()
    _SetSaveSync(True)          # 用户已做出选择 -> 开关1 保持开
    if IsCrossEmptyOrDefault():
        _ShowPopup(POPUP_CROSS_EMPTY)
    else:
        PullCrossToSave()
        SetTag(applied=True, app_stamp=SS.GetCrossStamp())
    return True


def _OnChoiceWriteCross():
    _ClearAwaiting()
    _SetSaveSync(True)
    PushSaveToCross()
    SetTag(applied=True, app_stamp=SS.GetCrossStamp())
    return True


def _OnChoiceLocalOnly():
    _ClearAwaiting()
    _SetSaveSync(False)
    SetTag(applied=False, app_stamp=0)
    return True


def OnPopUpClosed():
    if not _ENABLED:
        return False
    """
    任意弹窗关闭时由 Client.py 调用。
    若方向选择弹窗被直接关掉（没有点按钮）-> 开关1 自动回关。
    """
    if not _awaitingChoice:
        return False
    _ClearAwaiting()
    dlog.client_print(
        "==== SyncControl: choice popup dismissed, save_config_sync -> off ====")
    _SetSaveSync(False, force=True)
    return True


def OnSettingsClosed():
    if not _ENABLED:
        return False
    """
    退出设置界面：二次校验并同步。
    先把当前配置整包重推一次（兜住 SaveAllSettings 可能漏掉的项），
    再向服务端要一次副本，OnSyncStore 里做对账日志。
    """
    if not _remote.get("save_sync"):
        dlog.client_print("==== SyncControl OnSettingsClosed: switch off, skip ====")
        return False
    dlog.client_print("==== SyncControl OnSettingsClosed: reconcile & push ====")
    _PushToSave()
    RequestStore("reconcile")
    return True


def _ReconcileLog(serverSettings):
    """对账：比较本地（跨存档配置）与服务端（本存档配置）的差异项数。"""
    try:
        local = SS.GetAllData()
    except Exception:
        return -1
    keys = set(local.keys()) | set((serverSettings or {}).keys())
    diff = []
    for k in keys:
        if local.get(k) != (serverSettings or {}).get(k):
            diff.append(k)
    if diff:
        dlog.client_print("==== SyncControl reconcile: diff=%d %s ====" % (
            len(diff), diff[:8]))
    else:
        dlog.client_print("==== SyncControl reconcile: consistent (%d keys) ====" % len(local))
    return len(diff)


# ────────────────── 每次改动后的防抖上报 ──────────────────

def _OnPersisted(tag):
    """SettingState 每次写入跨存档配置后回调：开关1 开着就防抖同步到 B 层。"""
    if not _ENABLED:
        return
    global _pushTimer
    if not _remote.get("save_sync"):
        return
    if _system is None:
        return
    try:
        if _pushTimer is not None:
            return
        game = clientApi.GetEngineCompFactory().CreateGame(clientApi.GetLevelId())
        _pushTimer = game.AddTimer(0.6, _OnPushTimer)
    except Exception as e:
        dlog.client_print("==== SyncControl debounce error: %s ====" % str(e))


def _OnPushTimer():
    global _pushTimer
    _pushTimer = None
    if _remote.get("save_sync"):
        _PushToSave()


# ────────────────── 调试页按钮 ──────────────────

def OnClickClearCross(screenNode, item_id):
    """调试页「清空跨存档配置」：弹确认框。"""
    dlog.client_print("==== SyncControl OnClickClearCross ====")
    _RegisterPopUps()   # 幂等，兜住 Init 未跑到的场景
    _ShowPopup(POPUP_CLEAR_CROSS)


def _OnConfirmClearCross():
    ClearCrossConfig()
    return True


def ClearCrossConfig():
    """清空跨存档配置与时间戳（仅用于测试）。"""
    try:
        SS.ClearCrossData()
        _remote["cross_stamp"] = 0
        dlog.client_print("==== SyncControl ClearCrossConfig done ====")
    except Exception as e:
        dlog.client_print("==== SyncControl ClearCrossConfig error: %s ====" % str(e))
    RefreshUI()
    return True


def OnClickSyncInfo(screenNode, item_id):
    """调试页「查看同步状态」：把当前同步状态打到日志。"""
    dlog.client_print("==== SyncControl state: %s ====" % (_remote,))
    return True


# ────────────────── 工具 ──────────────────

def _ShowPopup(popupId):
    try:
        _system.ShowPopUp(popupId)
    except Exception as e:
        dlog.client_print("==== SyncControl ShowPopUp %s error: %s ====" % (popupId, str(e)))


def RefreshUI():
    """重建右侧内容（开关1 的值可能被外部改动）。"""
    node = getattr(_system, "mSettingsScreenNode", None)
    if node is None:
        return False
    group = getattr(node, "mCurrentRightGroup", None)
    if not group or group[0] is None:
        return False
    try:
        node.RebuildRightContent(group[0], group[1], group[2])
        return True
    except Exception as e:
        dlog.client_print("==== SyncControl RefreshUI error: %s ====" % str(e))
        return False


def _SoftEq(a, b):
    if a == b:
        return True
    try:
        return float(a) == float(b)
    except Exception:
        return False


def IsCrossEmptyOrDefault():
    """跨存档配置为空，或所有项都等于默认值。"""
    try:
        data = SS.GetAllData()
    except Exception:
        return True
    if not data:
        return True
    try:
        from CardRegistry import GetAllContentGroups, GetContentItems
        for group in GetAllContentGroups():
            for item in GetContentItems(group[0], group[1], group[2]):
                if item.type_name not in ("switch", "edit_box", "slider", "collapsible_menu"):
                    continue
                key = SS.MakeSettingKey(group[0], group[1], group[2], item.item_id)
                if key not in data:
                    continue
                default = getattr(item, "default_value", None)
                if item.type_name == "switch":
                    default = bool(default)
                if not _SoftEq(data[key], default):
                    return False
    except Exception as e:
        dlog.client_print("==== SyncControl IsCrossEmptyOrDefault error: %s ====" % str(e))
        return False
    return True