# -*- coding: utf-8 -*-
"""
Toast 提示系统
==============
基于 resource_pack_nka0OOhF/ui/toast.json 的轻量提示实现。

- 通过 CreateUI 以叠加层方式显示（非 PushScreen 弹窗，不打断游戏操作）。
- top / top_right 支持物品展示图层与图片图层，按需显示与设置内容。
- 三个位置均支持自定义文字与自定义文字颜色。
- 进入(1s) -> 停留(默认3s/可自定义) -> 退出(1s) 三段动画。
- 同一位置的多个 toast 按调用顺序排队播放（一个播完播下一个）。
- 另有「物品名提示」（ShowItemNameToast，对应 toast_item_name 控件）：不滑入，
  立即不透明显示，停留 2 秒后在 2 秒内把整块（底板 + 物品名 + 命名空间两行文字）
  淡到全透明；中途重复触发即"回到不透明并重新计时"，不排队。

对外 API 由 CardRegistryApi 再导出（ShowToast / ShowItemNameToast / ToastTop /
ToastTopRight / ToastUnder），外部模组需在 UiInitFinished 内延迟导入调用。
"""

import mod.client.extraClientApi as clientApi

from DebugLog import dlog

ScreenNode = clientApi.GetScreenNodeCls()

# ────────────────── 位置常量（对外） ──────────────────
ToastTop = "top"
ToastTopRight = "top_right"
ToastUnder = "under"

# 动画定义所在 JSON 的 namespace（toast.json）
_ANIM_NS = "toast"

# 位置 -> (uiKey, screenPath, enterAnim, exitAnim, animPath, shadowPath, shadowEnterAnim, shadowExitAnim)
# animPath 为动画目标控件（从 screen 根起的路径）；shadowPath 为需同步运动的阴影控件路径（无则为 None）
_POSITION_MAP = {
    ToastTop: ("ToastTop", "toast.toast_top", "toast_top_enter", "toast_top_exit", "/backdrop", None, None, None),
    ToastTopRight: ("ToastTopRight", "toast.toast_top_right", "toast_top_right_enter", "toast_top_right_exit", "/backdrop", None, None, None),
    ToastUnder: ("ToastUnder", "toast.toast_under", "toast_under_enter", "toast_under_exit", "/image",
                 "/under", "toast_under_shadow_enter", "toast_under_shadow_exit"),
}

# 位置 -> (入场默认音效, 出场默认音效)；出场默认音效为 "" 表示不播。
# 右上角用原版配方解锁弹窗音效（进 in / 出 out），上面与下面用默认 toast 音效，出场不播。
_DEFAULT_SOUNDS = {
    ToastTop: ("random.toast", ""),
    ToastTopRight: ("random.toast_recipe_unlocking_in", "random.toast_recipe_unlocking_out"),
    ToastUnder: ("random.toast", ""),
}

# ────────────────── 物品名提示（toast_item_name） ──────────────────
# 与上面三个滑入式位置不同：不走 offset 动画、不排队。显示时序固定为
# 「立即不透明 -> 停留 _ITEM_NAME_HOLD 秒 -> 用 2 秒淡到全透明」。
_ITEM_NAME_UI_KEY = "ToastItemName"
_ITEM_NAME_SCREEN = "toast.toast_item_name"
_ITEM_NAME_HOLD = 2.0                     # 不透明停留时长（秒）
_ITEM_NAME_FADE_ANIM = "toast_item_name_fade"   # toast.json 里的 2 秒 alpha 动画
# 参与淡出的控件（相对 toast_item_name 根节点）。
# alpha 不会从父控件传给子控件（要继承得配 propagate_alpha），而 SetAlpha / alpha
# 动画只对 image 与 label 生效，所以底板与两行文字必须逐个淡。
_ITEM_NAME_IMAGE = "/image"
_ITEM_NAME_LABEL = "/image/stack_panel/item_name"
_ITEM_NAME_NAMESPACE_LABEL = "/image/stack_panel/namespace"


