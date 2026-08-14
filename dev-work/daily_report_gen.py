#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""daily_report_gen.py — 事件驱动日报生成器（MVP·验证流程，暂不推送）
数据源：board API(tasks/audit/ext-notes) + current_state(缺陷/judge台账) + 记忆日志(待办) + git(今日提交)
输出：dev-work/daily_report/YYYY-MM-DD.md（展示用）
用法：python daily_report_gen.py [日期=今天]  （建议 PYTHONIOENCODING=utf-8）
"""
import json, subprocess, sys, urllib.request, datetime, pathlib
from collections import Counter

ROOT = pathlib.Path(__file__).resolve().parents[1]
HERE = pathlib.Path(__file__).resolve().parent
BOARD = "http://127.0.0.1:8788"
# 默认生成【昨天】全天日报：定时任务在凌晨 00:10 跑，此时昨天 00:00~23:59 数据已齐全，
# 不丢最后半小时；若想手动生成当天实时版，传日期参数：python daily_report_gen.py 2026-08-14
DEFAULT = (datetime.date.today() - datetime.timedelta(days=1)).isoformat()
TODAY = sys.argv[1] if len(sys.argv) > 1 else DEFAULT
OUTDIR = HERE / "daily_report"
OUTDIR.mkdir(exist_ok=True)

def get(url):
    try:
        with urllib.request.urlopen(url, timeout=6) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception as e:
        return {"__err__": str(e)}

def rd(p):
    try:
        return pathlib.Path(p).read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""

def git_log():
    try:
        out = subprocess.run(["git", "log", "--since=%s 00:00" % TODAY, "--oneline"],
                             cwd=str(ROOT), capture_output=True, text=True, timeout=10)
        return [l.strip() for l in out.stdout.splitlines() if l.strip()]
    except Exception:
        return []

# ── 1. 数据源 ──────────────────────────────────────────
tasks = get(f"{BOARD}/api/tasks?project_id=19")
audit = get(f"{BOARD}/api/audit")
notes = get(f"{BOARD}/api/ext/notes?project_id=19")
state = rd(ROOT / "dev-work/current_state.md")
mem = rd(ROOT / (".workbuddy/memory/%s.md" % TODAY))

# ── 2. 进度（board 状态统计）────────────────────────────
if isinstance(tasks, list) and tasks:
    st = Counter(t["status"] for t in tasks)
    prog = " · ".join("%s %d" % (k, v) for k, v in st.items())
    todo_titles = [t["title"] for t in tasks if t["status"] == "待办"]
else:
    prog, todo_titles = "board 不可达", []

# ── 3. 问题 / 解决（今天的事件信号）─────────────────────
today_audit = [a for a in audit if str(a.get("ts", "")).startswith(TODAY)] if isinstance(audit, list) else []
problems, solves = [], []
for a in today_audit:
    act = a.get("action", "") + " " + a.get("target", "")
    if "打回" in act or "删除" in act or "阻塞" in act:
        problems.append("[%s] %s" % (a.get("agent", ""), act))
    if "完成" in act or "放行" in act or "PASS" in act:
        solves.append("[%s] %s" % (a.get("agent", ""), act))
# judge 台账（current_state）今日打回 / PASS
for line in state.splitlines():
    if "judge=" in line and TODAY in line:
        (problems if "打回" in line else solves).append(line.strip().lstrip("- "))
# 今日提交
commits = git_log()
# 记忆日志里的计划/待办
plan_mem = [l.strip().lstrip("- ").lstrip("> ") for l in mem.splitlines()
            if any(k in l for k in ("待办", "下一步", "计划"))] if mem else []

# ── 4. 生成 markdown ───────────────────────────────────
L = []
L.append("# 📋 日报 · %s" % TODAY)
L.append("")
if not problems and not today_audit and not commits:
    L.append("✅ 无异常 · 进度：%s" % (prog or "—"))
    L.append("")
else:
    if problems:
        L.append("## ⚠️ 问题")
        L.extend("- " + p for p in problems[:8])
        L.append("")
    L.append("## 📈 进度")
    L.append("- 状态统计：%s" % (prog or "—"))
    if commits:
        L.append("- 今日提交：")
        L.extend("  - `%s`" % c for c in commits[:10])
    L.append("")
    if solves:
        L.append("## 🔧 解决")
        L.extend("- " + s for s in solves[:8])
        L.append("")
    if plan_mem or todo_titles:
        L.append("## ➡️ 计划")
        L.extend("- " + p for p in plan_mem[:6])
        if todo_titles:
            L.append("- board 待办：%s" % " / ".join(todo_titles[:6]))
        L.append("")
today_notes = [n for n in notes if str(n.get("ts", "")).startswith(TODAY)][-3:] if isinstance(notes, list) else []
if today_notes:
    L.append("## 💬 远程指导留言（今日）")
    for n in today_notes:
        L.append("- [%s] %s" % (n.get("ts", ""), n.get("text", "")))
    L.append("")

out = "\n".join(L)
outfile = OUTDIR / ("%s.md" % TODAY)
outfile.write_text(out, encoding="utf-8")
print("日报已生成: %s" % outfile)
print("---")
print(out)
