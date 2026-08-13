#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
route_registry_selftest.py · T-20260813-02 纯函数自测（不启动 8787）
=================================================================
铁律遵守：本脚本 importlib 加载 agnes_proxy 模块 —— 只触发模块级初始化
（读注册表/读 env/读 state），不 bind 端口（bind 在 if __name__=="__main__" 里）。
验证项：
  ① 注册表加载成功且含 /studio、/board 两条真实路由
  ② 前缀唯一校验：手工构造冲突注册表 → 应抛 RouteRegistryError；合法 → 通过
  ③ 无注册表（临时改名等价：调用不存在的路径 / monkeypatch _ROUTE_REGISTRY=None）→
     回退成功（_is_studio/_is_board 行为不变）
  ④ 注册表驱动匹配：_route_for 命中 /api/projects→studio、/board/*→board、/demo→demo
用法：python route_registry_selftest.py
退出码：0 = 全部 PASS；1 = 存在 FAIL。
"""
import importlib.util
import json
import os
import sys
import tempfile

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_MODULE_PATH = os.path.join(_REPO_ROOT, "agnes_proxy.py")

_PASS = []
_FAIL = []


def check(name, fn):
    try:
        fn()
        _PASS.append(name)
        print("  [PASS] %s" % name)
    except AssertionError as e:
        _FAIL.append(name)
        print("  [FAIL] %s :: %s" % (name, e))
    except Exception as e:  # noqa: BLE001 —— 测试脚本要兜住一切异常并如实报
        _FAIL.append(name)
        print("  [FAIL] %s :: 异常 %s: %s" % (name, type(e).__name__, e))


def load_agnes_proxy():
    spec = importlib.util.spec_from_file_location("agnes_proxy_selftest", _MODULE_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main():
    print("== route_registry_selftest（不启动 8787，纯函数自测）==")
    ap = load_agnes_proxy()
    print("  模块加载完成: %s (bind 在 __main__ 内, 未 bind 端口)" % _MODULE_PATH)

    # ① 注册表加载成功 + 含真实路由
    def t1():
        assert ap._ROUTE_REGISTRY is not None, "_ROUTE_REGISTRY 不应为 None"
        prefixes = [r["prefix"] for r in ap._ROUTE_REGISTRY]
        assert "/studio" in prefixes and "/board" in prefixes, "必须含 /studio 与 /board"
        board = [r for r in ap._ROUTE_REGISTRY if r["prefix"] == "/board"][0]
        assert board["target"] == "http://127.0.0.1:8788", "board target 应为 8788"
        assert board["flags"].get("board_token_inject") is True, "board 需保留 token 注入语义"
        assert board["flags"].get("rewrite_html_api") is True, "board 需保留 /api/→/board/api/ rewrite 语义"
        studio = [r for r in ap._ROUTE_REGISTRY if r["prefix"] == "/studio"][0]
        assert studio["target"] == "http://127.0.0.1:8777", "studio target 应为 8777"
        print("    → 注册表 %d 条, 含 /studio→8777(kind=studio) 与 /board→8788(flags 保留)" % len(ap._ROUTE_REGISTRY))
    check("① 注册表加载成功且含两条真实路由", t1)

    # ②a 前缀冲突：构造冲突注册表 → RouteRegistryError
    def t2_conflict():
        cases = [
            (["/api", "/api/spec"], ("/api", "/api/spec")),
            (["/board", "/board"], ("/board", "/board")),
            (["/studio", "/studio"], ("/studio", "/studio")),
        ]
        for prefixes, expect in cases:
            got = ap._find_prefix_conflict(prefixes)
            assert got == expect, "冲突对 %r 应判为 %r, 实际 %r" % (prefixes, expect, got)
        # 经文件加载路径：写临时冲突注册表 → _load_route_registry 应抛 RouteRegistryError
        with tempfile.TemporaryDirectory() as td:
            fp = os.path.join(td, "route_registry.json")
            with open(fp, "w", encoding="utf-8") as f:
                json.dump({"routes": [
                    {"prefix": "/api", "target": "http://127.0.0.1:8777", "kind": "studio"},
                    {"prefix": "/api/spec", "target": "http://127.0.0.1:8777", "kind": "studio"},
                ]}, f, ensure_ascii=False)
            try:
                ap._load_route_registry(fp)
            except ap.RouteRegistryError:
                pass
            else:
                raise AssertionError("冲突注册表应抛 RouteRegistryError, 实际未抛")
        print("    → /api 与 /api/spec 冲突被正确拦截; 重复前缀同样拦截")
    check("② 前缀唯一校验: 冲突→报错", t2_conflict)

    # ②b 合法集合不误报（含 /api/log 与 /api/logs 独立端点、/api/projects 与 /api/project/）
    def t2_valid():
        prefixes = ["/studio", "/board", "/api/log", "/api/logs",
                    "/api/projects", "/api/project/", "/api/spec", "/demo"]
        assert ap._find_prefix_conflict(prefixes) is None, "合法集合不应误报冲突"
        # 真实注册表自身也必须无冲突
        assert ap._find_prefix_conflict([r["prefix"] for r in ap._ROUTE_REGISTRY]) is None
        print("    → 真实注册表 %d 条 prefix 全集合无冲突" % len(ap._ROUTE_REGISTRY))
    check("② 前缀唯一校验: 合法集合通过", t2_valid)

    # ③ 无注册表 → 回退现有硬编码行为
    def t3():
        orig = ap._ROUTE_REGISTRY
        ap._ROUTE_REGISTRY = None
        try:
            assert ap._route_for("/api/projects") is None, "无注册表时 _route_for 应返回 None"
            assert ap._is_studio("/api/projects") is True, "回退: /api/projects 仍判 studio"
            assert ap._is_studio("/studio") is True, "回退: /studio 仍判 studio"
            assert ap._is_board("/board/x") is True, "回退: /board/x 仍判 board"
            assert ap._is_studio("/api/nope") is False, "回退: 未白名单路径不判 studio"
            print("    → _ROUTE_REGISTRY=None 时 _is_studio/_is_board 行为与旧版一致")
        finally:
            ap._ROUTE_REGISTRY = orig
        # 缺失文件路径 → _load_route_registry 返回 None（等价无注册表）
        missing = os.path.join(tempfile.gettempdir(), "no_such_route_registry_%d.json" % os.getpid())
        assert ap._load_route_registry(missing) is None, "缺失文件应回退 None"
        # 解析失败（坏 JSON）→ None
        with tempfile.TemporaryDirectory() as td:
            fp = os.path.join(td, "bad.json")
            with open(fp, "w", encoding="utf-8") as f:
                f.write("{not valid json")
            assert ap._load_route_registry(fp) is None, "坏 JSON 应回退 None"
        # 空 routes → None
        with tempfile.TemporaryDirectory() as td:
            fp = os.path.join(td, "empty.json")
            with open(fp, "w", encoding="utf-8") as f:
                json.dump({"routes": []}, f)
            assert ap._load_route_registry(fp) is None, "空 routes 应回退 None"
        print("    → 缺失/坏 JSON/空 routes 均回退 None（兼容不崩）")
    check("③ 无注册表→回退硬编码", t3)

    # ④ 注册表驱动匹配
    def t4():
        r = ap._route_for("/api/projects")
        assert r is not None and r["kind"] == "studio" and r["target"] == "http://127.0.0.1:8777"
        r = ap._route_for("/studio.html")
        assert r is not None and r["kind"] == "studio", "/studio.html 应命中 studio"
        r = ap._route_for("/board/api/projects")
        assert r is not None and r["kind"] == "board" and r["target"] == "http://127.0.0.1:8788"
        r = ap._route_for("/board")
        assert r is not None and r["kind"] == "board"
        r = ap._route_for("/boardfoo")   # board 需边界匹配，不应误判
        assert r is None, "/boardfoo 不应命中 board"
        r = ap._route_for("/demo")
        assert r is not None and r.get("demo") is True, "/demo 应命中 AC-1.5 演示条目"
        r = ap._route_for("/v1/chat/completions")
        assert r is None, "云 API /v1/* 不应被注册表拦截（仍走 AGNES 转发）"
        print("    → 注册表驱动匹配正确（studio/board/demo/边界/云API 均按预期）")
    check("④ 注册表驱动 _route_for 匹配", t4)

    print("-" * 60)
    print("自测结果: %d PASS, %d FAIL" % (len(_PASS), len(_FAIL)))
    if _FAIL:
        print("❌ 存在 FAIL（退出码 1）")
        return 1
    print("✅ 全部 PASS（退出码 0）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
