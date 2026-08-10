# -*- coding: utf-8 -*-
"""工作台回归测试（固化长期保留，老板 0811 定：真实测试 + 自测用免费 key）。

用法：
  python qa_regression.py fast     # 无 AGNES：语法/内存单测/契约/白名单（秒级，随时跑）
  python qa_regression.py real     # 真实 AGNES：分镜生成(thinking)+scene_type+幂等（烧测试 key）
  python qa_regression.py all      # fast + real
  python qa_regression.py fast --video   # fast + 真实 1 镜视频（烧额度，慎用）

环境：服务须在线（8787）；real 层建议 AGNES_TEST_MODE=1 的测试服务（免费 key 无限额度）。
"""
import json, os, re, subprocess, sys, time, urllib.request

BASE = os.environ.get("QA_BASE", "http://127.0.0.1:8787")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
PY = sys.executable
NODE = "C:/Users/67972/.workbuddy/binaries/node/versions/22.22.2/node.exe"

results = []
def check(l, ok, det=""):
    results.append(ok)
    print(("PASS " if ok else "FAIL ") + l + ("  | " + det if det else ""))

def api(path, body=None, method=None):
    req = urllib.request.Request(BASE + path,
                                 data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Content-Type": "application/json"},
                                 method=method or ("POST" if body is not None else "GET"))
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read().decode("utf-8", "ignore"))
    except urllib.error.HTTPError as e:
        return {"ok": False, "error": "HTTP %d %s" % (e.code, e.read().decode()[:120])}
    except Exception as e:
        return {"ok": False, "error": str(e)}

# ============ FAST 层（无 AGNES，秒级）============
def run_fast():
    print("\n===== FAST 层（无 AGNES）=====")
    # 1) 语法
    ok = subprocess.run([PY, "-m", "py_compile", os.path.join(HERE, "server.py")],
                        capture_output=True, text=True).returncode == 0
    check("server.py 语法", ok)
    html = open(os.path.join(HERE, "studio.html"), encoding="utf-8").read()
    scripts = re.findall(r"<script(?:[^>]*)>(.*?)</script>", html, re.S)
    open("_t.js", "w", encoding="utf-8").write(scripts[2])
    ok = subprocess.run([NODE, "--check", "_t.js"], capture_output=True, text=True).returncode == 0
    os.remove("_t.js")
    check("studio.html JS 语法", ok)

    # 2) 内存单测（import server 会触发日志，忽略）
    sys.path.insert(0, HERE)
    import server
    server.META = {}
    check("_video_size 默认 test 竖屏", server._video_size() == (480, 854), str(server._video_size()))
    server.META = {"aspect_mode": "landscape", "resolution_mode": "prod"}
    check("_video_size 横屏 prod", server._video_size() == (1280, 720), str(server._video_size()))
    server.META = {}
    cases = [({"cn_story": "内心独白", "subtitle": "", "id": 1}, "monologue"),
             ({"cn_story": "对话", "subtitle": "你好", "id": 2}, "dialogue_2"),
             ({"cn_story": "众人讨论", "subtitle": "大家说", "id": 3}, "dialogue_multi"),
             ({"cn_story": "空镜街道", "subtitle": "", "id": 4}, "action")]
    cls_ok = all(server._classify_scene_type(dict(s)) == w for s, w in cases)
    check("_classify_scene_type 4 类", cls_ok)
    check("_emotion_en 中文翻译", server._emotion_en("疲惫孤寂") == "tired and lonely")
    dirty = "photo, 9:16 vertical, no text, no watermark, film grain, 16:9 landscape, 8K"
    cl = server._clean_video_prompt(dirty)
    check("_clean_video_prompt 去尺寸/水印词", "9:16" not in cl and "16:9" not in cl and "watermark" not in cl and "film grain" in cl, cl[:60])

    # 3) 服务契约
    d = api("/api/projects")
    check("GET /api/projects", isinstance(d, dict) and "active" in d)
    kp = api("/api/key-pool")
    check("key-pool 含 mode", isinstance(kp, dict) and "mode" in kp, str(kp.get("mode")))
    al = api("/api/agnes/last")
    check("agnes/last 端点", isinstance(al, dict) and al.get("ok") is True)

    # 4) 代理白名单覆盖（前端全部 /api 都在 STUDIO_PREFIXES）
    proxy_src = open(os.path.join(ROOT, "agnes_proxy.py"), encoding="utf-8").read()
    m = re.search(r"STUDIO_PREFIXES = \((.*?)\)", proxy_src, re.S)
    wl = re.findall(r'"([^"]+)"', m.group(1)) if m else []
    apis = set(re.findall(r"api\(\s*['\"`](/api/[^'\"`?]{2,60})", html))
    miss = [a for a in apis if not any(a == w or a.startswith(w) for w in wl)]
    check("代理白名单全覆盖", not miss, str(miss[:3]) if miss else "%d 个 API" % len(apis))

# ============ REAL 层（真实 AGNES，用测试 key）============
def run_real():
    print("\n===== REAL 层（真实 AGNES，需 AGNES_TEST_MODE=1 测试服务）=====")
    sys.path.insert(0, HERE)
    sys.path.insert(0, os.path.expanduser("~/.workbuddy/skills/agnes-ai/scripts"))
    import server
    from agnes_client import chat
    novel = ("深夜的便利店，加班回来的外卖员阿远买了一份关东煮。收银的女孩小雨把一根热乎的"
             "鱼丸额外送给他：天冷，暖暖手。阿远愣了愣，笑了。")
    t0 = time.time()
    raw = chat(novel, system=server.STORYBOARD_SYS, temperature=0.5, max_tokens=10000, thinking=True)
    print("  分镜生成耗时 %.1fs" % (time.time() - t0))
    text = (raw or "").strip()
    s, e = text.find("{"), text.rfind("}")
    sb = json.loads(text[s:e + 1]) if s != -1 and e != -1 else None
    check("真实分镜生成 JSON", sb is not None, (raw or "")[:100])
    if sb:
        shots = sb.get("shots") or []
        sts = [sh.get("scene_type") for sh in shots]
        cov = len([x for x in sts if x])
        check("scene_type 覆盖 >=50%", cov >= max(1, int(len(shots) * 0.5)), "%d/%d" % (cov, len(shots)))

# ============ 真实 1 镜视频（烧额度，显式 --video）============
def run_video():
    print("\n===== 真实 1 镜视频（烧额度，需测试 key 服务）=====")
    d = api("/api/projects")
    pid = d.get("active")
    if not pid:
        check("无 ACTIVE 项目", False); return
    sp = api("/api/spec?project=" + pid)
    shots = (sp.get("spec") or {}).get("shots") or []
    if not shots:
        check("无分镜", False); return
    sid = shots[0]["id"]
    acc = api("/api/generate/shot", {"id": sid, "force": False})
    if acc.get("accepted"):
        for _ in range(80):
            time.sleep(15)
            st = api("/api/generate/status?shot=%d" % sid)
            if st.get("status") in ("done", "failed"):
                break
        check("真实 1 镜视频", st.get("status") == "done", "status=%s err=%s" % (st.get("status"), str(st.get("error"))[:60]))
    else:
        check("视频提交", False, str(acc)[:80])

if __name__ == "__main__":
    args = sys.argv[1:]
    if "fast" in args:
        run_fast()
    if "real" in args:
        run_real()
    if "--video" in args:
        run_video()
    if not args or "all" in args:
        run_fast()
        run_real()
    fails = [r for r in results if not r]
    print("\n==== 回归 PASS %d/%d ====" % (len(results) - len(fails), len(results)))
    sys.exit(1 if fails else 0)