# ────────────────── 模块级状态 ──────────────────
_registered = False        # UI 是否已注册
_screens = {}              # 位置 -> ScreenNode 实例
_queue = {                 # 位置 -> 待播放 cfg 队列
    ToastTop: [],
    ToastTopRight: [],
    ToastUnder: [],
}
_playing = {               # 位置 -> 是否正在播放
    ToastTop: False,
    ToastTopRight: False,
    ToastUnder: False,
}

_item_name_screen = None   # 当前物品名提示的叠加层实例（不排队，重复触发即重建）


# 设置界面内嵌底部提示宿主（ScreenNode 或 None）。
# 当设置界面打开时由 SettingsScreenNode 注册自身，底部 toast 改为路由到
# 设置界面内部的高层级面板显示（天然盖在设置 UI 之上），
# 否则（宿主为 None）走原来的 CreateUI 叠加层逻辑。
_settings_under_host = None


def register_settings_under_host(host):
    """设置在设置界面内显示底部提示的宿主 ScreenNode（设置界面 Create 时调用）。"""
    global _settings_under_host
    _settings_under_host = host


def unregister_settings_under_host(host):
    """注销内嵌底部提示宿主（设置界面 Destroy 时调用）。"""
    global _settings_under_host
    if _settings_under_host is host:
        _settings_under_host = None


def _SettingsScreenOnTop():
    """设置界面是否正位于 UI 栈顶（弹窗 / 背包等盖在上面时返回 False）。

    设置主界面是 `render_only_when_topmost: true` 的：被别的界面盖住时整屏不渲染，
    所以"设置界面存在"≠"它内部的附加层看得见"。物品名提示要求"点了就看得见"，
    这里用 clientApi.GetTopScreen() 判断；栈顶不是设置界面时改用叠加层
    （CreateUI 的层级锁定为当前 UI + 1000，天然盖在任何界面之上）。
    """
    if _settings_under_host is None:
        return False
    getter = getattr(clientApi, "GetTopScreen", None)
    if getter is None:
        # 老版本引擎没有该接口：沿用"设置界面存在即视为可见"的旧判定
        return True
    try:
        top = getter()
    except Exception:
        return True
    if top is None:
        return False
    if top is _settings_under_host:
        return True
    try:
        return str(top.GetScreenName() or "") == "setting.main"
    except Exception:
        return True


def RegisterToastScreens():
    """注册 Toast UI，需在 UiInitFinished 时调用一次（幂等）。"""
    global _registered
    if _registered:
        return
    for ui_key, screen_path, _, _, _, _, _, _ in _POSITION_MAP.values():
        clientApi.RegisterUI(
            "Script_NeteaseMod9sPMlz0K",
            ui_key,
            "Script_NeteaseMod9sPMlz0K.Toast.ToastScreenNode",
            screen_path
        )
    # 物品名提示（独立 ScreenNode：没有 offset 进出场，靠 alpha 动画淡出）
    clientApi.RegisterUI(
        "Script_NeteaseMod9sPMlz0K",
        _ITEM_NAME_UI_KEY,
        "Script_NeteaseMod9sPMlz0K.Toast.ItemNameToastScreenNode",
        _ITEM_NAME_SCREEN
    )
    _registered = True
    dlog.client_print("==== Toast UI registered ====")


