# -*- coding: utf-8 -*-
"""
跨存档同步 · 存档侧存储（服务端）
==================================
把客户端的设置整包按玩家存进存档，作为"本存档配置"的权威副本。

存储位置（ModAttr，needRestore=True 才会存档）：
    CreateModAttr(playerId)  -> 该存档内的玩家数据（每个存档、每个玩家各一份）
    CreateModAttr(levelId)   -> 该存档的世界数据（全服共享，世界级项用）

两个属性键：
    _STORE_KEY : {"settings": {<键>: value}, "updated_at": <unix ts>}
    _TAG_KEY   : {"handled": bool, "applied": bool, "app_stamp": <unix ts>}

注意：
- 服务端 SetAttr 会自动同步给客户端（客户端 GetAttr 可读）；客户端 SetAttr 只在本地有效。
- 高频写入用 autoSave=False，随后统一 SaveAttr()（见 FlushPlayer / FlushAll）。
"""

import time

import mod.server.extraServerApi as serverApi

from DebugLog import dlog

_STORE_KEY = "Script_NeteaseMod9sPMlz0K_store"
_TAG_KEY = "Script_NeteaseMod9sPMlz0K_save_tag"
# 开关1 在 B 层的存储键（与 SettingState 的 item_id 对应）
KEY_SAVE_SYNC = "save_config_sync"

# 已标脏、等待落盘的玩家
_dirtyPlayers = set()


def _Comp(entityId):
    return serverApi.GetEngineCompFactory().CreateModAttr(entityId)


def Now():
    return int(time.time())


# ────────────────── 玩家（本存档）配置 ──────────────────

def GetStore(playerId):
    """读取该玩家在本存档的配置包 -> {"settings": {...}, "updated_at": int}"""
    default = {"settings": {}, "updated_at": 0}
    try:
        data = _Comp(playerId).GetAttr(_STORE_KEY, None)
        if isinstance(data, dict):
            out = {"settings": {}, "updated_at": 0}
            if isinstance(data.get("settings"), dict):
                out["settings"] = dict(data["settings"])
            try:
                out["updated_at"] = int(data.get("updated_at", 0) or 0)
            except Exception:
                out["updated_at"] = 0
            return out
    except Exception as e:
        dlog.server_print("==== PlayerStore GetStore error: %s ====" % str(e))
    return default


def IsSaveSyncOn(playerId):
    """本存档配置同步开关（B 层权威值）。"""
    return bool(GetStore(playerId)["settings"].get(KEY_SAVE_SYNC, False))


def SetStore(playerId, settings, updated_at=None):
    """整包写入该玩家的配置（不立即落盘，需 FlushPlayer / FlushAll）。"""
    payload = {
        "settings": dict(settings or {}),
        "updated_at": int(updated_at if updated_at is not None else Now()),
    }
    try:
        _Comp(playerId).SetAttr(_STORE_KEY, payload, True, False)
        _dirtyPlayers.add(playerId)
        dlog.server_print("==== PlayerStore SetStore: player=%s keys=%d ts=%d ====" % (
            playerId, len(payload["settings"]), payload["updated_at"]))
        return True
    except Exception as e:
        dlog.server_print("==== PlayerStore SetStore error: %s ====" % str(e))
        return False


def FlushPlayer(playerId):
    """把该玩家标脏的属性落盘。返回是否真的执行了保存。"""
    if playerId not in _dirtyPlayers:
        return False
    try:
        _Comp(playerId).SaveAttr()
        _dirtyPlayers.discard(playerId)
        dlog.server_print("==== PlayerStore FlushPlayer: player=%s ====" % playerId)
        return True
    except Exception as e:
        dlog.server_print("==== PlayerStore FlushPlayer error: %s ====" % str(e))
        return False


def FlushAll():
    for pid in list(_dirtyPlayers):
        FlushPlayer(pid)


# ────────────────── 存档标签 ──────────────────

def GetTag(playerId):
    """-> {"handled": bool, "applied": bool, "app_stamp": int}"""
    default = {"handled": False, "applied": False, "app_stamp": 0}
    try:
        data = _Comp(playerId).GetAttr(_TAG_KEY, None)
        if isinstance(data, dict):
            try:
                stamp = int(data.get("app_stamp", 0) or 0)
            except Exception:
                stamp = 0
            return {
                "handled": bool(data.get("handled", False)),
                "applied": bool(data.get("applied", False)),
                "app_stamp": stamp,
            }
    except Exception as e:
        dlog.server_print("==== PlayerStore GetTag error: %s ====" % str(e))
    return default


def SetTag(playerId, applied=False, app_stamp=0):
    payload = {"handled": True, "applied": bool(applied),
               "app_stamp": int(app_stamp or 0)}
    try:
        _Comp(playerId).SetAttr(_TAG_KEY, payload, True, False)
        _dirtyPlayers.add(playerId)
        dlog.server_print("==== PlayerStore SetTag: player=%s applied=%s stamp=%d ====" % (
            playerId, payload["applied"], payload["app_stamp"]))
        return True
    except Exception as e:
        dlog.server_print("==== PlayerStore SetTag error: %s ====" % str(e))
        return False


# ────────────────── 世界级配置（A 层） ──────────────────

def GetWorld(key, default=None):
    try:
        return _Comp(serverApi.GetLevelId()).GetAttr(key, default)
    except Exception as e:
        dlog.server_print("==== PlayerStore GetWorld error: %s ====" % str(e))
        return default


def SetWorld(key, value, save=True):
    try:
        comp = _Comp(serverApi.GetLevelId())
        comp.SetAttr(key, value, True, False)
        if save:
            comp.SaveAttr()
        return True
    except Exception as e:
        dlog.server_print("==== PlayerStore SetWorld error: %s ====" % str(e))
        return False
