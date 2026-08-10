# -*- coding: utf-8 -*-
"""阿编健康检查：接手任务 5 秒掌握系统现状（端口/服务/项目/日志/key 池/磁盘/队列/git）。
用法：python health_check.py   （走 8787 门户；可 --direct 直连 8777）
"""
import json, os, subprocess, sys, time, urllib.request

BASE = os.environ.get("HC_BASE", "http://127.0.0.1:8787")
PROJ = "C:/Users/67972/WorkBuddy/workbuddy/short_drama_workflow/html_prototype"

def get(url, timeout=8):
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            raw = r.read().decode("utf-8", "ignore")
            try:
                return r.status, json.loads(raw)
            except Exception:
                return r.status, raw[:120]
    except Exception as e:
        return None, str(e)

def ports():
    try:
        out = subprocess.run(["netstat", "-ano"], capture_output=True, text=True,
                             encoding="gbk", errors="ignore").stdout or ""
    except Exception:
        out = subprocess.run(["netstat", "-ano"], capture_output=True, text=True,
                             errors="ignore").stdout or ""
    res = {}
    for p in ("8777", "8787", "8788"):
        hits = [l for l in out.splitlines() if ":%s " % p in l and "LISTENING" in l]
        res[p] = len(hits)
    return res

print("=" * 56)
print("短剧工作台 · 健康检查  %s" % time.strftime("%Y-%m-%d %H:%M:%S"))
print("=" * 56)

# 1) 端口
pt = ports()
print("\n[端口]")
for p, n in pt.items():
    print("  :%s  %s" % (p, "✅ LISTEN" if n else "❌ 未监听"))

# 2) 服务响应
print("\n[服务]")
s, d = get(BASE + "/api/projects")
print("  8787 /api/projects -> %s" % (s or d))
if isinstance(d, dict):
    print("  ACTIVE: %s | 项目数: %d" % (d.get("active"), len(d.get("projects") or [])))
    for p_ in (d.get("projects") or [])[:5]:
        print("    - %s | %s" % (p_.get("id"), p_.get("name")))
s2, _ = get(BASE + "/studio")
print("  studio.html -> %s" % (s2 or "ERR"))

# 3) 日志最近错误
print("\n[日志]")
logdir = os.path.join(PROJ, "logs")
errs = []
if os.path.isdir(logdir):
    files = [f for f in os.listdir(logdir) if f.startswith("server.log")]
    if files:
        f = max(files, key=lambda x: os.path.getmtime(os.path.join(logdir, x)))
        fp = os.path.join(logdir, f)
        lines = open(fp, encoding="utf-8", errors="ignore").read().splitlines()
        errs = [l for l in lines if "ERROR" in l or " 500 " in l or "Traceback" in l]
        print("  文件: %s | 最近 %d 行 | ERROR/500: %d 条" % (f, len(lines), len(errs)))
        for l in errs[-3:]:
            print("    !", l[-110:])
    else:
        print("  无 server.log 文件")
else:
    print("  无日志目录")

# 4) key 池
print("\n[AGNES key 池]")
s, d = get(BASE + "/api/key-pool")
if isinstance(d, dict):
    print("  模式: %s | 测试key: %s | 可用: %d/%d | 切换: %d次 | 冷却: %s" % (
        d.get("mode"), "✅" if d.get("has_test_key") else "❌",
        d.get("active"), d.get("total"), d.get("switches"), d.get("cooldown")))
else:
    print("  %s" % d)
s, d = get(BASE + "/api/agnes/last")
if isinstance(d, dict):
    print("  最近 AGNES 调用: %d 条（%s）" % (len(d.get("calls") or []),
          "; ".join("%s:%s" % (c.get("ts"), c.get("status")) for c in (d.get("calls") or [])[:5])))

# 5) 磁盘
print("\n[磁盘]")
try:
    sz = subprocess.run(["du", "-sh", os.path.join(PROJ, "projects")], capture_output=True, text=True).stdout.strip().split()[0]
    print("  projects/ 体积: %s" % sz)
except Exception:
    pass
try:
    if os.name == "nt":
        free = subprocess.run(["powershell", "-NoProfile", "-Command",
                               "[math]::Round((Get-PSDrive C).Free/1GB,1)"],
                              capture_output=True, text=True).stdout.strip()
        print("  C 盘剩余: %s GB" % free)
except Exception:
    pass

# 6) 队列
print("\n[队列]")
s, d = get(BASE + "/api/queue/list", ) if False else (None, None)
try:
    req = urllib.request.Request(BASE + "/api/queue/list", data=b"{}",
                                 headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=8) as r:
        d = json.loads(r.read().decode())
    print("  任务数: %d | 暂停: %s" % (len(d.get("jobs") or []), d.get("paused")))
except Exception as e:
    print("  %s" % str(e)[:80])

# 7) git
print("\n[git]")
try:
    out = subprocess.run(["git", "-C", "C:/Users/67972/WorkBuddy/workbuddy", "status", "--short"],
                         capture_output=True, text=True, cwd="C:/Users/67972/WorkBuddy/workbuddy")
    mod = [l for l in out.stdout.splitlines() if l.strip()]
    print("  未提交改动: %d 个文件" % len(mod))
    for l in mod[:5]:
        print("    ", l[:80])
except Exception as e:
    print("  %s" % str(e)[:60])

print("\n" + "=" * 56)
print("完成。有 ❌/ERROR 先处理；无则按 维护手册/00 开工。")