class ToastScreenNode(ScreenNode):

    def __init__(self, namespace, name, param):
        ScreenNode.__init__(self, namespace, name, param)
        self.position = param.get("position")
        self.enter_anim = None
        self.exit_anim = None
        self.shadow_enter_anim = None
        self.shadow_exit_anim = None
        self.target_ctrl = None   # 动画目标控件
        self.shadow_ctrl = None   # 阴影控件（仅 under 有）
        self.label_ctrl = None    # 文字控件
        self.item_ctrl = None     # 物品控件（top/top_right）
        self.image_ctrl = None    # 图片控件（top/top_right）
        self.duration = 3.0       # 停留时长（秒）
        self._anim_set = False    # 是否已设置过 offset 动画（首次播放无需清理）
        self._exit_sound = ""     # 本帧出场音效（为空则不播）

    def Create(self):
        """UI 创建时缓存控件引用，初始隐藏。"""
        # 兼容热重载下旧实例没有该属性（__init__ 只在新实例上执行）
        self._anim_set = getattr(self, "_anim_set", False)
        if self.position not in _POSITION_MAP:
            dlog.client_print("==== ToastScreenNode: invalid position %s ====" % self.position)
            return
        _, _, self.enter_anim, self.exit_anim, anim_path, shadow_path, \
            self.shadow_enter_anim, self.shadow_exit_anim = _POSITION_MAP[self.position]

        self.target_ctrl = self.GetBaseUIControl(anim_path)
        if not self.target_ctrl:
            dlog.client_print("==== ToastScreenNode: target control %s not found ====" % anim_path)
            return

        if shadow_path:
            self.shadow_ctrl = self.GetBaseUIControl(shadow_path)
            if not self.shadow_ctrl:
                dlog.client_print("==== ToastScreenNode: shadow control %s not found ====" % shadow_path)

        self.label_ctrl = self.GetBaseUIControl("%s/label" % anim_path)
        if self.label_ctrl:
            self.label_ctrl = self.label_ctrl.asLabel()
        else:
            dlog.client_print("==== ToastScreenNode: label control not found ====")

        if self.position in (ToastTop, ToastTopRight):
            self.item_ctrl = self.GetBaseUIControl("%s/item_renderer" % anim_path)
            if self.item_ctrl:
                self.item_ctrl = self.item_ctrl.asItemRenderer()
            else:
                dlog.client_print("==== ToastScreenNode: item_renderer not found ====")

            self.image_ctrl = self.GetBaseUIControl("%s/image" % anim_path)
            if self.image_ctrl:
                self.image_ctrl = self.image_ctrl.asImage()
            else:
                dlog.client_print("==== ToastScreenNode: image control not found ====")

        self.SetScreenVisible(False)

    def Play(self, cfg):
        """播放一个 toast（内部调用）。"""
        if not self.target_ctrl:
            dlog.client_print("==== ToastScreenNode.Play: target control missing ====")
            return
        self.duration = cfg.get("duration", 3.0)
        self._ApplyContent(cfg)
        self._PlayAnim(self.enter_anim, self.shadow_enter_anim, self._OnEnterEnd)
        self.SetScreenVisible(True)
        # 入场音效：cfg 未指定则用该位置默认；空串表示不播
        default_enter, default_exit = _DEFAULT_SOUNDS[self.position]
        enter_sound = cfg.get("enter_sound")
        if enter_sound is None:
            enter_sound = default_enter
        if enter_sound:
            self._PlayUiSound(enter_sound)
        # 出场音效：cfg 未指定则用该位置默认（右上角有，其余为不播）；空串表示不播
        exit_sound = cfg.get("exit_sound")
        if exit_sound is None:
            exit_sound = default_exit
        self._exit_sound = exit_sound

    def _OnEnterEnd(self):
        """入场动画结束，开始停留计时。"""
        game_comp = clientApi.GetEngineCompFactory().CreateGame(clientApi.GetLevelId())
        game_comp.AddTimer(self.duration, self._StartExit)

    def _StartExit(self):
        """开始退场动画；如本帧配了出场音效则播放。"""
        self._PlayAnim(self.exit_anim, self.shadow_exit_anim, self._OnExitEnd)
        if self._exit_sound:
            self._PlayUiSound(self._exit_sound)

    @staticmethod
    def _PlayUiSound(sound_name):
        """播放一个 UI 音效（客户端本地播放，不打断游戏）。"""
        comp = clientApi.GetEngineCompFactory().CreateCustomAudio(clientApi.GetLevelId())
        comp.PlayCustomUIMusic(sound_name, 1.0, 1.0, False)

    def _PlayAnim(self, anim_name, shadow_anim, end_callback):
        """先清理旧动画（仅当已设置过），再设置并播放指定 offset 动画（含阴影同步）。"""
        # 热重载下旧实例可能没有 _anim_set 属性，用 getattr 兜底
        if getattr(self, "_anim_set", False):
            self._StopAnim(self.target_ctrl)
            if self.shadow_ctrl:
                self._StopAnim(self.shadow_ctrl)
        self.target_ctrl.SetAnimation("offset", _ANIM_NS, anim_name)
        self.target_ctrl.PlayAnimation("offset")
        if self.shadow_ctrl and shadow_anim:
            self.shadow_ctrl.SetAnimation("offset", _ANIM_NS, shadow_anim)
            self.shadow_ctrl.PlayAnimation("offset")
        self._anim_set = True
        self.target_ctrl.SetAnimEndCallback(anim_name, end_callback)

    def _StopAnim(self, ctrl):
        """停止并移除控件上的 offset 动画。"""
        ctrl.StopAnimation("offset")
        ctrl.RemoveAnimation("offset")

    def _OnExitEnd(self):
        """退场动画结束，销毁节点并播放下一个。

        这里直接 SetRemove 并从缓存移除，而不是在 _PlayNext 重建前才移除：
        这样下一个 toast 创建时该位置没有同 uiKey 的残留节点，
        可以安全地同步（非延迟）重建，避免"当前 UI + 1000"层级上下文丢失。
        """
        self.SetScreenVisible(False)
        self.SetRemove()
        _screens.pop(self.position, None)
        _PlayNext(self.position)

    def _ApplyContent(self, cfg):
        """应用内容配置：背景、文字/颜色、物品层、图片层。"""
        # 背景贴图：cfg 传 background 则换贴图（需以 textures/ 开头），否则保持 JSON 默认
        background = cfg.get("background")
        if background:
            self.target_ctrl.asImage().SetSprite(background)
        # 背景九宫格剪裁：cfg 传 nine_slice=(左,右,上,下) 则启用原版九宫格适配
        nine_slice = cfg.get("nine_slice")
        if nine_slice:
            self.target_ctrl.asImage().SetImageAdaptionType("originNineSlice", nine_slice)

        # 文字
        text = cfg.get("text", "")
        if self.label_ctrl:
            self.label_ctrl.SetText(text, True)
            color = cfg.get("color")
            self.label_ctrl.SetTextColor(color if color else (1.0, 1.0, 1.0))

        if self.position in (ToastTop, ToastTopRight):
            # 物品层
            item_name = cfg.get("item_name")
            if self.item_ctrl:
                if item_name:
                    self.item_ctrl.SetUiItem(
                        item_name, cfg.get("item_aux", 0), cfg.get("is_enchanted", False)
                    )
                    self.item_ctrl.SetVisible(True)
                else:
                    self.item_ctrl.SetVisible(False)
            # 图片层
            icon = cfg.get("icon")
            if self.image_ctrl:
                if icon:
                    self.image_ctrl.SetSprite(icon)
                    self.image_ctrl.SetVisible(True)
                else:
                    self.image_ctrl.SetVisible(False)


