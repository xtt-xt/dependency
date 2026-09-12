# -*- coding: utf-8 -*-

import mod.client.extraClientApi as clientApi
from CardRegistry import (
    RegisterMainCard, GetMainCard, GetAllMainCardIds, GetMiddleCardBindings,
    RegisterMiddleCard, UnregisterMainCard, UnregisterMiddleCard, ClearAllCards,
    CreateContentInst, GetContentItems, GetContentItem, ClearContentItems,
    RegisterContentListener, UnregisterContentListener,
    SetCardChangedCallback, NormalizeMiddleCardId,
    RegisterCollapsibleMenu
)
from SettingState import (
    GetSettingValue, SetSettingValue, ResetSettingValue, ResetAllSettings,
    ResetGroupSettings,
    SetSettingChangedCallback, MakeSettingKey, LoadSettingData
)
from DebugLog import dlog

# 右侧内容项 UI 构建器注册表：type_name -> build function
# build function 签名：Build(screenNode, parent, item)
_contentBuilders = {}

# 模块级单例，供 ScreenNode 注册自身以接收每帧回调
_g_ClientSystem = None

ClientSystem = clientApi.GetClientSystemCls()
ScreenNode = clientApi.GetScreenNodeCls()
CustomUIScreenProxy = clientApi.GetUIScreenProxyCls()
NativeScreenManager = clientApi.GetNativeScreenManagerCls()
ViewBinder = clientApi.GetViewBinderCls()
ViewRequest = clientApi.GetViewViewRequestCls()


