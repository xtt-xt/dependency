# -*- coding: utf-8 -*-
"""
跨存档同步 · 事件名常量
========================
纯常量模块，不 import 任何引擎模块，客户端与服务端共用。

客户端 -> 服务端：
    REQ_STORE   {"playerId"}                        请求本存档配置 + 存档标签
    SAVE_STORE  {"playerId", "settings", "updated_at"}  整包写入本存档配置（B 层）
    SET_TAG     {"playerId", "applied", "app_stamp"}     写入存档标签

服务端 -> 客户端：
    SYNC_STORE  {"playerId", "save_sync", "store_settings", "updated_at", "tag"}
"""

NS = "Script_NeteaseMod9sPMlz0K"
SYS = "client"

REQ_STORE = "Script_NeteaseMod9sPMlz0K_ReqStore"
SAVE_STORE = "Script_NeteaseMod9sPMlz0K_SaveStore"
SET_TAG = "Script_NeteaseMod9sPMlz0K_SetTag"
SYNC_STORE = "Script_NeteaseMod9sPMlz0K_SyncStore"