class ItemNameFade(object):
    """物品名提示的显示计时与淡出（叠加层与设置界面内嵌面板共用）。

    时序：立即 alpha=1（不透明）-> 停留 _ITEM_NAME_HOLD 秒 -> 2 秒线性淡到 0。
    Restart 会掐掉上一轮计时、把控件拉回不透明再重新计时，所以"中途再弹一次"
    既不会叠加计时，也不会从半透明接着变暗。
    """

    def __init__(self):
        self.mTimer = None      # 停留计时（进入淡出前唯一需要清理的 timer）
        self.mCtrls = []        # 参与淡出的控件（image + label）
        self.mOnDone = None     # 淡出结束回调（隐藏面板）

    def Restart(self, ctrls, on_done=None):
        """重新开始一轮：控件回到完全不透明，_ITEM_NAME_HOLD 秒后开始淡出。"""
        self.Stop()
        self.mCtrls = [ctrl for ctrl in ctrls if ctrl]
        self.mOnDone = on_done
        for ctrl in self.mCtrls:
            # 上一轮淡出可能还挂着 alpha 动画（残留值 0），先摘掉再手动置 1
            try:
                ctrl.StopAnimation("alpha")
                ctrl.RemoveAnimation("alpha")
            except Exception:
                pass
            ctrl.SetAlpha(1.0)
        if not self.mCtrls:
            return
        try:
            game_comp = clientApi.GetEngineCompFactory().CreateGame(clientApi.GetLevelId())
            self.mTimer = game_comp.AddTimer(_ITEM_NAME_HOLD, self._StartFade)
        except Exception as e:
            dlog.client_print("==== ItemNameFade: timer error: %s ====" % str(e))

    def _StartFade(self):
        """停留结束：给每个控件挂上 2 秒 alpha 动画并同时播放。"""
        self.mTimer = None
        for ctrl in self.mCtrls:
            try:
                ctrl.SetAnimation("alpha", _ANIM_NS, _ITEM_NAME_FADE_ANIM)
                ctrl.PlayAnimation("alpha")
            except Exception as e:
                dlog.client_print("==== ItemNameFade: play fade error: %s ====" % str(e))
        # 结束回调只挂一个控件即可（三个动画同时开始、时长相同）
        if self.mCtrls and self.mOnDone:
            try:
                self.mCtrls[0].SetAnimEndCallback(_ITEM_NAME_FADE_ANIM, self.mOnDone)
            except Exception as e:
                dlog.client_print("==== ItemNameFade: end callback error: %s ====" % str(e))

    def Stop(self):
        """掐掉停留计时（淡出动画由调用方按需摘除）。"""
        if self.mTimer is not None:
            try:
                game_comp = clientApi.GetEngineCompFactory().CreateGame(clientApi.GetLevelId())
                game_comp.KillTimer(self.mTimer)
            except Exception:
                pass
            self.mTimer = None


