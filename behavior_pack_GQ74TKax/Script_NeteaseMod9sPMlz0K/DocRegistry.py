# -*- coding: utf-8 -*-
"""
文档注册 API（书 → 页）
=======================
任意模组注册「书（book）→ 页（page）」两级文档，玩家在游戏内的文档界面里翻阅。

用法:
    RegisterDocBook("fly_armor_docs", "飞行之羽教程", "textures/ui/icon_setting")
    RegisterDocPage("fly_armor_docs", "quickstart", "快速上手", body="# 快速上手\n...")
    RegisterDocPage("fly_armor_docs", "repair", "修复与配方", body="# 修复\n...")

约定:
- 纯数据模块：不 import 引擎、不读写磁盘、不写 SettingState（文档是客户端静态内容，
  与卡片注册同性质，不落盘、不进存档）。
- 全部幂等 upsert：重复注册只覆盖元数据、保留原位置，热重载或重跑注册不会产生重复卡片。
- body 原样存 Markdown 源码，由界面侧 build_doc_blocks() 逐行解释；本模块不解析内容。
- 导入方式与 CardRegistry 一致：扁平模块名（from DocRegistry import ...），
  被门面与 Client 共用同一份实例。
"""

from DebugLog import dlog

# ────────────────── 数据表 ──────────────────

_bookOrder = []   # [book_id, ...] 注册顺序（决定左栏卡片顺序）
_books = {}       # book_id -> {"name": str, "icon": str}
_pages = {}       # book_id -> [page_id, ...] 该书的页顺序
_pageMeta = {}    # (book_id, page_id) -> {"name": str, "icon": str, "body": str}

_docsChangedCallback = None


# ────────────────── 书 ──────────────────

def RegisterDocBook(book_id, name, icon=None):
    """
    注册（或更新）一本书。幂等：已存在时覆盖元数据、保留原位置。

    :param book_id: 书唯一标识符（与卡片 id 同一命名空间之外，建议带模组前缀）
    :param name:    书在左栏显示的名字
    :param icon:    图标路径；传 None 或空串表示不要图标（左栏卡片只显示文字）
    :returns:       True 成功；False 参数无效
    """
    if not book_id or not name:
        return False
    _books[book_id] = {"name": name, "icon": icon or ""}
    if book_id not in _bookOrder:
        _bookOrder.append(book_id)
    if book_id not in _pages:
        _pages[book_id] = []
    _NotifyDocsChanged()
    return True


def UnregisterDocBook(book_id):
    """
    注销一本书，连同它下面的所有页一起移除。

    :returns: True 移除成功；False 书不存在
    """
    if book_id not in _books:
        return False
    del _books[book_id]
    if book_id in _bookOrder:
        _bookOrder.remove(book_id)
    for page_id in _pages.pop(book_id, []):
        _pageMeta.pop((book_id, page_id), None)
    _NotifyDocsChanged()
    return True


def GetDocBook(book_id):
    """获取书信息 {"name": str, "icon": str} 或 None。"""
    return _books.get(book_id)


def GetAllDocBookIds():
    """按注册顺序返回所有书 id 列表。"""
    return list(_bookOrder)


def GetDocBookCount():
    """返回已注册书的数量。"""
    return len(_bookOrder)


# ────────────────── 页 ──────────────────

def RegisterDocPage(book_id, page_id, name, icon=None, body=""):
    """
    在某本书下注册（或更新）一页。幂等：已存在时覆盖元数据、保留原位置。

    :param book_id: 所属书 id（须先 RegisterDocBook；书不存在返回 False）
    :param page_id: 页唯一标识符（书内唯一，不同书可同名）
    :param name:    页在子卡片上显示的名字
    :param icon:    图标路径；传 None 或空串表示不要图标（页卡片只显示文字）
    :param body:    正文 Markdown 源码
    :returns:       True 成功；False 参数无效或书不存在
    """
    if not book_id or not page_id or not name:
        return False
    if book_id not in _books:
        return False
    pages = _pages.setdefault(book_id, [])
    if page_id not in pages:
        pages.append(page_id)
    _pageMeta[(book_id, page_id)] = {"name": name, "icon": icon or "", "body": body or ""}
    _NotifyDocsChanged()
    return True


def UnregisterDocPage(book_id, page_id):
    """注销某本书下的一页。返回 True 移除成功，False 该页不存在。"""
    pages = _pages.get(book_id)
    if not pages or page_id not in pages:
        return False
    pages.remove(page_id)
    _pageMeta.pop((book_id, page_id), None)
    _NotifyDocsChanged()
    return True


