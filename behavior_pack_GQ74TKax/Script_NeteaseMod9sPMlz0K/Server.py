# -*- coding: utf-8 -*-
"""
服务端系统
==========
监听 CustomCommandTriggerServerEvent 处理 /setting_open 自定义指令。
"""

import mod.server.extraServerApi as serverApi

ServerSystem = serverApi.GetServerSystemCls()

# 服务端→客户端 自定义事件名
SettingsOpenFromCommandEvent = "Script_NeteaseMod9sPMlz0K_OpenSettingsFromCommand"


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
        print "==== MyServerSystem init, listening for CustomCommandTriggerServerEvent ===="

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

        # 解析参数（按 name 匹配）
        target_raw = None
        main_card_id = ""
        middle_card_id = ""
        sub_key = ""

        for arg in command_args:
            arg_name = arg.get('name', '')
            arg_value = arg.get('value')
            if arg_name == u'\u76ee\u6807':  # 目标
                target_raw = arg_value
            elif arg_name == u'\u4e3b\u5361\u7247id':  # 主卡片id
                main_card_id = arg_value if arg_value else ""
            elif arg_name == u'\u4e2d\u95f4\u5361\u7247id':  # 中间卡片id
                middle_card_id = arg_value if arg_value else ""
            elif arg_name == u'\u5b50\u5361\u7247key':  # 子卡片key
                sub_key = arg_value if arg_value else ""

        # 解析目标玩家
        target_ids = self._ResolveTargets(target_raw, origin)

        if not target_ids:
            print "==== /setting_open: no target ===="
            return

        # 向每个目标客户端发送事件
        eventData = self.CreateEventData()
        eventData["main_card_id"] = main_card_id
        eventData["middle_card_id"] = middle_card_id
        eventData["sub_key"] = sub_key

        for targetId in target_ids:
            self.NotifyToClient(targetId, SettingsOpenFromCommandEvent, eventData)

        print "==== /setting_open: sent to %d player(s): main=%s middle=%s sub=%s ====" % (
            len(target_ids), main_card_id, middle_card_id, sub_key
        )

    def _ResolveTargets(self, target_raw, origin):
        """
        解析目标参数，返回 entityId 元组。

        target_raw 可能为：
        - None: 未传参，使用 origin.entityId
        - tuple: 引擎已解析的实体ID元组（如 @a 时）
        - str: 默认值 @s 未被解析为字符串，需手动解析
        """
        if target_raw is None:
            # 未传参，使用触发者自身
            eid = origin.get('entityId', '')
            return (eid,) if eid else ()

        if isinstance(target_raw, tuple):
            # 引擎已正确解析（如 @a 返回多个玩家ID）
            return target_raw

        if isinstance(target_raw, basestring):
            # 默认值 @s 未被引擎解析，使用 GetEntitiesBySelector 手动解析
            # 注意：GetEntitiesBySelector 在实体组件上，而非游戏组件
            try:
                comp = serverApi.GetEngineCompFactory().CreateEntity(serverApi.GetLevelId())
                result = comp.GetEntitiesBySelector(target_raw)
                if result:
                    return tuple(result)
            except Exception as e:
                print "==== /setting_open: GetEntitiesBySelector error: %s ====" % str(e)
            # 解析失败，回退到 origin.entityId
            eid = origin.get('entityId', '')
            return (eid,) if eid else ()

        # 其他情况，回退
        eid = origin.get('entityId', '')
        return (eid,) if eid else ()