class ItemNameToastScreenNode(ScreenNode):
    """物品名提示的叠加层实例（CreateUI 创建，设置界面未打开时使用）。

    没有进出场位移：创建后直接不透明显示，由 ItemNameFade 负责停留与淡出。
    """

    def __init__(self, namespace, name, param):
        ScreenNode.__init__(self, namespace, name, param)
        self.mFade = ItemNameFade()
        self.mImageCtrl = None
        self.mNameCtrl = None
        self.mNamespaceCtrl = None
        self.mNameLabel = None
        self.mNamespaceLabel = None

    def Create(self):
        """缓存控件引用，初始隐藏。"""
        self.mImageCtrl = self.GetBaseUIControl(_ITEM_NAME_IMAGE)
        self.mNameCtrl = self.GetBaseUIControl(_ITEM_NAME_LABEL)
        self.mNamespaceCtrl = self.GetBaseUIControl(_ITEM_NAME_NAMESPACE_LABEL)
        self.mNameLabel = self.mNameCtrl.asLabel() if self.mNameCtrl else None
        self.mNamespaceLabel = self.mNamespaceCtrl.asLabel() if self.mNamespaceCtrl else None
        if not self.mImageCtrl:
            dlog.client_print("==== ItemNameToastScreenNode: control %s not found ====" % _ITEM_NAME_IMAGE)
        self.SetScreenVisible(False)

    def Play(self, cfg):
        """显示一次物品名提示。"""
        if self.mNameLabel:
            self.mNameLabel.SetText(cfg.get("text", ""), True)
            color = cfg.get("color")
            if color:
                self.mNameLabel.SetTextColor(color)
        if self.mNamespaceLabel:
            self.mNamespaceLabel.SetText(cfg.get("namespace", ""), True)
            color = cfg.get("namespace_color")
            if color:
                self.mNamespaceLabel.SetTextColor(color)
        self.SetScreenVisible(True)
        self.mFade.Restart((self.mImageCtrl, self.mNameCtrl, self.mNamespaceCtrl),
                           self._OnFadeEnd)

    def Cancel(self):
        """掐掉停留计时（重新触发、销毁时调用）。"""
        if self.mFade:
            self.mFade.Stop()

    def _OnFadeEnd(self):
        """淡出结束：隐藏并销毁叠加层。"""
        global _item_name_screen
        self.SetScreenVisible(False)
        self.SetRemove()
        if _item_name_screen is self:
            _item_name_screen = None

    def Destroy(self):
        self.Cancel()
        try:
            ScreenNode.Destroy(self)
        except Exception:
            pass


