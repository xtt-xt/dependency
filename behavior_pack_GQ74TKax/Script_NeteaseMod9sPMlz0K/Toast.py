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

对外 API 由 CardRegistryApi 再导出（ShowToast / ToastTop / ToastTopRight / ToastUnder），
外部模组需在 UiInitFinished 内延迟导入调用。
"""

import mod.client.extraClientApi as clientApi

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
    _registered = True
    print "==== Toast UI registered ===="


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

    def Create(self):
        """UI 创建时缓存控件引用，初始隐藏。"""
        # 兼容热重载下旧实例没有该属性（__init__ 只在新实例上执行）
        self._anim_set = getattr(self, "_anim_set", False)
        if self.position not in _POSITION_MAP:
            print "==== ToastScreenNode: invalid position %s ====" % self.position
            return
        _, _, self.enter_anim, self.exit_anim, anim_path, shadow_path, \
            self.shadow_enter_anim, self.shadow_exit_anim = _POSITION_MAP[self.position]

        self.target_ctrl = self.GetBaseUIControl(anim_path)
        if not self.target_ctrl:
            print "==== ToastScreenNode: target control %s not found ====" % anim_path
            return

        if shadow_path:
            self.shadow_ctrl = self.GetBaseUIControl(shadow_path)
            if not self.shadow_ctrl:
                print "==== ToastScreenNode: shadow control %s not found ====" % shadow_path

        self.label_ctrl = self.GetBaseUIControl("%s/label" % anim_path)
        if self.label_ctrl:
            self.label_ctrl = self.label_ctrl.asLabel()
        else:
            print "==== ToastScreenNode: label control not found ===="

        if self.position in (ToastTop, ToastTopRight):
            self.item_ctrl = self.GetBaseUIControl("%s/item_renderer" % anim_path)
            if self.item_ctrl:
                self.item_ctrl = self.item_ctrl.asItemRenderer()
            else:
                print "==== ToastScreenNode: item_renderer not found ===="

            self.image_ctrl = self.GetBaseUIControl("%s/image" % anim_path)
            if self.image_ctrl:
                self.image_ctrl = self.image_ctrl.asImage()
            else:
                print "==== ToastScreenNode: image control not found ===="

        self.SetScreenVisible(False)

    def Play(self, cfg):
        """播放一个 toast（内部调用）。"""
        if not self.target_ctrl:
            print "==== ToastScreenNode.Play: target control missing ===="
            return
        self.duration = cfg.get("duration", 3.0)
        self._ApplyContent(cfg)
        self._PlayAnim(self.enter_anim, self.shadow_enter_anim, self._OnEnterEnd)
        self.SetScreenVisible(True)

    def _OnEnterEnd(self):
        """入场动画结束，开始停留计时。"""
        game_comp = clientApi.GetEngineCompFactory().CreateGame(clientApi.GetLevelId())
        game_comp.AddTimer(self.duration, self._StartExit)

    def _StartExit(self):
        """开始退场动画。"""
        self._PlayAnim(self.exit_anim, self.shadow_exit_anim, self._OnExitEnd)

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
        """退场动画结束，隐藏并播放下一个。"""
        self.SetScreenVisible(False)
        _PlayNext(self.position)

    def _ApplyContent(self, cfg):
        """应用内容配置：文字/颜色、物品层、图片层。"""
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


def ShowToast(position, text="", color=None, icon=None, item_name=None,
              item_aux=0, is_enchanted=False, duration=3.0):
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
    """
    if position not in _POSITION_MAP:
        print "==== ShowToast: invalid position %s ====" % position
        return
    cfg = {
        "text": text,
        "color": color,
        "icon": icon,
        "item_name": item_name,
        "item_aux": item_aux,
        "is_enchanted": is_enchanted,
        "duration": duration,
    }
    _queue[position].append(cfg)
    if not _playing[position]:
        _PlayNext(position)


def _PlayNext(position):
    """播放队列中下一个 toast；队列空则标记空闲。"""
    global _playing
    if not _queue[position]:
        _playing[position] = False
        return
    _playing[position] = True
    cfg = _queue[position].pop(0)

    ui_key = _POSITION_MAP[position][0]
    screen_node = _screens.get(position)
    if screen_node is None:
        # 懒创建叠加 UI（不传 isHud，即 isHud=0，会在比当前 UI 层级大 1000 处生成，
        # 从而显示在背包等已打开界面的上方）
        screen_node = clientApi.CreateUI("Script_NeteaseMod9sPMlz0K", ui_key,
                                         {"position": position})
        if screen_node:
            # 层级在创建时已锁定（保持高位，仍显示在其他 UI 上方），
            # SetIsHud(1) 只解除操作屏蔽，不影响层级
            screen_node.SetIsHud(1)
        else:
            print "==== _PlayNext: create UI %s failed ====" % ui_key
            _playing[position] = False
            return
        _screens[position] = screen_node

    screen_node.Play(cfg)
