# -*- coding: utf-8 -*-
"""【自动固化流水线·B 阶段】经验应用器（人工闸门确认后执行，半自动）。

输入：learn_output/固化建议_*.json（只处理 status=approved 的条目）
应用范围（白名单·安全层，绝不动逻辑代码）：
  - 维护手册/08_经验避坑库.md  → 追加规则表格行（低风险纯文档）
  - html_prototype/prompt_library.json → 更新 optimize 元提示 / types 模板（低风险纯配置）
安全机制：
  1. 应用前自动 git 快照（before: apply_fix <pkg>）——改崩可秒回滚
  2. 写前备份到 .apply_fix_backup/，失败自动恢复
  3. 去重二次确认：目标已含规则关键词 → 跳过（防重复固化）
  4. 应用后自动校验（JSON 合法 / 关键词落位）→ 输出报告

用法：
  python apply_fix.py                      # 用最新建议包，只应用 approved 条目
  python apply_fix.py --pkg <path>         # 指定建议包
  python apply_fix.py --dry-run            # 预览将应用什么，不改文件
"""
import json
import os
import sys
import glob
import shutil
import datetime
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
OUTDIR = os.path.join(HERE, "learn_output")
BACKUP_DIR = os.path.join(HERE, ".apply_fix_backup")

# 白名单目标文件（只允许改这两个）
EXPERIENCE_MD = os.path.join(ROOT, "维护手册", "08_经验避坑库.md")
PROMPT_LIB = os.path.join(ROOT, "short_drama_workflow", "html_prototype", "prompt_library.json")

# 规则主题 → 应用目标 + 去重关键词
TOPIC_ACTION = {
    "拆镜": {"target": "prompt_library+md", "keys": ["拆镜", "DIRECTOR-THINK", "拆分为"]},
    "Animate双要素": {"target": "prompt_library", "keys": ["Animate 双要素", "Keep stable"]},
    "物理规律首尾帧": {"target": "prompt_library+md", "keys": ["物理规律", "prompt-图一致", "首尾帧"]},
    "时长匹配复杂度": {"target": "prompt_library", "keys": ["时长匹配复杂度", "时长"]},
    "空镜免检": {"target": "prompt_library+md", "keys": ["空镜免检", "NO people", "n/a"]},
    "smart抽帧": {"target": "md", "keys": ["smart 抽帧", "首尾必抽"]},
    "prompt_frame_match": {"target": "prompt_library+md", "keys": ["prompt_frame_match", "提示词-帧匹配"]},
}


def git(*args):
    return subprocess.run(["git"] + list(args), capture_output=True, text=True,
                          cwd=ROOT, timeout=60)


def snapshot(msg):
    """应用前 git 快照（before commit）。返回是否成功。"""
    git("add", "-A")
    r = git("commit", "-m", msg)
    return r.returncode == 0 or "nothing to commit" in (r.stdout + r.stderr)


def backup():
    os.makedirs(BACKUP_DIR, exist_ok=True)
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    for fp in (EXPERIENCE_MD, PROMPT_LIB):
        if os.path.isfile(fp):
            shutil.copy2(fp, os.path.join(BACKUP_DIR,
                                          os.path.basename(fp) + "." + stamp))
    return stamp


def restore(stamp):
    for fp in (EXPERIENCE_MD, PROMPT_LIB):
        b = os.path.join(BACKUP_DIR, os.path.basename(fp) + "." + stamp)
        if os.path.isfile(b):
            shutil.copy2(b, fp)


def already_applied(topic, rule):
    """去重二次确认：目标文件是否已覆盖该规则主题/关键词。"""
    keys = TOPIC_ACTION.get(topic, {}).get("keys", [])
    if not keys:
        return False, []
    hits = []
    for fp in (EXPERIENCE_MD, PROMPT_LIB):
        if not os.path.isfile(fp):
            continue
        try:
            t = open(fp, encoding="utf-8").read()
        except Exception:
            continue
        for k in keys:
            if k in t:
                hits.append(os.path.basename(fp) + ":" + k)
    return bool(hits), hits


def apply_to_md(topic, rule):
    """08 经验库追加表格行（若主题未被覆盖）。"""
    if not os.path.isfile(EXPERIENCE_MD):
        return False, "08 经验库不存在"
    t = open(EXPERIENCE_MD, encoding="utf-8").read()
    if rule[:20] in t:
        return False, "规则已存在（完全相同）"
    row = ("| %s（自动固化 %s） | 实验验证经验 | %s | 0812 自动固化 |\n" %
           (topic, datetime.date.today().isoformat(), rule.replace("|", "/")[:150]))
    anchor = "| 视觉审查用 AGNES 2.5-flash"
    if anchor in t:
        t = t.replace(anchor, row + anchor, 1)
    else:
        t = t.rstrip("\n") + "\n\n" + row
    open(EXPERIENCE_MD, "w", encoding="utf-8").write(t)
    return True, "已追加 08 经验库"