class MyClientSystem(ClientSystem):

    def __init__(self, namespace, systemName):
        ClientSystem.__init__(self, namespace, systemName)
        global _g_ClientSystem
        _g_ClientSystem = self
        self.mUiCreated = False
        self.mKeyFactory = None
        self.mSettingsUIOpen = False
        self.mSettingsScreenNode = None
        self.mPendingNavigation = None  # 待处理导航参数 (main_card_id, sub_key, middle_card_id)
        self.mCurrentPopUp = None  # 当前待显示/显示的弹窗数据 {"title": str, "content": str, "buttons": [...]}
        self.mPopUpOpen = False    # 弹窗 UI 是否在场景栈中
        self.mPopUpScreenNode = None  # 弹窗 ScreenNode 引用（用于已打开时刷新内容）
        self.mReturningFromPopUp = False  # 弹窗刚关闭，设置界面 OnActive 时跳过重建，保留当前详情
        self.mCollapsibleMenuOpen = False    # 折叠菜单弹窗是否在场景栈中
        self.mCollapsibleMenuScreenNode = None  # 折叠菜单 ScreenNode 引用
        self.mCurrentCollapsibleMenu = None  # 当前折叠菜单数据 {"title": str, "cards": [(card_id, name), ...]}
        self.mCurrentCollapsibleItem = None  # 关联的 CollapsibleMenuContentItem（用于读写选中状态）
        self.mCardToggleOpen = False       # 组合开关弹窗是否在场景栈中
        self.mCardToggleScreenNode = None  # 组合开关 ScreenNode 引用
        self.mCurrentCardToggle = None     # 当前组合开关数据集 {"title","mode","buttons","options"}
        self.mCurrentToggleId = ""         # 当前组合开关 toggle_id
        self.mPendingCloseSettings = False  # 确认关闭动画后：OnActive 时立即关闭设置界面
        # 注册主卡片变更回调：当主卡片注册/注销时自动刷新 UI
        SetCardChangedCallback(self._OnCardChanged)
        self.ListenForEvent(
            clientApi.GetEngineNamespace(),
            clientApi.GetEngineSystemName(),
            'UiInitFinished',
            self,
            self.OnUIInitFinished
        )
        self.ListenForEvent(
            clientApi.GetEngineNamespace(),
            clientApi.GetEngineSystemName(),
            'PushScreenEvent',
            self,
            self.OnPushScreen
        )
        self.ListenForEvent(
            clientApi.GetEngineNamespace(),
            clientApi.GetEngineSystemName(),
            'PopScreenEvent',
            self,
            self.OnPopScreen
        )
        self.ListenForEvent(
            clientApi.GetEngineNamespace(),
            clientApi.GetEngineSystemName(),
            'OnKeyPressInGame',
            self,
            self.OnKeyPressInGame
        )
        self.ListenForEvent(
            clientApi.GetEngineNamespace(),
            clientApi.GetEngineSystemName(),
            'OnScriptTickClient',
            self,
            self.OnScriptTickClient
        )
        self.ListenForEvent(
            clientApi.GetEngineNamespace(),
            clientApi.GetEngineSystemName(),
            'OnCustomKeyPressInGame',
            self,
            self.OnCustomKeyPressed
        )
        self.ListenForEvent(
            "Script_NeteaseMod9sPMlz0K",
            "server",
            "Script_NeteaseMod9sPMlz0K_OpenSettingsFromCommand",
            self,
            self.OnOpenSettingsFromCommand
        )
        # 服务端全局日志开关同步（服务端->客户端）
        self.ListenForEvent(
            "Script_NeteaseMod9sPMlz0K",
            "server",
            "Script_NeteaseMod9sPMlz0K_ServerLogSync",
            self,
            self.OnServerLogSync
        )
        # 服务端日志导出回执（服务端->客户端）
        self.ListenForEvent(
            "Script_NeteaseMod9sPMlz0K",
            "server",
            "Script_NeteaseMod9sPMlz0K_ServerLogDumpResp",
            self,
            self.OnServerLogDumpResp
        )
        NativeScreenManager.instance().RegisterScreenProxy(
            'pause.pause_screen',
            'Script_NeteaseMod9sPMlz0K.Client.PauseScreenProxy'
        )
        NativeScreenManager.instance().RegisterScreenProxy(
            'fold_menu.fold_menu_dialog_screen',
            'Script_NeteaseMod9sPMlz0K.Client.FoldMenuProxy'
        )
        dlog.client_print("==== MyClientSystem init, waiting for UiInitFinished ====")

    def OnPushScreen(self, args):
        screenDef = args.get('screenDef', 'unknown')
        dlog.client_print("==== PushScreenEvent screenDef: %s ====" % screenDef)
        if screenDef == 'setting.main':
            self.mSettingsUIOpen = True
            # 新开设置界面，清除弹窗返回标志（防滞留）
            self.mReturningFromPopUp = False
            from CardRegistry import SettingsUIOpenEvent
            eventData = self.CreateEventData()
            eventData["playerId"] = clientApi.GetLocalPlayerId()
            self.BroadcastEvent(SettingsUIOpenEvent, eventData)

    def OnPopScreen(self, args):
        screenDef = args.get('screenDef', 'unknown')
        dlog.client_print("==== PopScreenEvent screenDef: %s ====" % screenDef)
        if screenDef == 'setting.main':
            self.mSettingsUIOpen = False
            # 退出设置界面时统一提交所有设置项改动（OnTick 不再实时写存储）
            try:
                from SettingState import SaveAllSettings
                count = SaveAllSettings()
                if count:
                    dlog.client_print("==== SettingsUI closed, saved %d settings ====" % count)
            except Exception as e:
                dlog.client_print("==== SettingsUI close save error: %s ====" % str(e))
            from CardRegistry import SettingsUICloseEvent
            eventData = self.CreateEventData()
            eventData["playerId"] = clientApi.GetLocalPlayerId()
            self.BroadcastEvent(SettingsUICloseEvent, eventData)
        elif screenDef in ('pop_up.main', 'pop_up.main_scroll'):
            self.mPopUpOpen = False
            self.mCurrentPopUp = None
            self.mReturningFromPopUp = False
            from CardRegistry import PopUpCloseEvent
            eventData = self.CreateEventData()
            eventData["playerId"] = clientApi.GetLocalPlayerId()
            self.BroadcastEvent(PopUpCloseEvent, eventData)
        elif screenDef == 'pop_up.collapsible_menu':
            self.mCollapsibleMenuOpen = False
            self.mCurrentCollapsibleMenu = None
            self.mCurrentCollapsibleItem = None
            self.mReturningFromPopUp = False
        elif screenDef == 'pop_up.card_toggle_panel':
            self.mCardToggleOpen = False
            self.mCurrentCardToggle = None
            self.mCurrentToggleId = ""
            self.mReturningFromPopUp = False

    def OnKeyPressInGame(self, args):
        keyValue = int(args.get('key', 0))
        isDown = int(args.get('isDown', 0))
        dlog.client_print("==== OnKeyPressInGame key: %d isDown: %d settingsOpen: %s popUpOpen: %s ====" % (keyValue, isDown, self.mSettingsUIOpen, self.mPopUpOpen))
        if isDown and keyValue == 27:
            # ESC：折叠菜单/弹窗打开时只关对应层；否则关闭设置界面
            if self.mCollapsibleMenuOpen:
                dlog.client_print("==== ESC pressed, close CollapsibleMenu ====")
                self.CloseCollapsibleMenu()
            elif self.mCardToggleOpen:
                dlog.client_print("==== ESC pressed, close CardToggle ====")
                self.CloseCardToggle()
            elif self.mPopUpOpen:
                dlog.client_print("==== ESC pressed, close PopUp only ====")
                self.ClosePopUp()
            elif self.mSettingsUIOpen:
                dlog.client_print("==== ESC pressed, close SettingsUI ====")
                clientApi.PopScreen()
                # 立即置 False 防重复 Pop（PopScreenEvent 异步到达）
                self.mSettingsUIOpen = False

    def OnCustomKeyPressed(self, args):
        """
        监听 RegisterCustomKeyMapping 注册的自定义按键（可在游戏设置中改键）。
        """
        name = args.get('name', '')
        isDown = args.get('isDown', '')
        dlog.client_print("==== OnCustomKeyPressInGame name: %s isDown: %s settingsOpen: %s ====" % (
            name, isDown, self.mSettingsUIOpen
        ))
        if name == '打开设置' and str(isDown) == '1' and not self.mSettingsUIOpen:
            dlog.client_print("==== custom key pressed: open settings ====")
            self.OpenSettings()

    def OnOpenSettingsFromCommand(self, args):
        """
        服务端通过 /setting_open 命令通知客户端打开设置 UI。

        跳转前会抛出 SettingsNavigateEvent 供外部模组监听/拦截：
        - 若命中跳转拦截回调（RegNavigateBlockCallback 已注册且返回 True），
          则弹提示"跳转已被拦截"，不再执行跳转。
        """
        # 空字符串转为 None，与 OpenSettings 函数行为一致
        main_card_id = args.get("main_card_id", "") or None
        middle_card_id = args.get("middle_card_id", "") or None
        sub_key = args.get("sub_key", "") or None
        playerId = clientApi.GetLocalPlayerId()
        dlog.client_print("==== OnOpenSettingsFromCommand: main=%s sub=%s middle=%s ====" % (
            main_card_id, sub_key, middle_card_id
        ))

        # 1. 抛出跳转前置事件，外部模组可监听做自定义处理
        from CardRegistry import SettingsNavigateEvent
        navData = self.CreateEventData()
        navData["playerId"] = playerId
        navData["main_card_id"] = main_card_id
        navData["sub_key"] = sub_key
        navData["middle_card_id"] = middle_card_id
        self.BroadcastEvent(SettingsNavigateEvent, navData)

        # 2. 检查是否被外部模组拦截（返回 (是否拦截, 提示文案)）
        from CardRegistry import IsNavigateBlocked
        is_blocked, block_msg = IsNavigateBlocked(
            playerId, main_card_id, sub_key, middle_card_id
        )
        if is_blocked:
            dlog.client_print("==== /setting_open: 跳转被拦截，忽略 ====")
            try:
                from CardRegistryApi import ShowToast, ToastUnder
                ShowToast(ToastUnder, block_msg)
            except Exception as e:
                dlog.client_print("==== show block toast error: %s ====" % str(e))
            return

        self.OpenSettings(main_card_id, sub_key, middle_card_id)

    # ===== 服务端全局日志开关相关（由 setting.py 的服务端调试分类使用）=====
    def SendServerLogRequest(self):
        """请求服务端下发全局日志开关值 + 自身 OP 状态（用于同步开关值与锁定）。"""
        try:
            data = self.CreateEventData()
            data['playerId'] = clientApi.GetLocalPlayerId()
            self.NotifyToServer("Script_NeteaseMod9sPMlz0K_ReqServerLog", data)
        except Exception as e:
            dlog.client_print("==== SendServerLogRequest error: %s ====" % str(e))

    def SendServerLogEnabled(self, enabled):
        """通知服务端修改全局日志开关（服务端自行鉴权 OP，非 OP 会被忽略）。"""
        try:
            data = self.CreateEventData()
            data['playerId'] = clientApi.GetLocalPlayerId()
            data['enabled'] = bool(enabled)
            self.NotifyToServer("Script_NeteaseMod9sPMlz0K_SetServerLog", data)
        except Exception as e:
            dlog.client_print("==== SendServerLogEnabled error: %s ====" % str(e))

    def OnServerLogSync(self, args):
        """服务端下发全局日志开关状态：同步到当前可见的服务端调试开关。"""
        enabled = bool(args.get('enabled', False))
        is_op = bool(args.get('is_op', False))
        if self.mSettingsScreenNode:
            self.mSettingsScreenNode.ApplyServerLogSwitch(enabled, is_op)

    def NotifyResetGroup(self, sub_key, middle_card_id):
        """通知服务端重置指定服务端分组为默认（服务端鉴权 OP 并广播全服）。

        参考飞行之羽模组（FlyArmor）的"服务端权威重置"：客户端本地重置完成后，
        由服务端重置权威默认值并广播，保证其他在线玩家的 UI 同步刷新。
        """
        try:
            data = self.CreateEventData()
            data['playerId'] = clientApi.GetLocalPlayerId()
            data['sub_key'] = sub_key
            data['middle_card_id'] = middle_card_id
            self.NotifyToServer("Script_NeteaseMod9sPMlz0K_ResetGroup", data)
        except Exception as e:
            dlog.client_print("==== NotifyResetGroup error: %s ====" % str(e))

    # ===== 调试日志导出（复制到剪贴板） =====
    def CopyClientLogToClipboard(self, count):
        """复制最近 count 条客户端调试日志到剪贴板，并给出提示。"""
        try:
            text = dlog.format_client_history(count or 200)
            self._WriteClipboard(text, "客户端")
        except Exception as e:
            dlog.client_print("==== CopyClientLogToClipboard error: %s ====" % str(e))

    def RequestServerLogDump(self, count):
        """请求服务端返回最近 count 条服务端日志（回执由 OnServerLogDumpResp 复制）。"""
        try:
            data = self.CreateEventData()
            data['playerId'] = clientApi.GetLocalPlayerId()
            data['count'] = int(count or 200)
            self.NotifyToServer("Script_NeteaseMod9sPMlz0K_ReqServerLogDump", data)
        except Exception as e:
            dlog.client_print("==== RequestServerLogDump error: %s ====" % str(e))

    def OnServerLogDumpResp(self, args):
        """服务端返回的服务端日志：复制到本机剪贴板 + 提示。"""
        if args.get('playerId', '') != clientApi.GetLocalPlayerId():
            return
        self._WriteClipboard(args.get('lines', ''), "服务端")

    def _WriteClipboard(self, text, side):
        """把文本写入系统剪贴板（客户端 GameComponentClient），并弹底部 toast 提示。"""
        content = text if isinstance(text, basestring) else ""
        lines = content.split('\n') if content else []
        try:
            comp = clientApi.GetEngineCompFactory().CreateGame(clientApi.GetLevelId())
            comp.SetClipboardContent(content)
        except Exception as e:
            dlog.client_print("==== set clipboard error: %s ====" % str(e))
        try:
            from CardRegistryApi import ShowToast, ToastUnder
            ShowToast(ToastUnder, "已复制%s最近%d条日志到剪贴板" % (side, len(lines)))
        except Exception as e:
            dlog.client_print("==== toast copy result error: %s ====" % str(e))

    def RegisterSettingsScreenNode(self, screenNode):
        self.mSettingsScreenNode = screenNode

    def UnregisterSettingsScreenNode(self, screenNode):
        if self.mSettingsScreenNode is screenNode:
            self.mSettingsScreenNode = None

    def _OnCardChanged(self):
        """主卡片注册/注销回调——自动刷新 UI（若设置界面已打开）。"""
        if self.mSettingsScreenNode and hasattr(self.mSettingsScreenNode, 'RebuildMainCards'):
            self.mSettingsScreenNode.RebuildMainCards()

    def OnScriptTickClient(self):
        if self.mSettingsScreenNode and hasattr(self.mSettingsScreenNode, 'OnTick'):
            self.mSettingsScreenNode.OnTick()
    def OnUIInitFinished(self, args=None):
        if self.mUiCreated:
            return
        self.mUiCreated = True

        # 加载设置项状态（本地存储 ConfigCompClient）
        try:
            LoadSettingData()
        except Exception as e:
            dlog.client_print("==== LoadSettingData error: %s ====" % str(e))

        clientApi.RegisterUI(
            'Script_NeteaseMod9sPMlz0K',
            'Test1UI',
            'Script_NeteaseMod9sPMlz0K.Client.Test1ScreenNode',
            'setting.main'
        )

        clientApi.RegisterUI(
            'Script_NeteaseMod9sPMlz0K',
            'SettingsUI',
            'Script_NeteaseMod9sPMlz0K.Client.SettingsScreenNode',
            'setting.main'
        )
        dlog.client_print("==== SettingsUI registered ====")

        clientApi.RegisterUI(
            'Script_NeteaseMod9sPMlz0K',
            'PopUpUI',
            'Script_NeteaseMod9sPMlz0K.Client.PopUpScreenNode',
            'pop_up.main'
        )
        dlog.client_print("==== PopUpUI registered ====")

        clientApi.RegisterUI(
            'Script_NeteaseMod9sPMlz0K',
            'PopUpScrollUI',
            'Script_NeteaseMod9sPMlz0K.Client.PopUpScrollScreenNode',
            'pop_up.main_scroll'
        )
        dlog.client_print("==== PopUpScrollUI registered ====")

        clientApi.RegisterUI(
            'Script_NeteaseMod9sPMlz0K',
            'CollapsibleMenuUI',
            'Script_NeteaseMod9sPMlz0K.Client.CollapsibleMenuScreenNode',
            'pop_up.collapsible_menu'
        )
        dlog.client_print("==== CollapsibleMenuUI registered ====")

        clientApi.RegisterUI(
            'Script_NeteaseMod9sPMlz0K',
            'CardToggleUI',
            'Script_NeteaseMod9sPMlz0K.Client.CardToggleScreenNode',
            'pop_up.card_toggle_panel'
        )
        dlog.client_print("==== CardToggleUI registered ====")

        # 注册 Toast 系统
        try:
            from Toast import RegisterToastScreens
            RegisterToastScreens()
            dlog.client_print("==== Toast screens registered ====")
        except Exception as e:
            dlog.client_print("==== Toast register error: %s ====" % str(e))

        # 注册"设置配置"主卡片（延迟导入，允许新增/改名而不改本文件）
        try:
            from setting import RegisterSettingsConfig
            RegisterSettingsConfig()
            dlog.client_print("==== settings_config main card registered ====")
        except Exception as e:
            dlog.client_print("==== settings_config register error: %s ====" % str(e))

        self.InitKeyBindings()
        self._RegisterOfficialSettingsEntry()

    def InitKeyBindings(self):
        # 注册自定义按键映射：玩家可在游戏设置中修改该按键
        try:
            comp = clientApi.GetEngineCompFactory().CreatePlayerView(clientApi.GetLevelId())
            success = comp.RegisterCustomKeyMapping("打开设置", 85, "模组设置")
            dlog.client_print("==== RegisterCustomKeyMapping open_settings: %s ====" % str(success))
        except Exception as e:
            dlog.client_print("==== RegisterCustomKeyMapping error: %s ====" % str(e))

    def _RegisterOfficialSettingsEntry(self):
        """
        在官方"暂停菜单 -> 模组"的通用设置界面注册一个按钮。
        点击该按钮会关闭官方通用设置界面并打开本模组的设置界面。
        """
        try:
            comp = clientApi.GetEngineCompFactory().CreateNeteaseWindow(clientApi.GetLevelId())
            # 参数1：开发环境为唯一命名空间；正式服需改为开平上传模组后的 ItemID
            setting_inst = comp.RegisterSettingInst(
                "Script_NeteaseMod9sPMlz0K", "模组设置", "textures/ui/icon_setting"
            )
            if setting_inst:
                setting_inst.AddButton(
                    "open_my_settings",
                    "打开本模组的自定义设置界面",
                    "打开设置",
                    self._OnOfficialSettingButtonClick,
                    1
                )
                dlog.client_print("==== official settings button registered ====")
            else:
                dlog.client_print("==== RegisterSettingInst returned None ====")
        except Exception as e:
            dlog.client_print("==== Register official settings entry error: %s ====" % str(e))

    def _OnOfficialSettingButtonClick(self, key, value=None):
        """官方通用设置按钮回调：关闭官方设置界面，稍后打开本模组设置界面。"""
        dlog.client_print("==== official setting button click: %s ====" % str(key))
        try:
            comp = clientApi.GetEngineCompFactory().CreateNeteaseWindow(clientApi.GetLevelId())
            comp.CloseSettingUI()
        except Exception as e:
            dlog.client_print("==== CloseSettingUI error: %s ====" % str(e))
        # 等官方界面关闭完成后再打开本模组设置界面，避免压栈冲突
        game_comp = clientApi.GetEngineCompFactory().CreateGame(clientApi.GetLevelId())
        game_comp.AddTimer(0.15, self._OpenMySettings)

    def _OpenMySettings(self):
        """官方通用设置界面关闭后，打开本模组设置界面。"""
        self.OpenSettings()

    def OpenSettings(self, main_card_id=None, sub_key=None, middle_card_id=None):
        """
        打开设置 UI，可选导航到指定卡片。

        :param main_card_id:  主卡片 ID（如 "basic_settings"），传 None 则不导航
        :param sub_key:       子卡片 key，可选 "client" 或 "server"
        :param middle_card_id: 中间卡片 ID（如 "client_opt_a"）
        """
        dlog.client_print("==== OpenSettings: main=%s sub=%s middle=%s ====" % (
            main_card_id, sub_key, middle_card_id
        ))
        if self.mSettingsUIOpen or self.mSettingsScreenNode is not None:
            # UI 已打开（标志或实际 ScreenNode 任一命中），直接导航，避免重复 PushScreen
            if main_card_id and self.mSettingsScreenNode:
                self.mSettingsScreenNode.SetPendingNavigation(main_card_id, sub_key, middle_card_id)
            return
        self.mPendingNavigation = (main_card_id, sub_key, middle_card_id)
        clientApi.PushScreen('Script_NeteaseMod9sPMlz0K', 'SettingsUI')

    def ShowPopUp(self, popup_id, force_scroll=None):
        """
        打开指定 ID 的弹窗（须先 RegisterPopUp 注册）。
        若弹窗已打开则刷新内容；否则压栈新弹窗界面。

        :param popup_id:    弹窗唯一标识符
        :param force_scroll: True 强制使用滚动版；False 强制普通版；
                             None 自动根据内容长度决定（默认）
        """
        from CardRegistry import GetPopUp, PopUpOpenEvent
        data = GetPopUp(popup_id)
        if not data:
            dlog.client_print("==== ShowPopUp: popup '%s' not registered ====" % popup_id)
            return False
        self.mCurrentPopUp = data
        if self.mPopUpOpen:
            # 弹窗已打开：重新 Push 会破坏场景栈，直接复用现有 ScreenNode 刷新
            dlog.client_print("==== ShowPopUp: popup already open, refresh content ====")
            if self.mPopUpScreenNode:
                try:
                    self.mPopUpScreenNode._ApplyPopUp()
                except Exception as e:
                    dlog.client_print("==== ShowPopUp: refresh error: %s ====" % str(e))
            return True
        useScroll = self._DecideScroll(data, force_scroll)
        # 弹窗即将压栈：设置界面将失去栈顶，标记"弹窗会话"，关闭时 OnActive 跳过重建保留详情
        self.mReturningFromPopUp = True
        if useScroll:
            clientApi.PushScreen('Script_NeteaseMod9sPMlz0K', 'PopUpScrollUI')
        else:
            clientApi.PushScreen('Script_NeteaseMod9sPMlz0K', 'PopUpUI')
        self.mPopUpOpen = True
        eventData = self.CreateEventData()
        eventData["playerId"] = clientApi.GetLocalPlayerId()
        eventData["popupId"] = popup_id
        eventData["useScroll"] = useScroll
        self.BroadcastEvent(PopUpOpenEvent, eventData)
        return True

    def _DecideScroll(self, data, force_scroll):
        """
        决定弹窗是否使用滚动版。

        优先级：force_scroll 显式指定 > 内容自动判断。
        自动判断：估算内容需要的总显示行数（按换行与每行约 30 字符计算），
        超过普通弹窗内容区可容纳的行数（约 4 行）即使用滚动版。
        """
        if force_scroll is not None:
            return bool(force_scroll)
        content = data.get("content", "") or ""
        if not content:
            return False
        lines = 0
        for seg in content.split("\n"):
            if not seg:
                lines += 1
            else:
                lines += max(1, (len(seg) + 29) // 30)
        return lines > 4

    def ClosePopUp(self):
        """关闭当前弹窗（PopScreen 返回上一层）。"""
        if self.mPopUpOpen:
            clientApi.PopScreen()
            self.mPopUpOpen = False

    def ShowCollapsibleMenu(self, menu_id, item):
        """
        打开指定 ID 的折叠菜单弹窗（须先 RegisterCollapsibleMenu 注册卡片）。

        :param menu_id: 折叠菜单 ID
        :param item:    关联的 CollapsibleMenuContentItem（读取/更新选中状态与回调）
        :returns:       True 打开成功；False 菜单未注册
        """
        from CardRegistry import GetCollapsibleMenu
        data = GetCollapsibleMenu(menu_id)
        if not data:
            dlog.client_print("==== ShowCollapsibleMenu: menu '%s' not registered ====" % menu_id)
            return False
        self.mCurrentCollapsibleMenu = data
        self.mCurrentCollapsibleItem = item
        if self.mCollapsibleMenuOpen:
            # 已打开：重新 Push 会破坏场景栈，复用现有 ScreenNode 刷新内容
            dlog.client_print("==== ShowCollapsibleMenu: menu already open, refresh content ====")
            if self.mCollapsibleMenuScreenNode:
                try:
                    self.mCollapsibleMenuScreenNode._ApplyMenu()
                except Exception as e:
                    dlog.client_print("==== ShowCollapsibleMenu refresh error: %s ====" % str(e))
            return True
        # 折叠菜单即将压栈：设置界面将失去栈顶，标记"弹窗会话"，关闭时 OnActive 跳过重建保留详情
        self.mReturningFromPopUp = True
        clientApi.PushScreen('Script_NeteaseMod9sPMlz0K', 'CollapsibleMenuUI')
        self.mCollapsibleMenuOpen = True
        return True

    def CloseCollapsibleMenu(self):
        """关闭当前折叠菜单弹窗（PopScreen 返回上一层）。"""
        if self.mCollapsibleMenuOpen:
            clientApi.PopScreen()
            self.mCollapsibleMenuOpen = False

    def OpenCardToggle(self, toggle_id):
        """打开组合开关弹窗。供普通按钮 on_click / 外部模组调用。

        数据集须先用 RegisterCardToggle/AddCardToggleOption 注册。
        """
        from CardRegistry import GetCardToggle
        data = GetCardToggle(toggle_id)
        dlog.client_print("==== OpenCardToggle invoked: toggle=%s data=%s mOpen=%s ====" % (
            toggle_id, bool(data), self.mCardToggleOpen))
        if not data:
            dlog.client_print("==== OpenCardToggle: toggle '%s' not registered ====" % toggle_id)
            return False
        self.mCurrentCardToggle = data
        self.mCurrentToggleId = toggle_id
        if self.mCardToggleOpen:
            # 已打开：复用现有 ScreenNode 刷新内容
            dlog.client_print("==== OpenCardToggle: already open, refresh ====")
            if self.mCardToggleScreenNode:
                try:
                    self.mCardToggleScreenNode._ApplyPanel()
                except Exception as e:
                    dlog.client_print("==== OpenCardToggle refresh error: %s ====" % str(e))
            return True
        # 组合开关即将压栈：设置界面将失去栈顶，标记"弹窗会话"
        self.mReturningFromPopUp = True
        clientApi.PushScreen('Script_NeteaseMod9sPMlz0K', 'CardToggleUI')
        self.mCardToggleOpen = True
        return True

    def CloseCardToggle(self):
        """关闭当前组合开关弹窗（PopScreen 返回上一层）。关闭前先持久化当前开关状态。"""
        if self.mCardToggleOpen:
            # 弹窗子 screen 不保证 OnTick 被调用，故在关闭时一次性读当前状态写入存储
            if self.mCardToggleScreenNode:
                try:
                    self.mCardToggleScreenNode._PersistStates()
                except Exception as e:
                    dlog.client_print("==== CloseCardToggle persist error: %s ====" % str(e))
            clientApi.PopScreen()
            self.mCardToggleOpen = False

    def SetLocked(self, item_id_or_path, locked):
        """
        统一设置指定内容项（按钮/开关/edit_box）的锁定状态（等效于 mSettingsScreenNode.SetLocked）。
        支持传入右侧面板内容项 ID 或 edit_box 控件完整路径。
        """
        if self.mSettingsScreenNode:
            self.mSettingsScreenNode.SetLocked(item_id_or_path, locked)
        else:
            dlog.client_print("==== SetLocked: settings screen not open ====")


class Test1ScreenNode(ScreenNode):

    def __init__(self, namespace, name, param):
        ScreenNode.__init__(self, namespace, name, param)
        self.mWrappers = []
        self.mCardBtns = []
        self.mSubPanels = []
        self.mSubCards = {}
        self.mSubCardStates = {}
        self.mSubCardPressing = None  # (index, key)
        self.mSelectedIndex = -1
        self.mScrollContent = None

    def Create(self):
        dlog.client_print("==== Test1ScreenNode.Create called ====")
        self.mScrollContent = self.GetBaseUIControl("/groung/mods/scroll_content")
        if not self.mScrollContent:
            dlog.client_print("==== scroll_content not found ====")
            return

        dlog.client_print("==== scroll_content found, creating cards ====")
        testCards = [
            ("基础设置", "textures/ui/icon_setting"),
            ("音量调节", "textures/ui/icon_volume"),
            ("画质选项", "textures/ui/icon_display"),
            ("测试卡片4", "textures/ui/icon_setting"),
            ("测试卡片5", "textures/ui/icon_volume"),
        ]
        for text, icon in testCards:
            self.AddCard(text, icon)
        dlog.client_print("==== test cards created, total: %d ====" % len(self.mWrappers))

    def Init(self):
        pass

    def AddCard(self, text, icon):
        if not self.mScrollContent:
            return -1
        index = len(self.mWrappers)
        try:
            wrapper = self.CreateChildControl(
                'setting.card_group',
                'card_%d' % index,
                self.mScrollContent,
                True
            )
        except Exception as e:
            dlog.client_print("==== CreateCardGroup error: %s ====" % str(e))
            return -1
        if not wrapper:
            dlog.client_print("==== card_group_%d returned None ====" % index)
            return -1

        btnCtrl = wrapper.GetChildByName('card_btn')
        if not btnCtrl:
            dlog.client_print("==== card_btn not found in card_%d ====" % index)
            return -1

        try:
            labelCtrl = btnCtrl.GetChildByName('name')
            if labelCtrl:
                labelCtrl.asLabel().SetText(text)
        except Exception as e:
            dlog.client_print("==== set name error: %s ====" % str(e))

        try:
            iconCtrl = btnCtrl.GetChildByName('icon')
            if iconCtrl:
                iconCtrl.SetPropertyBag({"texture": icon})
        except Exception as e:
            dlog.client_print("==== set icon error: %s ====" % str(e))

        try:
            btn = btnCtrl.asButton()
            btn.AddTouchEventParams({})
            btn.SetButtonTouchDownCallback(self.OnCardClick)
        except Exception as e:
            dlog.client_print("==== touch setup error: %s ====" % str(e))

        subPanel = wrapper.GetChildByName('sub_panel')

        self.mWrappers.append(wrapper)
        self.mCardBtns.append(btnCtrl)
        self.mSubPanels.append(subPanel)
        self.mSubCards[index] = {}
        self.mSubCardStates[index] = {}
        dlog.client_print("==== card_%d created: %s ====" % (index, text))
        return index

    def OnCardClick(self, args):
        cardPath = args.get('ButtonPath', '')
        dlog.client_print("==== OnCardClick path: %s ====" % cardPath)
        for i in range(len(self.mCardBtns)):
            if 'card_%d/card_btn' % i in cardPath:
                if self.mSelectedIndex == i:
                    return ViewRequest.Nothing

                self.HideSubCards(self.mSelectedIndex)

                if self.mSelectedIndex >= 0:
                    self.SetCardState(self.mSelectedIndex, False)

                self.mSelectedIndex = i
                self.SetCardState(i, True)
                self.ShowSubCards(i)

                dlog.client_print("==== card_%d selected ====" % i)
                break
        return ViewRequest.Nothing

    def SetCardState(self, index, selected):
        card = self.mCardBtns[index]
        normalCtrl = card.GetChildByName('normal')
        hoverCtrl = card.GetChildByName('hover')
        pressCtrl = card.GetChildByName('press')
        if selected:
            if normalCtrl:
                normalCtrl.SetVisible(False)
            if hoverCtrl:
                hoverCtrl.SetVisible(False)
            if pressCtrl:
                pressCtrl.SetVisible(True)
        else:
            if normalCtrl:
                normalCtrl.SetVisible(True)
            if pressCtrl:
                pressCtrl.SetVisible(False)

    def ShowSubCards(self, index):
        if index < 0 or index >= len(self.mSubPanels):
            return
        if self.mSubCards.get(index):
            for key, ctrl in self.mSubCards[index].items():
                ctrl.SetVisible(True)
                # 重新初始化 backdrop UV（动画状态已重置）
                backdropCtrl = ctrl.GetChildByName('icon_backdrop')
                if backdropCtrl:
                    backdropImg = backdropCtrl.asImage()
                    if backdropImg:
                        backdropImg.SetSpriteUV((0, 0))
                        backdropImg.SetSpriteUVSize((self.mBackdropFrameSize, self.mBackdropFrameSize))
                        self.mSubCardBackdropCtrls[(index, key)] = backdropImg
                # 重置动画状态
                self.mSubCardAnimStates[(index, key)] = {
                    "frame": 0,
                    "timer": 0,
                    "playing": False
                }
                if self.mSubCardStates[index][key]:
                    self.mSubCardStates[index][key] = False
                    self.SetSubCardState(ctrl, False)
            return
        subPanel = self.mSubPanels[index]
        if not subPanel:
            return
        for key, text in [("client", "客户端"), ("server", "服务端")]:
            try:
                ctrl = self.CreateChildControl(
                    'setting.sub_card',
                    'sub_%d_%s' % (index, key),
                    subPanel,
                    True
                )
                if ctrl:
                    label = ctrl.GetChildByName('sub_label')
                    if label:
                        label.asLabel().SetText(text)
                    backdropCtrl = ctrl.GetChildByName('icon_backdrop')
                    if backdropCtrl:
                        iconCtrl = backdropCtrl.GetChildByName('icon')
                        if iconCtrl:
                            iconPath = "textures/ui/sidebar_icons/addon" if key == "client" else "textures/ui/sidebar_icons/realms"
                            img = iconCtrl.asImage()
                            if img:
                                img.SetSprite(iconPath)
                                dlog.client_print("==== sub_card icon set: %s -> %s ====" % (key, iconPath))
                            else:
                                dlog.client_print("==== sub_card icon asImage failed ====")
                        else:
                            dlog.client_print("==== sub_card icon not found inside icon_backdrop ====")
                    else:
                        dlog.client_print("==== sub_card icon_backdrop not found ====")
                    btn = ctrl.asButton()
                    if btn:
                        btn.AddTouchEventParams({})
                        btn.SetButtonTouchDownCallback(self.OnSubCardTouchDown)
                        btn.SetButtonTouchUpCallback(self.OnSubCardTouchUp)
                    self.mSubCards[index][key] = ctrl
                    self.mSubCardStates[index][key] = False
                    self.SetSubCardVisualState(ctrl, "normal")
                    dlog.client_print("==== sub_card created: %s ====" % text)
            except Exception as e:
                dlog.client_print("==== sub_card error: %s ====" % str(e))

    def HideSubCards(self, index):
        if index < 0:
            return
        if index in self.mSubCards:
            for key, ctrl in self.mSubCards[index].items():
                ctrl.SetVisible(False)
                # 重置该子卡片的动画状态
                state = self.mSubCardAnimStates.get((index, key))
                if state and state["playing"]:
                    state["frame"] = 0
                    state["timer"] = 0
                    state["playing"] = False
                    self._ApplySubCardBackdropFrame(index, key, 0)

    def SetSubCardVisualState(self, ctrl, state):
        normalCtrl = ctrl.GetChildByName('normal_bg')
        pressingCtrl = ctrl.GetChildByName('pressing_bg')
        pressCtrl = ctrl.GetChildByName('press_bg')
        if normalCtrl:
            normalCtrl.SetVisible(state == "normal")
        if pressingCtrl:
            pressingCtrl.SetVisible(state == "pressing")
        if pressCtrl:
            pressCtrl.SetVisible(state == "selected")

    def SetSubCardState(self, ctrl, selected):
        self.SetSubCardVisualState(ctrl, "selected" if selected else "normal")

    def ParseSubCardPath(self, subPath):
        if 'sub_' not in subPath:
            return None
        parts = subPath.split('/')
        if not parts:
            return None
        name = parts[-1]
        if not name.startswith('sub_'):
            return None
        tokens = name.split('_')
        if len(tokens) < 3:
            return None
        try:
            index = int(tokens[1])
            key = tokens[2]
        except (ValueError, IndexError):
            return None
        if index not in self.mSubCards or key not in self.mSubCards[index]:
            return None
        return (index, key)

    def OnSubCardTouchDown(self, args):
        if self.mSubCardPressing is not None:
            return ViewRequest.Nothing
        subPath = args.get('ButtonPath', '')
        result = self.ParseSubCardPath(subPath)
        if not result:
            return ViewRequest.Nothing
        index, key = result
        self.mSubCardPressing = (index, key)
        self.SetSubCardVisualState(self.mSubCards[index][key], "pressing")
        dlog.client_print("==== Test1 sub_card touch down: sub_%d_%s ====" % (index, key))
        return ViewRequest.Nothing

    def OnSubCardTouchUp(self, args):
        subPath = args.get('ButtonPath', '')
        prevPressing = self.mSubCardPressing
        self.mSubCardPressing = None
        result = self.ParseSubCardPath(subPath)
        if not result:
            if prevPressing:
                index, key = prevPressing
                self.SetSubCardVisualState(
                    self.mSubCards[index][key],
                    "selected" if self.mSubCardStates[index][key] else "normal"
                )
            return ViewRequest.Nothing
        index, key = result
        if prevPressing and prevPressing != (index, key):
            pi, pk = prevPressing
            self.SetSubCardVisualState(
                self.mSubCards[pi][pk],
                "selected" if self.mSubCardStates[pi][pk] else "normal"
            )
        if prevPressing == (index, key):
            self._StartSubCardBackdropAnimation(index, key)
            self.SelectSubCard(index, key)
        else:
            self.SetSubCardVisualState(
                self.mSubCards[index][key],
                "selected" if self.mSubCardStates[index][key] else "normal"
            )
        return ViewRequest.Nothing

    def SelectSubCard(self, index, key):
        if self.mSubCardStates[index][key]:
            self.SetSubCardVisualState(self.mSubCards[index][key], "selected")
            return
        for otherKey in self.mSubCardStates[index]:
            if otherKey != key and self.mSubCardStates[index][otherKey]:
                self.mSubCardStates[index][otherKey] = False
                self.SetSubCardVisualState(self.mSubCards[index][otherKey], "normal")
        self.mSubCardStates[index][key] = True
        self.SetSubCardVisualState(self.mSubCards[index][key], "selected")
        dlog.client_print("==== Test1 sub_card sub_%d_%s selected ====" % (index, key))


class SettingsScreenNode(ScreenNode):

    def __init__(self, namespace, name, param):
        ScreenNode.__init__(self, namespace, name, param)
        self.mWrappers = []
        self.mCardBtns = []
        self.mSubPanels = []
        self.mSubCards = {}
        self.mSubCardStates = {}
        self.mCardIcons = []
        self.mDefaultIcon = "textures/ui/icon_setting"
        self.mSelectedIndex = -1
        self.mScrollContent = None
        self.mBasePath = None
        self.mPreviewIcon = None
        self.mMiddleCtrl = None
        self.mMiddleOpen = False
        self.mMiddleHasAnimation = False
        self.mRightCtrl = None
        self.mRightOpen = False
        self.mRightHasAnimation = False
        self.mRightScrollContent = None
        self.mRightScrollContentPath = None
        self.mRightContentCtrls = []  # 右侧内容控件列表
        self.mRightBtnCtrlMap = {}    # itemId -> 右侧按钮控件
        self.mRightLockCtrlMap = {}   # itemId -> 右侧按钮的 lock 控件
        self.mRightSwitchCtrlMap = {} # itemId -> 右侧开关控件
        self.mRightSwitchStates = {}  # itemId -> 上次已知开关状态 (True/False)
        self.mRightEditBoxCtrlMap = {} # itemId -> 右侧编辑框控件
        self.mRightSliderCtrlMap = {} # itemId -> 右侧滑块控件（SliderUIControl）
        self.mRightSliderStates = {}  # itemId -> 上次已知滑块值 (float)
        self.mRightSliderValueMap = {} # itemId -> 滑块数值显示 label 控件
        self.mCollapsibleMenuTextMap = {} # itemId -> 折叠菜单按钮文字 label 控件（选择后实时更新）
        self.mRightCollapsibleMenuCtrlMap = {} # itemId -> 折叠菜单按钮控件（锁定控制用）
        self.mRightSliderBaseMap = {} # itemId -> 滑块基础控件（BaseUIControl）
        self.mRightSliderBgMap = {} # itemId -> 滑块锁定灰层控件（slider_lock_bg，运行时动态创建）
        self.mRightSliderLockOverlayMap = {} # itemId -> 滑块锁定输入拦截层控件（lock_overlay，运行时动态创建）
        self.mCurrentSliderItemLocked = False # 当前右侧显示的 slider 项锁定状态（供原生 #settings_slider_enabled 绑定）
        self.mRightFinishedStates = {}  # group -> set(item_id)，记录已 finish 的按钮
        self.mCurrentRightGroup = None  # 当前右侧面板对应的 (main, sub, middle)
        self.mCurrentSubKey = None      # 当前选中的子卡片 key（client/server）
        # 服务端全局日志开关同步状态
        self.mServerLogSwitchItem = None  # 服务端调试开关 item_id，None 表示当前分组无需同步
        self.mServerLockItems = []        # 服务端调试分类需按 OP 状态锁定/解锁的项 id（复制数量/复制日志）
        self.mNeedServerLogRequest = False  # 服务端调试开关渲染完成后是否请求全局值
        self.mServerLogPending = None       # 尚未应用的 (enabled, is_op) 待处理状态
        self.mServerLockState = None        # 服务端锁项已应用的锁定状态（None=尚未收到 OP 信息）
        self.mRightPendingItems = []  # 等待延迟创建的右侧内容项数据队列
        self.mRightContentDelayTimer = 0
        self.mRightContentDelayInterval = 2  # 每2帧创建一项，避免瞬间加载过多卡顿
        self.mRightFadingInCtrls = []  # [(ctrl, current_alpha), ...] 淡入队列
        self.mRightFadingOutCtrls = []  # [(ctrl, current_alpha), ...] 淡出队列
        self.mRightShowPending = None   # 等待旧内容淡出后显示的右侧内容项
        self.mRightShowDelayTimer = 0   # 旧内容淡出后额外等待帧数
        self.mRightFadeInSpeed = 0.08   # 淡入每帧透明度变化量
        self.mRightFadeOutSpeed = 0.18  # 淡出每帧透明度变化量，更快
        self.mRightEditBoxLockTextMap = {}   # itemId -> lock_text label 控件
        self.mRightEditBoxLockTextCache = {} # itemId -> 上次显示的 lock 文字
        self.mMiddleScrollContent = None
        self.mMiddleOptionCtrls = []
        self.mMiddleCardIds = []        # 与 mMiddleOptionCtrls 一一对应，记录 middle_card_id
        self.mMiddleCardNames = []  # 与 mMiddleOptionCtrls 一一对应，存储控制名
        self.mMiddleSelectedIndex = -1
        self.mPressingIndex = -1
        self.mMiddlePressingIndex = -1
        self.mSubCardPressing = None  # (index, key)
        self.mPendingMiddleCards = []  # 等待延迟创建的中间卡片数据队列
        self.mMiddleCardDelayTimer = 0
        self.mMiddleCardDelayInterval = 2  # 每2帧创建一张，避免瞬间加载过多卡顿
        self.mMiddleFadingInCtrls = []  # [(ctrl, current_alpha), ...] 淡入队列
        self.mMiddleFadingOutCtrls = []  # [(ctrl, current_alpha), ...] 淡出队列
        self.mMiddleShowPending = None   # 等待旧卡片淡出后显示的中间卡片数据
        self.mMiddleShowDelayTimer = 0   # 旧卡片淡出后额外等待帧数
        self.mMiddleFadeInSpeed = 0.08   # 淡入每帧透明度变化量
        self.mMiddleFadeOutSpeed = 0.18  # 淡出每帧透明度变化量，更快
        self.mSubCardsFadingOut = {}  # index -> {key: alpha} 子卡片淡出队列
        self.mSubCardFadeSpeed = 0.18  # 子卡片淡出速度
        self.mMainCardFade = {}  # index -> {target: normal/selected, alpha: float} 主卡片状态渐隐
        self.mMainCardFadeSpeed = 0.18  # 主卡片渐隐速度
        self.mCardIdToIndex = {}   # main_card_id -> index
        self.mIndexToCardId = []   # index -> main_card_id
        self.mMainCardPending = []  # [(name, icon, card_id), ...] 待懒加载创建的主卡片数据
        self.mMainCardPerTick = 4  # 每帧创建的主卡片数量（加速进入）
        self.mMainCardSnapshot = None  # 主卡片注册表快照，用于打开时跳过无变化的重建
        # 面板滑入动画延迟播放：首次显示时刚 SetVisible 的控件立即 PlayAnimation
        # 会停在 from（初始位），改为 SetAnimation 后下一帧 OnTick 再 Play
        self.mMiddlePendingPlay = False
        self.mRightPendingPlay = False
        self.mMainCardFadingIn = []  # [(wrapper, current_alpha), ...] 主卡片淡入队列
        self.mMainCardFadeInSpeed = 0.3  # 主卡片快速淡入速度
        # "显示"分类：设置项与中间卡片的缓入/缓出动画开关（默认开）
        self.mEnableFadeAnim = True
        self.mEnableEnterAnim = True   # 中间/右边面板的滑入进入动画（默认开）
        try:
            from setting import (DISPLAY_CATEGORY_ID, SWITCH_FADE_ANIM, SWITCH_ENTER_ANIM)
            self.mEnableFadeAnim = bool(GetSettingValue(
                "settings_config", "client", DISPLAY_CATEGORY_ID, SWITCH_FADE_ANIM,
                default=True))
            self.mEnableEnterAnim = bool(GetSettingValue(
                "settings_config", "client", DISPLAY_CATEGORY_ID, SWITCH_ENTER_ANIM,
                default=True))
        except Exception:
            self.mEnableFadeAnim = True
            self.mEnableEnterAnim = True
        self.mNavInstant = None    # 导航定位到中间卡片时的"本次打开不播动画"一次性标志
        self.mMiddleCardSeq = 0    # 中间卡片控件名序列号
        self.mPendingNavigation = None      # (main_card_id, sub_key, middle_card_id)
        self.mPendingMiddleCardId = None    # 待选中的中间卡片 ID

        # ===== icon_backdrop 序列帧动画状态 =====
        self.mCardBackdropCtrls = []       # [imageUIControl or None, ...] 与 mCardBtns 一一对应
        self.mBackdropAnimStates = {}      # index -> {frame, timer, playing}
        self.mBackdropFrameCount = 8       # 总帧数
        self.mBackdropFrameInterval = 2    # 每帧间隔帧数（2 tick）
        self.mBackdropFrameSize = 12       # 每帧像素宽度（根据实际精灵图调整）

        # ===== sub_card icon_backdrop 动画状态 =====
        self.mSubCardBackdropCtrls = {}    # (index, key) -> imageUIControl
        self.mSubCardAnimStates = {}       # (index, key) -> {frame, timer, playing}

        # ===== middle_card icon_backdrop 动画状态 =====
        self.mMiddleCardBackdropCtrls = [] # [imageUIControl or None, ...] 与 mMiddleOptionCtrls 一一对应
        self.mMiddleCardAnimStates = {}    # index -> {frame, timer, playing}

        # ===== 透明度控件引用缓存（避免每帧递归 GetChildByName 造成卡顿）=====
        self.mAlphaCtrlCache = {}          # id(ctrl) -> [可设置透明度的子控件列表]

        global _g_ClientSystem
        if _g_ClientSystem:
            _g_ClientSystem.RegisterSettingsScreenNode(self)
            dlog.client_print("==== SettingsScreenNode registered to client system ====")

    def Destroy(self):
        # 重置按压状态，防止残留
        self.mPressingIndex = -1
        self.mMiddlePressingIndex = -1
        self.mSubCardPressing = None
        global _g_ClientSystem
        if _g_ClientSystem:
            _g_ClientSystem.UnregisterSettingsScreenNode(self)
            dlog.client_print("==== SettingsScreenNode unregistered from client system ====")
        # 注销为底部 toast 的内嵌宿主
        try:
            from Toast import unregister_settings_under_host
            unregister_settings_under_host(self)
        except Exception:
            pass
        # 清理内嵌底部提示的停留定时器，避免关闭界面后残留回调
        if getattr(self, "mEmbeddedUnderTimer", None) is not None:
            try:
                comp = clientApi.GetEngineCompFactory().CreateGame(clientApi.GetLevelId())
                comp.KillTimer(self.mEmbeddedUnderTimer)
            except Exception:
                pass
            self.mEmbeddedUnderTimer = None
        try:
            UnregisterContentListener(self._OnContentChanged)
            dlog.client_print("==== content change listener unregistered ====")
        except Exception:
            pass
        try:
            ScreenNode.Destroy(self)
        except Exception:
            pass

    def Create(self):
        dlog.client_print("==== SettingsScreenNode.Create called ====")
        self.mBasePath = self.ExploreAndFindBasePath()
        dlog.client_print("==== SettingsScreenNode: resolved base path: %s ====" % self.mBasePath)

        if self.mBasePath is not None:
            self.mScrollContent = self.FindScrollingContent(self.mBasePath)
        else:
            self.mScrollContent = None

        if self.mScrollContent:
            dlog.client_print("==== scroll_content resolved ====")
        else:
            dlog.client_print("==== SettingsScreenNode: scroll_content not found, will still bind back button ====")

        previewCtrl = self.GetBaseUIControlByBase('/left/icon_under/image')
        if previewCtrl:
            self.mPreviewIcon = previewCtrl.asImage()
            self.UpdatePreviewIcon(self.mDefaultIcon)
            dlog.client_print("==== preview icon bound ====")
        else:
            dlog.client_print("==== preview icon not found ====")

        middleCtrl = self.GetBaseUIControlByBase('/middle')
        if middleCtrl:
            self.mMiddleCtrl = middleCtrl
            dlog.client_print("==== middle panel bound ====")
        else:
            dlog.client_print("==== middle panel not found ====")

        rightCtrl = self.GetBaseUIControlByBase('/right')
        if rightCtrl:
            self.mRightCtrl = rightCtrl
            dlog.client_print("==== right panel bound ====")
        else:
            dlog.client_print("==== right panel not found ====")

        if self.mBasePath is not None:
            self.mMiddleScrollContent = self.FindMiddleScrollingContent(self.mBasePath)
        else:
            self.mMiddleScrollContent = None

        if self.mMiddleScrollContent:
            dlog.client_print("==== middle scroll_content resolved ====")
        else:
            dlog.client_print("==== middle scroll_content not found ====")

        if self.mBasePath is not None:
            self.mRightScrollContent = self.FindRightScrollingContent(self.mBasePath)
        else:
            self.mRightScrollContent = None

        if self.mRightScrollContent:
            dlog.client_print("==== right scroll_content resolved ====")
        else:
            dlog.client_print("==== right scroll_content not found ====")

        # 测试/示例注册项已全部删除。
        # 真实设置项由外部模组通过 CardRegistryApi 提供的受支持接口在运行时注册：
        #   - RegisterMainCard / RegisterMiddleCard      主卡片 / 中间卡片
        #   - RegisterPopUp / RegisterCollapsibleMenu    弹窗 / 下拉菜单
        #   - CreateContentInst(...).AddXXX(...)         内容项（文本/开关/按钮/输入框/滑块等）
        # -> 首次打开设置界面必须在此重建主卡片（网易 SDK 不回调 OnActive，
        #    故不能依赖 OnActive 触发 RebuildMainCards）。

        if self.mScrollContent:
            self.RebuildMainCards()
            dlog.client_print("==== Create: 从注册表重建 %d 张主卡片 ====" % len(self.mWrappers))
        else:
            dlog.client_print("==== Create: scroll_content 未解析，跳过主卡片重建 ====")

        # 执行待执行导航参数（来自 /setting_open 命令）
        global _g_ClientSystem
        if _g_ClientSystem and _g_ClientSystem.mPendingNavigation:
            main_card_id, sub_key, middle_card_id = _g_ClientSystem.mPendingNavigation
            _g_ClientSystem.mPendingNavigation = None
            dlog.client_print("==== Create: executing pending navigation: %s %s %s ====" % (
                main_card_id, sub_key, middle_card_id
            ))
            self._ExecuteNavigation(main_card_id, sub_key, middle_card_id)

        self.BindBackButton()

        # 注册为底部 toast 的内嵌宿主：设置界面打开时底部提示显示在此处（盖在其上）
        self._SetupEmbeddedUnderToast()

    def _SetupEmbeddedUnderToast(self):
        """缓存设置界面内嵌底部提示面板的控件引用，并向 Toast 注册宿主。

        内嵌面板通过 $additional_screen_content 挂在 screen 根级
        （与 root_screen_panel 同级，layer 1000 盖在主内容之上），
        结构与 toast.json 的 toast_under 完全一致。
        """
        try:
            from Toast import register_settings_under_host
        except ImportError:
            self.mEmbeddedUnderToast = None
            return
        self.mEmbeddedUnderToast = None
        self.mEmbeddedUnderTimer = None
        base = self.mBasePath or ""
        # additional_screen_content 与 root_screen_panel 在 screen_panel 下同级
        additional = base.replace("/root_screen_panel", "/additional_screen_content")
        candidates = [
            additional + "/under_toast",
            base + "/additional_screen_content/under_toast",
            "/screen_panel/additional_screen_content/under_toast",
            "/additional_screen_content/under_toast",
            base + "/under_toast",
        ]
        self.mEmbeddedUnderRoot = None
        self.mEmbeddedUnderImage = None
        self.mEmbeddedUnderShadow = None
        self.mEmbeddedUnderLabel = None
        self._embedded_anim_set = False
        for path in candidates:
            try:
                root = self.GetBaseUIControl(path)
                if root:
                    self.mEmbeddedUnderRoot = root
                    self.mEmbeddedUnderImage = self.GetBaseUIControl(path + "/image")
                    self.mEmbeddedUnderShadow = self.GetBaseUIControl(path + "/under")
                    label = self.GetBaseUIControl(path + "/image/label")
                    if label:
                        label = label.asLabel()
                    self.mEmbeddedUnderLabel = label
                    dlog.client_print("==== embedded under toast found at: %s ====" % path)
                    break
            except Exception as e:
                dlog.client_print("==== embedded under toast path error %s: %s ====" % (path, str(e)))
        if self.mEmbeddedUnderRoot:
            # 默认隐藏：防止设置界面首次打开时内嵌面板闪出
            try:
                self.mEmbeddedUnderRoot.SetVisible(False)
            except Exception:
                pass
            register_settings_under_host(self)
            dlog.client_print("==== SettingsScreenNode: embedded under toast host registered ====")
        else:
            dlog.client_print("==== SettingsScreenNode: embedded under toast panel not found ====")

    def _PlayEmbeddedUnderAnim(self, enter_anim, shadow_anim, end_callback=None):
        """播放内嵌底部提示的 offset 动画（image 主图 + under 阴影同步，与原版一致）。

        动画定义在 toast.json 的 toast 命名空间（toast_under_enter/exit 等）。
        用 _embedded_anim_set 守护：只有控件上已有动画时才 Stop/Remove，
        避免首次播放时对无动画控件调用导致报错。置位放在全部控件处理之后，
        确保同一次调用里 image/under 两个分支看到的标志一致。
        """
        if self.mEmbeddedUnderImage:
            try:
                if self._embedded_anim_set:
                    self.mEmbeddedUnderImage.StopAnimation("offset")
                    self.mEmbeddedUnderImage.RemoveAnimation("offset")
                self.mEmbeddedUnderImage.SetAnimation("offset", "toast", enter_anim)
                self.mEmbeddedUnderImage.PlayAnimation("offset")
                if end_callback:
                    self.mEmbeddedUnderImage.SetAnimEndCallback(enter_anim, end_callback)
            except Exception as e:
                dlog.client_print("==== _PlayEmbeddedUnderAnim image error: %s ====" % str(e))
        if self.mEmbeddedUnderShadow and shadow_anim:
            try:
                if self._embedded_anim_set:
                    self.mEmbeddedUnderShadow.StopAnimation("offset")
                    self.mEmbeddedUnderShadow.RemoveAnimation("offset")
                self.mEmbeddedUnderShadow.SetAnimation("offset", "toast", shadow_anim)
                self.mEmbeddedUnderShadow.PlayAnimation("offset")
            except Exception as e:
                dlog.client_print("==== _PlayEmbeddedUnderAnim shadow error: %s ====" % str(e))
        # 全部控件设置完动画后再置位
        self._embedded_anim_set = True

    def ShowEmbeddedUnderToast(self, cfg):
        """在设置界面内部显示底部提示（由 Toast.ShowToast 在设置打开时路由调用）。

        与原版 toast_under 一致：入场动画 -> 停留 -> 出场动画 -> 隐藏。
        """
        if not self.mEmbeddedUnderRoot:
            return
        text = cfg.get("text", "")
        color = cfg.get("color")
        duration = cfg.get("duration", 3.0)
        if self.mEmbeddedUnderLabel:
            self.mEmbeddedUnderLabel.SetText(text, True)
            self.mEmbeddedUnderLabel.SetTextColor(color if color else (1.0, 1.0, 1.0))
        # 清掉上次未完成的停留定时器，避免提前隐藏本次提示
        if self.mEmbeddedUnderTimer is not None:
            try:
                comp = clientApi.GetEngineCompFactory().CreateGame(clientApi.GetLevelId())
                comp.KillTimer(self.mEmbeddedUnderTimer)
            except Exception:
                pass
            self.mEmbeddedUnderTimer = None
        # 面板设为可见并播放入场动画
        self.mEmbeddedUnderRoot.SetVisible(True)
        self._PlayEmbeddedUnderAnim("toast_under_enter", "toast_under_shadow_enter")
        # 入场音效：与 Toast 语义一致（ToastUnder 默认 random.toast，空串不播）
        enter_sound = cfg.get("enter_sound")
        if enter_sound is None:
            enter_sound = "random.toast"
        if enter_sound:
            try:
                audio_comp = clientApi.GetEngineCompFactory().CreateCustomAudio(clientApi.GetLevelId())
                audio_comp.PlayCustomUIMusic(enter_sound, 1.0, 1.0, False)
            except Exception as e:
                dlog.client_print("==== ShowEmbeddedUnderToast sound error: %s ====" % str(e))
        # 停留结束后播放出场动画
        try:
            comp = clientApi.GetEngineCompFactory().CreateGame(clientApi.GetLevelId())
            self.mEmbeddedUnderTimer = comp.AddTimer(duration, self._StartEmbeddedUnderExit)
        except Exception as e:
            dlog.client_print("==== ShowEmbeddedUnderToast timer error: %s ====" % str(e))

    def _StartEmbeddedUnderExit(self):
        """停留结束，播放出场动画。"""
        self.mEmbeddedUnderTimer = None
        if not self.mEmbeddedUnderRoot:
            return
        self._PlayEmbeddedUnderAnim("toast_under_exit", "toast_under_shadow_exit",
                                    end_callback=self._OnEmbeddedUnderExitEnd)

    def _OnEmbeddedUnderExitEnd(self):
        """出场动画结束，隐藏内嵌底部提示面板。"""
        if self.mEmbeddedUnderRoot:
            try:
                self.mEmbeddedUnderRoot.SetVisible(False)
            except Exception:
                pass

    def _OnContentChanged(self, group):
        """内容项注册表变更回调。如果当前右侧面板正好显示该分组，则刷新。"""
        if self.mCurrentRightGroup == group:
            dlog.client_print("==== content changed for current group %s, rebuilding ====" % str(group))
            self.RebuildRightContent(*group)

    def OnActive(self):
        """
        ScreenNode 每次变为活动状态时调用（每次打开设置界面）。
        从注册表重建主卡片，确保动态增删后 UI 刷新。
        从弹窗返回时跳过重建，保留当前详情（中间/右边面板不变）。
        """
        ScreenNode.OnActive(self)
        dlog.client_print("==== SettingsScreenNode.OnActive called ====")
        global _g_ClientSystem
        if _g_ClientSystem and _g_ClientSystem.mReturningFromPopUp:
            _g_ClientSystem.mReturningFromPopUp = False
            dlog.client_print("==== OnActive: returning from popup, keep detail ====")
            # 确认"关闭面板滑入动画"后：立即关闭设置界面（下次打开生效）
            if _g_ClientSystem.mPendingCloseSettings:
                _g_ClientSystem.mPendingCloseSettings = False
                dlog.client_print("==== OnActive: close settings (enter anim disabled) ====")
                clientApi.PopScreen()
                _g_ClientSystem.mSettingsUIOpen = False
            return
        # 从 MyClientSystem 获取待执行导航参数
        if _g_ClientSystem and _g_ClientSystem.mPendingNavigation:
            self.mPendingNavigation = _g_ClientSystem.mPendingNavigation
            _g_ClientSystem.mPendingNavigation = None
        if self.mScrollContent:
            self.RebuildMainCards()
            dlog.client_print("==== OnActive: 从注册表重建 %d 张主卡片 ====" % len(self.mWrappers))
            # 处理待执行导航参数
            if self.mPendingNavigation:
                main_card_id, sub_key, middle_card_id = self.mPendingNavigation
                self.mPendingNavigation = None
                self._ExecuteNavigation(main_card_id, sub_key, middle_card_id)

    def GetBaseUIControlByBase(self, relativePath):
        if self.mBasePath is None:
            return None
        fullPath = self.mBasePath + relativePath
        return self.GetBaseUIControl(fullPath)

    def ExploreAndFindBasePath(self):
        candidates = [
            "",
            "/main_content",
            "/root_screen_panel",
            "/screen_panel/root_screen_panel",
            "/safezone_screen_matrix/inner_matrix/safezone_screen_panel/screen_panel/root_screen_panel",
            "/safezone_screen_matrix/inner_matrix/safezone_screen_panel/root_screen_panel",
            "/variables_button_mappings_and_controls/safezone_screen_matrix/inner_matrix/safezone_screen_panel/screen_panel/root_screen_panel",
            "/variables_button_mappings_and_controls/safezone_screen_matrix/inner_matrix/safezone_screen_panel/root_screen_panel",
        ]
        for base in candidates:
            leftPath = base + "/left" if base else "/left"
            try:
                leftCtrl = self.GetBaseUIControl(leftPath)
                if leftCtrl:
                    dlog.client_print("==== base path candidate found: %s ====" % base)
                    return base
            except Exception as e:
                dlog.client_print("==== path check error %s: %s ====" % (leftPath, str(e)))
        dlog.client_print("==== no base path candidate found, dumping root ====")
        self.DumpChildren("/", 0, 6)
        return None

    def FindScrollingContent(self, basePath):
        modsPath = basePath + "/left/mods"
        modsCtrl = self.GetBaseUIControl(modsPath)
        if not modsCtrl:
            dlog.client_print("==== mods not found at: %s ====" % modsPath)
            return None

        possiblePaths = [
            modsPath + "/scroll_mouse/scroll_view/stack_panel/background_and_viewport/scrolling_view_port/scrolling_content",
            modsPath + "/scroll_touch/scroll_view/panel/background_and_viewport/scrolling_view_port/scrolling_content",
            modsPath + "/scroll_view/stack_panel/background_and_viewport/scrolling_view_port/scrolling_content",
            modsPath + "/scroll_view/panel/background_and_viewport/scrolling_view_port/scrolling_content",
        ]
        for p in possiblePaths:
            try:
                ctrl = self.GetBaseUIControl(p)
                if ctrl:
                    dlog.client_print("==== scroll_content found at: %s ====" % p)
                    return ctrl
            except Exception as e:
                dlog.client_print("==== scroll_content check error %s: %s ====" % (p, str(e)))

        dlog.client_print("==== common scroll_content paths failed, exploring mods tree ====")
        self.DumpChildren(modsPath, 0, 10)
        return None

    def FindMiddleScrollingContent(self, basePath):
        modsPath = basePath + "/middle/mods"
        modsCtrl = self.GetBaseUIControl(modsPath)
        if not modsCtrl:
            dlog.client_print("==== middle mods not found at: %s ====" % modsPath)
            return None

        possiblePaths = [
            modsPath + "/scroll_mouse/scroll_view/stack_panel/background_and_viewport/scrolling_view_port/scrolling_content",
            modsPath + "/scroll_touch/scroll_view/panel/background_and_viewport/scrolling_view_port/scrolling_content",
            modsPath + "/scroll_view/stack_panel/background_and_viewport/scrolling_view_port/scrolling_content",
            modsPath + "/scroll_view/panel/background_and_viewport/scrolling_view_port/scrolling_content",
        ]
        for p in possiblePaths:
            try:
                ctrl = self.GetBaseUIControl(p)
                if ctrl:
                    dlog.client_print("==== middle scroll_content found at: %s ====" % p)
                    return ctrl
            except Exception as e:
                dlog.client_print("==== middle scroll_content check error %s: %s ====" % (p, str(e)))

        dlog.client_print("==== common middle scroll_content paths failed, exploring mods tree ====")
        self.DumpChildren(modsPath, 0, 10)
        return None

    def FindRightScrollingContent(self, basePath):
        modsPath = basePath + "/right/mods"
        modsCtrl = self.GetBaseUIControl(modsPath)
        if not modsCtrl:
            dlog.client_print("==== right mods not found at: %s ====" % modsPath)
            return None
        possiblePaths = [
            modsPath + "/scroll_mouse/scroll_view/stack_panel/background_and_viewport/scrolling_view_port/scrolling_content",
            modsPath + "/scroll_touch/scroll_view/panel/background_and_viewport/scrolling_view_port/scrolling_content",
            modsPath + "/scroll_view/stack_panel/background_and_viewport/scrolling_view_port/scrolling_content",
            modsPath + "/scroll_view/panel/background_and_viewport/scrolling_view_port/scrolling_content",
        ]
        for p in possiblePaths:
            try:
                ctrl = self.GetBaseUIControl(p)
                if ctrl:
                    dlog.client_print("==== right scroll_content found at: %s ====" % p)
                    self.mRightScrollContentPath = p
                    return ctrl
            except Exception as e:
                dlog.client_print("==== right scroll_content check error %s: %s ====" % (p, str(e)))
        dlog.client_print("==== common right scroll_content paths failed, exploring mods tree ====")
        self.DumpChildren(modsPath, 0, 10)
        return None

    def DumpChildren(self, path, depth=0, maxDepth=8):
        if depth > maxDepth:
            return
        try:
            children = self.GetChildrenName(path)
            if not children:
                return
            for child in children:
                childPath = path + "/" + child if path != "/" else "/" + child
                dlog.client_print("==== path[%d]: %s ====" % (depth, childPath))
                if depth < maxDepth:
                    self.DumpChildren(childPath, depth + 1, maxDepth)
        except Exception as e:
            dlog.client_print("==== DumpChildren error at %s: %s ====" % (path, str(e)))

    def BindBackButton(self):
        backPaths = [
            "/background/back",
            "/main_content/background/back",
            "/root_screen_panel/background/back",
        ]
        if self.mBasePath is not None:
            backPaths.insert(0, self.mBasePath + "/background/back")
        for backPath in backPaths:
            try:
                backBtn = self.GetBaseUIControl(backPath)
                if backBtn:
                    btn = backBtn.asButton()
                    if btn:
                        btn.AddTouchEventParams({})
                        btn.SetButtonTouchUpCallback(self.OnBackClick)
                        dlog.client_print("==== back button bound at: %s ====" % backPath)
                    else:
                        dlog.client_print("==== back button asButton failed at: %s ====" % backPath)
                    return
            except Exception as e:
                dlog.client_print("==== back button bind error at %s: %s ====" % (backPath, str(e)))
        dlog.client_print("==== back button not found ====")

    def UpdatePreviewIcon(self, iconPath):
        if self.mPreviewIcon:
            self.mPreviewIcon.SetSprite(iconPath)
            dlog.client_print("==== preview icon updated: %s ====" % iconPath)

    def Init(self):
        pass

    @ViewBinder.binding(ViewBinder.BF_BindBool, "#settings_slider_enabled")
    def OnSliderEnabled(self):
        """slider 启用状态绑定：返回 True 使原版 transparent_grey 灰层默认隐藏。"""
        return True

    def OnBackClick(self, args):
        dlog.client_print("==== back button clicked ====")
        clientApi.PopScreen()
        return ViewRequest.Nothing

    def AddCard(self, text, icon, card_id=None):
        if not self.mScrollContent:
            return -1
        index = len(self.mWrappers)
        if card_id is None:
            card_id = "card_%d" % index
        try:
            wrapper = self.CreateChildControl(
                'setting.card_group',
                'card_%d' % index,
                self.mScrollContent,
                True
            )
        except Exception as e:
            dlog.client_print("==== Settings AddCard error: %s ====" % str(e))
            return -1
        if not wrapper:
            return -1

        btnCtrl = wrapper.GetChildByName('card_btn')
        if not btnCtrl:
            return -1

        try:
            labelCtrl = btnCtrl.GetChildByName('name')
            if labelCtrl:
                labelCtrl.asLabel().SetText(text)
        except Exception:
            pass

        # 获取 icon_backdrop 控件，并从中获取内部的 icon 控件
        try:
            backdropCtrl = btnCtrl.GetChildByName('icon_backdrop')
            if backdropCtrl:
                # 设置 icon_backdrop 初始 UV
                backdropImg = backdropCtrl.asImage()
                if backdropImg:
                    backdropImg.SetSpriteUV((0, 0))
                    backdropImg.SetSpriteUVSize((self.mBackdropFrameSize, self.mBackdropFrameSize))
                    self.mCardBackdropCtrls.append(backdropImg)
                else:
                    self.mCardBackdropCtrls.append(None)

                # 设置内部自定义 icon 纹理
                iconCtrl = backdropCtrl.GetChildByName('icon')
                if iconCtrl:
                    img = iconCtrl.asImage()
                    if img:
                        img.SetSprite(icon)
                        dlog.client_print("==== Settings card icon set: %s -> %s ====" % (text, icon))
                    else:
                        dlog.client_print("==== Settings card icon asImage failed ====")
                else:
                    dlog.client_print("==== Settings card icon not found inside icon_backdrop ====")
            else:
                self.mCardBackdropCtrls.append(None)
                dlog.client_print("==== Settings card icon_backdrop not found ====")
        except Exception as e:
            self.mCardBackdropCtrls.append(None)
            dlog.client_print("==== Settings card icon error: %s ====" % str(e))

        # 初始化动画状态
        # 初始透明度为 0，加入淡入队列
        try:
            wrapper.SetAlpha(0.0)
        except Exception:
            pass
        self.mMainCardFadingIn.append([wrapper, 0.0])

        # 初始化动画状态
        self.mBackdropAnimStates[index] = {
            "frame": 0,
            "timer": 0,
            "playing": False
        }

        try:
            btn = btnCtrl.asButton()
            btn.AddTouchEventParams({})
            btn.SetButtonTouchDownCallback(self.OnCardTouchDown)
            btn.SetButtonTouchUpCallback(self.OnCardTouchUp)
            btn.SetButtonTouchCancelCallback(self.OnCardTouchCancel)
        except Exception as e:
            dlog.client_print("==== Settings card event error: %s ====" % str(e))

        subPanel = wrapper.GetChildByName('sub_panel')

        self.mWrappers.append(wrapper)
        self.mCardBtns.append(btnCtrl)
        self.mSubPanels.append(subPanel)
        self.mSubCards[index] = {}
        self.mSubCardStates[index] = {}
        self.mCardIcons.append(icon)
        self.mCardIdToIndex[card_id] = index
        self.mIndexToCardId.append(card_id)
        return index

    def _ComputeMainCardSnapshot(self):
        """计算主卡片注册表快照（id+name+icon 的有序拼接），用于检测注册表是否变化。"""
        from CardRegistry import GetAllMainCardIds, GetMainCard
        parts = []
        for cardId in GetAllMainCardIds():
            info = GetMainCard(cardId)
            if info:
                parts.append("%s|%s|%s" % (cardId, info.get("name", ""), info.get("icon", "")))
        return "||".join(parts)

    def RebuildMainCards(self):
        """
        清除所有主卡片 UI 控件并从注册表重建（懒加载，逐帧创建）。
        对外部模块的调用约定:
            UnregisterMainCard("xxx") 或 RegisterMainCard("yyy", ...)
            然后 self.RebuildMainCards()
        """
        # 快照比对：注册表未变化且已有控件时，完全复用现有 UI，跳过全量重建
        # （这是打开设置界面不卡顿的关键优化）
        snapshot = self._ComputeMainCardSnapshot()
        if snapshot == self.mMainCardSnapshot and self.mWrappers:
            # 收起所有子卡片并恢复主卡片视觉为 normal
            for idx in range(len(self.mWrappers)):
                self.HideSubCards(idx)
                try:
                    self.SetMainCardVisualState(idx, "normal")
                except Exception:
                    pass
                if idx in self.mSubCardStates:
                    for key in self.mSubCardStates[idx]:
                        self.mSubCardStates[idx][key] = False
            # 重置主卡片 backdrop 动画状态
            for idx in range(len(self.mCardBackdropCtrls)):
                state = self.mBackdropAnimStates.get(idx)
                if state:
                    state["frame"] = 0
                    state["timer"] = 0
                    state["playing"] = False
                backdrop = self.mCardBackdropCtrls[idx] if idx < len(self.mCardBackdropCtrls) else None
                if backdrop:
                    try:
                        backdrop.SetSpriteUV((0, 0))
                    except Exception:
                        pass
            # 重置选中/按压/面板状态
            self.mSelectedIndex = -1
            self.mPressingIndex = -1
            self.mMiddlePressingIndex = -1
            self.mSubCardPressing = None
            self.mMainCardFade = {}
            self.mMainCardFadingIn = []
            # 真正隐藏并清理中间/右侧面板，避免状态标志与控件不一致导致无法切换
            if self.mMiddleOpen:
                self.HideMiddlePanel()
            if self.mRightOpen:
                self.HideRightPanel()
            dlog.client_print("==== RebuildMainCards: registry unchanged, skip rebuild (%d cards) ====" % len(self.mWrappers))
            return
        self.mMainCardSnapshot = snapshot

        # 关闭中间面板和右侧面板
        if self.mMiddleOpen:
            self.mMiddleOpen = False
            self.ClearMiddleOptions()
        self.mMiddleOpen = False
        if self.mRightOpen:
            self.mRightOpen = False
        self.mRightOpen = False
        self.mSelectedIndex = -1
        self.mMainCardFade = {}
        self.mMainCardFadingIn = []

        # 移除旧的 UI 控件
        for wrapper in reversed(self.mWrappers):
            try:
                self.RemoveChildControl(wrapper)
            except Exception:
                try:
                    wrapper.SetVisible(False)
                except Exception:
                    pass
        # 重置所有列表
        self.mWrappers = []
        self.mCardBtns = []
        self.mSubPanels = []
        self.mSubCards = {}
        self.mSubCardStates = {}
        self.mCardIcons = []
        self.mCardIdToIndex = {}
        self.mIndexToCardId = []
        self.mCardBackdropCtrls = []
        self.mBackdropAnimStates = {}
        self.mSubCardBackdropCtrls = {}
        self.mSubCardAnimStates = {}
        self.mMiddleCardBackdropCtrls = []
        self.mMiddleCardAnimStates = {}

        # 准备待创建的卡片数据（懒加载队列）
        from CardRegistry import GetAllMainCardIds, GetMainCard
        pending = []
        for cardId in GetAllMainCardIds():
            info = GetMainCard(cardId)
            if info:
                pending.append((info["name"], info["icon"], cardId))
        self.mMainCardPending = pending
        # 立即创建前 N 张卡片，让界面快速响应（剩余卡片由 OnTick 逐帧创建）
        self._CreatePendingMainCards(urgent=True)

    def _CreatePendingMainCards(self, urgent=False):
        """从 mMainCardPending 中创建下一批主卡片。"""
        batch = self.mMainCardPerTick if not urgent else 8
        created = 0
        while self.mMainCardPending and created < batch:
            name, icon, cardId = self.mMainCardPending.pop(0)
            self.AddCard(name, icon, cardId)
            created += 1
        if not self.mMainCardPending:
            self._LogMainCardCount()

    def _LogMainCardCount(self):
        """打印主卡片总数日志。"""
        if not self.mMainCardPending:
            dlog.client_print("==== RebuildMainCards: %d cards (lazy loaded) ====" % len(self.mWrappers))

    def FindCardIndexByPath(self, cardPath):
        for i in range(len(self.mCardBtns)):
            if 'card_%d/card_btn' % i in cardPath:
                return i
        return -1

    def OnCardTouchDown(self, args):
        if self.mPressingIndex >= 0:
            return ViewRequest.Nothing
        cardPath = args.get('ButtonPath', '')
        index = self.FindCardIndexByPath(cardPath)
        if index < 0:
            return ViewRequest.Nothing
        # 已选中的卡片再次按下不显示 pressing、不响应
        if index == self.mSelectedIndex:
            return ViewRequest.Nothing
        self.mPressingIndex = index
        self.SetCardVisualState(self.mCardBtns[index], "pressing")
        dlog.client_print("==== Settings card_%d touch down ====" % index)
        return ViewRequest.Nothing

    def OnCardTouchUp(self, args):
        # 兼容：个别引擎版本可能把取消事件路由进 Up 回调（Cancel=3）
        if args.get('TouchEvent') == 3:
            return self.OnCardTouchCancel(args)
        cardPath = args.get('ButtonPath', '')
        prevPressing = self.mPressingIndex
        self.mPressingIndex = -1
        index = self.FindCardIndexByPath(cardPath)
        if index < 0:
            if 0 <= prevPressing < len(self.mCardBtns):
                self._RestoreMainCardVisual(prevPressing)
            return ViewRequest.Nothing
        if 0 <= prevPressing < len(self.mCardBtns) and prevPressing != index:
            self._RestoreMainCardVisual(prevPressing)
        if prevPressing == index:
            # 已按下（选中）的卡片再次点击不响应
            if index == self.mSelectedIndex:
                self.SetMainCardVisualState(index, "selected")
                return ViewRequest.Nothing
            self._StartBackdropAnimation(index)
            self.SelectMainCard(index)
        else:
            self._RestoreMainCardVisual(index)
        return ViewRequest.Nothing

    def OnCardTouchCancel(self, args):
        """触控在按钮范围外弹起时触发：只恢复视觉，不触发选中。"""
        index = self.mPressingIndex
        self.mPressingIndex = -1
        if index >= 0:
            self._RestoreMainCardVisual(index)
            dlog.client_print("==== Settings card_%d touch cancel ====" % index)
        return ViewRequest.Nothing

    def SelectMainCard(self, index):
        if self.mSelectedIndex != index:
            if self.mMiddleOpen:
                self.HideMiddlePanel()
            if self.mRightOpen:
                self.HideRightPanel()
            self.HideSubCards(self.mSelectedIndex)
            # 重置当前主卡片下所有子卡片的动画状态（不删除，下次切回来时复用）
            if self.mSelectedIndex in self.mSubCards:
                for key in self.mSubCards[self.mSelectedIndex]:
                    state = self.mSubCardAnimStates.get((self.mSelectedIndex, key))
                    if state:
                        state["frame"] = 0
                        state["timer"] = 0
                        state["playing"] = False
                    ctrl = self.mSubCardBackdropCtrls.get((self.mSelectedIndex, key))
                    if ctrl:
                        ctrl.SetSpriteUV((0, 0))
            if self.mSelectedIndex >= 0:
                self._StopBackdropAnimation(self.mSelectedIndex)
                self.SetMainCardVisualState(self.mSelectedIndex, "normal")
            self.mSelectedIndex = index
            self.ShowSubCards(index)
            self.UpdatePreviewIcon(self.mCardIcons[index])
            dlog.client_print("==== Settings card_%d selected ====" % index)
        self.SetMainCardVisualState(index, "selected")

    def SetCardState(self, index, selected):
        if 0 <= index < len(self.mCardBtns):
            self.SetMainCardVisualState(index, "selected" if selected else "normal")

    def SetCardVisualState(self, card, state):
        normalCtrl = card.GetChildByName('normal')
        pressingCtrl = card.GetChildByName('pressing')
        pressCtrl = card.GetChildByName('press')
        if normalCtrl:
            normalCtrl.SetVisible(state == "normal")
        if pressingCtrl:
            pressingCtrl.SetVisible(state == "pressing")
        if pressCtrl:
            pressCtrl.SetVisible(state == "selected")

    def _RestoreMainCardVisual(self, index):
        """恢复主卡片视觉为 selected/normal（供 TouchUp/TouchCancel 复用）。"""
        if 0 <= index < len(self.mCardBtns):
            self.SetMainCardVisualState(
                index,
                "selected" if index == self.mSelectedIndex else "normal"
            )

    def SetMainCardVisualState(self, index, state):
        """主卡片状态切换，normal<->selected 使用渐隐，pressing 立即切换"""
        if not (0 <= index < len(self.mCardBtns)):
            return
        if state == "pressing":
            self.mMainCardFade.pop(index, None)
            self.SetCardVisualState(self.mCardBtns[index], "pressing")
            return
        # 从 pressing 状态切换时，立即隐藏 pressing 控件，防止残留
        pressingCtrl = self.mCardBtns[index].GetChildByName('pressing')
        if pressingCtrl:
            pressingCtrl.SetVisible(False)
        self._StartMainCardFade(index, state)

    def _StartMainCardFade(self, index, targetState):
        card = self.mCardBtns[index]
        normalCtrl = card.GetChildByName('normal')
        pressCtrl = card.GetChildByName('press')
        if not normalCtrl or not pressCtrl:
            self.SetCardVisualState(card, targetState)
            return

        fade = self.mMainCardFade.get(index)
        if fade:
            alpha = fade["alpha"]
        else:
            alpha = 1.0 if pressCtrl.GetVisible() else 0.0

        target = "selected" if targetState == "selected" else "normal"
        if target == "selected" and alpha >= 1.0:
            self._FinishMainCardFade(index, "selected")
            return
        if target == "normal" and alpha <= 0.0:
            self._FinishMainCardFade(index, "normal")
            return

        normalCtrl.SetVisible(True)
        pressCtrl.SetVisible(True)
        self.mMainCardFade[index] = {"target": target, "alpha": alpha}

    def _FinishMainCardFade(self, index, target):
        self.mMainCardFade.pop(index, None)
        if 0 <= index < len(self.mCardBtns):
            self.SetCardVisualState(self.mCardBtns[index], target)

    def _UpdateMainCardFade(self):
        for index in list(self.mMainCardFade.keys()):
            fade = self.mMainCardFade[index]
            alpha = fade["alpha"]
            if fade["target"] == "selected":
                alpha += self.mMainCardFadeSpeed
                if alpha >= 1.0:
                    self._FinishMainCardFade(index, "selected")
                    continue
            else:
                alpha -= self.mMainCardFadeSpeed
                if alpha <= 0.0:
                    self._FinishMainCardFade(index, "normal")
                    continue
            fade["alpha"] = alpha
            card = self.mCardBtns[index]
            normalCtrl = card.GetChildByName('normal')
            pressCtrl = card.GetChildByName('press')
            if normalCtrl:
                normalCtrl.SetAlpha(1.0 - alpha)
            if pressCtrl:
                pressCtrl.SetAlpha(alpha)

    def ShowSubCards(self, index):
        if index < 0 or index >= len(self.mSubPanels):
            return
        if self.mSubCards.get(index):
            for key, ctrl in self.mSubCards[index].items():
                ctrl.SetVisible(True)
                if self.mSubCardStates[index][key]:
                    self.mSubCardStates[index][key] = False
                    self.SetSubCardState(ctrl, False)
            return
        subPanel = self.mSubPanels[index]
        if not subPanel:
            return
        for key, text in [("client", "客户端"), ("server", "服务端")]:
            try:
                ctrl = self.CreateChildControl(
                    'setting.sub_card',
                    'sub_%d_%s' % (index, key),
                    subPanel,
                    True
                )
                if ctrl:
                    label = ctrl.GetChildByName('sub_label')
                    if label:
                        label.asLabel().SetText(text)
                    # 通过 icon_backdrop 获取内部的 icon 控件
                    backdropCtrl = ctrl.GetChildByName('icon_backdrop')
                    if backdropCtrl:
                        # 初始化 icon_backdrop UV（序列帧动画）
                        backdropImg = backdropCtrl.asImage()
                        if backdropImg:
                            backdropImg.SetSpriteUV((0, 0))
                            backdropImg.SetSpriteUVSize((self.mBackdropFrameSize, self.mBackdropFrameSize))
                            self.mSubCardBackdropCtrls[(index, key)] = backdropImg
                        else:
                            self.mSubCardBackdropCtrls[(index, key)] = None
                        # 初始化动画状态
                        self.mSubCardAnimStates[(index, key)] = {
                            "frame": 0,
                            "timer": 0,
                            "playing": False
                        }
                        # 设置内部自定义 icon 纹理
                        iconCtrl = backdropCtrl.GetChildByName('icon')
                        if iconCtrl:
                            iconPath = "textures/ui/sidebar_icons/addon" if key == "client" else "textures/ui/sidebar_icons/realms"
                            img = iconCtrl.asImage()
                            if img:
                                img.SetSprite(iconPath)
                                dlog.client_print("==== Settings sub_card icon set: %s -> %s ====" % (key, iconPath))
                            else:
                                dlog.client_print("==== Settings sub_card icon asImage failed ====")
                        else:
                            dlog.client_print("==== Settings sub_card icon not found inside icon_backdrop ====")
                    else:
                        self.mSubCardBackdropCtrls[(index, key)] = None
                        self.mSubCardAnimStates[(index, key)] = {
                            "frame": 0,
                            "timer": 0,
                            "playing": False
                        }
                        dlog.client_print("==== Settings sub_card icon_backdrop not found ====")
                    btn = ctrl.asButton()
                    if btn:
                        btn.AddTouchEventParams({})
                        btn.SetButtonTouchDownCallback(self.OnSubCardTouchDown)
                        btn.SetButtonTouchUpCallback(self.OnSubCardTouchUp)
                        btn.SetButtonTouchCancelCallback(self.OnSubCardTouchCancel)
                    self.mSubCards[index][key] = ctrl
                    self.mSubCardStates[index][key] = False
                    self.SetSubCardVisualState(ctrl, "normal")
            except Exception as e:
                dlog.client_print("==== Settings sub_card error: %s ====" % str(e))

    def HideSubCards(self, index):
        if index < 0:
            return
        if index in self.mSubCards:
            for ctrl in self.mSubCards[index].values():
                ctrl.SetVisible(False)

    def SetSubCardVisualState(self, ctrl, state):
        normalCtrl = ctrl.GetChildByName('normal_bg')
        pressingCtrl = ctrl.GetChildByName('pressing_bg')
        pressCtrl = ctrl.GetChildByName('press_bg')
        if normalCtrl:
            normalCtrl.SetVisible(state == "normal")
        if pressingCtrl:
            pressingCtrl.SetVisible(state == "pressing")
        if pressCtrl:
            pressCtrl.SetVisible(state == "selected")

    def _RestoreSubCardVisual(self, index, key):
        """恢复子卡片视觉为 selected/normal（供 TouchUp/TouchCancel 复用）。"""
        ctrl = self.mSubCards.get(index, {}).get(key)
        if ctrl is not None:
            self.SetSubCardVisualState(
                ctrl,
                "selected" if self.mSubCardStates.get(index, {}).get(key, False) else "normal"
            )

    def SetSubCardState(self, ctrl, selected):
        self.SetSubCardVisualState(ctrl, "selected" if selected else "normal")

    def ParseSubCardPath(self, subPath):
        if 'sub_' not in subPath:
            return None
        parts = subPath.split('/')
        if not parts:
            return None
        name = parts[-1]
        if not name.startswith('sub_'):
            return None
        tokens = name.split('_')
        if len(tokens) < 3:
            return None
        try:
            index = int(tokens[1])
            key = tokens[2]
        except (ValueError, IndexError):
            return None
        if index not in self.mSubCards or key not in self.mSubCards[index]:
            return None
        return (index, key)

    def OnSubCardTouchDown(self, args):
        if self.mSubCardPressing is not None:
            return ViewRequest.Nothing
        subPath = args.get('ButtonPath', '')
        result = self.ParseSubCardPath(subPath)
        if not result:
            return ViewRequest.Nothing
        index, key = result
        # 已选中的卡片再次按下不显示 pressing、不响应
        if self.mSubCardStates[index][key]:
            return ViewRequest.Nothing
        self.mSubCardPressing = (index, key)
        self.SetSubCardVisualState(self.mSubCards[index][key], "pressing")
        dlog.client_print("==== Settings sub_card touch down: sub_%d_%s ====" % (index, key))
        return ViewRequest.Nothing

    def OnSubCardTouchUp(self, args):
        # 兼容：个别引擎版本可能把取消事件路由进 Up 回调（Cancel=3）
        if args.get('TouchEvent') == 3:
            return self.OnSubCardTouchCancel(args)
        subPath = args.get('ButtonPath', '')
        prevPressing = self.mSubCardPressing
        self.mSubCardPressing = None
        result = self.ParseSubCardPath(subPath)
        if not result:
            if prevPressing:
                index, key = prevPressing
                self._RestoreSubCardVisual(index, key)
            return ViewRequest.Nothing
        index, key = result
        if prevPressing and prevPressing != (index, key):
            pi, pk = prevPressing
            self._RestoreSubCardVisual(pi, pk)
        if prevPressing == (index, key):
            # 已按下（选中）的卡片再次点击不响应
            if self.mSubCardStates[index][key]:
                self.SetSubCardVisualState(self.mSubCards[index][key], "selected")
                return ViewRequest.Nothing
            self._StartSubCardBackdropAnimation(index, key)
            self.SelectSubCard(index, key)
        else:
            self._RestoreSubCardVisual(index, key)
        return ViewRequest.Nothing

    def OnSubCardTouchCancel(self, args):
        """触控在按钮范围外弹起时触发：只恢复视觉，不触发选中。"""
        prevPressing = self.mSubCardPressing
        self.mSubCardPressing = None
        if prevPressing:
            index, key = prevPressing
            self._RestoreSubCardVisual(index, key)
            dlog.client_print("==== Settings sub_card touch cancel: sub_%d_%s ====" % (index, key))
        return ViewRequest.Nothing

    def SelectSubCard(self, index, key):
        if self.mSubCardStates[index][key]:
            self.SetSubCardVisualState(self.mSubCards[index][key], "selected")
            return
        for otherKey in self.mSubCardStates[index]:
            if otherKey != key and self.mSubCardStates[index][otherKey]:
                self.mSubCardStates[index][otherKey] = False
                self.SetSubCardVisualState(self.mSubCards[index][otherKey], "normal")
        self.mSubCardStates[index][key] = True
        self.SetSubCardVisualState(self.mSubCards[index][key], "selected")
        self.mCurrentSubKey = key
        self.BuildMiddleOptions(index, key)
        self.OpenMiddlePanel()
        # 清空右侧面板，等待用户选择具体中间卡片
        mainCardId = self.mIndexToCardId[index] if 0 <= index < len(self.mIndexToCardId) else None
        self.ClearRightContent()
        self.mCurrentRightGroup = (mainCardId, key, None) if mainCardId else None
        self.OpenRightPanel()
        dlog.client_print("==== sub_card sub_%d_%s selected, middle+right panels opened ====" % (index, key))

    def BuildMiddleOptions(self, index, key):
        self.ClearMiddleOptions()
        if not self.mMiddleScrollContent:
            dlog.client_print("==== BuildMiddleOptions: scroll content not found ====")
            return
        # 通过 index 查找主卡片 ID
        mainCardId = self.mIndexToCardId[index] if 0 <= index < len(self.mIndexToCardId) else None
        if not mainCardId:
            dlog.client_print("==== BuildMiddleOptions: invalid index %d ====" % index)
            return
        # 从全局绑定中获取该主卡片+子卡片的中间卡片列表
        bindings = GetMiddleCardBindings(mainCardId, key)
        dlog.client_print("==== BuildMiddleOptions for %s/%s: %d cards ====" % (mainCardId, key, len(bindings)))
        # 先暂存，等旧卡片淡出完成 + 极短停顿后再开始创建
        self.mMiddleShowPending = list(bindings)
        self.mMiddleShowDelayTimer = 3  # 约 3 帧（约 0.05s）额外等待，可调

    def CreateNextMiddleCard(self):
        if not self.mPendingMiddleCards:
            return
        cardId, name, icon = self.mPendingMiddleCards.pop(0)
        try:
            self.mMiddleCardSeq += 1
            ctrlName = 'middle_card_reg_%d' % self.mMiddleCardSeq
            ctrl = self.CreateChildControl(
                'setting.middle_card',
                ctrlName,
                self.mMiddleScrollContent,
                True
            )
            if not ctrl:
                dlog.client_print("==== middle card '%s' create failed ====" % cardId)
                return
            label = ctrl.GetChildByName('name')
            if label:
                label.asLabel().SetText(name)
            # 获取 icon_backdrop 控件，初始化 UV 和动画状态
            backdropCtrl = ctrl.GetChildByName('icon_backdrop')
            if backdropCtrl:
                backdropImg = backdropCtrl.asImage()
                if backdropImg:
                    backdropImg.SetSpriteUV((0, 0))
                    backdropImg.SetSpriteUVSize((self.mBackdropFrameSize, self.mBackdropFrameSize))
                    self.mMiddleCardBackdropCtrls.append(backdropImg)
                else:
                    self.mMiddleCardBackdropCtrls.append(None)
                # 设置内部 icon 纹理
                iconCtrl = backdropCtrl.GetChildByName('icon')
                if iconCtrl:
                    iconCtrl.SetPropertyBag({"texture": icon})
                    iconImg = iconCtrl.asImage()
                    if iconImg:
                        iconImg.SetSprite(icon)
            else:
                self.mMiddleCardBackdropCtrls.append(None)
                # 兼容旧版：直接设置 icon
                iconCtrl = ctrl.GetChildByName('icon')
                if iconCtrl:
                    iconCtrl.SetPropertyBag({"texture": icon})
                    iconImg = iconCtrl.asImage()
                    if iconImg:
                        iconImg.SetSprite(icon)
            # 初始化动画状态
            newIndex = len(self.mMiddleOptionCtrls)
            self.mMiddleCardAnimStates[newIndex] = {
                "frame": 0,
                "timer": 0,
                "playing": False
            }
            btn = ctrl.asButton()
            if btn:
                btn.AddTouchEventParams({})
                btn.SetButtonTouchDownCallback(self.OnMiddleCardTouchDown)
                btn.SetButtonTouchUpCallback(self.OnMiddleCardTouchUp)
                btn.SetButtonTouchCancelCallback(self.OnMiddleCardTouchCancel)
            self.SetCardVisualState(ctrl, "normal")
            # 初始透明，交给 OnTick 手动淡入（动画关闭时直接显示）
            if self.mEnableFadeAnim:
                self.SetMiddleCardAlpha(ctrl, 0.0)
                self.mMiddleFadingInCtrls.append([ctrl, 0.0])
            else:
                self.SetMiddleCardAlpha(ctrl, 1.0)
            self.mMiddleOptionCtrls.append(ctrl)
            self.mMiddleCardIds.append(cardId)
            self.mMiddleCardNames.append(ctrlName)
            # 如果有待选中间卡片，优先尝试选中
            if self.mPendingMiddleCardId is not None:
                self._TrySelectPendingMiddleCard()
            # 如果没有任何卡片被选中，自动选中第一个
            if self.mMiddleSelectedIndex < 0 and self.mMiddleOptionCtrls:
                self.SelectMiddleCard(0)
            dlog.client_print("==== middle card '%s' created: %s ====" % (cardId, name))
        except Exception as e:
            dlog.client_print("==== middle card '%s' error: %s ====" % (cardId, str(e)))

    def SetMiddleCardAlpha(self, ctrl, alpha):
        """设置中间卡片内部所有 image/label 子控件的透明度（递归覆盖 icon_backdrop 内部）"""
        # 注意：SetAlpha 仅对 image 和 label 控件生效，对 button 本身无效
        self._SetControlTreeAlpha(ctrl, alpha)

    def SetPendingNavigation(self, main_card_id, sub_key, middle_card_id):
        """
        设置并立即执行导航参数（UI 已打开时调用）。
        """
        dlog.client_print("==== SetPendingNavigation: %s %s %s ====" % (main_card_id, sub_key, middle_card_id))
        self._ExecuteNavigation(main_card_id, sub_key, middle_card_id)

    def _ExecuteNavigation(self, main_card_id, sub_key, middle_card_id):
        """
        执行导航：选中主卡片 → 子卡片 → 中间卡片。
        若主卡片尚未创建（懒加载未完成），则延迟到 OnTick 重试。
        """
        dlog.client_print("==== _ExecuteNavigation: %s %s %s ====" % (main_card_id, sub_key, middle_card_id))
        if not main_card_id:
            return
        main_index = self.mCardIdToIndex.get(main_card_id)
        if main_index is None:
            # 主卡片尚未创建，存入待处理导航，由 OnTick 重试
            self.mPendingNavigation = (main_card_id, sub_key, middle_card_id)
            dlog.client_print("==== _ExecuteNavigation: main_card_id '%s' not yet created, queued ====" % main_card_id)
            return
        # 1. 选中主卡片
        self.SelectMainCard(main_index)
        # 2. 如果指定了子卡片，选中子卡片
        if sub_key in ("client", "server"):
            # 定位到子卡片：本次打开中间/右边面板不播进入动画（仅这一次），之后按设置
            self.mNavInstant = True
            self.SelectSubCard(main_index, sub_key)
            # 3. 如果指定了中间卡片，记录待选（异步创建，需等待）
            if middle_card_id:
                self.mPendingMiddleCardId = middle_card_id
                self._TrySelectPendingMiddleCard()
        else:
            self.mPendingMiddleCardId = None

    def _TrySelectPendingMiddleCard(self):
        """尝试选中待处理的中间卡片。如果尚未创建，下次 OnTick 重试。"""
        if self.mPendingMiddleCardId is None:
            return
        try:
            middle_index = self.mMiddleCardIds.index(self.mPendingMiddleCardId)
        except ValueError:
            middle_index = -1
        if middle_index >= 0:
            dlog.client_print("==== _TrySelectPendingMiddleCard: '%s' at index %d ====" % (
                self.mPendingMiddleCardId, middle_index
            ))
            self.SelectMiddleCard(middle_index)
            self.mPendingMiddleCardId = None
        else:
            dlog.client_print("==== _TrySelectPendingMiddleCard: '%s' not yet loaded ====" % (
                self.mPendingMiddleCardId
            ))

    # ===== icon_backdrop 序列帧动画控制 =====

    def _StartBackdropAnimation(self, index):
        """启动指定卡片的 icon_backdrop 序列帧动画，每次调用都从第1帧重新播放。"""
        state = self.mBackdropAnimStates.get(index)
        if not state:
            return
        state["frame"] = 0
        state["timer"] = 0
        state["playing"] = True
        self._ApplyBackdropFrame(index, 0)

    def _StopBackdropAnimation(self, index):
        """强制停止指定卡片的动画并复位到第1帧。"""
        state = self.mBackdropAnimStates.get(index)
        if not state:
            return
        state["frame"] = 0
        state["timer"] = 0
        state["playing"] = False
        self._ApplyBackdropFrame(index, 0)

    def _ApplyBackdropFrame(self, index, frame):
        """将指定卡片的 icon_backdrop 设置到第 frame 帧（0-based）。"""
        if index < 0 or index >= len(self.mCardBackdropCtrls):
            return
        imgCtrl = self.mCardBackdropCtrls[index]
        if imgCtrl is None:
            return
        v = frame * self.mBackdropFrameSize
        imgCtrl.SetSpriteUV((0, v))

    # ===== sub_card icon_backdrop 动画控制 =====

    def _StartSubCardBackdropAnimation(self, index, key):
        """启动指定子卡片的 icon_backdrop 序列帧动画，每次调用都从第1帧重新播放。"""
        state = self.mSubCardAnimStates.get((index, key))
        if not state:
            return
        state["frame"] = 0
        state["timer"] = 0
        state["playing"] = True
        self._ApplySubCardBackdropFrame(index, key, 0)

    def _ApplySubCardBackdropFrame(self, index, key, frame):
        """将指定子卡片的 icon_backdrop 设置到第 frame 帧（0-based）。"""
        imgCtrl = self.mSubCardBackdropCtrls.get((index, key))
        if imgCtrl is None:
            return
        v = frame * self.mBackdropFrameSize
        imgCtrl.SetSpriteUV((0, v))

    # ===== middle_card icon_backdrop 动画控制 =====

    def _StartMiddleCardBackdropAnimation(self, index):
        """启动指定中间卡片的 icon_backdrop 序列帧动画，每次调用都从第1帧重新播放。"""
        state = self.mMiddleCardAnimStates.get(index)
        if not state:
            return
        state["frame"] = 0
        state["timer"] = 0
        state["playing"] = True
        self._ApplyMiddleCardBackdropFrame(index, 0)

    def _ApplyMiddleCardBackdropFrame(self, index, frame):
        """将指定中间卡片的 icon_backdrop 设置到第 frame 帧（0-based）。"""
        if index < 0 or index >= len(self.mMiddleCardBackdropCtrls):
            return
        imgCtrl = self.mMiddleCardBackdropCtrls[index]
        if imgCtrl is None:
            return
        v = frame * self.mBackdropFrameSize
        imgCtrl.SetSpriteUV((0, v))

    def ApplyServerLogSwitch(self, enabled, is_op):
        """服务端下发全局日志开关状态：应用到服务端调试开关（未渲染则暂存）。"""
        self.mServerLogPending = (bool(enabled), bool(is_op))
        item_id = self.mServerLogSwitchItem
        if not item_id:
            return
        switchCtrl = self.mRightSwitchCtrlMap.get(item_id)
        if switchCtrl is None:
            return  # 开关尚未渲染，等 OnTick 时应用暂存状态
        self._ApplyServerLogSwitchToCtrl(switchCtrl, enabled, is_op)

    def _ApplyServerLogSwitchToCtrl(self, switchCtrl, enabled, is_op):
        """将全局日志开关值与锁定状态同步到指定开关控件（锁定由玩家是否 OP 决定）。"""
        item_id = self.mServerLogSwitchItem
        if not item_id:
            return
        try:
            toggle = switchCtrl.asSwitchToggle()
            if toggle and toggle.GetToggleState("/this_toggle") != bool(enabled):
                toggle.SetToggleState(bool(enabled), "/this_toggle")
                self.mRightSwitchStates[item_id] = bool(enabled)
        except Exception as e:
            dlog.client_print("==== ApplyServerLogSwitch value error: %s ====" % str(e))
        # 非 OP 查看时锁定（禁用交互），OP 可正常切换
        try:
            switchCtrl.SetTouchEnable(bool(is_op))
        except Exception as e:
            dlog.client_print("==== ApplyServerLogSwitch lock error: %s ====" % str(e))
        # 服务端调试分类下的其他控件（复制数量/复制日志）按 OP 状态统一锁定/解锁
        self.mServerLockState = not bool(is_op)
        for lock_item_id in self.mServerLockItems:
            try:
                self.SetLocked(lock_item_id, self.mServerLockState)
            except Exception as e:
                dlog.client_print("==== ApplyServerLogSwitch lock item %s error: %s ====" % (lock_item_id, str(e)))

    def OnTick(self):
        # 处理主卡片状态渐隐
        self._UpdateMainCardFade()

        # 服务端调试开关同步：渲染完成后请求全局值并应用（含待处理状态）
        if self.mNeedServerLogRequest:
            item_id = self.mServerLogSwitchItem
            if item_id and item_id in self.mRightSwitchCtrlMap:
                if self.mServerLogPending:
                    pending_enabled, pending_is_op = self.mServerLogPending
                    self._ApplyServerLogSwitchToCtrl(
                        self.mRightSwitchCtrlMap[item_id], pending_enabled, pending_is_op)
                    self.mServerLogPending = None
                self.mNeedServerLogRequest = False
                if _g_ClientSystem:
                    _g_ClientSystem.SendServerLogRequest()

        # 服务端锁项（复制数量/复制日志）若尚未渲染完成，逐帧补应用 OP 锁定状态
        if self.mServerLockState is not None and self.mServerLockItems:
            pending_lock_ids = [iid for iid in self.mServerLockItems
                                if iid not in self.mRightCollapsibleMenuCtrlMap
                                and iid not in self.mRightBtnCtrlMap]
            if pending_lock_ids:
                for iid in self.mServerLockItems:
                    if iid in self.mRightCollapsibleMenuCtrlMap or iid in self.mRightBtnCtrlMap:
                        self.SetLocked(iid, self.mServerLockState)
            else:
                self.mServerLockState = None

        # 主卡片懒加载：逐帧创建剩余卡片
        if self.mMainCardPending:
            self._CreatePendingMainCards()
            # 创建后重试待处理导航
            if self.mPendingNavigation:
                main_card_id, sub_key, middle_card_id = self.mPendingNavigation
                self.mPendingNavigation = None
                self._ExecuteNavigation(main_card_id, sub_key, middle_card_id)

        # 主卡片淡入（懒加载创建时透明度从 0 快速渐变到 1）
        for i in range(len(self.mMainCardFadingIn) - 1, -1, -1):
            wrapper, curAlpha = self.mMainCardFadingIn[i]
            curAlpha += self.mMainCardFadeInSpeed
            if curAlpha >= 1.0:
                curAlpha = 1.0
                self.mMainCardFadingIn.pop(i)
            else:
                self.mMainCardFadingIn[i][1] = curAlpha
            try:
                wrapper.SetAlpha(curAlpha)
            except Exception:
                self.mMainCardFadingIn.pop(i)

        # 面板滑入动画延迟播放（首帧 SetVisible 后，次帧布局完成再 Play）
        if self.mMiddlePendingPlay and self.mMiddleCtrl:
            self.mMiddlePendingPlay = False
            try:
                self.mMiddleCtrl.PlayAnimation("offset")
            except Exception as e:
                dlog.client_print("==== middle pending play error: %s ====" % str(e))
        if self.mRightPendingPlay and self.mRightCtrl:
            self.mRightPendingPlay = False
            try:
                self.mRightCtrl.PlayAnimation("offset")
            except Exception as e:
                dlog.client_print("==== right pending play error: %s ====" % str(e))

        # 中间卡片淡入
        for i in range(len(self.mMiddleFadingInCtrls) - 1, -1, -1):
            ctrl, curAlpha = self.mMiddleFadingInCtrls[i]
            curAlpha += self.mMiddleFadeInSpeed
            if curAlpha >= 1.0:
                curAlpha = 1.0
                self.mMiddleFadingInCtrls.pop(i)
            else:
                self.mMiddleFadingInCtrls[i][1] = curAlpha
            self.SetMiddleCardAlpha(ctrl, curAlpha)

        # 中间卡片淡出
        for i in range(len(self.mMiddleFadingOutCtrls) - 1, -1, -1):
            ctrl, curAlpha = self.mMiddleFadingOutCtrls[i]
            curAlpha -= self.mMiddleFadeOutSpeed
            if curAlpha <= 0.0:
                self.mMiddleFadingOutCtrls.pop(i)
                self.SafeRemoveMiddleCard(ctrl)
            else:
                self.mMiddleFadingOutCtrls[i][1] = curAlpha
                self.SetMiddleCardAlpha(ctrl, curAlpha)

        # 有待显示的中间卡片：等旧卡片淡出后 + 延迟开始创建
        if self.mMiddleShowPending is not None:
            if not self.mMiddleFadingOutCtrls:
                self.mMiddleShowDelayTimer -= 1
                if self.mMiddleShowDelayTimer <= 0:
                    self.mPendingMiddleCards = list(self.mMiddleShowPending)
                    self.mMiddleShowPending = None
                    self.mMiddleCardDelayTimer = 0
                    self.CreateNextMiddleCard()
        elif self.mPendingMiddleCards:
            self.mMiddleCardDelayTimer += 1
            if self.mMiddleCardDelayTimer >= self.mMiddleCardDelayInterval:
                self.mMiddleCardDelayTimer = 0
                self.CreateNextMiddleCard()

        # ===== 右侧内容淡入淡出与延迟创建 =====

        # 右侧内容淡入
        for i in range(len(self.mRightFadingInCtrls) - 1, -1, -1):
            ctrl, curAlpha = self.mRightFadingInCtrls[i]
            curAlpha += self.mRightFadeInSpeed
            if curAlpha >= 1.0:
                curAlpha = 1.0
                self.mRightFadingInCtrls.pop(i)
            else:
                self.mRightFadingInCtrls[i][1] = curAlpha
            self.SetRightContentAlpha(ctrl, curAlpha)

        # 右侧内容淡出
        for i in range(len(self.mRightFadingOutCtrls) - 1, -1, -1):
            ctrl, curAlpha = self.mRightFadingOutCtrls[i]
            curAlpha -= self.mRightFadeOutSpeed
            if curAlpha <= 0.0:
                self.mRightFadingOutCtrls.pop(i)
                self.SafeRemoveRightContent(ctrl)
            else:
                self.mRightFadingOutCtrls[i][1] = curAlpha
                self.SetRightContentAlpha(ctrl, curAlpha)

        # 有待显示的右侧内容：等旧内容淡出后 + 延迟开始创建
        if self.mRightShowPending is not None:
            if not self.mRightFadingOutCtrls:
                self.mRightShowDelayTimer -= 1
                if self.mRightShowDelayTimer <= 0:
                    self.mRightPendingItems = list(self.mRightShowPending)
                    self.mRightShowPending = None
                    self.mRightContentDelayTimer = 0
                    self.CreateNextRightContent()
        elif self.mRightPendingItems:
            self.mRightContentDelayTimer += 1
            if self.mRightContentDelayTimer >= self.mRightContentDelayInterval:
                self.mRightContentDelayTimer = 0
                self.CreateNextRightContent()

        # 检查待选中的中间卡片（异步加载完成后延迟选中）
        if self.mPendingMiddleCardId is not None and not self.mPendingMiddleCards:
            self._TrySelectPendingMiddleCard()

        # ===== icon_backdrop 序列帧动画驱动（主卡片） =====
        for index in list(self.mBackdropAnimStates.keys()):
            state = self.mBackdropAnimStates[index]
            if not state["playing"]:
                continue
            state["timer"] += 1
            if state["timer"] < self.mBackdropFrameInterval:
                continue
            state["timer"] = 0
            nextFrame = state["frame"] + 1
            if nextFrame >= self.mBackdropFrameCount:
                # 播放完毕，回到第1帧并停止
                state["frame"] = 0
                state["playing"] = False
                self._ApplyBackdropFrame(index, 0)
            else:
                state["frame"] = nextFrame
                self._ApplyBackdropFrame(index, nextFrame)

        # ===== sub_card icon_backdrop 序列帧动画驱动 =====
        for (index, key) in list(self.mSubCardAnimStates.keys()):
            state = self.mSubCardAnimStates[(index, key)]
            if not state["playing"]:
                continue
            state["timer"] += 1
            if state["timer"] < self.mBackdropFrameInterval:
                continue
            state["timer"] = 0
            nextFrame = state["frame"] + 1
            if nextFrame >= self.mBackdropFrameCount:
                # 播放完毕，回到第1帧并停止
                state["frame"] = 0
                state["playing"] = False
                self._ApplySubCardBackdropFrame(index, key, 0)
            else:
                state["frame"] = nextFrame
                self._ApplySubCardBackdropFrame(index, key, nextFrame)

        # ===== middle_card icon_backdrop 序列帧动画驱动 =====
        for index in list(self.mMiddleCardAnimStates.keys()):
            state = self.mMiddleCardAnimStates[index]
            if not state["playing"]:
                continue
            state["timer"] += 1
            if state["timer"] < self.mBackdropFrameInterval:
                continue
            state["timer"] = 0
            nextFrame = state["frame"] + 1
            if nextFrame >= self.mBackdropFrameCount:
                # 播放完毕，回到第1帧并停止
                state["frame"] = 0
                state["playing"] = False
                self._ApplyMiddleCardBackdropFrame(index, 0)
            else:
                state["frame"] = nextFrame
                self._ApplyMiddleCardBackdropFrame(index, nextFrame)

        # 右侧控件轮询（开关/编辑框/滑块）：每 3 帧执行一次，降低低端设备上
        # 每帧读取原生控件状态带来的 CPU 压力，从而缓解右侧卡片加载时的卡顿
        self._rightPollTick = getattr(self, "_rightPollTick", 0) + 1
        if self._rightPollTick % 3 == 0:
            self._PollRightControlsUi()

    def _PollRightControlsUi(self):
        """低频轮询右侧原生控件状态（开/关、编辑框、滑块），间隔 3 帧由 OnTick 触发。

        原版控件交互（拖滑块、输入文本）的帧级响应由引擎自身保证，这里仅仅用于
        把 UI 上的改动同步回 item 运行时值并触发回调，3 帧一次的频率足够且大幅省开销。
        """
        # ===== 开关状态轮询检测 =====
        for item_id, switchCtrl in list(self.mRightSwitchCtrlMap.items()):
            if not switchCtrl:
                continue
            switchToggle = switchCtrl.asSwitchToggle()
            if not switchToggle:
                continue
            try:
                current_state = switchToggle.GetToggleState("/this_toggle")
                last_state = self.mRightSwitchStates.get(item_id)
                if last_state is not None and current_state != last_state:
                    # 更新 item 运行时值（不立即写存储，等 SaveGroupSettings/退出时提交）
                    if self.mCurrentRightGroup:
                        items = GetContentItems(*self.mCurrentRightGroup)
                        for it in items:
                            if it.item_id == item_id:
                                if hasattr(it, "SetValue"):
                                    it.SetValue(current_state)
                                if hasattr(it, "on_toggle") and it.on_toggle:
                                    try:
                                        it.on_toggle(self, item_id, current_state)
                                    except Exception as e:
                                        dlog.client_print("==== switch on_toggle error: %s ====" % str(e))
                                break
                # 更新状态记录
                self.mRightSwitchStates[item_id] = current_state
            except Exception as e:
                dlog.client_print("==== OnTick switch state check error: %s ====" % str(e))

        # ===== 编辑框内容保存轮询 =====
        for item_id, editBoxCtrl in list(self.mRightEditBoxCtrlMap.items()):
            if not editBoxCtrl:
                continue
            inputCtrl = editBoxCtrl.GetChildByName('input')
            if not inputCtrl:
                continue
            textEditBox = inputCtrl.asTextEditBox()
            if not textEditBox:
                continue
            try:
                current_text = textEditBox.GetEditText()
            except Exception as e:
                dlog.client_print("==== OnTick edit_box read error: %s ====" % str(e))
                continue
            if self.mCurrentRightGroup:
                items = GetContentItems(*self.mCurrentRightGroup)
                for it in items:
                    if it.item_id == item_id and hasattr(it, "SetValue"):
                        last_val = getattr(it, "value", None)
                        if current_text != last_val:
                            it.SetValue(current_text)
                            if getattr(it, "locked", False):
                                _SyncEditBoxLockText(self, item_id, current_text)
                            # 触发输入内容变化回调（如 0 锁定 / 1 解锁 控制）
                            on_change = getattr(it, "on_value_change", None)
                            if on_change:
                                try:
                                    on_change(self, item_id, current_text)
                                except Exception as e:
                                    dlog.client_print("==== edit_box on_value_change error: %s ====" % str(e))
                        break

        # ===== 滑块值轮询检测 =====
        for item_id, sliderCtrl in list(self.mRightSliderCtrlMap.items()):
            if not sliderCtrl:
                continue
            try:
                current_visual = float(sliderCtrl.GetSliderValue())
                last_visual = self.mRightSliderStates.get(item_id)
                if last_visual is not None and abs(current_visual - last_visual) > 1e-6:
                    # 锁定滑块兜底：即使被拖动也强制回滚到原值，阻止锁定值变化
                    if self.mCurrentRightGroup:
                        items = GetContentItems(*self.mCurrentRightGroup)
                        for it in items:
                            if it.item_id == item_id:
                                if getattr(it, "locked", False):
                                    try:
                                        sliderCtrl.SetSliderValue(last_visual)
                                    except Exception:
                                        pass
                                    _UpdateSliderValueLabel(self, it, last_visual)
                                    # 状态记录保持回滚后的值，防止反复回滚
                                    self.mRightSliderStates[item_id] = last_visual
                                    break
                                else:
                                    # 更新 item 运行时值（不立即写存储，等 SaveGroupSettings/退出时提交）
                                    steps = float(getattr(it, "steps", 1) or 1)
                                    if steps > 1:
                                        # 固定格类型：量化到最近档位（0~steps）
                                        quantized = int(round(current_visual * steps))
                                        quantized = max(0, min(int(steps), quantized))
                                        value = float(quantized)
                                    else:
                                        value = max(0.0, min(1.0, current_visual))
                                    if hasattr(it, "SetValue"):
                                        it.SetValue(value)
                                    _UpdateSliderValueLabel(self, it, value)
                                    if hasattr(it, "on_value_change") and it.on_value_change:
                                        try:
                                            it.on_value_change(self, item_id, value)
                                        except Exception as e:
                                            dlog.client_print("==== slider on_value_change error: %s ====" % str(e))
                                break
                    self.mRightSliderStates[item_id] = current_visual
            except Exception as e:
                dlog.client_print("==== OnTick slider state check error: %s ====" % str(e))

    def ClearMiddleOptions(self):
        self.mPendingMiddleCards = []
        self.mMiddleCardDelayTimer = 0
        self.mMiddleShowPending = None
        self.mMiddleShowDelayTimer = 0
        # 清空中间卡片 backdrop 动画状态
        self.mMiddleCardBackdropCtrls = []
        self.mMiddleCardAnimStates = {}
        # 清空正在淡入的卡片，改为淡出（动画关闭时直接移除）
        for item in self.mMiddleFadingInCtrls:
            if self.mEnableFadeAnim:
                self.mMiddleFadingOutCtrls.append(item)
            else:
                self.SafeRemoveMiddleCard(item[0])
        self.mMiddleFadingInCtrls = []
        exitingCtrls = list(self.mMiddleOptionCtrls)
        self.mMiddleOptionCtrls = []
        self.mMiddleCardIds = []
        self.mMiddleCardNames = []
        self.mMiddleSelectedIndex = -1
        for ctrl in exitingCtrls:
            try:
                if self.mEnableFadeAnim:
                    self.SetMiddleCardAlpha(ctrl, 1.0)
                    self.mMiddleFadingOutCtrls.append([ctrl, 1.0])
                else:
                    self.SafeRemoveMiddleCard(ctrl)
            except Exception:
                self.SafeRemoveMiddleCard(ctrl)

    def SafeRemoveMiddleCard(self, ctrl):
        self.mAlphaCtrlCache.pop(id(ctrl), None)
        try:
            self.RemoveChildControl(ctrl)
        except Exception:
            try:
                ctrl.SetVisible(False)
            except Exception:
                pass

    def FindMiddleCardIndexByPath(self, cardPath):
        for i, name in enumerate(self.mMiddleCardNames):
            if name in cardPath:
                return i
        return -1

    def _RestoreMiddleCardVisual(self, index):
        """恢复中间卡片视觉为 selected/normal（供 TouchUp/TouchCancel 复用）。"""
        if 0 <= index < len(self.mMiddleOptionCtrls):
            self.SetCardVisualState(
                self.mMiddleOptionCtrls[index],
                "selected" if index == self.mMiddleSelectedIndex else "normal"
            )

    def OnMiddleCardTouchDown(self, args):
        if self.mMiddlePressingIndex >= 0:
            return ViewRequest.Nothing
        cardPath = args.get('ButtonPath', '')
        index = self.FindMiddleCardIndexByPath(cardPath)
        if index < 0:
            return ViewRequest.Nothing
        # 已选中的卡片再次按下不显示 pressing、不响应
        if index == self.mMiddleSelectedIndex:
            return ViewRequest.Nothing
        self.mMiddlePressingIndex = index
        self.SetCardVisualState(self.mMiddleOptionCtrls[index], "pressing")
        dlog.client_print("==== Settings middle card %d touch down ====" % index)
        return ViewRequest.Nothing

    def OnMiddleCardTouchUp(self, args):
        # 兼容：个别引擎版本可能把取消事件路由进 Up 回调（Cancel=3）
        if args.get('TouchEvent') == 3:
            return self.OnMiddleCardTouchCancel(args)
        cardPath = args.get('ButtonPath', '')
        prevPressing = self.mMiddlePressingIndex
        self.mMiddlePressingIndex = -1
        index = self.FindMiddleCardIndexByPath(cardPath)
        if index < 0:
            if 0 <= prevPressing < len(self.mMiddleOptionCtrls):
                self._RestoreMiddleCardVisual(prevPressing)
            return ViewRequest.Nothing
        if 0 <= prevPressing < len(self.mMiddleOptionCtrls) and prevPressing != index:
            self._RestoreMiddleCardVisual(prevPressing)
        if prevPressing == index:
            # 已按下（选中）的卡片再次点击不响应
            if index == self.mMiddleSelectedIndex:
                self.SetCardVisualState(self.mMiddleOptionCtrls[index], "selected")
                return ViewRequest.Nothing
            self._StartMiddleCardBackdropAnimation(index)
            self.SelectMiddleCard(index)
        else:
            self._RestoreMiddleCardVisual(index)
        return ViewRequest.Nothing

    def OnMiddleCardTouchCancel(self, args):
        """触控在按钮范围外弹起时触发：只恢复视觉，不触发选中。"""
        index = self.mMiddlePressingIndex
        self.mMiddlePressingIndex = -1
        if index >= 0:
            self._RestoreMiddleCardVisual(index)
            dlog.client_print("==== Settings middle card %d touch cancel ====" % index)
        return ViewRequest.Nothing

    def SelectMiddleCard(self, index):
        if self.mMiddleSelectedIndex != index:
            if self.mMiddleSelectedIndex >= 0:
                self.SetCardVisualState(self.mMiddleOptionCtrls[self.mMiddleSelectedIndex], "normal")
                nameCtrl = self.mMiddleOptionCtrls[self.mMiddleSelectedIndex].GetChildByName('name')
                if nameCtrl:
                    nameCtrl.asLabel().SetTextColor([0.0, 0.0, 0.0])
            self.mMiddleSelectedIndex = index
            self._StartMiddleCardBackdropAnimation(index)
            dlog.client_print("==== middle card %d selected ====" % index)
        self.SetCardVisualState(self.mMiddleOptionCtrls[index], "selected")
        nameCtrl = self.mMiddleOptionCtrls[index].GetChildByName('name')
        if nameCtrl:
            nameCtrl.asLabel().SetTextColor([1.0, 1.0, 1.0])
        # 刷新对应中间卡片的右侧内容
        mainCardId = self.mIndexToCardId[self.mSelectedIndex] if 0 <= self.mSelectedIndex < len(self.mIndexToCardId) else None
        middleCardId = self.mMiddleCardIds[index] if 0 <= index < len(self.mMiddleCardIds) else None
        if mainCardId and middleCardId and self.mCurrentSubKey:
            self.RebuildRightContent(mainCardId, self.mCurrentSubKey, middleCardId)

    def OpenMiddlePanel(self):
        if not self.mMiddleCtrl:
            dlog.client_print("==== OpenMiddlePanel: middle control not found ====")
            return
        if self.mMiddleOpen:
            dlog.client_print("==== OpenMiddlePanel: already open ====")
            return
        if self.mMiddleHasAnimation:
            self.mMiddleCtrl.StopAnimation("offset")
            self.mMiddleCtrl.RemoveAnimation("offset")
        self.mMiddleCtrl.SetVisible(True)
        if self.mEnableEnterAnim:
            self.mMiddleCtrl.SetAnimation("offset", "setting", "middle_enter")
            self.mMiddleCtrl.PlayAnimation("offset")
            self.mMiddleHasAnimation = True
        else:
            # 关闭滑入动画：清理残留动画（否则 offset 会停在动画初始位），
            # 移除后面板回落到 json 默认 offset（结束位置）
            try:
                if self.mMiddleHasAnimation:
                    self.mMiddleCtrl.StopAnimation("offset")
                    self.mMiddleCtrl.RemoveAnimation("offset")
            except Exception:
                pass
            self.mMiddleHasAnimation = False
        self.mMiddleOpen = True
        dlog.client_print("==== middle panel enter animation played ====")

    def HideMiddlePanel(self):
        if not self.mMiddleCtrl:
            dlog.client_print("==== HideMiddlePanel: middle control not found ====")
            return
        if not self.mMiddleOpen:
            return
        self.mMiddleOpen = False
        self.ClearMiddleOptions()
        if not self.mEnableEnterAnim:
            # 关闭滑入动画：面板直接隐藏，不播滑出动画
            try:
                if self.mMiddleHasAnimation:
                    self.mMiddleCtrl.StopAnimation("offset")
                    self.mMiddleCtrl.RemoveAnimation("offset")
            except Exception:
                pass
            self.mMiddleCtrl.SetVisible(False)
            self.mMiddleHasAnimation = False
            dlog.client_print("==== middle panel hidden (enter anim off) ====")
            return
        if self.mMiddleHasAnimation:
            self.mMiddleCtrl.StopAnimation("offset")
            self.mMiddleCtrl.RemoveAnimation("offset")
        self.mMiddleCtrl.SetAnimation("offset", "setting", "middle_exit")
        self.mMiddleCtrl.SetAnimEndCallback("middle_exit", self.OnMiddleHidden)
        self.mMiddleCtrl.PlayAnimation("offset")
        self.mMiddleHasAnimation = True
        dlog.client_print("==== middle panel exit animation played ====")

    def OnMiddleHidden(self):
        if self.mMiddleOpen:
            dlog.client_print("==== OnMiddleHidden skipped, panel reopened ====")
            return
        if self.mMiddleCtrl:
            self.mMiddleCtrl.SetVisible(False)
        if self.mMiddleHasAnimation:
            self.mMiddleCtrl.RemoveAnimation("offset")
            self.mMiddleHasAnimation = False
        dlog.client_print("==== middle panel hidden ====")

    def OpenRightPanel(self):
        if not self.mRightCtrl:
            dlog.client_print("==== OpenRightPanel: right control not found ====")
            return
        if self.mRightOpen:
            # 面板已开，本次不涉及"打开动画"，消费一次性标志防止残留
            if self.mNavInstant:
                self.mNavInstant = None
            dlog.client_print("==== OpenRightPanel: already open ====")
            return
        if self.mRightHasAnimation:
            self.mRightCtrl.StopAnimation("offset")
            self.mRightCtrl.RemoveAnimation("offset")
        dlog.client_print("==== OpenRightPanel: anim=%s hasAnim=%s open=%s ====" % (
            self.mEnableEnterAnim, self.mRightHasAnimation, self.mRightOpen))
        self.mRightCtrl.SetVisible(True)
        suppress = self.mNavInstant
        self.mNavInstant = None  # 消费一次性导航"不播动画"：仅本次打开有效
        if self.mEnableEnterAnim and not suppress:
            self.mRightCtrl.SetAnimation("offset", "setting", "right_enter")
            # 延迟到下一帧 Play：刚 SetVisible 的控件立即 PlayAnimation 会停在 from
            self.mRightPendingPlay = True
            self.mRightHasAnimation = True
        else:
            # 关闭滑入动画：清理残留动画（否则 offset 会停在动画初始位），
            # 移除后面板回落到 json 默认 offset（结束位置）
            try:
                if self.mRightHasAnimation:
                    self.mRightCtrl.StopAnimation("offset")
                    self.mRightCtrl.RemoveAnimation("offset")
            except Exception:
                pass
            self.mRightHasAnimation = False
        self.mRightOpen = True
        dlog.client_print("==== right panel enter animation played ====")

    def HideRightPanel(self):
        if not self.mRightCtrl:
            dlog.client_print("==== HideRightPanel: right control not found ====")
            return
        if not self.mRightOpen:
            return
        # 收起右侧面板前保存当前分组的设置改动（切换主卡片等场景）
        old_group = self.mCurrentRightGroup
        if old_group and old_group[0] is not None:
            try:
                from SettingState import SaveGroupSettings
                SaveGroupSettings(old_group[0], old_group[1], old_group[2])
            except Exception as e:
                dlog.client_print("==== HideRightPanel: save group error: %s ====" % str(e))
        self.mRightOpen = False
        if not self.mEnableEnterAnim:
            # 关闭滑入动画：面板直接隐藏，不播滑出动画
            try:
                if self.mRightHasAnimation:
                    self.mRightCtrl.StopAnimation("offset")
                    self.mRightCtrl.RemoveAnimation("offset")
            except Exception:
                pass
            self.mRightCtrl.SetVisible(False)
            self.mRightHasAnimation = False
            dlog.client_print("==== right panel hidden (enter anim off) ====")
            return
        if self.mRightHasAnimation:
            self.mRightCtrl.StopAnimation("offset")
            self.mRightCtrl.RemoveAnimation("offset")
        self.mRightCtrl.SetAnimation("offset", "setting", "right_exit")
        self.mRightCtrl.SetAnimEndCallback("right_exit", self.OnRightHidden)
        self.mRightCtrl.PlayAnimation("offset")
        self.mRightHasAnimation = True
        dlog.client_print("==== right panel exit animation played ====")

    def OnRightHidden(self):
        if self.mRightOpen:
            dlog.client_print("==== OnRightHidden skipped, panel reopened ====")
            return
        if self.mRightCtrl:
            self.mRightCtrl.SetVisible(False)
        if self.mRightHasAnimation:
            self.mRightCtrl.RemoveAnimation("offset")
            self.mRightHasAnimation = False
        # 面板完全隐藏后，立即清除所有内容控件，避免下次打开时旧内容闪现
        for ctrl in self.mRightContentCtrls:
            self.SafeRemoveRightContent(ctrl)
        self.mRightContentCtrls = []
        self.mRightBtnCtrlMap.clear()
        self.mRightLockCtrlMap.clear()
        self.mRightSwitchCtrlMap.clear()
        self.mRightSwitchStates.clear()
        self.mRightEditBoxCtrlMap.clear()
        self.mRightEditBoxLockTextMap.clear()
        self.mRightEditBoxLockTextCache.clear()
        self.mRightSliderCtrlMap.clear()
        self.mRightSliderStates.clear()
        self.mRightSliderValueMap.clear()
        self.mRightSliderBaseMap.clear()
        self.mRightSliderBgMap.clear()
        self.mRightSliderLockOverlayMap.clear()
        self.mCollapsibleMenuTextMap.clear()
        self.mRightCollapsibleMenuCtrlMap.clear()
        for item in self.mRightFadingInCtrls:
            self.SafeRemoveRightContent(item[0])
        self.mRightFadingInCtrls = []
        for item in self.mRightFadingOutCtrls:
            self.SafeRemoveRightContent(item[0])
        self.mRightFadingOutCtrls = []
        self.mRightPendingItems = []
        self.mRightContentDelayTimer = 0
        self.mRightShowPending = None
        self.mRightShowDelayTimer = 0
        dlog.client_print("==== right panel hidden, content cleared ====")

    def ClearRightContent(self):
        """清空右侧内容控件（淡出后移除）。切换前先保存当前分组的设置改动。"""
        # 切换卡片/收起面板前，保存当前分组的未提交改动
        old_group = self.mCurrentRightGroup
        if old_group and old_group[0] is not None:
            try:
                from SettingState import SaveGroupSettings
                SaveGroupSettings(old_group[0], old_group[1], old_group[2])
            except Exception as e:
                dlog.client_print("==== ClearRightContent: save group error: %s ====" % str(e))
        self.mRightPendingItems = []
        self.mRightContentDelayTimer = 0
        self.mRightShowPending = None
        self.mRightShowDelayTimer = 0
        # 清空正在淡入的，改为淡出（动画关闭时直接移除）
        for item in self.mRightFadingInCtrls:
            if self.mEnableFadeAnim:
                self.mRightFadingOutCtrls.append(item)
            else:
                self.SafeRemoveRightContent(item[0])
        self.mRightFadingInCtrls = []
        # 现有控件改淡出（动画关闭时直接移除）
        exitingCtrls = list(self.mRightContentCtrls)
        self.mRightContentCtrls = []
        self.mRightBtnCtrlMap.clear()
        self.mRightLockCtrlMap.clear()
        self.mRightSwitchCtrlMap.clear()
        self.mRightSwitchStates.clear()
        self.mRightEditBoxCtrlMap.clear()
        self.mRightEditBoxLockTextMap.clear()
        self.mRightEditBoxLockTextCache.clear()
        self.mRightSliderCtrlMap.clear()
        self.mRightSliderStates.clear()
        self.mRightSliderValueMap.clear()
        self.mRightSliderBaseMap.clear()
        self.mRightSliderBgMap.clear()
        self.mRightSliderLockOverlayMap.clear()
        self.mCollapsibleMenuTextMap.clear()
        self.mRightCollapsibleMenuCtrlMap.clear()
        for ctrl in exitingCtrls:
            try:
                if self.mEnableFadeAnim:
                    self.SetRightContentAlpha(ctrl, 1.0)
                    self.mRightFadingOutCtrls.append([ctrl, 1.0])
                else:
                    self.SafeRemoveRightContent(ctrl)
            except Exception:
                self.SafeRemoveRightContent(ctrl)

    def RebuildRightContent(self, main_card_id, sub_key, middle_card_id):
        """从注册表重建右侧内容项（按 主卡片id + 子卡片key + 中间卡片id 分组）。

        切换卡片前先保存上一个分组的设置项改动（避免切换时丢失未提交的值）。
        """
        self.ClearRightContent()
        self.mCurrentRightGroup = (main_card_id, sub_key, middle_card_id)
        self.mRightFinishedStates.setdefault(self.mCurrentRightGroup, set())
        self.mRightFinishedStates[self.mCurrentRightGroup].clear()
        # 服务端"调试"分类：标记需要向服务端请求全局日志开关状态（由 OnTick 同步）
        self.mServerLogSwitchItem = None
        self.mServerLockItems = []
        self.mNeedServerLogRequest = False
        if sub_key == "server":
            try:
                from setting import (DEBUG_CATEGORY_ID, SWITCH_SERVER_LOG_OUTPUT,
                                     SERVER_COPY_COUNT, SERVER_COPY_BTN, SERVER_RESET_ID)
                if NormalizeMiddleCardId(middle_card_id) == DEBUG_CATEGORY_ID:
                    self.mServerLogSwitchItem = SWITCH_SERVER_LOG_OUTPUT
                    self.mServerLockItems = [SERVER_COPY_COUNT, SERVER_COPY_BTN, SERVER_RESET_ID]
                    self.mNeedServerLogRequest = True
                    # 服务端调试项锁定由服务端按玩家 OP 实时下发；清除持久化的旧锁定态，
                    # 避免 OP 曾解锁被保存后，下次(哪怕是其他权限)打开误用旧状态而穿透鉴权。
                    try:
                        from SettingState import ClearSettingLocked
                        for iid in (SWITCH_SERVER_LOG_OUTPUT,
                                    SERVER_COPY_COUNT, SERVER_COPY_BTN, SERVER_RESET_ID):
                            ClearSettingLocked(main_card_id, sub_key, middle_card_id, iid)
                    except Exception:
                        pass
            except ImportError:
                pass
        if not self.mRightScrollContent:
            dlog.client_print("==== RebuildRightContent: scroll content not found ====")
            return
        items = GetContentItems(main_card_id, sub_key, middle_card_id)
        dlog.client_print("==== RebuildRightContent for %s/%s/%s: %d items ====" % (main_card_id, sub_key, middle_card_id, len(items)))
        # 等旧内容淡出后立即开始逐项创建+淡入（与中间面板选中同步）
        self.mRightShowPending = list(items)
        self.mRightShowDelayTimer = 0

    def CreateNextRightContent(self):
        """延迟创建下一个右侧内容项，初始透明并入淡入队列。"""
        if not self.mRightPendingItems:
            return
        item = self.mRightPendingItems.pop(0)
        builder = _contentBuilders.get(item.type_name)
        if builder is None:
            dlog.client_print("==== CreateNextRightContent: builder for type '%s' not found ====" % item.type_name)
            return
        try:
            builder(self, self.mRightScrollContent, item)
            # 找到刚创建的控件（最后一个），设置初始透明（动画关闭时直接显示）
            if self.mRightContentCtrls:
                ctrl = self.mRightContentCtrls[-1]
                if self.mEnableFadeAnim:
                    self.SetRightContentAlpha(ctrl, 0.0)
                    self.mRightFadingInCtrls.append([ctrl, 0.0])
                else:
                    self.SetRightContentAlpha(ctrl, 1.0)
        except Exception as e:
            dlog.client_print("==== CreateNextRightContent item '%s' error: %s ====" % (item.item_id, str(e)))

    def SetEnterAnimEnabled(self, enabled):
        """开启/禁用中间/右边面板的滑入进入动画（"显示"分类开关回调）。

        关闭时正在播放的进入动画立即停止并回落到最终位置（移除 offset 动画）。
        """
        disabled_now = self.mEnableEnterAnim and not bool(enabled)
        self.mEnableEnterAnim = bool(enabled)
        if not disabled_now:
            return
        # 关闭动画：若面板正在滑入播放中，立即停掉并移除 offset，回到最终位置
        try:
            if self.mMiddleOpen and self.mMiddleHasAnimation:
                self.mMiddleCtrl.StopAnimation("offset")
                self.mMiddleCtrl.RemoveAnimation("offset")
                self.mMiddleHasAnimation = False
        except Exception as e:
            dlog.client_print("==== SetEnterAnimEnabled middle error: %s ====" % str(e))
        try:
            if self.mRightOpen and self.mRightHasAnimation:
                self.mRightCtrl.StopAnimation("offset")
                self.mRightCtrl.RemoveAnimation("offset")
                self.mRightHasAnimation = False
        except Exception as e:
            dlog.client_print("==== SetEnterAnimEnabled right error: %s ====" % str(e))
        dlog.client_print("==== 面板滑入进入动画已禁用 ====")

    def SetFadeAnimEnabled(self, enabled):
        """开启/禁用设置项与中间卡片的缓入/缓出动画（"优化"分类开关回调）。"""
        enabled = bool(enabled)
        self.mEnableFadeAnim = enabled
        if enabled:
            return
        # 关闭动画时立即完成所有进行中的淡入/淡出，避免残留透明控件
        # 右侧内容：淡入项直接置为不透明，淡出项直接移除
        for ctrl, _ in self.mRightFadingInCtrls:
            try:
                self.SetRightContentAlpha(ctrl, 1.0)
            except Exception:
                pass
        self.mRightFadingInCtrls = []
        for ctrl, _ in self.mRightFadingOutCtrls:
            try:
                self.SafeRemoveRightContent(ctrl)
            except Exception:
                pass
        self.mRightFadingOutCtrls = []
        # 中间卡片：淡入项直接置为不透明，淡出项直接移除
        for ctrl, _ in self.mMiddleFadingInCtrls:
            try:
                self.SetMiddleCardAlpha(ctrl, 1.0)
            except Exception:
                pass
        self.mMiddleFadingInCtrls = []
        for ctrl, _ in self.mMiddleFadingOutCtrls:
            try:
                self.SafeRemoveMiddleCard(ctrl)
            except Exception:
                pass
        self.mMiddleFadingOutCtrls = []
        dlog.client_print("==== 设置项与中间卡片缓入/缓出动画已禁用 ====")

    def SetRightContentAlpha(self, ctrl, alpha):
        """设置右侧内容项内部所有 image/label 子控件的透明度（使用缓存引用，避免每帧递归查找）"""
        self._SetAlphaWithCache(ctrl, alpha)

    def _CollectAlphaCtrls(self, ctrl):
        """一次性收集控件树中所有可设置透明度的子控件引用并缓存。

        返回收集到的控件列表（含 ctrl 自身）。仅在控件创建时调用一次，
        之后淡入淡出动画直接遍历缓存，避免每帧跨引擎 GetChildByName。
        """
        result = []

        def _collect(c):
            result.append(c)
            for childName in ("panel", "button", "switch", "edit_box", "input", "litle", "label", "desc",
                              "normal", "hover", "pressing", "lock", "lock_text", "finish", "text",
                              "icon_backdrop", "icon", "edit_box_label", "text_box", "place_holder"):
                try:
                    child = c.GetChildByName(childName)
                except Exception:
                    child = None
                if child is not None:
                    _collect(child)

        try:
            _collect(ctrl)
        except Exception:
            pass
        self.mAlphaCtrlCache[id(ctrl)] = result
        return result

    def _SetAlphaWithCache(self, ctrl, alpha):
        """从缓存获取控件树引用并设置透明度；无缓存时先收集再设置。"""
        ctrlId = id(ctrl)
        cached = self.mAlphaCtrlCache.get(ctrlId)
        if cached is None:
            cached = self._CollectAlphaCtrls(ctrl)
        for c in cached:
            try:
                c.SetAlpha(alpha)
            except Exception:
                pass

    def _SetControlTreeAlpha(self, ctrl, alpha):
        """递归设置控件树中所有子控件的透明度（image/label 生效）。

        用于控件创建时的初始透明；动画帧中请使用 _SetAlphaWithCache 避免重复查找。
        """
        self._SetAlphaWithCache(ctrl, alpha)

    def SafeRemoveRightContent(self, ctrl):
        """安全移除右侧内容控件。"""
        self.mAlphaCtrlCache.pop(id(ctrl), None)
        try:
            self.RemoveChildControl(ctrl)
        except Exception:
            try:
                ctrl.SetVisible(False)
            except Exception:
                pass

    def OnRightButtonClick(self, args, item_id):
        """右侧按钮点击回调：隐藏按钮文字，显示 finish 图标，并触发注册回调。"""
        dlog.client_print("==== OnRightButtonClick: %s ====" % item_id)
        ctrl = self.mRightBtnCtrlMap.get(item_id)
        if not ctrl:
            return ViewRequest.Nothing

        try:
            buttonCtrl = ctrl.GetChildByName('button')
            if not buttonCtrl:
                return ViewRequest.Nothing

            textLabel = buttonCtrl.GetChildByName('text')
            finishImg = buttonCtrl.GetChildByName('finish')

            if textLabel:
                textLabel.SetVisible(False)
            if finishImg:
                finishImg.SetVisible(True)

            if self.mCurrentRightGroup:
                self.mRightFinishedStates.setdefault(self.mCurrentRightGroup, set()).add(item_id)

            # 触发注册时传入的回调，传递 screenNode 和 item_id 以便动态更新 UI
            if self.mCurrentRightGroup:
                items = GetContentItems(*self.mCurrentRightGroup)
                for it in items:
                    if it.item_id == item_id and hasattr(it, "on_click") and it.on_click:
                        try:
                            it.on_click(self, item_id)
                        except Exception as e:
                            dlog.client_print("==== button on_click error: %s ====" % str(e))
                        break
        except Exception as e:
            dlog.client_print("==== OnRightButtonClick error: %s ====" % str(e))

        return ViewRequest.Nothing

    def OnCollapsibleMenuClick(self, args, menu_id, item):
        """折叠菜单内容项按钮点击回调：弹出关联折叠菜单。"""
        dlog.client_print("==== OnCollapsibleMenuClick: item_id=%s menu_id=%s ====" % (item.item_id, menu_id))
        global _g_ClientSystem
        if _g_ClientSystem:
            _g_ClientSystem.ShowCollapsibleMenu(menu_id, item)
        return ViewRequest.Nothing

    def UpdateCollapsibleMenuButtonText(self, item_id, text):
        """更新折叠菜单内容项按钮上实时显示的选择文字。"""
        textLabel = self.mCollapsibleMenuTextMap.get(item_id)
        if textLabel:
            _SetLabelText(textLabel, text, "UpdateCollapsibleMenuButtonText")
            textLabel.SetVisible(True)

    def SetLocked(self, item_id_or_path, locked):
        """
        统一设置指定内容项（按钮/开关/edit_box）的锁定状态。
        自动根据传入参数判断类型：
          - 若是右侧面板内容项 ID（按钮/开关/edit_box），执行对应内容项锁定逻辑
          - 若是 edit_box 完整控件路径，显示/隐藏 lock 子控件并禁用/启用输入

        :param item_id_or_path: 内容项 ID（AddButton/AddSwitch/AddEditBox 的 item_id）或 edit_box 控件完整路径
        :param locked:  True 锁定，False 解锁
        """
        dlog.client_print("==== SetLocked: target=%s locked=%s ====" % (item_id_or_path, locked))
        item_id = item_id_or_path
        # 1. 更新右侧面板内容项数据层
        if self.mCurrentRightGroup:
            item = GetContentItem(self.mCurrentRightGroup[0], self.mCurrentRightGroup[1],
                                  self.mCurrentRightGroup[2], item_id)
            if item and hasattr(item, "SetLocked"):
                item.SetLocked(locked)
        # 2. 判断类型并更新 UI 层
        # 2a. 按钮锁定逻辑
        btnCtrl = self.mRightBtnCtrlMap.get(item_id)
        if btnCtrl:
            lockCtrl = self.mRightLockCtrlMap.get(item_id)
            if lockCtrl:
                lockCtrl.SetVisible(locked)
            # 锁定状态切换时，从按钮上移除/恢复点击事件
            buttonCtrl = btnCtrl.GetChildByName('button')
            if buttonCtrl:
                btn = buttonCtrl.asButton()
                if btn:
                    if locked:
                        btn.SetButtonTouchUpCallback(lambda args: None)
                    else:
                        btn.AddTouchEventParams({})
                        _itm = None
                        if self.mCurrentRightGroup:
                            _itm = GetContentItem(self.mCurrentRightGroup[0],
                                                  self.mCurrentRightGroup[1],
                                                  self.mCurrentRightGroup[2], item_id)
                        if _itm is not None and _itm.type_name == "reset":
                            btn.SetButtonTouchUpCallback(
                                lambda args, iid=item_id: _OnResetButtonClick(self, iid)
                            )
                        else:
                            btn.SetButtonTouchUpCallback(
                                lambda args, iid=item_id: self.OnRightButtonClick(args, iid)
                            )
            return
        # 2b. 开关锁定逻辑
        switchCtrl = self.mRightSwitchCtrlMap.get(item_id)
        if switchCtrl:
            try:
                switchCtrl.SetTouchEnable(not locked)
            except Exception as e:
                dlog.client_print("==== SetLocked: SetTouchEnable error: %s ====" % str(e))
            return
        # 2b2. slider 锁定逻辑
        sliderCtrl = self.mRightSliderCtrlMap.get(item_id)
        if sliderCtrl:
            try:
                sliderCtrl.SetTouchEnable(not locked)
            except Exception as e:
                dlog.client_print("==== SetLocked: slider SetTouchEnable error: %s ====" % str(e))
            # 锁定视觉由运行时动态创建的灰层(slider_lock_bg)+拦截层(lock_overlay)+柄内锁定贴图(slider_lock)驱动
            sliderBaseCtrl = self.mRightSliderBaseMap.get(item_id)
            bgCtrl = getattr(self, 'mRightSliderBgMap', {}).get(item_id)
            overlayCtrl = getattr(self, 'mRightSliderLockOverlayMap', {}).get(item_id)
            _ApplySliderLockVisual(sliderBaseCtrl, bgCtrl, overlayCtrl, None, locked)
            return
        # 2b3. collapsible_menu 锁定逻辑
        cmBtnCtrl = self.mRightCollapsibleMenuCtrlMap.get(item_id)
        if cmBtnCtrl:
            lockCtrl = cmBtnCtrl.GetChildByName('lock')
            if lockCtrl:
                lockCtrl.SetVisible(locked)
            btn = cmBtnCtrl.asButton()
            if btn:
                if locked:
                    btn.SetButtonTouchUpCallback(lambda args: None)
                else:
                    btn.AddTouchEventParams({})
                    mid = ""
                    itm = None
                    if self.mCurrentRightGroup:
                        itm = GetContentItem(self.mCurrentRightGroup[0],
                                             self.mCurrentRightGroup[1],
                                             self.mCurrentRightGroup[2], item_id)
                        if itm:
                            mid = getattr(itm, "menu_id", "")
                    btn.SetButtonTouchUpCallback(
                        lambda args, mid=mid, itm=itm: self.OnCollapsibleMenuClick(args, mid, itm)
                    )
            return
        # 2c. edit_box 内容项锁定逻辑（按内容项 ID）
        editBoxCtrl = self.mRightEditBoxCtrlMap.get(item_id)
        if editBoxCtrl:
            lockCtrl = editBoxCtrl.GetChildByName('lock')
            if lockCtrl:
                lockCtrl.SetVisible(locked)
            else:
                dlog.client_print("==== SetLocked: edit_box lock child not found ====")
            try:
                editBoxCtrl.SetTouchEnable(not locked)
            except Exception as e:
                dlog.client_print("==== SetLocked: edit_box SetTouchEnable error: %s ====" % str(e))
            # 防御性：显式禁用/启用内部原生输入框
            inputCtrl = editBoxCtrl.GetChildByName('input')
            if inputCtrl:
                try:
                    inputCtrl.SetTouchEnable(not locked)
                except Exception as e:
                    dlog.client_print("==== SetLocked: input SetTouchEnable error: %s ====" % str(e))
            # 锁定层显示输入框当前文字
            if locked and inputCtrl:
                teb = inputCtrl.asTextEditBox()
                if teb:
                    try:
                        _SyncEditBoxLockText(self, item_id, teb.GetEditText())
                    except Exception:
                        pass
            return
        # 2d. edit_box 锁定逻辑（按完整控件路径）
        if item_id and isinstance(item_id, str) and item_id.startswith('/'):
            editBoxCtrl = self.GetBaseUIControl(item_id)
            if editBoxCtrl:
                # 显示/隐藏 lock 子控件
                lockCtrl = editBoxCtrl.GetChildByName('lock')
                if lockCtrl:
                    lockCtrl.SetVisible(locked)
                else:
                    dlog.client_print("==== SetLocked: edit_box lock child not found at %s ====" % item_id)
                # 禁用/启用编辑框交互
                try:
                    editBoxCtrl.SetTouchEnable(not locked)
                except Exception as e:
                    dlog.client_print("==== SetLocked: edit_box SetTouchEnable error: %s ====" % str(e))
                # 防御性：显式禁用/启用内部原生输入框
                inputCtrl = editBoxCtrl.GetChildByName('input')
                if inputCtrl:
                    try:
                        inputCtrl.SetTouchEnable(not locked)
                    except Exception as e:
                        dlog.client_print("==== SetLocked: input SetTouchEnable error: %s ====" % str(e))
                # 锁定层显示输入框当前文字
                if locked and inputCtrl:
                    teb = inputCtrl.asTextEditBox()
                    if teb:
                        try:
                            _SyncEditBoxLockText(self, item_id, teb.GetEditText())
                        except Exception:
                            pass
            else:
                dlog.client_print("==== SetLocked: edit_box not found at %s ====" % item_id)
            return
        dlog.client_print("==== SetLocked: unknown target %s ====" % item_id)

    def OnSwitchToggle(self, args, item_id):
        """开关状态改变回调。"""
        dlog.client_print("==== OnSwitchToggle: %s ====" % item_id)
        # 获取开关当前状态
        state = None
        switchCtrl = self.mRightSwitchCtrlMap.get(item_id)
        if switchCtrl:
            switchToggle = switchCtrl.asSwitchToggle()
            if switchToggle:
                toggle_path = "/this_toggle"
                try:
                    state = switchToggle.GetToggleState(toggle_path)
                    dlog.client_print("==== OnSwitchToggle: %s -> %s ====" % (item_id, state))
                except Exception as e:
                    dlog.client_print("==== OnSwitchToggle: GetToggleState error: %s ====" % str(e))
        # 触发 on_toggle 回调
        if self.mCurrentRightGroup and state is not None:
            items = GetContentItems(*self.mCurrentRightGroup)
            for it in items:
                if it.item_id == item_id and hasattr(it, "on_toggle") and it.on_toggle:
                    try:
                        it.on_toggle(self, item_id, state)
                    except Exception as e:
                        dlog.client_print("==== switch on_toggle error: %s ====" % str(e))
                    break
        return ViewRequest.Nothing

def RegisterContentBuilder(type_name, builder):
    """注册右侧内容项 UI 构建器。"""
    _contentBuilders[type_name] = builder


def _SetLabelText(ctrl, text, logPrefix):
    """同时通过 PropertyBag 和 asLabel().SetText() 设置 label 文本，确保生效。"""
    if not ctrl:
        dlog.client_print("==== %s: control is None ====" % logPrefix)
        return False
    try:
        # PropertyBag 中 key 为属性名 text（不带 $），覆盖变量绑定解析后的值
        ctrl.SetPropertyBag({"text": text})
        label = ctrl.asLabel()
        if label:
            label.SetText(text)
        return True
    except Exception as e:
        dlog.client_print("==== %s set text error: %s ====" % (logPrefix, str(e)))
        return False


def BuildTextContent(screenNode, parent, item):
    """文本内容项 UI 创建。"""
    dlog.client_print("==== BuildTextContent item_id=%s title=%s text=%s ====" % (item.item_id, item.title, item.text))
    ctrl = screenNode.CreateChildControl(
        'setting.text_content',
        'rtext_' + item.item_id,
        parent,
        True
    )
    if not ctrl:
        dlog.client_print("==== BuildTextContent: create control failed ====")
        return
    # 立即设置透明，避免创建时闪现（默认 alpha=1.0，右侧面板滑动进入时可见）
    try:
        screenNode._SetControlTreeAlpha(ctrl, 0.0)
    except Exception:
        pass
    # text_content 根节点是 image，子控件在 panel 内（litle 小标题 + label 正文）
    panelCtrl = ctrl.GetChildByName('panel')
    if panelCtrl:
        litleCtrl = panelCtrl.GetChildByName('litle')
        if litleCtrl:
            _SetLabelText(litleCtrl, item.title, "BuildTextContent.litle")
            litleCtrl.SetVisible(bool(item.title))  # 空标题隐藏，正文上移贴顶
        else:
            dlog.client_print("==== BuildTextContent: litle child not found in panel ====")
        labelCtrl = panelCtrl.GetChildByName('label')
        if labelCtrl:
            _SetLabelText(labelCtrl, item.text, "BuildTextContent.label")
            labelCtrl.SetVisible(bool(item.text))  # 空正文防御性隐藏
        else:
            dlog.client_print("==== BuildTextContent: label child not found in panel ====")
    else:
        dlog.client_print("==== BuildTextContent: panel child not found ====")
    screenNode.mRightContentCtrls.append(ctrl)


def _UpdateSliderValueLabel(screenNode, item, value):
    """更新滑块数值显示 label（支持自定义显示文本）。"""
    valueCtrl = screenNode.mRightSliderValueMap.get(item.item_id)
    if not valueCtrl:
        return
    try:
        # 先同步 item.value（确保 GetDisplayText 读最新值）
        if hasattr(item, "SetValue"):
            item.SetValue(value)
        if hasattr(item, "GetDisplayText"):
            text = item.GetDisplayText()
        else:
            steps = float(getattr(item, "steps", 1) or 1)
            if steps > 1:
                text = "%d" % int(round(float(value)))
            else:
                text = "%.0f%%" % (float(value) * 100)
        _SetLabelText(valueCtrl, text, "BuildSliderContent.value")
    except Exception as e:
        dlog.client_print("==== UpdateSliderValueLabel error: %s ====" % str(e))


def _RestoreItemLocked(screenNode, item):
    """Build 内容项时从存储恢复动态锁定状态，并更新 item 数据层。"""
    group = getattr(screenNode, 'mCurrentRightGroup', None)
    if not group or group[0] is None:
        return
    try:
        from SettingState import GetSettingLocked
        locked = GetSettingLocked(group[0], group[1], group[2], item.item_id,
                                  default=getattr(item, "locked", False))
        if hasattr(item, "SetLocked"):
            item.SetLocked(bool(locked))
        else:
            item.locked = bool(locked)
        item._loaded = True
    except Exception as e:
        dlog.client_print("==== RestoreItemLocked error %s: %s ====" % (item.item_id, str(e)))


def BuildButtonContent(screenNode, parent, item):
    """按钮内容项 UI 创建。"""
    _RestoreItemLocked(screenNode, item)
    dlog.client_print("==== BuildButtonContent item_id=%s desc=%s button_text=%s litle=%s ====" % (
        item.item_id, item.desc, item.button_text, item.litle
    ))
    ctrl = screenNode.CreateChildControl(
        'setting.button_content',
        'rbtn_' + item.item_id,
        parent,
        True
    )
    if not ctrl:
        dlog.client_print("==== BuildButtonContent: create control failed ====")
        return
    # 立即设置透明，避免创建时闪现（默认 alpha=1.0，右侧面板滑动进入时可见）
    try:
        screenNode._SetControlTreeAlpha(ctrl, 0.0)
    except Exception:
        pass
    # 子控件（desc 描述 + litle 小标题）在 panel 内
    panelCtrl = ctrl.GetChildByName('panel')
    if panelCtrl:
        # 设置小标题
        litleCtrl = panelCtrl.GetChildByName('litle')
        if litleCtrl:
            _SetLabelText(litleCtrl, item.litle, "BuildButtonContent.litle")
            litleCtrl.SetVisible(bool(item.litle))  # 空标题隐藏，正文上移贴顶
        # 设置左侧描述文字
        descCtrl = panelCtrl.GetChildByName('desc')
        if descCtrl:
            _SetLabelText(descCtrl, item.desc, "BuildButtonContent.desc")
            descCtrl.SetVisible(bool(item.desc))  # 空正文防御性隐藏
        else:
            dlog.client_print("==== BuildButtonContent: desc child not found in panel ====")
    else:
        dlog.client_print("==== BuildButtonContent: panel child not found ====")

    buttonCtrl = ctrl.GetChildByName('button')
    if not buttonCtrl:
        dlog.client_print("==== BuildButtonContent: button child not found ====")
        return

    textLabel = buttonCtrl.GetChildByName('text')
    finishImg = buttonCtrl.GetChildByName('finish')

    if textLabel:
        _SetLabelText(textLabel, item.button_text, "BuildButtonContent.text")
        textLabel.SetVisible(True)
    else:
        dlog.client_print("==== BuildButtonContent: text child not found ====")
    if finishImg:
        finishImg.SetVisible(False)

    # 锁定处理：显示 lock 图层并禁止点击
    lockCtrl = buttonCtrl.GetChildByName('lock')
    dlog.client_print("==== BuildButton: item=%s locked=%s bindCb=%s ====" % (
        item.item_id, item.locked, not item.locked))
    if item.locked:
        if lockCtrl:
            lockCtrl.SetVisible(True)
        # 锁定状态不注册点击回调，按钮无法交互
    else:
        if lockCtrl:
            lockCtrl.SetVisible(False)
        btn = buttonCtrl.asButton()
        if btn:
            btn.AddTouchEventParams({})
            btn.SetButtonTouchUpCallback(
                lambda args, iid=item.item_id: screenNode.OnRightButtonClick(args, iid)
            )

    # 存储 lock 控件引用，用于动态更新锁定状态
    if lockCtrl:
        screenNode.mRightLockCtrlMap[item.item_id] = lockCtrl

    screenNode.mRightContentCtrls.append(ctrl)
    screenNode.mRightBtnCtrlMap[item.item_id] = ctrl


def BuildCollapsibleMenuContent(screenNode, parent, item):
    """折叠菜单内容项 UI 创建：litle/desc + 按钮(左对齐显示当前选择 + 右侧箭头)，点击弹出折叠菜单。"""
    # 恢复持久化锁定状态 + 选中状态（优先读存储，无存储值时回退运行时/默认选中卡）
    _RestoreItemLocked(screenNode, item)
    group = screenNode.mCurrentRightGroup
    if group and group[0] is not None:
        stored = GetSettingValue(group[0], group[1], group[2], item.item_id,
                                 default=item.selected_id)
    else:
        stored = item.selected_id
    stored_id = stored if stored is not None else item.default_selected_id
    if stored_id is not None:
        item.SetSelected(stored_id, item._NameOf(stored_id))
    item.value = item.selected_id
    item._loaded = True
    dlog.client_print("==== BuildCollapsibleMenuContent item_id=%s desc=%s menu_id=%s litle=%s selected=%s locked=%s ====" % (
        item.item_id, item.desc, item.menu_id, item.litle, item.GetDisplayText(), item.locked
    ))
    ctrl = screenNode.CreateChildControl(
        'setting.collapsible_menu_content',
        'rcm_' + item.item_id,
        parent,
        True
    )
    if not ctrl:
        dlog.client_print("==== BuildCollapsibleMenuContent: create control failed ====")
        return
    # 立即设置透明，避免创建时闪现
    try:
        screenNode._SetControlTreeAlpha(ctrl, 0.0)
    except Exception:
        pass
    # 子控件（litle 小标题 + desc 描述 + button）在 panel 内
    panelCtrl = ctrl.GetChildByName('panel')
    if not panelCtrl:
        dlog.client_print("==== BuildCollapsibleMenuContent: panel child not found ====")
    else:
        litleCtrl = panelCtrl.GetChildByName('litle')
        if litleCtrl:
            _SetLabelText(litleCtrl, item.litle, "BuildCollapsibleMenuContent.litle")
            litleCtrl.SetVisible(bool(item.litle))  # 空标题隐藏，正文上移贴顶
        descCtrl = panelCtrl.GetChildByName('desc')
        if descCtrl:
            _SetLabelText(descCtrl, item.desc, "BuildCollapsibleMenuContent.desc")
            descCtrl.SetVisible(bool(item.desc))  # 空正文防御性隐藏
        # 按钮：位于 button_wrap 容器内（容器占满 panel 宽，按钮用 center 锚点水平居中）
        wrapCtrl = panelCtrl.GetChildByName('button_wrap')
        buttonCtrl = wrapCtrl.GetChildByName('button') if wrapCtrl else None
        if not buttonCtrl:
            dlog.client_print("==== BuildCollapsibleMenuContent: button child not found ====")
        else:
            textLabel = buttonCtrl.GetChildByName('text')
            if textLabel:
                _SetLabelText(textLabel, item.GetDisplayText(), "BuildCollapsibleMenuContent.text")
                textLabel.SetVisible(True)
                # 记录按钮文字 label，用于选择后实时更新
                screenNode.mCollapsibleMenuTextMap[item.item_id] = textLabel
            # 记录按钮控件，供 SetLocked 禁用/恢复点击与锁定图层
            screenNode.mRightCollapsibleMenuCtrlMap[item.item_id] = buttonCtrl
            # 锁定处理：显示 lock 图层并禁止点击
            lockCtrl = buttonCtrl.GetChildByName('lock')
            if lockCtrl:
                lockCtrl.SetVisible(item.locked)
            btn = buttonCtrl.asButton()
            if btn:
                if not item.locked:
                    btn.AddTouchEventParams({})
                    btn.SetButtonTouchUpCallback(
                        lambda args, mid=item.menu_id, itm=item: screenNode.OnCollapsibleMenuClick(args, mid, itm)
                    )
                else:
                    btn.SetButtonTouchUpCallback(lambda args: None)
    screenNode.mRightContentCtrls.append(ctrl)


def BuildSwitchContent(screenNode, parent, item):
    """开关内容项 UI 创建。"""
    _RestoreItemLocked(screenNode, item)
    dlog.client_print("==== BuildSwitchContent item_id=%s desc=%s default_value=%s locked=%s litle=%s ====" % (
        item.item_id, item.desc, item.default_value, item.locked, item.litle
    ))
    ctrl = screenNode.CreateChildControl(
        'setting.switch_content',
        'rsw_' + item.item_id,
        parent,
        True
    )
    if not ctrl:
        dlog.client_print("==== BuildSwitchContent: create control failed ====")
        return
    # 立即设置透明，避免创建时闪现
    try:
        screenNode._SetControlTreeAlpha(ctrl, 0.0)
    except Exception:
        pass

    # 子控件（desc 描述 + litle 小标题）在 panel 内
    panelCtrl = ctrl.GetChildByName('panel')
    if panelCtrl:
        # 设置小标题
        litleCtrl = panelCtrl.GetChildByName('litle')
        if litleCtrl:
            _SetLabelText(litleCtrl, item.litle, "BuildSwitchContent.litle")
            litleCtrl.SetVisible(bool(item.litle))  # 空标题隐藏，正文上移贴顶
        # 设置左侧描述文字
        descCtrl = panelCtrl.GetChildByName('desc')
        if descCtrl:
            _SetLabelText(descCtrl, item.desc, "BuildSwitchContent.desc")
            descCtrl.SetVisible(bool(item.desc))  # 空正文防御性隐藏
        else:
            dlog.client_print("==== BuildSwitchContent: desc child not found in panel ====")
    else:
        dlog.client_print("==== BuildSwitchContent: panel child not found ====")

    # 获取开关控件
    switchCtrl = ctrl.GetChildByName('switch')
    if not switchCtrl:
        dlog.client_print("==== BuildSwitchContent: switch child not found ====")
        return

    # 设置默认值（优先读持久化状态，无存储值时回退 default_value）
    switchToggle = switchCtrl.asSwitchToggle()
    if switchToggle:
        toggle_path = "/this_toggle"
        group = screenNode.mCurrentRightGroup
        if group and group[0] is not None:
            init_state = GetSettingValue(group[0], group[1], group[2], item.item_id,
                                         default=item.default_value)
        else:
            init_state = item.default_value
        try:
            switchToggle.SetToggleState(bool(init_state), toggle_path)
            # 同步 item 运行时值（供退出时 SaveAllSettings 批量提交）
            if hasattr(item, "SetValue"):
                item.SetValue(bool(init_state))
            item._loaded = True
        except Exception as e:
            dlog.client_print("==== BuildSwitchContent: SetToggleState error: %s ====" % str(e))

    # 锁定处理：禁用交互（SetTouchEnable 是 BaseUIControl 的方法）
    try:
        switchCtrl.SetTouchEnable(not item.locked)
    except Exception as e:
        dlog.client_print("==== BuildSwitchContent: SetTouchEnable error: %s ====" % str(e))

    # 存储引用（存 switchCtrl 以调用 SetTouchEnable 等 BaseUIControl 方法）
    screenNode.mRightSwitchCtrlMap[item.item_id] = switchCtrl
    # 记录初始状态用于轮询检测
    try:
        toggle = switchCtrl.asSwitchToggle()
        if toggle:
            screenNode.mRightSwitchStates[item.item_id] = toggle.GetToggleState("/this_toggle")
    except Exception as e:
        dlog.client_print("==== BuildSwitchContent: init state error: %s ====" % str(e))
    screenNode.mRightContentCtrls.append(ctrl)


def _SyncEditBoxLockText(screenNode, item_id, text):
    """同步 edit_box 锁定层的显示文字。"""
    lockTextCtrl = screenNode.mRightEditBoxLockTextMap.get(item_id)
    if not lockTextCtrl:
        return
    last = screenNode.mRightEditBoxLockTextCache.get(item_id)
    if last != text:
        _SetLabelText(lockTextCtrl, text, "OnTick.edit_box.lock_text")
        screenNode.mRightEditBoxLockTextCache[item_id] = text


def BuildEditBoxContent(screenNode, parent, item):
    """编辑框内容项 UI 创建。"""
    _RestoreItemLocked(screenNode, item)
    dlog.client_print("==== BuildEditBoxContent item_id=%s desc=%s default_value=%s placeholder=%s locked=%s litle=%s ====" % (
        item.item_id, item.desc, item.default_value, item.placeholder, item.locked, item.litle
    ))
    ctrl = screenNode.CreateChildControl(
        'setting.edit_box_content',
        'redt_' + item.item_id,
        parent,
        True
    )
    if not ctrl:
        dlog.client_print("==== BuildEditBoxContent: create control failed ====")
        return
    # 立即设置透明，避免创建时闪现
    try:
        screenNode._SetControlTreeAlpha(ctrl, 0.0)
    except Exception:
        pass
    # 左侧 panel：litle 小标题 + desc 描述
    panelCtrl = ctrl.GetChildByName('panel')
    if panelCtrl:
        litleCtrl = panelCtrl.GetChildByName('litle')
        if litleCtrl:
            _SetLabelText(litleCtrl, item.litle, "BuildEditBoxContent.litle")
            litleCtrl.SetVisible(bool(item.litle))  # 空标题隐藏，正文上移贴顶
        descCtrl = panelCtrl.GetChildByName('desc')
        if descCtrl:
            _SetLabelText(descCtrl, item.desc, "BuildEditBoxContent.desc")
            descCtrl.SetVisible(bool(item.desc))  # 空正文防御性隐藏
        else:
            dlog.client_print("==== BuildEditBoxContent: desc child not found in panel ====")
    else:
        dlog.client_print("==== BuildEditBoxContent: panel child not found ====")

    # 右侧编辑框包装器
    editBoxCtrl = ctrl.GetChildByName('edit_box')
    if not editBoxCtrl:
        dlog.client_print("==== BuildEditBoxContent: edit_box child not found ====")
        return

    # 取真正的原生输入控件
    inputCtrl = editBoxCtrl.GetChildByName('input')
    if not inputCtrl:
        dlog.client_print("==== BuildEditBoxContent: input child not found ====")
        return

    # 设置 placeholder
    try:
        inputCtrl.SetPropertyBag({"place_holder_text": item.placeholder})
    except Exception as e:
        dlog.client_print("==== BuildEditBoxContent: SetPropertyBag placeholder error: %s ====" % str(e))

    # 设置初始内容（优先读持久化状态，其次运行时 value，最后 default_value）
    textEditBox = inputCtrl.asTextEditBox()
    if textEditBox:
        group = screenNode.mCurrentRightGroup
        if group and group[0] is not None:
            init_text = GetSettingValue(group[0], group[1], group[2], item.item_id,
                                        default=item.default_value)
        else:
            init_text = getattr(item, "value", None)
            if init_text is None:
                init_text = item.default_value
        item.value = init_text if init_text is not None else ""
        item._loaded = True
        try:
            textEditBox.SetEditText(item.value)
        except Exception as e:
            dlog.client_print("==== BuildEditBoxContent: SetEditText error: %s ====" % str(e))
    else:
        dlog.client_print("==== BuildEditBoxContent: asTextEditBox failed ====")

    # 锁定处理：显示 lock 覆盖层并禁用整个包装器（连带 input）
    lockCtrl = editBoxCtrl.GetChildByName('lock')
    if lockCtrl:
        lockCtrl.SetVisible(item.locked)
    try:
        editBoxCtrl.SetTouchEnable(not item.locked)
    except Exception as e:
        dlog.client_print("==== BuildEditBoxContent: SetTouchEnable error: %s ====" % str(e))

    # 记录 lock_text 控件引用，锁定时显示输入框当前文字
    lockTextCtrl = None
    if lockCtrl:
        lockTextCtrl = lockCtrl.GetChildByName('lock_text')
    screenNode.mRightEditBoxLockTextMap[item.item_id] = lockTextCtrl
    if item.locked and lockTextCtrl:
        _SetLabelText(lockTextCtrl, item.value, "BuildEditBoxContent.lock_text")

    # 存储包装器引用，供 SetLocked 动态更新锁定状态
    screenNode.mRightEditBoxCtrlMap[item.item_id] = editBoxCtrl
    screenNode.mRightContentCtrls.append(ctrl)


def _ApplySliderLockVisual(sliderBaseCtrl, bgCtrl, overlayCtrl, value, locked):
    """锁定滑块：灰层 slider_lock_bg + 输入拦截层 lock_overlay（slider 运行时子控件，覆盖 slider 区域），柄贴图替换为 button_lock。

    slider_lock_bg（灰底 #6a6a6a(50%)）与 lock_overlay（input_panel，is_swallow 吞掉滑块区域输入）在 BuildSliderContent 里
    运行时动态创建为 slider 的子控件，铺满 slider 区域（100%x100%）；slider_lock（button_lock 贴图）作为 slider_box 的子控件随柄移动。
    动态创建不影响 slider_content 的 100%c 高度计算（slider 高度固定 10px），锁定/未锁定卡片高度一致。
    注意：lock_overlay 不能用 modal（modal 会吞掉全屏输入导致界面卡死），配合 SetTouchEnable(False) 实现锁定。
    """
    if bgCtrl:
        try:
            bgCtrl.SetVisible(bool(locked))
        except Exception as e:
            dlog.client_print("==== _ApplySliderLockVisual: bg SetVisible error: %s ====" % str(e))
    if overlayCtrl:
        try:
            overlayCtrl.SetVisible(bool(locked))
        except Exception as e:
            dlog.client_print("==== _ApplySliderLockVisual: overlay SetVisible error: %s ====" % str(e))
    if sliderBaseCtrl:
        try:
            sliderBoxCtrl = sliderBaseCtrl.GetChildByName('slider_box')
            if sliderBoxCtrl:
                # 锁定时隐藏原 default 柄贴图，仅显示 button_lock 贴图
                defaultCtrl = sliderBoxCtrl.GetChildByName('default')
                if defaultCtrl:
                    defaultCtrl.SetVisible(not locked)
                lockImg = sliderBoxCtrl.GetChildByName('slider_lock')
                if lockImg:
                    lockImg.SetVisible(bool(locked))
        except Exception as e:
            dlog.client_print("==== _ApplySliderLockVisual: slider lock visual error: %s ====" % str(e))


def BuildSliderContent(screenNode, parent, item):
    """滑块内容项 UI 创建（上面 litle+desc 文字，下面 slider）。"""
    _RestoreItemLocked(screenNode, item)
    dlog.client_print("==== BuildSliderContent item_id=%s desc=%s value=%s steps=%s locked=%s litle=%s ====" % (
        item.item_id, item.desc, item.value, item.steps, item.locked, item.litle
    ))
    ctrl = screenNode.CreateChildControl(
        'setting.slider_content',
        'rsl_' + item.item_id,
        parent,
        True
    )
    if not ctrl:
        dlog.client_print("==== BuildSliderContent: create control failed ====")
        return
    # 立即设置透明，避免创建时闪现
    try:
        screenNode._SetControlTreeAlpha(ctrl, 0.0)
    except Exception:
        pass

    # 文字 panel：litle 小标题 + desc 描述（顶层子控件）
    panelCtrl = ctrl.GetChildByName('panel')
    if panelCtrl:
        litleCtrl = panelCtrl.GetChildByName('litle')
        if litleCtrl:
            _SetLabelText(litleCtrl, item.litle, "BuildSliderContent.litle")
            litleCtrl.SetVisible(bool(item.litle))
        descCtrl = panelCtrl.GetChildByName('desc')
        if descCtrl:
            _SetLabelText(descCtrl, item.desc, "BuildSliderContent.desc")
            descCtrl.SetVisible(bool(item.desc))
    else:
        dlog.client_print("==== BuildSliderContent: panel child not found ====")
    # 动态数值 label
    valueCtrl = ctrl.GetChildByName('value')
    if valueCtrl:
        screenNode.mRightSliderValueMap[item.item_id] = valueCtrl
    else:
        dlog.client_print("==== BuildSliderContent: value child not found ====")

    # 获取滑块控件
    sliderBaseCtrl = ctrl.GetChildByName('slider')
    if not sliderBaseCtrl:
        dlog.client_print("==== BuildSliderContent: slider child not found ====")
        return
    sliderCtrl = sliderBaseCtrl.asSlider()
    if not sliderCtrl:
        dlog.client_print("==== BuildSliderContent: asSlider failed ====")
        return

    # 设置初始值（优先读持久化状态，无存储值时回退 item.value/default_value）
    group = screenNode.mCurrentRightGroup
    if group and group[0] is not None:
        init_value = GetSettingValue(group[0], group[1], group[2], item.item_id,
                                     default=item.value if item.value is not None else item.default_value)
    else:
        init_value = item.value if item.value is not None else item.default_value
    try:
        init_value = float(init_value)
    except Exception:
        init_value = float(item.default_value)
    steps = float(getattr(item, "steps", 1) or 1)
    if steps > 1:
        # 固定格类型：item.value 为档位整数，视觉位置 = value / steps
        init_value = max(0.0, min(steps, init_value))
        visual_value = init_value / steps
        item.SetValue(init_value)
    else:
        # 百分比类型：0~1
        visual_value = max(0.0, min(1.0, init_value))
        item.SetValue(visual_value)
    item._loaded = True
    try:
        sliderCtrl.SetSliderValue(visual_value)
    except Exception as e:
        dlog.client_print("==== BuildSliderContent: SetSliderValue error: %s ====" % str(e))
    # 设置数值显示文本（供动态显示当前滑块值）
    _UpdateSliderValueLabel(screenNode, item, item.value)

    # 锁定视觉：运行时动态创建灰层 slider_lock_bg + 拦截层 lock_overlay 作为 slider 子控件（铺满 slider 区域），
    # 柄内 button_lock 贴图锁定时显示。注意：不可写进 slider@common.slider 的 JSON controls
    # （会顶掉基类 slider_box 等子控件，导致 "Control name could not be resolved: slider_box" 崩溃）
    bgCtrl = None
    lockOverlayCtrl = None
    try:
        bgCtrl = screenNode.CreateChildControl(
            'setting.slider_lock_bg', 'slider_lock_bg', sliderBaseCtrl, True)
        if bgCtrl:
            screenNode.mRightSliderBgMap[item.item_id] = bgCtrl
        lockOverlayCtrl = screenNode.CreateChildControl(
            'setting.slider_lock_overlay', 'lock_overlay', sliderBaseCtrl, True)
        if lockOverlayCtrl:
            screenNode.mRightSliderLockOverlayMap[item.item_id] = lockOverlayCtrl
        sliderBoxCtrl = sliderBaseCtrl.GetChildByName('slider_box')
        if sliderBoxCtrl:
            lockImg = screenNode.CreateChildControl(
                'setting.slider_box_locked', 'slider_lock', sliderBoxCtrl, True)
            if lockImg:
                lockImg.SetVisible(item.locked)
    except Exception as e:
        dlog.client_print("==== BuildSliderContent: create slider_lock error: %s ====" % str(e))

    # 锁定处理：lock_overlay 吞掉滑块区域输入（is_swallow，不用 modal 以免全屏输入卡死）+ 灰层，柄内 button_lock 贴图
    _ApplySliderLockVisual(sliderBaseCtrl, bgCtrl, lockOverlayCtrl, visual_value, item.locked)
    try:
        sliderCtrl.SetTouchEnable(not item.locked)
    except Exception as e:
        dlog.client_print("==== BuildSliderContent: SetTouchEnable error: %s ====" % str(e))

    # 存储引用供 OnTick 轮询检测（记录视觉位置）
    screenNode.mRightSliderCtrlMap[item.item_id] = sliderCtrl
    screenNode.mRightSliderBaseMap[item.item_id] = sliderBaseCtrl
    try:
        screenNode.mRightSliderStates[item.item_id] = visual_value
    except Exception as e:
        dlog.client_print("==== BuildSliderContent: init state error: %s ====" % str(e))
    screenNode.mRightContentCtrls.append(ctrl)


def _ApplySettingToOpenUI(main_card_id, key, middle_card_id, item_id, value):
    """API 修改设置值后同步刷新已打开 UI。幂等：控件当前值已等于目标值时跳过。"""
    if not _g_ClientSystem:
        return
    node = _g_ClientSystem.mSettingsScreenNode
    if not node:
        return
    group = node.mCurrentRightGroup
    if not group:
        return
    if (group[0] != main_card_id or group[1] != key or
            NormalizeMiddleCardId(group[2]) != NormalizeMiddleCardId(middle_card_id)):
        return
    # 开关
    switchCtrl = node.mRightSwitchCtrlMap.get(item_id)
    if switchCtrl is not None:
        toggle = switchCtrl.asSwitchToggle()
        if toggle:
            try:
                new_state = bool(value)
                if toggle.GetToggleState("/this_toggle") != new_state:
                    toggle.SetToggleState(new_state, "/this_toggle")
                    node.mRightSwitchStates[item_id] = new_state
            except Exception as e:
                dlog.client_print("==== ApplySettingToOpenUI switch error: %s ====" % str(e))
        it = GetContentItem(group[0], group[1], NormalizeMiddleCardId(group[2]), item_id)
        if it and hasattr(it, "SetValue"):
            it.SetValue(bool(value))
            it._loaded = True
        return
    # 滑块
    sliderCtrl = node.mRightSliderCtrlMap.get(item_id)
    if sliderCtrl is not None:
        it = GetContentItem(group[0], group[1], NormalizeMiddleCardId(group[2]), item_id)
        try:
            new_value = float(value)
            steps = float(getattr(it, "steps", 1) or 1) if it else 1.0
            if steps > 1:
                # 固定格类型：value 为档位，视觉位置 = value / steps
                new_value = max(0.0, min(steps, new_value))
                visual = new_value / steps
            else:
                visual = max(0.0, min(1.0, new_value))
            if abs(float(sliderCtrl.GetSliderValue()) - visual) > 1e-6:
                sliderCtrl.SetSliderValue(visual)
                node.mRightSliderStates[item_id] = visual
        except Exception as e:
            dlog.client_print("==== ApplySettingToOpenUI slider error: %s ====" % str(e))
        if it and hasattr(it, "SetValue"):
            it.SetValue(float(value))
            it._loaded = True
            _UpdateSliderValueLabel(node, it, float(value))
        return
    # 编辑框
    editBoxCtrl = node.mRightEditBoxCtrlMap.get(item_id)
    if editBoxCtrl is not None:
        inputCtrl = editBoxCtrl.GetChildByName('input')
        teb = inputCtrl.asTextEditBox() if inputCtrl else None
        new_text = str(value) if value is not None else ""
        if teb:
            try:
                if teb.GetEditText() != new_text:
                    teb.SetEditText(new_text)
            except Exception as e:
                dlog.client_print("==== ApplySettingToOpenUI edit_box error: %s ====" % str(e))
        it = GetContentItem(group[0], group[1], NormalizeMiddleCardId(group[2]), item_id)
        if it and hasattr(it, "SetValue"):
            it.SetValue(new_text)
            it._loaded = True
        if it and getattr(it, "locked", False):
            _SyncEditBoxLockText(node, item_id, new_text)
        return
    # 折叠菜单（外部 SetSettingValue/Reset 后实时刷新按钮文字与选中态）
    cmBtnCtrl = node.mRightCollapsibleMenuCtrlMap.get(item_id)
    if cmBtnCtrl is not None:
        it = GetContentItem(group[0], group[1], NormalizeMiddleCardId(group[2]), item_id)
        if it and hasattr(it, "SetValue"):
            it.SetValue(value)
            it._loaded = True
        textLabel = node.mCollapsibleMenuTextMap.get(item_id)
        if textLabel:
            _SetLabelText(textLabel, it.GetDisplayText() if it else str(value),
                          "ApplySettingToOpenUI.collapsible_menu")


def BuildResetContent(screenNode, parent, item):
    """重置按钮内容项 UI 创建（仅显示按钮，点击后弹出关联确认弹窗）。"""
    dlog.client_print("==== BuildResetContent item_id=%s button_text=%s popup_id=%s ====" % (
        item.item_id, item.button_text, item.popup_id
    ))
    ctrl = screenNode.CreateChildControl(
        'setting.reset_content',
        'rreset_' + item.item_id,
        parent,
        True
    )
    if not ctrl:
        dlog.client_print("==== BuildResetContent: create control failed ====")
        return
    # 立即设置透明，避免创建时闪现
    try:
        screenNode._SetControlTreeAlpha(ctrl, 0.0)
    except Exception:
        pass

    buttonCtrl = ctrl.GetChildByName('button')
    if not buttonCtrl:
        dlog.client_print("==== BuildResetContent: button child not found ====")
        return
    textLabel = buttonCtrl.GetChildByName('text')
    if textLabel:
        _SetLabelText(textLabel, item.button_text, "BuildResetContent.text")
        textLabel.SetVisible(True)
    # 重置按钮不使用 finish 图层，强制隐藏
    finishImg = buttonCtrl.GetChildByName('finish')
    if finishImg:
        finishImg.SetVisible(False)

    # 锁定处理：显示 lock 图层并禁止点击
    lockCtrl = buttonCtrl.GetChildByName('lock')
    if item.locked:
        if lockCtrl:
            lockCtrl.SetVisible(True)
    else:
        if lockCtrl:
            lockCtrl.SetVisible(False)
        btn = buttonCtrl.asButton()
        if btn:
            btn.AddTouchEventParams({})
            btn.SetButtonTouchUpCallback(
                lambda args, iid=item.item_id: _OnResetButtonClick(screenNode, iid)
            )
    # 存储 lock 控件引用，用于动态更新锁定状态
    if lockCtrl:
        screenNode.mRightLockCtrlMap[item.item_id] = lockCtrl

    screenNode.mRightContentCtrls.append(ctrl)
    screenNode.mRightBtnCtrlMap[item.item_id] = ctrl


def _OnResetButtonClick(screenNode, item_id):
    """reset 内容项按钮点击：打开关联弹窗并触发 on_click 回调。"""
    dlog.client_print("==== _OnResetButtonClick: %s ====" % item_id)
    if not _g_ClientSystem:
        return
    group = screenNode.mCurrentRightGroup
    if not group:
        return
    it = GetContentItem(group[0], group[1], NormalizeMiddleCardId(group[2]), item_id)
    if it is None:
        return
    if getattr(it, "locked", False):
        return  # 锁定状态不可点击
    if it and getattr(it, "popup_id", None):
        _g_ClientSystem.ShowPopUp(it.popup_id)
    if it and getattr(it, "on_click", None):
        try:
            it.on_click(screenNode, item_id)
        except Exception as e:
            dlog.client_print("==== reset on_click error: %s ====" % str(e))


# 注册内置内容项构建器
RegisterContentBuilder("text", BuildTextContent)
RegisterContentBuilder("button", BuildButtonContent)
RegisterContentBuilder("switch", BuildSwitchContent)
RegisterContentBuilder("edit_box", BuildEditBoxContent)
RegisterContentBuilder("reset", BuildResetContent)
RegisterContentBuilder("slider", BuildSliderContent)
RegisterContentBuilder("collapsible_menu", BuildCollapsibleMenuContent)

# 设置值变更时同步刷新已打开 UI
SetSettingChangedCallback(_ApplySettingToOpenUI)


class PauseScreenProxy(CustomUIScreenProxy):

    def __init__(self, screenName, screenNode):
        CustomUIScreenProxy.__init__(self, screenName, screenNode)

    def OnCreate(self):
        dlog.client_print("==== PauseScreenProxy OnCreate ====")
        basePath = "/variables_button_mappings_and_controls/safezone_screen_matrix/inner_matrix/safezone_screen_panel/root_screen_panel"
        btnPath = (
            basePath +
            "/pause_screen_main_panels/menu/the_rest_panel/pause_menu/"
            "menu_button_control/menu_background/button_panel/my_mod_settings_button"
        )
        # 开关：未启用"注册到暂停菜单"则不注入设置入口
        if not GetSettingValue("settings_config", "client", "display",
                               "register_pause_menu", True):
            # 按钮由资源包 JSON 静态注入，仅跳过代理仍会显示，需主动隐藏
            try:
                screen = self.GetScreenNode()
                btnControl = screen.GetBaseUIControl(btnPath)
                if btnControl:
                    btnControl.SetVisible(False)
                    dlog.client_print("==== pause menu entry disabled, button hidden ====")
                else:
                    dlog.client_print("==== pause menu entry disabled, button not found ====")
            except Exception as e:
                dlog.client_print("==== pause menu hide error: %s ====" % str(e))
            return
        screen = self.GetScreenNode()
        btnControl = screen.GetBaseUIControl(btnPath)
        if btnControl:
            # 恢复可见性：关闭注册时曾 SetVisible(False)，可能跨会话保留，
            # 重新开启时必须重新显示，否则按钮一直隐藏直到重启才恢复。
            btnControl.SetVisible(True)
            screen.AddTouchEventHandler(btnPath, self.OnSettingsClick, None)
            dlog.client_print("==== settings button touch handler bound ====")
            return

        dlog.client_print("==== my_mod_settings_button not found, try dynamic create ====")
        panelPath = (
            basePath +
            "/pause_screen_main_panels/menu/the_rest_panel/pause_menu/"
            "menu_button_control/menu_background/button_panel"
        )
        panelControl = screen.GetBaseUIControl(panelPath)
        if not panelControl:
            dlog.client_print("==== button_panel not found, dump paths ====")
            paths = screen.GetAllChildrenPath(basePath)
            dlog.client_print("==== root %s count %d ====" % (basePath, len(paths)))
            for p in paths[:30]:
                dlog.client_print(p)
            return

        screen.CreateChildControl(
            'Script_NeteaseMod9sPMlz0K.mod_settings_spacer',
            'my_mod_settings_spacer',
            panelControl,
            True
        )

        btnControl = screen.CreateChildControl(
            'Script_NeteaseMod9sPMlz0K.mod_settings_button',
            'my_mod_settings_button',
            panelControl,
            True
        )
        if not btnControl:
            dlog.client_print("==== CreateChildControl failed ====")
            return

        screen.AddTouchEventHandler(btnPath, self.OnSettingsClick, None)
        dlog.client_print("==== settings button dynamically added ====")

    def OnSettingsClick(self, args):
        # 只响应松手事件（TouchUp）
        touchEvent = clientApi.GetMinecraftEnum().TouchEvent
        eventType = args.get('TouchEvent')
        dlog.client_print("==== Pause OnSettingsClick: TouchEvent=%s ====" % str(eventType))
        if eventType != touchEvent.TouchUp:
            return
        dlog.client_print("==== My Mod Settings clicked (TouchUp) ====")
        if _g_ClientSystem:
            # 复用 OpenSettings：内部有 mSettingsUIOpen/ScreenNode 双重保护，避免重复 PushScreen
            _g_ClientSystem.OpenSettings()


class FoldMenuProxy(CustomUIScreenProxy):

    def __init__(self, screenName, screenNode):
        CustomUIScreenProxy.__init__(self, screenName, screenNode)
        self.mTickCount = 0
        self.mBound = False

    def OnCreate(self):
        dlog.client_print("==== FoldMenuProxy OnCreate ====")
        # 开关：未启用"注册到折叠菜单"则不注入设置入口
        if not GetSettingValue("settings_config", "client", "display",
                               "register_fold_menu", True):
            dlog.client_print("==== fold menu entry disabled by switch, skip ====")
            return
        self.mBound = False
        screen = self.GetScreenNode()
        panelFold = screen.GetBaseUIControl("/panel_foldmenu")
        if not panelFold:
            dlog.client_print("==== /panel_foldmenu not found ====")
            return
        panelControl = screen.CreateChildControl(
            'Script_NeteaseMod9sPMlz0K.fold_menu_panel_template',
            'panel_my_settings',
            panelFold,
            True
        )
        if not panelControl:
            dlog.client_print("==== CreateChildControl panel failed ====")
            return
        btnControl = screen.CreateChildControl(
            'Script_NeteaseMod9sPMlz0K.fold_menu_settings_button',
            'button_my_settings',
            panelControl,
            True
        )
        if not btnControl:
            dlog.client_print("==== CreateChildControl button failed ====")
            return
        screen.AddTouchEventHandler("/panel_foldmenu/panel_my_settings/button_my_settings", self.OnSettingsClick, None)
        self.mBound = True
        dlog.client_print("==== fold menu settings button created ====")

    def OnDestroy(self):
        self.mBound = False

    def OnTick(self):
        pass

    def OnSettingsClick(self, args):
        # 只响应松手事件（TouchUp）
        touchEvent = clientApi.GetMinecraftEnum().TouchEvent
        eventType = args.get('TouchEvent')
        dlog.client_print("==== Fold OnSettingsClick: TouchEvent=%s ====" % str(eventType))
        if eventType != touchEvent.TouchUp:
            return
        dlog.client_print("==== My Mod Settings clicked from fold menu (TouchUp) ====")
        if _g_ClientSystem:
            # 复用 OpenSettings：内部有 mSettingsUIOpen/ScreenNode 双重保护，避免重复 PushScreen
            _g_ClientSystem.OpenSettings()


class PopUpScreenNode(ScreenNode):
    """弹窗界面 ScreenNode：显示标题/内容，动态创建底部按钮，内容超长可滚动。"""

    def __init__(self, namespace, name, param):
        ScreenNode.__init__(self, namespace, name, param)
        self.mButtonsCreated = False
        self.mBackBound = False
        global _g_ClientSystem
        if _g_ClientSystem:
            _g_ClientSystem.mPopUpScreenNode = self

    def Create(self):
        dlog.client_print("==== PopUpScreenNode.Create called ====")
        self._ApplyPopUp()

    def OnActive(self):
        dlog.client_print("==== PopUpScreenNode.OnActive called ====")
        self._ApplyPopUp()

    def _GetContentPath(self):
        """内容控件路径（普通版：middle 下的 text label）。"""
        return "/backdrop/stack_panel/middle/text"

    def _ApplyPopUp(self):
        """应用当前弹窗数据（标题/内容/底部按钮）。"""
        data = None
        if _g_ClientSystem:
            data = _g_ClientSystem.mCurrentPopUp
        if not data:
            dlog.client_print("==== PopUpScreenNode: no popup data ====")
            return
        title = data.get("title", "")
        content = data.get("content", "")
        buttons = data.get("buttons", []) or []

        # 1. 标题
        titleCtrl = self.GetBaseUIControl("/backdrop/stack_panel/top/litle")
        if titleCtrl:
            _SetLabelText(titleCtrl, title, "PopUpScreenNode.title")
        else:
            dlog.client_print("==== PopUpScreenNode: title ctrl not found ====")

        # 2. 内容
        contentCtrl = self.GetBaseUIControl(self._GetContentPath())
        if contentCtrl:
            _SetLabelText(contentCtrl, content, "PopUpScreenNode.content")
        else:
            dlog.client_print("==== PopUpScreenNode: content ctrl not found ====")

        # 3. 底部按钮（仅首次创建）
        if not self.mButtonsCreated:
            panelCtrl = self.GetBaseUIControl("/backdrop/stack_panel/under/stack_panel")
            if panelCtrl:
                self._CreateButtons(panelCtrl, buttons)
                self.mButtonsCreated = True
            else:
                dlog.client_print("==== PopUpScreenNode: under stack_panel not found ====")

        # 4. 返回按钮（仅绑定一次）
        if not self.mBackBound:
            backCtrl = self.GetBaseUIControl("/backdrop/stack_panel/top/back")
            if backCtrl:
                btn = backCtrl.asButton()
                if btn:
                    btn.AddTouchEventParams({})
                    btn.SetButtonTouchUpCallback(lambda args: self._OnBackClick())
                    self.mBackBound = True
            else:
                dlog.client_print("==== PopUpScreenNode: back button not found ====")

    @staticmethod
    def _EstimateTextHeight(text):
        """估算文本显示高度：每行约 30 字符、行高 10px，最小 20px。"""
        if not text:
            return 20
        lines = 0
        for seg in text.split("\n"):
            if not seg:
                lines += 1
            else:
                lines += max(1, (len(seg) + 29) // 30)
        return max(1, lines) * 10

    def _CreateButtons(self, panelCtrl, buttons):
        """在 under 区域按注册顺序创建按钮（模板总高 24，按钮间自带空隙）。"""
        for i, (text, cb) in enumerate(buttons):
            btnCtrl = self.CreateChildControl(
                'pop_up.pop_up_button',
                'popup_btn_%d' % i,
                panelCtrl,
                True
            )
            if not btnCtrl:
                dlog.client_print("==== PopUpScreenNode: create button %d failed ====" % i)
                continue
            labelCtrl = btnCtrl.GetChildByName('label')
            if labelCtrl:
                _SetLabelText(labelCtrl, text, "PopUpScreenNode.button_text")
            btn = btnCtrl.asButton()
            if btn:
                btn.AddTouchEventParams({})
                btn.SetButtonTouchUpCallback(
                    lambda args, cb=cb: self._OnButtonClick(cb)
                )

    def _OnButtonClick(self, callback):
        """弹窗按钮点击：执行回调，默认关闭弹窗；回调返回 False 时阻止关闭。"""
        close = True
        if callback:
            try:
                ret = callback()
                if ret is False:
                    close = False
            except Exception as e:
                dlog.client_print("==== PopUpScreenNode button callback error: %s ====" % str(e))
        if close and _g_ClientSystem:
            _g_ClientSystem.ClosePopUp()

    def _OnBackClick(self):
        """返回按钮：关闭弹窗。"""
        if _g_ClientSystem:
            _g_ClientSystem.ClosePopUp()

    def Destroy(self):
        self.mButtonsCreated = False
        self.mBackBound = False
        global _g_ClientSystem
        if _g_ClientSystem and _g_ClientSystem.mPopUpScreenNode is self:
            _g_ClientSystem.mPopUpScreenNode = None
        try:
            ScreenNode.Destroy(self)
        except Exception:
            pass


class PopUpScrollScreenNode(PopUpScreenNode):
    """滚动版弹窗 ScreenNode：内容区使用滚动面板，标题/按钮逻辑复用父类。"""

    def _GetContentPath(self):
        """滚动版内容 label 路径（$touch: true 时固定为 touch 路径，label 位于 scroll_panel 内）。"""
        return ("/backdrop/stack_panel/middle/scroll_view/scroll_touch/scroll_view/"
                "panel/background_and_viewport/scrolling_view_port/scrolling_content/text")

    def _ApplyPopUp(self):
        """应用当前弹窗数据。滚动面板高度由 JSON（scroll_panel size 100%c+10px）自动按文字包裹。"""
        PopUpScreenNode._ApplyPopUp(self)


class CollapsibleMenuScreenNode(ScreenNode):
    """折叠菜单弹窗 ScreenNode：标题 + 中间垂直卡片列表，卡片互斥选择，点击后选中并关闭。"""

    def __init__(self, namespace, name, param):
        ScreenNode.__init__(self, namespace, name, param)
        self.mCardsCreated = False
        self.mBackBound = False
        self.mCardCtrls = []  # [(card_id, ctrl), ...]
        global _g_ClientSystem
        if _g_ClientSystem:
            _g_ClientSystem.mCollapsibleMenuScreenNode = self

    def Create(self):
        dlog.client_print("==== CollapsibleMenuScreenNode.Create called ====")
        self._ApplyMenu()

    def OnActive(self):
        dlog.client_print("==== CollapsibleMenuScreenNode.OnActive called ====")
        self._ApplyMenu()

    def _ApplyMenu(self):
        """应用当前折叠菜单数据（标题 + 中间卡片列表 + 返回按钮）。"""
        data = None
        if _g_ClientSystem:
            data = _g_ClientSystem.mCurrentCollapsibleMenu
        if not data:
            dlog.client_print("==== CollapsibleMenuScreenNode: no menu data ====")
            return
        title = data.get("title", "")
        cards = data.get("cards", []) or []

        # 1. 标题
        titleCtrl = self.GetBaseUIControl("/backdrop/stack_panel/top/litle")
        if titleCtrl:
            _SetLabelText(titleCtrl, title, "CollapsibleMenuScreenNode.title")
        else:
            dlog.client_print("==== CollapsibleMenuScreenNode: title ctrl not found ====")

        # 2. 中间卡片（仅首次创建，后续刷新仅更新选中态）
        middleCtrl = self.GetBaseUIControl("/backdrop/stack_panel/middle")
        if not middleCtrl:
            dlog.client_print("==== CollapsibleMenuScreenNode: middle ctrl not found ====")
            return
        if not self.mCardsCreated:
            self._CreateCards(middleCtrl, cards)
            self.mCardsCreated = True
        else:
            self._RefreshCardSelected()

        # 3. 返回按钮（仅绑定一次）
        if not self.mBackBound:
            backCtrl = self.GetBaseUIControl("/backdrop/stack_panel/top/back")
            if backCtrl:
                btn = backCtrl.asButton()
                if btn:
                    btn.AddTouchEventParams({})
                    btn.SetButtonTouchUpCallback(lambda args: self._OnBackClick())
                    self.mBackBound = True
            else:
                dlog.client_print("==== CollapsibleMenuScreenNode: back button not found ====")

    def _CreateCards(self, middleCtrl, cards):
        """在 middle 区域按注册顺序创建卡片，恢复当前选中态。"""
        # 清空旧卡片（防止复用刷新时残留）
        for _, ctrl in self.mCardCtrls:
            try:
                self.RemoveChildControl(ctrl)
            except Exception:
                pass
        self.mCardCtrls = []
        item = None
        if _g_ClientSystem:
            item = _g_ClientSystem.mCurrentCollapsibleItem
        current_id = item.selected_id if item else None
        for i, (card_id, name) in enumerate(cards):
            ctrl = self.CreateChildControl(
                'pop_up.collapsible_menu_card',
                'menu_card_%d' % i,
                middleCtrl,
                True
            )
            if not ctrl:
                dlog.client_print("==== CollapsibleMenuScreenNode: create card %d failed ====" % i)
                continue
            # 卡片文字（button_label，模板左对齐）
            labelCtrl = ctrl.GetChildByName('button_label')
            if labelCtrl:
                _SetLabelText(labelCtrl, name, "CollapsibleMenuScreenNode.card_text")
            # 选中图层：默认隐藏，仅当前选中卡显示
            selectedCtrl = ctrl.GetChildByName('selected')
            if selectedCtrl:
                selectedCtrl.SetVisible(card_id == current_id)
            # 点击回调（松手触发）
            btn = ctrl.asButton()
            if btn:
                btn.AddTouchEventParams({})
                btn.SetButtonTouchUpCallback(
                    lambda args, cid=card_id: self._OnCardClick(cid)
                )
            self.mCardCtrls.append((card_id, ctrl))

    def _RefreshCardSelected(self):
        """刷新所有卡片的 selected 图层可见性（跟随当前选中态）。"""
        item = None
        if _g_ClientSystem:
            item = _g_ClientSystem.mCurrentCollapsibleItem
        current_id = item.selected_id if item else None
        for card_id, ctrl in self.mCardCtrls:
            selectedCtrl = ctrl.GetChildByName('selected')
            if selectedCtrl:
                selectedCtrl.SetVisible(card_id == current_id)

    def _OnCardClick(self, card_id):
        """卡片点击：更新选中态、触发回调、同步按钮文字并关闭弹窗。"""
        dlog.client_print("==== CollapsibleMenuScreenNode._OnCardClick: %s ====" % card_id)
        item = None
        if _g_ClientSystem:
            item = _g_ClientSystem.mCurrentCollapsibleItem
        if item:
            name = ""
            data = None
            if _g_ClientSystem:
                data = _g_ClientSystem.mCurrentCollapsibleMenu
            for cid, cname in (data.get("cards", []) if data else []):
                if cid == card_id:
                    name = cname
                    break
            item.SetSelected(card_id, name)
            # 触发注册回调 on_select(screenNode, item_id, card_id)
            if item.on_select:
                try:
                    sn = None
                    if _g_ClientSystem:
                        sn = _g_ClientSystem.mSettingsScreenNode
                    item.on_select(sn, item.item_id, card_id)
                except Exception as e:
                    dlog.client_print("==== CollapsibleMenuScreenNode on_select error: %s ====" % str(e))
        # 更新所有卡片 selected 图层
        self._RefreshCardSelected()
        # 同步设置界面按钮文字（实时显示当前选择项）
        if item and _g_ClientSystem and _g_ClientSystem.mSettingsScreenNode:
            try:
                _g_ClientSystem.mSettingsScreenNode.UpdateCollapsibleMenuButtonText(
                    item.item_id, item.GetDisplayText()
                )
            except Exception as e:
                dlog.client_print("==== CollapsibleMenuScreenNode update button text error: %s ====" % str(e))
        # 关闭折叠菜单弹窗
        if _g_ClientSystem:
            _g_ClientSystem.CloseCollapsibleMenu()

    def _OnBackClick(self):
        """返回按钮：关闭折叠菜单弹窗。"""
        if _g_ClientSystem:
            _g_ClientSystem.CloseCollapsibleMenu()

    def Destroy(self):
        self.mCardsCreated = False
        self.mBackBound = False
        self.mCardCtrls = []
        global _g_ClientSystem
        if _g_ClientSystem and _g_ClientSystem.mCollapsibleMenuScreenNode is self:
            _g_ClientSystem.mCollapsibleMenuScreenNode = None
        try:
            ScreenNode.Destroy(self)
        except Exception:
            pass


class CardToggleScreenNode(ScreenNode):
    """组合开关弹窗 ScreenNode：标题 + 中间多行开关卡片 + 底部自定义按钮。

    每行卡片复用 setting.card_toggle（物品渲染 + 描述 + 开关），支持单选/多选模式。
    用 OnTick 轮询原生开关值来捕获用户改动并持久化（对齐 slider 的既有轮询模式）。
    """

    def __init__(self, namespace, name, param):
        ScreenNode.__init__(self, namespace, name, param)
        self.mPanelApplied = False
        self.mBackBound = False
        self.mRowCtrls = []          # [(option_id, switchCtrl, rowCtrl, locked, editInputCtrl), ...]
        self.mStates = {}            # option_id -> bool（缓存当前开关状态）
        self.mToggleId = ""
        self.mMode = "multi"
        global _g_ClientSystem
        if _g_ClientSystem:
            _g_ClientSystem.mCardToggleScreenNode = self

    def Create(self):
        dlog.client_print("==== CardToggleScreenNode.Create called ====")
        self._ApplyPanel()

    def OnActive(self):
        dlog.client_print("==== CardToggleScreenNode.OnActive called ====")
        self._ApplyPanel()

    def _ApplyPanel(self):
        data = None
        if _g_ClientSystem:
            data = _g_ClientSystem.mCurrentCardToggle
            self.mToggleId = _g_ClientSystem.mCurrentToggleId
        if not data:
            dlog.client_print("==== CardToggleScreenNode: no toggle data ====")
            return
        self.mMode = data.get("mode", "multi")
        options = data.get("options", []) or []
        # 1. 标题
        titleCtrl = self.GetBaseUIControl("/backdrop/stack_panel/top/litle")
        if titleCtrl:
            _SetLabelText(titleCtrl, data.get("title", ""), "CardToggleScreenNode.title")
        # 2. 返回按钮（仅绑定一次）
        if not self.mBackBound:
            backCtrl = self.GetBaseUIControl("/backdrop/stack_panel/top/back")
            if backCtrl:
                btn = backCtrl.asButton()
                if btn:
                    btn.AddTouchEventParams({})
                    btn.SetButtonTouchUpCallback(lambda args: self._OnBackClick())
                    self.mBackBound = True
        # 3. 中间多行开关卡片（滚动面板内容 = scrolling_content 栈）
        middleStack = self.GetBaseUIControl(
            "/backdrop/stack_panel/middle/scroll_view/scroll_touch/scroll_view/"
            "panel/background_and_viewport/scrolling_view_port/scrolling_content")
        dlog.client_print("==== CardToggle _ApplyPanel: mode=%s options=%d middleStack=%s ====" % (
            self.mMode, len(options), bool(middleStack)))
        if not middleStack:
            dlog.client_print("==== CardToggleScreenNode: middle stack not found ====")
            return
        self._ClearRows()
        from SettingState import GetCardToggleState
        for i, op in enumerate(options):
            # options 元素兼容 5 元组(旧) / 7 元组(新: 含 ctrl_type, locked) /
            # 8 元组(新: 含 default_value 编辑框默认文本)
            if len(op) >= 8:
                option_id, item_name, item_aux, desc, default_on, ctrl_type, locked, default_value = op[:8]
            elif len(op) >= 7:
                option_id, item_name, item_aux, desc, default_on, ctrl_type, locked = op[:7]
                default_value = ""
            else:
                option_id, item_name, item_aux, desc, default_on = op[:5]
                ctrl_type = "toggle"
                locked = False
                default_value = ""
            if ctrl_type == "toggle_text":
                template = 'setting.card_toggle_text'
            elif ctrl_type == "toggle_edit_box":
                template = 'setting.card_toggle_edit_box'
            else:
                ctrl_type = "toggle"
                template = 'setting.card_toggle'
            ctrl = self.CreateChildControl(
                template,
                'tog_%d' % i,
                middleStack,
                True
            )
            if not ctrl:
                dlog.client_print("==== CardToggleScreenNode: create row %d failed ====" % i)
                continue
            # card_toggle 结构为 panel > image > (item_renderer/label/switch|edit_box/lock)，
            # GetChildByName 只查直接子，故先取 image 再取内部子控件
            base = ctrl.GetChildByName('image') or ctrl
            # 物品图标渲染（toggle_text 无 item_renderer，自动跳过）
            itemCtrl = base.GetChildByName('item_renderer')
            if itemCtrl and item_name:
                try:
                    it = itemCtrl.asItemRenderer()
                    if it:
                        it.SetUiItem(item_name, item_aux, False)
                except Exception as e:
                    dlog.client_print("==== CardToggleScreenNode item render error: %s ====" % str(e))
            # 自定义描述文字
            labelCtrl = base.GetChildByName('label')
            if labelCtrl:
                _SetLabelText(labelCtrl, desc, "CardToggleScreenNode.label")
            # 开关：初始化状态 + 记录（存转换后的 SwitchToggleUIControl，供 Get/SetToggleState 使用）
            switchCtrl = base.GetChildByName('switch')
            state = GetCardToggleState(self.mToggleId, option_id, default_on)
            toggleObj = None
            if switchCtrl:
                self.mStates[option_id] = bool(state)
                try:
                    toggleObj = switchCtrl.asSwitchToggle()
                    if toggleObj:
                        toggleObj.SetToggleState(bool(state), "/this_toggle")
                        # 锁定：禁用交互；视觉由 switch 内置锁定贴图
                        # （$checked_locked_texture / $unchecked_locked_texture）自动呈现
                        toggleObj.SetTouchEnable(not locked)
                except Exception as e:
                    dlog.client_print("==== CardToggleScreenNode switch init error: %s ====" % str(e))
            # 编辑框（toggle_edit_box 行）：设置初始文本 + 锁定覆盖层
            editInputCtrl = None
            editBoxCtrl = base.GetChildByName('edit_box')
            if editBoxCtrl:
                text_value = GetCardToggleState(self.mToggleId, option_id, default_value)
                self.mStates[option_id] = text_value
                inputCtrl = editBoxCtrl.GetChildByName('input')
                if inputCtrl:
                    try:
                        teb = inputCtrl.asTextEditBox()
                        if teb:
                            teb.SetEditText(text_value)
                            editInputCtrl = teb
                    except Exception as e:
                        dlog.client_print("==== CardToggleScreenNode edit box init error: %s ====" % str(e))
                # 锁定：显示 edit_box 内置 lock 覆盖层并禁用整行交互
                lockCtrl = editBoxCtrl.GetChildByName('lock')
                if lockCtrl:
                    lockCtrl.SetVisible(bool(locked))
                    if locked:
                        lockTextCtrl = lockCtrl.GetChildByName('lock_text')
                        if lockTextCtrl:
                            _SetLabelText(lockTextCtrl, text_value, "CardToggleScreenNode.lock_text")
                try:
                    editBoxCtrl.SetTouchEnable(not locked)
                except Exception as e:
                    dlog.client_print("==== CardToggleScreenNode edit box lock error: %s ====" % str(e))
            self.mRowCtrls.append((option_id, toggleObj, ctrl, locked, editInputCtrl))
        self.mPanelApplied = True
        dlog.client_print("==== CardToggle applied: rows=%d/%d ====" % (len(self.mRowCtrls), len(options)))
        # 4. 底部自定义按钮
        self._BuildButtons(data.get("buttons", []) or [])

    def _ClearRows(self):
        for _oid, _sc, ctrl, _lk, _ed in self.mRowCtrls:
            try:
                self.RemoveChildControl(ctrl)
            except Exception:
                pass
        self.mRowCtrls = []
        self.mStates = {}

    def _BuildButtons(self, buttons):
        underStack = self.GetBaseUIControl("/backdrop/stack_panel/under/stack_panel")
        if not underStack:
            dlog.client_print("==== CardToggleScreenNode: under stack not found ====")
            return
        for i, (text, callback) in enumerate(buttons):
            btnCtrl = self.CreateChildControl(
                'pop_up.pop_up_button',
                'btn_%d' % i,
                underStack,
                True
            )
            if not btnCtrl:
                continue
            # 按钮文字：label 子控件
            try:
                labelCtrl = btnCtrl.GetChildByName('label')
                if labelCtrl:
                    _SetLabelText(labelCtrl, text, "CardToggleScreenNode.btn_label")
            except Exception:
                pass
            btn = btnCtrl.asButton()
            if btn:
                btn.AddTouchEventParams({})
                btn.SetButtonTouchUpCallback(
                    lambda args, cb=callback: self._OnCustomButton(cb)
                )

    def _OnCustomButton(self, callback):
        """底部自定义按钮点击：先同步最新开关状态再回调。"""
        try:
            dlog.client_print("==== CardToggle custom button CALLED, toggle=%s ====" % self.mToggleId)
            self._PersistStates()
            sn = None
            if _g_ClientSystem:
                sn = _g_ClientSystem.mSettingsScreenNode
            callback(sn, self.mToggleId, dict(self.mStates))
        except Exception as e:
            dlog.client_print("==== CardToggleScreenNode button callback error: %s ====" % str(e))

    def _OnBackClick(self):
        """返回按钮：关闭组合开关弹窗。"""
        if _g_ClientSystem:
            _g_ClientSystem.CloseCardToggle()

    def _PersistStates(self):
        """读取当前所有开关原生状态并写入持久化（供关闭弹窗时调用，不依赖 OnTick）。"""
        if not self.mToggleId:
            return
        from SettingState import SetCardToggleState
        raw = []
        changed = False
        for option_id, switchCtrl, _, locked, editInputCtrl in self.mRowCtrls:
            if editInputCtrl is not None:
                # 编辑框行：读取输入文本并持久化（锁定行跳过）
                if locked:
                    raw.append((option_id, "LOCKED"))
                    continue
                try:
                    cur_text = editInputCtrl.GetEditText()
                except Exception as e:
                    raw.append((option_id, "ERR:" + str(e)))
                    continue
                raw.append((option_id, cur_text))
                if cur_text != self.mStates.get(option_id, ""):
                    self.mStates[option_id] = cur_text
                    SetCardToggleState(self.mToggleId, option_id, cur_text)
                    changed = True
                continue
            if switchCtrl is None or locked:
                raw.append((option_id, "SKIP" if locked else "NOCTRL"))
                continue
            try:
                cur = switchCtrl.GetToggleState("/this_toggle")
            except Exception as e:
                raw.append((option_id, "ERR:" + str(e)))
                continue
            try:
                cur_bool = bool(cur)
            except Exception:
                cur_bool = None
            raw.append((option_id, cur))
            if cur_bool is not None and cur_bool != self.mStates.get(option_id, False):
                self.mStates[option_id] = cur_bool
                SetCardToggleState(self.mToggleId, option_id, cur_bool)
                changed = True
        dlog.client_print("==== CardToggle persist raw: %s changed=%s ====" % (raw, changed))

    def OnTick(self):
        """轮询原生开关值：捕获用户改动 → 持久化；单选模式开一关余。"""
        if not self.mPanelApplied or not self.mToggleId:
            return
        from SettingState import SetCardToggleState
        changed = False
        for option_id, switchCtrl, _, locked, _ed in self.mRowCtrls:
            if switchCtrl is None or locked:
                continue
            try:
                cur = switchCtrl.GetToggleState("/this_toggle")
            except Exception:
                cur = None
            if cur is None:
                continue
            cur = bool(cur)
            if cur == self.mStates.get(option_id, False):
                continue
            self.mStates[option_id] = cur
            SetCardToggleState(self.mToggleId, option_id, cur)
            changed = True
            # 单选互斥：开了当前项则关闭其余
            if self.mMode == "single" and cur:
                for oid2, sc2, _, locked2, _ed2 in self.mRowCtrls:
                    if oid2 == option_id or sc2 is None or locked2:
                        continue
                    try:
                        sc2.SetToggleState(False, "/this_toggle")
                    except Exception:
                        pass
                    self.mStates[oid2] = False
                    SetCardToggleState(self.mToggleId, oid2, False)
        if changed:
            dlog.client_print("==== CardToggleScreenNode: toggle states updated ====")

    def Destroy(self):
        self.mPanelApplied = False
        self.mBackBound = False
        self.mRowCtrls = []
        self.mStates = {}
        global _g_ClientSystem
        if _g_ClientSystem and _g_ClientSystem.mCardToggleScreenNode is self:
            _g_ClientSystem.mCardToggleScreenNode = None
        try:
            ScreenNode.Destroy(self)
        except Exception:
            pass
