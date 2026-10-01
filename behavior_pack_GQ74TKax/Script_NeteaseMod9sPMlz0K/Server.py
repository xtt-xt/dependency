# -*- coding: utf-8 -*-
"""
服务端系统
==========
1. 监听 CustomCommandTriggerServerEvent 处理 /setting_open 自定义指令。
2. 维护服务端全局调试日志开关（仅 OP 可改，ModAttr 持久化），并向各客户端同步。

服务端日志开关相关事件：
- ReqServerLogEvent   (client -> server) 客户端请求当前全局值 + 自身 OP 状态
- SetServerLogEvent   (client -> server) 客户端请求修改全局值（服务端鉴权 OP）
- ServerLogSyncEvent  (server -> client) 服务端下发当前全局值 + 该客户端 OP 状态
服务端日志导出相关事件：
- ReqServerLogDumpEvent (client -> server) 客户端请求导出最近 N 条服务端日志
- ServerLogDumpRespEvent (server -> client) 服务端下发最近 N 条服务端日志
重置本页相关事件：
- ResetGroupEvent      (client -> server) 客户端请求重置指定服务端分组为默认（服务端鉴权 OP）
"""

import mod.server.extraServerApi as serverApi

import PlayerStore as PS
from DebugLog import dlog
from StoreEvents import REQ_STORE, SAVE_STORE, SET_TAG, SYNC_STORE

ServerSystem = serverApi.GetServerSystemCls()

# 服务端→客户端 自定义事件名（打开设置界面）
SettingsOpenFromCommandEvent = "Script_NeteaseMod9sPMlz0K_OpenSettingsFromCommand"
# 服务端日志开关：客户端→服务端
ReqServerLogEvent = "Script_NeteaseMod9sPMlz0K_ReqServerLog"
SetServerLogEvent = "Script_NeteaseMod9sPMlz0K_SetServerLog"
# 服务端日志开关：服务端→客户端
ServerLogSyncEvent = "Script_NeteaseMod9sPMlz0K_ServerLogSync"
# 服务端日志导出：客户端→服务端
ReqServerLogDumpEvent = "Script_NeteaseMod9sPMlz0K_ReqServerLogDump"
# 服务端日志导出：服务端→客户端
ServerLogDumpRespEvent = "Script_NeteaseMod9sPMlz0K_ServerLogDumpResp"
# 重置本页：客户端→服务端
ResetGroupEvent = "Script_NeteaseMod9sPMlz0K_ResetGroup"

# ModAttr 全局属性键（服务端全局日志开关），注意带 mod 前缀避免冲突
_SERVER_LOG_ATTR_KEY = "Script_NeteaseMod9sPMlz0K_server_log_enabled"
# 服务端权威默认设置存储：各服务端分组的默认键（重置本页用，键须与 setting.py 一致）
_SERVER_GROUP_DEFAULT_KEYS = {
    "debug": ["server_log_output"],
}


def IsOperator(playerId):
    """判断玩家是否为 OP（Operator/Custom，权限类型 >= 2）。

    权限类型：0=Visitor，1=Member，2=Operator，3=Custom。
    """
    try:
        comp = serverApi.GetEngineCompFactory().CreatePlayer(playerId)
        return comp.GetPlayerOperation() >= 2
    except Exception:
        return False


