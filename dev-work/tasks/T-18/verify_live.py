#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""T-18 线上 8787 最终核验：纯 ASCII 资产路由 + 既有路由零回归 + 穿越防护。"""
import http.client, json, sys

HOST, PORT = "127.0.0.1", 8787
CAND = [f"w{r:02d}_{c}.png" for r in range(1, 28) for c in (1, 2)]  # 54
REF  = ["charA_front.png", "charA_side.png"]                        # 2

def raw(path):
    c = http.client.HTTPConnection(HOST, PORT, timeout=15)
    try:
        c.request("GET", path)
        r = c.getresponse()
        body = r.read()
        return r.status, r.getheader("Content-Type"), len(body)
    finally:
        c.close()

def jget(path):
    c = http.client.HTTPConnection(HOST, PORT, timeout=15)
    try:
        c.request("GET", path)
        r = c.getresponse()
        return r.status, r.getheader("Content-Type"), len(r.read())
    finally:
        c.close()

print("=== T-18 线上 8787 最终核验 (PID 26628) ===\n")

# 1) 面板 HTML 可达 + 中文目录 URL 已清零
st, ct, sz = jget("/batch")
html = None
c = http.client.HTTPConnection(HOST, PORT, timeout=15)
c.request("GET", "/batch"); r = c.getresponse(); html = r.read().decode("utf-8", "replace"); c.close()
zh_dir = html.count("01_配方训练")
print(f"[面板] /batch -> {st} {ct} bytes={sz}  中文目录URL出现次数={zh_dir} (须=0)")

# 2) 54 候选图全 200 + image/png
cand_ok = cand_bad = 0
for f in CAND:
    st, ct, sz = raw(f"/batch/__asset__/cand/{f}")
    if st == 200 and (ct or "").startswith("image/png") and sz > 0:
        cand_ok += 1
    else:
        cand_bad += 1
        print(f"  候选图异常 {f}: {st} {ct} {sz}")
print(f"[候选图] 54 张 -> 200/合法 image/png = {cand_ok}, 异常 = {cand_bad}")

# 3) 2 参考图全 200
ref_ok = ref_bad = 0
for f in REF:
    st, ct, sz = raw(f"/batch/__asset__/ref/{f}")
    if st == 200 and (ct or "").startswith("image/png") and sz > 0:
        ref_ok += 1
    else:
        ref_bad += 1
        print(f"  参考图异常 {f}: {st} {ct} {sz}")
print(f"[参考图] 2 张 -> 200/合法 image/png = {ref_ok}, 异常 = {ref_bad}")

# 4) 安全：穿越 / 非白名单 kind / 非 png / 不存在
trav = raw("/batch/__asset__/cand/../agnes_proxy.py")        # 穿越
nonkind = raw("/batch/__asset__/evil/x.png")                # 非白名单 kind
nonpng = raw("/batch/__asset__/cand/prompts.csv")           # 非 png
notfound = raw("/batch/__asset__/cand/nope.png")            # 不存在
print(f"[安全] 穿越 .. = {trav[0]}(须403) | 非白名单kind = {nonkind[0]}(须403) | 非png = {nonpng[0]}(须403) | 不存在 = {notfound[0]}(须404)")

# 5) 既有 6 路由零回归
routes = ["/", "/board", "/batch", "/hub.html", "/studio", "/api/spec"]
print("[回归] 既有路由:")
for rt in routes:
    st, ct, sz = jget(rt)
    print(f"   {rt:14s} -> {st} {ct} bytes={sz}")

# 6) 面板内 wp-cmp 行数
wp_cmp = html.count('class="wp-cmp"')
print(f"\n[面板内容] wp-cmp 对比行数 = {wp_cmp} (须=27)")

# 结论
ok = (zh_dir == 0 and cand_ok == 54 and ref_ok == 2 and
      trav[0] == 403 and nonkind[0] == 403 and nonpng[0] == 403 and notfound[0] == 404 and
      wp_cmp == 27)
print("\n=== 结论:", "ALL PASS ✅" if ok else "FAIL ❌", "===")
sys.exit(0 if ok else 1)
