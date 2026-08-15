"""T-18 隔离实例 8799 全量验证脚本 (urllib, 不动线上 8787)."""
import urllib.request
import urllib.error

BASE = "http://127.0.0.1:8799"
cands = [f"w{n:02d}_{i}.png" for n in range(1, 28) for i in (1, 2)]
refs = ["charA_front.png", "charA_side.png"]


def get(path):
    url = BASE + path
    try:
        with urllib.request.urlopen(url, timeout=10) as r:
            data = r.read()
            return r.status, r.headers.get("Content-Type", ""), len(data)
    except urllib.error.HTTPError as e:
        return e.code, e.headers.get("Content-Type", ""), len(e.read())
    except Exception as e:  # noqa
        return -1, str(e), 0


print("=" * 60)
print("T-18 隔离实例 8799 验证")
print("=" * 60)

# ① 54 张候选图
ok_cand = 0
bad_cand = []
for c in cands:
    code, ctype, _ = get(f"/batch/__asset__/cand/{c}")
    if code == 200 and "image/png" in ctype:
        ok_cand += 1
    else:
        bad_cand.append((c, code, ctype))
print(f"① 候选图 /batch/__asset__/cand/*.png : {ok_cand}/{len(cands)} -> 200 image/png")
assert ok_cand == len(cands), f"候选图失败: {bad_cand[:5]}"

# ② 2 张参考图
ok_ref = 0
bad_ref = []
for r in refs:
    code, ctype, _ = get(f"/batch/__asset__/ref/{r}")
    if code == 200 and "image/png" in ctype:
        ok_ref += 1
    else:
        bad_ref.append((r, code, ctype))
print(f"② 参考图 /batch/__asset__/ref/*.png   : {ok_ref}/{len(refs)} -> 200 image/png")
assert ok_ref == len(refs), f"参考图失败: {bad_ref}"

# ③ /batch HTML
code, ctype, _ = get("/batch")
print(f"③ /batch (HTML)                    : {code} {ctype}")
assert code == 200, f"/batch 失败: {code}"

# ④ 目录穿越 -> 403
trav_paths = [
    "/batch/__asset__/cand/../../Windows/System32/drivers/etc/hosts.png",
    "/batch/__asset__/cand/../ref/charA_front.png",
    "/batch/__asset__/cand/..%2f..%2fWindows/notepad.png",
]
print("④ 目录穿越测试:")
for tp in trav_paths:
    code, _, _ = get(tp)
    print(f"   {tp} -> {code} (期望 403)")
    assert code == 403, f"穿越未拦截: {tp} -> {code}"

# ⑤ 既有路由零回归
routes = ["/console", "/studio", "/training", "/board", "/soundsfree", "/logs"]
print("⑤ 既有路由零回归:")
for rt in routes:
    code, ctype, _ = get(rt)
    print(f"   {rt:<12} -> {code} {ctype}")
    assert code == 200, f"既有路由回归: {rt} -> {code}"

print("=" * 60)
print("✔ 全部验证通过: 54候选(200/png) + 2参考(200) + /batch(200) + 穿越(403) + 6路由零回归")
print("=" * 60)