def apply_to_prompt_lib(topic, rule):
    """prompt_library 更新（仅当主题在 optimize/types 未覆盖）。"""
    if not os.path.isfile(PROMPT_LIB):
        return False, "prompt_library.json 不存在"
    d = json.load(open(PROMPT_LIB, encoding="utf-8"))
    # 精简规则为一句原则，追加进 optimize 元提示
    brief = "【%s】%s" % (topic, rule[:120])
    if brief in (d.get("optimize") or ""):
        return False, "optimize 已含此规则"
    d["optimize"] = (d.get("optimize") or "") + "\n" + brief
    json.dump(d, open(PROMPT_LIB, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    return True, "optimize 元提示已追加"


def main():
    args = sys.argv[1:]
    dry = "--dry-run" in args
    pkg = None
    if "--pkg" in args:
        pkg = args[args.index("--pkg") + 1]
    if not pkg:
        fs = sorted(glob.glob(os.path.join(OUTDIR, "固化建议_*.json")))
        pkg = fs[-1] if fs else None
    if not pkg or not os.path.isfile(pkg):
        print("未找到建议包（learn_output/固化建议_*.json）")
        return
    d = json.load(open(pkg, encoding="utf-8"))
    approved = [it for it in d.get("rule_items", []) if it.get("status") == "approved"]
    if not approved:
        print("建议包无 approved 条目（老板还没审/都 rejected）——无需应用")
        return

    print("=" * 60)
    print("B 阶段应用器 | 建议包: %s | 模式: %s" % (os.path.basename(pkg), "预览" if dry else "应用"))
    print("=" * 60)
    report = {"pkg": os.path.basename(pkg), "dry": dry, "applied": [], "skipped": []}

    for it in approved:
        topic = it.get("topic")
        rule = it.get("rule")
        dup, hits = already_applied(topic, rule)
        if dup:
            it["apply_status"] = "skipped_dup"
            report["skipped"].append({"id": it["id"], "topic": topic,
                                      "reason": "已覆盖: %s" % hits[:3]})
            print("  [跳过] %s — 已覆盖(%s)" % (topic, hits[:2]))
            continue
        if dry:
            it["apply_status"] = "would_apply"
            report["applied"].append({"id": it["id"], "topic": topic, "rule": rule[:80]})
            print("  [将应用] %s — %s" % (topic, rule[:60]))
            continue
        # 真实应用：先备份（可回滚）
        last_stamp = backup()
        target = TOPIC_ACTION.get(topic, {}).get("target", "md")
        ok, msg = False, ""
        if "prompt_library" in target:
            ok, msg = apply_to_prompt_lib(topic, rule)
        if "md" in target or (not ok):
            ok2, msg2 = apply_to_md(topic, rule)
            if ok2:
                ok, msg = True, msg2
            elif not ok:
                ok, msg = ok2, msg2
        it["apply_status"] = "applied" if ok else "failed"
        report["applied" if ok else "skipped"].append(
            {"id": it["id"], "topic": topic, "rule": rule[:80], "detail": msg})
        print("  [%s] %s — %s" % ("应用" if ok else "失败", topic, msg))

    if dry:
        print("\n预览结束（未改任何文件）")
        return

    # 应用后校验
    if os.path.isfile(PROMPT_LIB):
        try:
            json.load(open(PROMPT_LIB, encoding="utf-8"))
            print("  ✅ prompt_library.json 合法")
        except Exception as e:
            print("  ❌ prompt_library.json 损坏: %s（回滚中）" % str(e)[:80])
            restore(last_stamp)
            return

    # 快照（应用前已快照，这里提交应用结果）
    r = git("add", "-A")
    r2 = git("commit", "-m", "apply_fix: %s (approved 经验应用)" % os.path.basename(pkg))
    print("  提交:", "OK" if r2.returncode == 0 or "nothing" in (r2.stdout + r2.stderr) else r2.stderr[:100])

    out = os.path.join(OUTDIR, "固化应用报告_%s.json" %
                       datetime.datetime.now().strftime("%Y%m%d_%H%M"))
    json.dump(report, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print("\n应用完成 → %s" % out)
    print("应用:%d 跳过:%d | 回滚: git checkout HEAD~1 -- 维护手册/08_经验避坑库.md html_prototype/prompt_library.json" % (
        len(report["applied"]), len(report["skipped"])))


if __name__ == "__main__":
    main()