def SetDocPageBody(book_id, page_id, body):
    """
    只更新某页正文（不动名字/图标/顺序）。供外部模组动态改文案。

    :returns: True 成功；False 该页不存在
    """
    meta = _pageMeta.get((book_id, page_id))
    if not meta:
        return False
    meta["body"] = body or ""
    _NotifyDocsChanged()
    return True


def GetDocPageIds(book_id):
    """按注册顺序返回某本书的所有页 id 列表（书不存在返回空列表）。"""
    return list(_pages.get(book_id, []))


def GetDocPageCount(book_id):
    """返回某本书的页数。"""
    return len(_pages.get(book_id, []))


def GetDocPage(book_id, page_id):
    """获取页数据 {"name": str, "icon": str, "body": str} 或 None。"""
    return _pageMeta.get((book_id, page_id))


def FindDocPageByPageId(page_id):
    """
    按页 id 在所有书里找第一处匹配，返回 (book_id, page_id) 或 None。

    供 /doc_open 只给页 id 时定位（书 id 省略的场景）。
    """
    if not page_id:
        return None
    for book_id in _bookOrder:
        if (book_id, page_id) in _pageMeta:
            return (book_id, page_id)
    return None


def GetAllDocPages():
    """
    返回 [(book_id, page_id), ...]，按书顺序 + 页顺序展开。

    界面重建、命令参数校验等需要遍历全量页时使用。
    """
    result = []
    for book_id in _bookOrder:
        for page_id in _pages.get(book_id, []):
            result.append((book_id, page_id))
    return result


# ────────────────── 动作（正文里的可点代码入口） ──────────────────

# 正文可以写 `[文字](action:动作id)`，点击时执行这里注册的回调。
# 刻意不支持「在正文里写代码字符串再 eval」：正文属于数据（可能来自别的模组、
# 服务端下发或存档），eval 等于把任意代码执行权交给数据；注册动作 id 与正文解耦、
# 可审计、可卸载，正文里写错 id 只会得到一条提示。

_actions = {}      # action_id -> callback


def RegisterDocAction(action_id, callback):
    """
    注册一个动作链接的回调。重复注册覆盖旧回调（幂等，热重载友好）。

    :param action_id: 动作 id，正文里写 `[文字](action:动作id)`
    :param callback:  无参可调用对象；点击时调用，抛异常只打日志、不影响界面
    :returns:         True 成功；False 参数无效（id 为空或 callback 不可调用）
    """
    if not action_id or not callable(callback):
        return False
    if action_id in _actions:
        dlog.client_print("==== doc action re-registered: %s ====" % action_id)
    _actions[action_id] = callback
    return True


def UnregisterDocAction(action_id):
    """注销一个动作。返回 True 移除成功，False 动作不存在。"""
    if action_id not in _actions:
        return False
    del _actions[action_id]
    return True


def GetDocAction(action_id):
    """取动作回调（不存在返回 None）。界面侧派发点击时调用。"""
    return _actions.get(action_id)


def ClearAllDocActions():
    """清空所有动作（测试 / 热重载兜底用，不影响书与页）。"""
    _actions.clear()


# ────────────────── 整体重置 ──────────────────

def ClearAllDocs():
    """清空所有书与页（主要用于测试/热重载兜底）。"""
    _bookOrder[:] = []
    _books.clear()
    _pages.clear()
    _pageMeta.clear()
    _NotifyDocsChanged()


# ────────────────── 变更回调 ──────────────────

def SetDocChangedCallback(callback):
    """
    设置文档注册变更回调。
    RegisterDocBook / RegisterDocPage / Unregister* / SetDocPageBody / ClearAllDocs
    成功后自动调用，通常由文档界面设置，用于按 id 原地刷新（保留当前选中的书与页）。
    """
    global _docsChangedCallback
    _docsChangedCallback = callback


def _NotifyDocsChanged():
    """通知文档注册已变更（回调异常只打日志，不影响注册调用方）。"""
    if _docsChangedCallback:
        try:
            _docsChangedCallback()
        except Exception as e:
            dlog.client_print("==== doc changed callback error: %s ====" % str(e))


# ============================================================
# 事件常量定义
# ============================================================

# 文档 UI 打开事件，由 MyClientSystem 在 PushScreen 时抛出
# 事件数据: {"playerId": str}
DocsUIOpenEvent = "Script_NeteaseMod9sPMlz0K_DocsUIOpen"

# 文档 UI 关闭事件，由 MyClientSystem 在 PopScreen 时抛出
# 事件数据: {"playerId": str}
DocsUICloseEvent = "Script_NeteaseMod9sPMlz0K_DocsUIClose"

# 文档跳转前置事件，由 MyClientSystem 响应 /doc_open 命令、执行跳转前抛出
# 事件数据: {"playerId": str, "book_id": str, "page_id": str}
DocsNavigateEvent = "Script_NeteaseMod9sPMlz0K_DocsNavigate"