def ShowToast(position, text="", color=None, icon=None, item_name=None,
              item_aux=0, is_enchanted=False, duration=3.0, enter_sound=None,
              exit_sound=None, background=None, nine_slice=None):
    """
    显示一个 toast 提示（外部调用入口）。

    :param position:     位置常量（ToastTop / ToastTopRight / ToastUnder）
    :param text:         显示文字
    :param color:        文字颜色 (r, g, b)，0~1，默认白色
    :param icon:         图片路径（如 "textures/ui/xxx"），非空则显示图片层
    :param item_name:    物品 identifier（如 "minecraft:diamond"），非空则显示物品层
    :param item_aux:     物品附加值
    :param is_enchanted: 是否显示附魔效果
    :param duration:     停留时长（秒），默认 3
    :param enter_sound:  自定义入场音效名；None 用位置默认（上面/下面 random.toast，
                         右上角 random.toast_recipe_unlocking_in），空串 "" 不播
    :param exit_sound:   自定义出场音效名；None 用位置默认（仅右上角 random.toast_recipe_unlocking_out，
                         其余不播），空串 "" 不播
    :param background:   自定义背景贴图路径（需以 textures/ 开头）；None 用 JSON 默认
    :param nine_slice:   背景九宫格剪裁 (左,右,上,下)；None 不启用
    """
    if position not in _POSITION_MAP:
        dlog.client_print("==== ShowToast: invalid position %s ====" % position)
        return
    cfg = {
        "text": text,
        "color": color,
        "icon": icon,
        "item_name": item_name,
        "item_aux": item_aux,
        "is_enchanted": is_enchanted,
        "duration": duration,
        "enter_sound": enter_sound,
        "exit_sound": exit_sound,
        "background": background,
        "nine_slice": nine_slice,
    }
    # 设置界面打开时，底部提示路由到设置界面内部的高层级面板（盖在其上）；
    # 否则走原 CreateUI 叠加层逻辑。
    if position == ToastUnder and _settings_under_host is not None:
        host = _settings_under_host
        if hasattr(host, "ShowEmbeddedUnderToast"):
            try:
                host.ShowEmbeddedUnderToast(cfg)
                return
            except Exception as e:
                dlog.client_print("==== ShowToast: embedded under host error: %s ====" % str(e))
    _queue[position].append(cfg)
    if not _playing[position]:
        _PlayNext(position)


