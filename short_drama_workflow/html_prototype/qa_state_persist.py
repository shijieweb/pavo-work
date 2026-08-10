# -*- coding: utf-8 -*-
"""全状态持久化 QA：操控→保存→刷新→还原 端到端验证（走 8787 门户）。测试后还原老板原始状态。"""
import json, sys, time
from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:8787"
PROJECT = "ep_0810_193832"
PROXY_JS = "document.querySelector('#app').__vue_app__._container._vnode.component.proxy"

def get_proxy(page, name):
    return page.evaluate(f"() => ({PROXY_JS})?.['{name}']")

def set_proxy(page, name, val):
    page.evaluate(f"p => (({PROXY_JS}).{name} = p)", val)

results = []
def check(label, cond, detail=""):
    results.append((label, bool(cond), detail))
    print(("PASS " if cond else "FAIL ") + label + ("  | " + detail if detail else ""))

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={"width": 1440, "height": 900})
    errors = []
    page.on("console", lambda m: errors.append((m.text, str(m.location.get("url", "") if isinstance(m.location, dict) else getattr(m.location, "url", "")))) if m.type == "error" else None)
    page.on("pageerror", lambda e: errors.append((str(e), "")))

    # 1) 载入工作台
    page.goto(BASE + "/studio", wait_until="networkidle")
    page.wait_for_timeout(800)
    # 确保目标项目
    pid = get_proxy(page, "projectId")
    if pid != PROJECT:
        page.evaluate(f"p => (({PROXY_JS}).projectId = p)", PROJECT)
        page.evaluate(f"() => (({PROXY_JS}).selectProject())")
        page.wait_for_timeout(1500)
    pid = get_proxy(page, "projectId")
    check("载入目标项目", pid == PROJECT, f"projectId={pid}")

    # 2) 记录服务端原始 workspace_state（测试后还原用）
    import urllib.request
    with urllib.request.urlopen(f"{BASE}/api/spec?project={PROJECT}") as r:
        spec0 = json.loads(r.read().decode("utf-8"))
    orig_ws = dict((spec0.get("meta") or {}).get("workspace_state") or {})
    print("原始 workspace_state:", json.dumps(orig_ws, ensure_ascii=False))

    # 3) 模拟用户操控：改各模块状态（watch 自动触发保存）
    set_proxy(page, "sourceMode", "theme")
    set_proxy(page, "assetTab", "scene")
    set_proxy(page, "matFilter", "role")
    set_proxy(page, "mergeTransition", "fade")
    set_proxy(page, "novelInput", "QA草稿测试文本-刷新不能丢")
    set_proxy(page, "themeInput", "社恐程序员在AI公司逆袭")
    page.wait_for_timeout(1800)  # 防抖 400/300ms + 网络

    # 4) 服务端 workspace_state 已写入
    with urllib.request.urlopen(f"{BASE}/api/spec?project={PROJECT}") as r:
        spec1 = json.loads(r.read().decode("utf-8"))
    ws1 = (spec1.get("meta") or {}).get("workspace_state") or {}
    check("服务端 source_mode=theme", ws1.get("source_mode") == "theme", f"got={ws1.get('source_mode')}")
    check("服务端 asset_tab=scene", ws1.get("asset_tab") == "scene", f"got={ws1.get('asset_tab')}")
    check("服务端 mat_filter=role", ws1.get("mat_filter") == "role", f"got={ws1.get('mat_filter')}")
    check("服务端 merge_transition=fade", ws1.get("merge_transition") == "fade", f"got={ws1.get('merge_transition')}")

    # 5) localStorage 草稿已写入
    local = page.evaluate(f"localStorage.getItem('studio:ui:{PROJECT}')")
    lv = json.loads(local) if local else {}
    check("localStorage 草稿 novelInput", lv.get("novelInput") == "QA草稿测试文本-刷新不能丢", f"got={lv.get('novelInput')}")
    check("localStorage 草稿 themeInput", lv.get("themeInput") == "社恐程序员在AI公司逆袭", f"got={lv.get('themeInput')}")

    # 6) 刷新页面 → 全状态还原
    page.reload(wait_until="networkidle")
    page.wait_for_timeout(1500)
    pid2 = get_proxy(page, "projectId")
    check("刷新后仍载入同一项目", pid2 == PROJECT, f"projectId={pid2}")
    check("还原 activeModule", get_proxy(page, "activeModule") == ws1.get("active_module"), f"{get_proxy(page,'activeModule')} vs {ws1.get('active_module')}")
    check("还原 confirmedSteps", get_proxy(page, "confirmedSteps") == list(ws1.get("confirmed_steps") or []), f"{get_proxy(page,'confirmedSteps')}")
    check("还原 sourceMode=theme", get_proxy(page, "sourceMode") == "theme", f"got={get_proxy(page,'sourceMode')}")
    check("还原 assetTab=scene", get_proxy(page, "assetTab") == "scene", f"got={get_proxy(page,'assetTab')}")
    check("还原 matFilter=role", get_proxy(page, "matFilter") == "role", f"got={get_proxy(page,'matFilter')}")
    check("还原 mergeTransition=fade", get_proxy(page, "mergeTransition") == "fade", f"got={get_proxy(page,'mergeTransition')}")
    check("还原 novelInput 草稿", get_proxy(page, "novelInput") == "QA草稿测试文本-刷新不能丢", f"got={get_proxy(page,'novelInput')}")
    check("还原 themeInput 草稿", get_proxy(page, "themeInput") == "社恐程序员在AI公司逆袭", f"got={get_proxy(page,'themeInput')}")

    # 7) 控制台零错误（错误含 URL，便于定位；favicon 类忽略）
    #    白名单：ep_0810_193832 历史遗留 ref 指向 xiaoxia.png/aning.png，references 目录无此文件
    #    （broken 机制已兜底显示占位，属环境遗留非回归；若出现新的 404 仍会报警）
    real_errors = [e for e in errors
                   if "favicon" not in e[0] and "favicon" not in e[1]
                   and "xiaoxia.png" not in e[1] and "aning.png" not in e[1]]
    check("控制台零错误(白名单排除历史缺图)", len(real_errors) == 0, "; ".join(f"{t}@{u}" for t, u in real_errors[:5]))

    # 8) 还原老板原始状态：服务端 workspace_state + 清本机草稿
    if orig_ws:
        req = urllib.request.Request(f"{BASE}/api/meta",
                                     data=json.dumps({"workspace_state": orig_ws}).encode("utf-8"),
                                     headers={"Content-Type": "application/json"}, method="PUT")
        with urllib.request.urlopen(req) as r:
            rj = json.loads(r.read().decode("utf-8"))
        check("还原服务端原始 workspace_state", rj.get("ok") is True)
    page.evaluate(f"localStorage.removeItem('studio:ui:{PROJECT}')")
    page.reload(wait_until="networkidle")
    page.wait_for_timeout(1200)
    # 草稿清除后 novelInput 应回到服务端真实小说（meta.source_text / meta.novel），而非残留 QA 草稿
    exp_novel = (spec0.get("meta") or {}).get("source_text") or (spec0.get("meta") or {}).get("novel") or ""
    check("还原后 novelInput 回服务端小说", get_proxy(page, "novelInput") == exp_novel, f"got={get_proxy(page,'novelInput')!r} exp={exp_novel!r}")
    check("还原后 sourceMode 回原始", get_proxy(page, "sourceMode") == (orig_ws.get("source_mode") or "novel"), f"got={get_proxy(page,'sourceMode')}")
    check("还原后 localStorage 不含 QA 草稿残留", "QA草稿测试文本" not in (page.evaluate(f"localStorage.getItem('studio:ui:{PROJECT}')") or ""))

    browser.close()

print("\n========== 汇总 ==========")
fails = [r for r in results if not r[1]]
print(f"PASS {len(results)-len(fails)}/{len(results)}")
for f in fails:
    print("FAILED:", f[0], f[2])
sys.exit(1 if fails else 0)
