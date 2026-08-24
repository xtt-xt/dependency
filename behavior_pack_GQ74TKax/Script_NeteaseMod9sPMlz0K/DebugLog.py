# -*- coding: utf-8 -*-
"""
调试日志模块
============
统一控制客户端与服务端的调试日志输出（即各系统里 `==== ... ====` 这类日志）。

- 客户端日志：由"设置配置 > 调试 > 日志输出"开关控制，每个玩家各自独立
- 服务端日志：由"设置配置(服务端) > 调试 > 日志输出"开关控制，全局共享，仅 OP 可改

本模块不 import 任何引擎模块，可在 CardRegistry 等纯逻辑模块中被引用。

用法：
    from DebugLog import dlog
    dlog.client_print("=== 调试信息 ===")   # 仅在客户端开关开启时输出
    dlog.server_print("=== 服务端信息 ===") # 仅在服务端开关开启时输出

注意：客户端与服务端在本地主机联机时共享同一模块实例，但两个开关彼此独立，
      client_print / server_print 各自只受对应开关控制，互不影响。
"""

import time

# 每侧日志历史保留条数（供"复制日志"使用，需 >= 默认复制条数 200）
_MAX_HISTORY = 600


class _DebugLog(object):
    """客户端/服务端调试日志开关控制器（client 与 server 两个开关相互独立）。"""

    def __init__(self):
        self._client_enabled = True
        self._server_enabled = True
        self._client_history = []
        self._server_history = []

    # ---------------- 开关设置 ----------------
    def set_client_enabled(self, enabled):
        """设置客户端日志开关。返回设置后的状态。"""
        self._client_enabled = bool(enabled)
        return self._client_enabled

    def set_server_enabled(self, enabled):
        """设置服务端全局日志开关。返回设置后的状态。"""
        self._server_enabled = bool(enabled)
        return self._server_enabled

    # ---------------- 开关获取 ----------------
    def get_client_enabled(self):
        return self._client_enabled

    def get_server_enabled(self):
        return self._server_enabled

    # ---------------- 日志输出 ----------------
    def client_print(self, *args):
        """客户端调试日志输出（受客户端开关控制），并记入客户端历史。"""
        if self._client_enabled:
            print " ".join(str(a) for a in args)
            self._record(self._client_history, args)

    def server_print(self, *args):
        """服务端调试日志输出（受服务端全局开关控制），并记入服务端历史。"""
        if self._server_enabled:
            print " ".join(str(a) for a in args)
            self._record(self._server_history, args)

    # ---------------- 日志历史（复制用） ----------------
    @staticmethod
    def _record(history, args):
        """给一行日志打上时间戳并追加到环形历史，超出上限时淘汰最旧。"""
        line = "[%s] %s" % (time.strftime("%H:%M:%S"), " ".join(str(a) for a in args))
        history.append(line)
        if len(history) > _MAX_HISTORY:
            del history[0]

    def client_history(self):
        """返回客户端日志历史（副本，按时间先后排列）。"""
        return list(self._client_history)

    def server_history(self):
        """返回服务端日志历史（副本，按时间先后排列）。"""
        return list(self._server_history)

    def format_client_history(self, count=200):
        """返回最近 count 条客户端日志（保留最后一次输出在最底部），不足则返回全部。"""
        return "\n".join(self._client_history[-count:])

    def format_server_history(self, count=200):
        """返回最近 count 条服务端日志（保留最后一次输出在最底部），不足则返回全部。"""
        return "\n".join(self._server_history[-count:])


# 模块级单例
dlog = _DebugLog()