class MyServerSystem(ServerSystem):

    def __init__(self, namespace, systemName):
        ServerSystem.__init__(self, namespace, systemName)
        self.ListenForEvent(
            serverApi.GetEngineNamespace(),
            serverApi.GetEngineSystemName(),
            'CustomCommandTriggerServerEvent',
            self,
            self.OnCustomCommand
        )
        # 客户端→服务端 请求/修改 全局日志开关
        self.ListenForEvent(
            "Script_NeteaseMod9sPMlz0K",
            "client",
            ReqServerLogEvent,
            self,
            self.OnReqServerLog
        )
        self.ListenForEvent(
            "Script_NeteaseMod9sPMlz0K",
            "client",
            SetServerLogEvent,
            self,
            self.OnSetServerLog
        )
        # 客户端→服务端 请求导出服务端日志
        self.ListenForEvent(
            "Script_NeteaseMod9sPMlz0K",
            "client",
            ReqServerLogDumpEvent,
            self,
            self.OnReqServerLogDump
        )
        # 客户端→服务端 重置本页（仅 OP，重置后广播全服）
        self.ListenForEvent(
            "Script_NeteaseMod9sPMlz0K",
            "client",
            ResetGroupEvent,
            self,
            self.OnResetGroup
        )
        # 跨存档同步：本存档配置（B 层）+ 存档标签
        self.ListenForEvent("Script_NeteaseMod9sPMlz0K", "client", REQ_STORE,
                            self, self.OnReqStore)
        self.ListenForEvent("Script_NeteaseMod9sPMlz0K", "client", SAVE_STORE,
                            self, self.OnSaveStore)
        self.ListenForEvent("Script_NeteaseMod9sPMlz0K", "client", SET_TAG,
                            self, self.OnSetTag)
        # 玩家离开：把标脏的本存档配置落盘
        self.ListenForEvent(serverApi.GetEngineNamespace(),
                            serverApi.GetEngineSystemName(),
                            'DelServerPlayerEvent', self, self.OnDelServerPlayer)
        # 定时兜底落盘
        try:
            serverApi.GetEngineCompFactory().CreateGame(
                serverApi.GetLevelId()).AddRepeatedTimer(5.0, self._OnFlushTimer)
        except Exception as e:
            dlog.server_print("==== flush timer register error: %s ====" % str(e))
        # 加载并初始化服务端全局日志开关
        self.mServerLogEnabled = self._LoadServerLogEnabled()
        dlog.set_server_enabled(self.mServerLogEnabled)
        dlog.server_print("==== MyServerSystem init, server log output=%s ====" % self.mServerLogEnabled)

    # ---------------- 全局日志开关 ----------------

    def _GetOnlinePlayers(self):
        """获取当前在线玩家 entityId 列表。"""
        try:
            comp = serverApi.GetEngineCompFactory().CreatePlayerList()
            return comp.GetAllPlayers()
        except Exception:
            return []

    def _LoadServerLogEnabled(self):
        """读取持久化的服务端全局日志开关。"""
        try:
            comp = serverApi.GetEngineCompFactory().CreateModAttr(serverApi.GetLevelId())
            return bool(comp.GetAttr(_SERVER_LOG_ATTR_KEY, False))
        except Exception:
            return False

    def _SaveServerLogEnabled(self, enabled):
        """持久化服务端全局日志开关（needRestore=True，随后统一 SaveAttr）。"""
        try:
            comp = serverApi.GetEngineCompFactory().CreateModAttr(serverApi.GetLevelId())
            comp.SetAttr(_SERVER_LOG_ATTR_KEY, bool(enabled), True, False)
            comp.SaveAttr()
        except Exception as e:
            dlog.server_print("==== save server log attr error: %s ====" % str(e))

    def OnReqServerLog(self, args):
        """客户端请求当前全局值 + 自身 OP 状态。"""
        playerId = args.get('playerId', '')
        if not playerId:
            return
        is_op = IsOperator(playerId)
        data = self.CreateEventData()
        data['enabled'] = self.mServerLogEnabled
        data['is_op'] = is_op
        self.NotifyToClient(playerId, ServerLogSyncEvent, data)
        dlog.server_print("==== OnReqServerLog: player=%s is_op=%s value=%s ====" % (
            playerId, is_op, self.mServerLogEnabled))

    def OnReqServerLogDump(self, args):
        """客户端请求导出服务端日志：返回最近 count 条服务端缓冲日志。"""
        playerId = args.get('playerId', '')
        if not playerId:
            return
        try:
            count = int(args.get('count', 200))
        except Exception:
            count = 200
        lines = dlog.format_server_history(count)
        data = self.CreateEventData()
        data['playerId'] = playerId
        data['lines'] = lines
        self.NotifyToClient(playerId, ServerLogDumpRespEvent, data)
        dlog.server_print("==== OnReqServerLogDump: player=%s count=%d ====" % (
            playerId, count))

    def OnSetServerLog(self, args):
        """客户端请求修改全局日志开关（仅 OP 允许）。"""
        playerId = args.get('playerId', '')
        enabled = bool(args.get('enabled', False))
        if not IsOperator(playerId):
            # 非 OP 试图修改：忽略，并把当前全局值回发一次以纠正其 UI
            dlog.server_print("==== OnSetServerLog denied: player=%s not operator ====" % playerId)
            data = self.CreateEventData()
            data['enabled'] = self.mServerLogEnabled
            data['is_op'] = False
            if playerId:
                self.NotifyToClient(playerId, ServerLogSyncEvent, data)
            return
        self.mServerLogEnabled = enabled
        dlog.set_server_enabled(enabled)
        self._SaveServerLogEnabled(enabled)
        self._BroadcastServerLog()

    def _BroadcastServerLog(self):
        """向所有在线玩家下发当前全局日志开关状态（附各自 OP 状态用于锁定）。"""
        for pid in self._GetOnlinePlayers():
            data = self.CreateEventData()
            data['enabled'] = self.mServerLogEnabled
            data['is_op'] = IsOperator(pid)
            self.NotifyToClient(pid, ServerLogSyncEvent, data)
        dlog.server_print("==== BroadcastServerLog: value=%s ====" % self.mServerLogEnabled)

    # ---------------- 重置本页（服务端权威） ----------------

    def OnResetGroup(self, args):
        """客户端请求重置指定服务端分组为默认（仅 OP），并广播全服。

        该方法参考飞行之羽模组（FlyArmor）的"服务端权威重置 + 全局广播"：
        - 客户端本地已先将该分组 Client.py 存储重置（ResetGroupSettings）
        - 服务端在此处重置服务端权威默认值（服务端日志开关等）
        - 重置后向所有在线玩家广播，各客户端同步 UI（含服务端下发日志开关）
        """
        playerId = args.get('playerId', '')
        middle_card_id = args.get('middle_card_id', '')
        if not playerId:
            return
        if not IsOperator(playerId):
            dlog.server_print("==== ResetGroup denied: player=%s not operator ====" % playerId)
            return
        keys = _SERVER_GROUP_DEFAULT_KEYS.get(middle_card_id)
        if not keys:
            return
        # 重置服务端权威默认值并持久化（当前仅服务端日志开关）
        changed = False
        if "server_log_output" in keys:
            self.mServerLogEnabled = False
            dlog.set_server_enabled(False)
            self._SaveServerLogEnabled(False)
            changed = True
        if changed:
            self._BroadcastServerLog()
        dlog.server_print("==== ResetGroup reset page=%s ====" % middle_card_id)

    # ---------------- 打开设置界面指令 ----------------

    def OnCustomCommand(self, args):
        """
        监听自定义指令触发事件。
        指令定义在 netease_commands/ 目录下的 JSON 文件中。
        """
        command = args.get('command', '')
        if command != 'setting_open':
            return

        command_args = args.get('args', [])
        origin = args.get('origin', {})
        caller_id = origin.get('entityId', '')
        if not caller_id:
            dlog.server_print("==== /setting_open: no origin entityId ====")
            return

        # 安全约束：命令对所有成员可用，但仅作用于调用者自己（忽略 @a/指定他人，防骚扰）
        target_id = caller_id

        # 解析参数（按 name 匹配）
        main_card_id = ""
        middle_card_id = ""
        sub_key = ""

        for arg in command_args:
            arg_name = arg.get('name', '')
            arg_value = arg.get('value')
            if arg_name == u'\u4e3b\u5361\u7247id':  # 主卡片id
                main_card_id = arg_value if arg_value else ""
            elif arg_name == u'\u4e2d\u95f4\u5361\u7247id':  # 中间卡片id
                middle_card_id = arg_value if arg_value else ""
            elif arg_name == u'\u5b50\u5361\u7247key':  # 子卡片key
                sub_key = arg_value if arg_value else ""

        # 向目标客户端发送事件
        eventData = self.CreateEventData()
        eventData["main_card_id"] = main_card_id
        eventData["middle_card_id"] = middle_card_id
        eventData["sub_key"] = sub_key
        self.NotifyToClient(target_id, SettingsOpenFromCommandEvent, eventData)

        # 命令成功反馈：聊天栏显示"设置已打开"（key 定义在资源包 texts/zh_CN.lang）
        args["return_msg_key"] = "commands.custom.setting_open"

        dlog.server_print("==== /setting_open: 设置已打开：main=%s middle=%s sub=%s ====" % (
            main_card_id, middle_card_id, sub_key
        ))

    # ---------------- 跨存档同步（本存档配置，B 层） ----------------

    def OnReqStore(self, args):
        """客户端请求本存档配置 + 存档标签。"""
        playerId = args.get("playerId", "")
        if not playerId:
            return
        store = PS.GetStore(playerId)
        data = self.CreateEventData()
        data["playerId"] = playerId
        data["store_settings"] = store["settings"]
        data["updated_at"] = store["updated_at"]
        data["tag"] = PS.GetTag(playerId)
        self.NotifyToClient(playerId, SYNC_STORE, data)
        dlog.server_print("==== OnReqStore: player=%s keys=%d ts=%d ====" % (
            playerId, len(store["settings"]), store["updated_at"]))

    def OnSaveStore(self, args):
        """客户端整包写入本存档配置。"""
        playerId = args.get("playerId", "")
        if not playerId:
            return
        settings = args.get("settings") or {}
        if not isinstance(settings, dict):
            return
        try:
            ts = int(args.get("updated_at", 0) or 0)
        except Exception:
            ts = 0
        PS.SetStore(playerId, settings, ts or None)
        PS.FlushPlayer(playerId)

    def OnSetTag(self, args):
        """客户端写入存档标签。"""
        playerId = args.get("playerId", "")
        if not playerId:
            return
        try:
            stamp = int(args.get("app_stamp", 0) or 0)
        except Exception:
            stamp = 0
        PS.SetTag(playerId, bool(args.get("applied", False)), stamp)
        PS.FlushPlayer(playerId)

    def OnDelServerPlayer(self, args):
        """玩家离开：落盘。"""
        playerId = args.get("playerId", "")
        if playerId:
            PS.FlushPlayer(playerId)

    def _OnFlushTimer(self):
        """定时兜底落盘。"""
        try:
            PS.FlushAll()
        except Exception as e:
            dlog.server_print("==== flush all error: %s ====" % str(e))