def ShowItemNameToast(text, namespace="", color=None, namespace_color=None):
    """
    显示「物品名提示」（类原版点击物品弹出的名称框，对应 toast_item_name 控件）。

    时序固定，不可配：立即以完全不透明显示 -> 停留 2 秒 -> 2 秒内把整块
    （紫色底板 + 物品名 + 命名空间两行文字）线性淡到全透明 -> 隐藏。
    中途再次调用视为"重弹"：马上回到完全不透明并重新计时，不排队、不叠加。

    显示位置按当前打开界面决定：设置界面打开时显示在设置界面内部
    （盖在设置 UI 之上，与底部 toast 同一套路由）；否则用 CreateUI 叠加层。

    :param text:           物品显示名（第一行，白色）
    :param namespace:      命名空间/identifier（第二行，默认紫色，可传空串只显示名称）
    :param color:          第一行文字颜色 (r, g, b)，0~1；None 用 JSON 默认白色
    :param namespace_color: 第二行文字颜色 (r, g, b)，0~1；None 用 JSON 默认紫色
    """
    cfg = {
        "text": text,
        "namespace": namespace,
        "color": color,
        "namespace_color": namespace_color,
    }
    # 设置界面开着且在最上层时显示在界面内部的高层级面板上；
    # 界面被弹窗盖住（render_only_when_topmost 不渲染）或没开时走 CreateUI 叠加层
    host = _settings_under_host
    if host is not None and _SettingsScreenOnTop() and hasattr(host, "ShowEmbeddedItemNameToast"):
        try:
            host.ShowEmbeddedItemNameToast(cfg)
            return
        except Exception as e:
            dlog.client_print("==== ShowItemNameToast: embedded host error: %s ====" % str(e))

    # 每次显示都重建（与 _PlayNext 同理）：CreateUI 的层级在创建那一刻锁定为
    # "当前 UI + 1000"，沿用旧实例会在打开新界面后被盖住；重建同时天然把
    # alpha 复位到完全不透明，符合"中途重弹即回到 100"的要求。
    global _item_name_screen
    old_node = _item_name_screen
    if old_node is not None:
        try:
            old_node.Cancel()
            old_node.SetRemove()
        except Exception:
            pass
        _item_name_screen = None

    screen_node = clientApi.CreateUI("Script_NeteaseMod9sPMlz0K", _ITEM_NAME_UI_KEY, {})
    if not screen_node:
        dlog.client_print("==== ShowItemNameToast: create UI %s failed ====" % _ITEM_NAME_UI_KEY)
        return
    # SetIsHud(1) 只解除操作屏蔽，不影响创建时已锁定的层级
    screen_node.SetIsHud(1)
    _item_name_screen = screen_node
    screen_node.Play(cfg)


def _PlayNext(position):
    """播放队列中下一个 toast；队列空则标记空闲。"""
    global _playing
    if not _queue[position]:
        _playing[position] = False
        return
    _playing[position] = True
    cfg = _queue[position].pop(0)

    ui_key = _POSITION_MAP[position][0]

    # 为何每次都要重建？CreateUI 不传 isHud（即 isHud=0）时，层级在创建那一刻
    # 被锁定为"当前 UI + 1000"，之后 SetIsHud 无法再修改层级。若沿用缓存的旧实例，
    # 其层级会停留在首次创建时的值——若首次是在纯游戏画面下创建，层级偏低，
    # 之后打开设置/背包等界面就会被盖住。所以每次显示都重建，使层级始终锁定为
    # "触发那一刻的当前 UI + 1000"，顶部与底部保持一致的最上层。
    # 创建必须同步进行（不要 AddTimer 延迟），否则触发时的"当前 UI"上下文会丢失，
    # 导致层级偏低、顶部 toast 被已打开界面盖住。
    old_node = _screens.get(position)
    if old_node is not None:
        old_node.SetRemove()
        _screens.pop(position, None)

    screen_node = clientApi.CreateUI("Script_NeteaseMod9sPMlz0K", ui_key,
                                     {"position": position})
    if not screen_node:
        dlog.client_print("==== _PlayNext: create UI %s failed ====" % ui_key)
        _playing[position] = False
        return
    # SetIsHud(1) 只解除操作屏蔽，不影响层级（层级在创建时已锁定为高位）
    screen_node.SetIsHud(1)
    # 这里不再调用 SetLayer：CreateUI 不传 isHud(默认0) 时，层级已被自动锁定为
    # "当前 UI + 1000"（即 isHud=0 的官方行为），天然盖过当前打开的任何界面
    # （如本框架的设置界面）。若再用 SetLayer 覆盖为固定值，一旦当前界面的最终
    # 渲染层级 >= 该固定值，toast 反而会被其盖住，故保留自动高位、不手动覆盖。
    _screens[position] = screen_node

    screen_node.Play(cfg)
