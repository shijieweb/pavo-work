#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
route_diff_test.py · 8787 路由清单 diff 回归（T-20260813-02 / AC-1.4 + AC-1.5）
================================================================================
读取 route_registry.json（单一事实源），对每个 prefix 经 8787 统一门户做探测断言：
  - GET    <prefix>            → 期望 200/404（后端可达 = 转发目标正确）
  - PUT    <prefix>/__route_diff_probe__  → 期望非「门户 501」（body 含 unsupported method 才算未转发；后端透传的 501 属转发生效）
  - DELETE <prefix>/__route_diff_probe__  → 同上（AC-1.3：PUT/DELETE 对注册表内所有前缀生效）
零 AGNES 额度：所有探测只打 127.0.0.1:8787（及其内网后端 127.0.0.1:*），不碰任何外部 API。
柔性断言（AC-1.5 demo 条目，如 /demo → 127.0.0.1:8779）：假服务未必在跑，命中 502/503
（连接拒绝/转发已生效）也算预期；唯一判 FAIL 的是「门户未加载该注册表行」（404 unknown path / 501）。

用法：python route_diff_test.py [--base http://127.0.0.1:8787] [--registry <path>] [--timeout 10]
退出码：0 = 全部 PASS；1 = 存在 FAIL。
只做探测，不做任何修改。
"""
import argparse
import json
import os
import sys
import urllib.error
import urllib.request

# 复用网关同一份注册表加载/校验逻辑（单一事实源，schema 永不漂移）
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from agnes_proxy import _load_route_registry, RouteRegistryError  # noqa: E402

PORTAL_UNKNOWN = "unknown path"
PROBE_SUFFIX = "__route_diff_probe__"


def _probe(base, path, method, timeout):
    """对 base+path 发探测请求，返回 (status, body_bytes, err)。err 为 None 表示 HTTP 应答到手。"""
    url = base.rstrip("/") + path
    req = urllib.request.Request(url, data=None, method=method,
                                 headers={"User-Agent": "route_diff_test/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read(), None
    except urllib.error.HTTPError as e:
        return e.code, e.read(), None
    except Exception as e:
        return None, b"", str(e)


def _check_route(base, route, timeout):
    """对单条路由做 GET/PUT/DELETE 断言，返回 (lines, ok)。"""
    prefix = route["prefix"]
    target = route["target"]
    demo = bool(route.get("demo", False))
    lines = []
    ok = True

    # ---- GET：转发目标正确（后端 200/404 = 转发已生效）----
    st, body, err = _probe(base, prefix, "GET", timeout)
    if err is not None:
        lines.append("GET %-28s -> 连接失败: %s" % (prefix, err))
        ok = False
    elif demo:
        if st in (200, 502, 503) or (st == 404 and PORTAL_UNKNOWN not in body.decode("utf-8", "ignore")):
            lines.append("GET %-28s -> %s (demo 柔性: 后端未跑 502/503 亦属预期, 注册表加载已生效)" % (prefix, st))
        elif st == 404 and PORTAL_UNKNOWN in body.decode("utf-8", "ignore"):
            lines.append("GET %-28s -> 404 unknown path (FAIL: 门户未加载该注册表行)" % prefix)
            ok = False
        else:
            lines.append("GET %-28s -> %s (FAIL: 非预期状态)" % (prefix, st))
            ok = False
    else:
        if st in (200, 404):
            extra = ""
            if prefix == "/board" and st == 200 and b"/board/api/" in body:
                extra = " [board rewrite 生效]"
            lines.append("GET %-28s -> %s -> %s%s" % (prefix, st, target, extra))
        else:
            lines.append("GET %-28s -> %s (FAIL: 期望 200/404, 转发目标不正确)" % (prefix, st))
            ok = False

    # ---- PUT / DELETE：AC-1.3 注册表内所有前缀（含 board/demo）都转发，不再 501 ----
    for method in ("PUT", "DELETE"):
        st, body, err = _probe(base, prefix + "/" + PROBE_SUFFIX, method, timeout)
        if err is not None:
            lines.append("%-6s %-28s -> 连接失败: %s" % (method, prefix, err))
            ok = False
        elif st == 501 and b"unsupported method" in body:
            lines.append("%-6s %-28s -> 501 (FAIL: 未转发到目标, 仅注册表内路由才应 501)" % (method, prefix))
            ok = False
        elif st == 501:
            lines.append("%-6s %-28s -> %s (转发生效, 后端 %s 应答, 后端自身不支持该 method)" % (method, prefix, st, target))
        elif st == 404 and PORTAL_UNKNOWN in body.decode("utf-8", "ignore"):
            lines.append("%-6s %-28s -> 404 unknown path (FAIL: 门户未加载该注册表行)" % (method, prefix))
            ok = False
        else:
            lines.append("%-6s %-28s -> %s (转发生效, 后端 %s 应答)" % (method, prefix, st, target))
    return lines, ok


def main():
    ap = argparse.ArgumentParser(description="8787 路由清单 diff 回归（零 AGNES 额度）")
    ap.add_argument("--base", default="http://127.0.0.1:8787", help="门户基址（默认 8787）")
    ap.add_argument("--registry", default=None, help="注册表路径（默认 <repo>/route_registry.json）")
    ap.add_argument("--timeout", type=float, default=10.0, help="单探测超时秒数（默认 10）")
    args = ap.parse_args()

    registry_path = args.registry or os.path.join(_REPO_ROOT, "route_registry.json")
    try:
        routes = _load_route_registry(registry_path)
    except RouteRegistryError as e:
        print("FAIL: 注册表校验失败（与网关同一校验逻辑）: %s" % e)
        return 1
    if not routes:
        print("FAIL: 无法加载 %s（缺失/解析失败/空 routes）" % registry_path)
        return 1

    print("== 8787 路由清单 diff 回归 ==")
    print("== 注册表: %s (%d 条路由) | 基址: %s | 零 AGNES 额度 ==" % (registry_path, len(routes), args.base))
    print("-" * 96)

    total_ok = True
    pass_n = 0
    fail_n = 0
    for route in routes:
        lines, ok = _check_route(args.base, route, args.timeout)
        tag = "PASS" if ok else "FAIL"
        if ok:
            pass_n += 1
        else:
            fail_n += 1
            total_ok = False
        for ln in lines:
            print("  [%s] %s" % (tag, ln))

    print("-" * 96)
    print("汇总: %d 路由, PASS=%d, FAIL=%d" % (len(routes), pass_n, fail_n))
    if total_ok:
        print("✅ 全部 PASS (退出码 0)")
        return 0
    print("❌ 存在 FAIL (退出码 1)")
    return 1


if __name__ == "__main__":
    sys.exit(main())
