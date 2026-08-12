# -*- coding: utf-8 -*-
"""【自动固化流水线·A 阶段】经验提取器（只读，不写任何源文件）。

扫描 experiments_data/exp_*.json → 提取 pass 变体的结构化经验（learn 块）→
过滤（重复/冲突检测/置信度标注）→ 生成「固化建议包」JSON。

产出：learn_output/固化建议_YYYYMMDD_HHMM.json（唯一允许的写操作，供人工闸门审视）

纪律：
- 绝不修改 exp_*.json / prompt_library.json / server.py / 经验库 md
- 所有建议只进建议包，应用由人工确认后走 apply_fix（B 阶段，另建）
"""
import json
import glob
import os
import re
import sys
import hashlib
import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))   # workbuddy
EXPDIR = os.path.join(HERE, "..", "..", "..", "experiments_data") if os.path.isdir(os.path.join(HERE, "..", "..", "..", "experiments_data")) else os.path.join(HERE, "experiments_data")
EXPDIR = os.path.abspath(EXPDIR)
OUTDIR = os.path.join(HERE, "learn_output")

# 冲突检测关键词表：规则主题 → prompt_library/经验库中的既有表述（命中=疑似重复）
TOPIC_KEYS = {
    "拆镜": ["拆镜", "拆成", "两个独立镜头", "DIRECTOR-THINK", "拆分为"],
    "Animate双要素": ["Animate", "Keep stable", "什么动", "什么不动", "双要素"],
    "物理规律首尾帧": ["物理规律", "首尾帧", "可衔接", "prompt-图一致", "同机位"],
    "时长匹配复杂度": ["时长匹配", "复杂度", "时长"],
    "空镜免检": ["空镜免检", "no people", "NO people", "n/a"],
    "smart抽帧": ["smart 抽帧", "首尾必抽", "0.5s 间隔", "首帧 0s"],
    "prompt_frame_match": ["prompt_frame_match", "提示词-帧匹配", "开场", "结束"],
}


def load_all_exps():
    exps = []
    for fp in sorted(glob.glob(os.path.join(EXPDIR, "exp_*.json"))):
        try:
            exps.append((fp, json.load(open(fp, encoding="utf-8"))))
        except Exception as e:
            print("[skip] %s 读取失败: %s" % (os.path.basename(fp), str(e)[:60]))
    return exps


def topic_of(rule_text):
    for topic, keys in TOPIC_KEYS.items():
        if any(k in rule_text for k in keys):
            return topic
    return "其他"


def has_conflict(topic, pl):
    """检查 prompt_library.json 与经验库 md 是否已覆盖该主题（粗匹配）。"""
    keys = TOPIC_KEYS.get(topic, [])
    if not keys:
        return False, []
    hits = []
    pl_txt = json.dumps(pl, ensure_ascii=False)
    for k in keys:
        if k in pl_txt:
            hits.append("prompt_library:" + k)
    for md in glob.glob(os.path.join(ROOT, "维护手册", "*.md")):
        try:
            t = open(md, encoding="utf-8").read()
        except Exception:
            continue
        for k in keys:
            if k in t:
                hits.append(os.path.basename(md) + ":" + k)
    return bool(hits), hits


def main():
    exps = load_all_exps()
    if not exps:
        print("无实验数据（experiments_data 为空）")
        return
    os.makedirs(OUTDIR, exist_ok=True)
    pl = {}
    pl_fp = os.path.join(ROOT, "short_drama_workflow", "html_prototype", "prompt_library.json")
    if os.path.isfile(pl_fp):
        try:
            pl = json.load(open(pl_fp, encoding="utf-8"))
        except Exception:
            pass

    items = []          # 建议条目
    rule_seen = set()   # 去重哈希
    stats = {"exp": len(exps), "variants": 0, "pass": 0, "learn": 0,
             "dup_skip": 0, "conflict_mark": 0}
    exp_top = []        # 实验级规则草案（顶层 rules_draft）

    for fp, d in exps:
        exp_id = d.get("id") or os.path.basename(fp)[:-5]
        etype = d.get("type") or ""
        status = d.get("status") or ""
        # 实验级 rules_draft（若实验脚本/人工已填）
        for r in (d.get("rules_draft") or []):
            exp_top.append({"rule": r, "exp": exp_id, "level": "experiment"})
        for v in (d.get("variants") or []):
            stats["variants"] += 1
            learn = v.get("learn") or {}
            verdict = v.get("verdict")
            if verdict == "pass":
                stats["pass"] += 1
            rules = learn.get("rules_draft") or []
            ev = learn.get("evidence") or {}
            reason = learn.get("pass_reason") or ""
            if not rules:
                continue
            stats["learn"] += 1
            for rule in rules:
                h = hashlib.md5(rule.encode("utf-8")).hexdigest()[:12]
                if h in rule_seen:
                    stats["dup_skip"] += 1
                    continue
                rule_seen.add(h)
                topic = topic_of(rule)
                conflict, hits = has_conflict(topic, pl)
                if conflict:
                    stats["conflict_mark"] += 1
                # 置信度：candidate 实验的单次 pass = 中；runs>=2（不同实验）才算高
                runs = 1
                for fp2, d2 in exps:
                    if fp2 == fp:      # 排除自身
                        continue
                    if (d2.get("type") == etype) and any(
                            x.get("name") == v.get("name") and x.get("verdict") == "pass"
                            for x in (d2.get("variants") or [])):
                        runs += 1
                confidence = "high" if runs >= 2 else (
                    "medium" if status == "candidate" else "low")
                items.append({
                    "id": h,
                    "topic": topic,
                    "rule": rule,
                    "source_exp": exp_id,
                    "source_variant": v.get("name"),
                    "hyp": v.get("hyp", "")[:120],
                    "evidence": ev,
                    "pass_reason": reason,
                    "runs": runs,
                    "confidence": confidence,
                    "conflict": conflict,
                    "conflict_hits": hits[:5],
                    "action": _suggest_action(topic, conflict, confidence),
                    "status": "pending",   # 人工闸门：pending/approved/rejected
                })

    # 组装建议包
    pkg = {
        "meta": {
            "created": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
            "exps_scanned": stats["exp"],
            "variants": stats["variants"],
            "pass": stats["pass"],
            "learn_blocks": stats["learn"],
            "dup_skipped": stats["dup_skip"],
            "conflict_marked": stats["conflict_mark"],
            "note": "【人工闸门】以下建议均需老板/阿编审视后由 apply_fix.py 应用；本文件由只读提取器生成，未修改任何源文件。",
        },
        "rule_items": items,
        "exp_level_rules": exp_top,
        "param_snapshot": _param_snapshot(exps),
    }
    # 实验级规则也去重
    seen2 = set()
    pkg["exp_level_rules"] = [r for r in exp_top
                              if not (r["rule"] in seen2 or seen2.add(r["rule"]))]
    out = os.path.join(OUTDIR, "固化建议_%s.json" %
                       datetime.datetime.now().strftime("%Y%m%d_%H%M"))
    with open(out, "w", encoding="utf-8") as f:
        json.dump(pkg, f, ensure_ascii=False, indent=2)
    print("=" * 60)
    print("经验提取完成 → %s" % out)
    print("=" * 60)
    print("实验:%d 变体:%d pass:%d learn:%d 去重:%d 冲突标记:%d" % (
        stats["exp"], stats["variants"], stats["pass"], stats["learn"],
        stats["dup_skip"], stats["conflict_mark"]))
    for it in items:
        print("  [%s] %s | 置信度:%s | 冲突:%s | 动作:%s" % (
            it["topic"], it["rule"][:46], it["confidence"],
            "Y" if it["conflict"] else "N", it["action"][:20]))
    return out


def _suggest_action(topic, conflict, confidence):
    """建议动作（人工确认后执行）：映射到固化目标位置。"""
    if conflict:
        return "人工裁决: 与既有表述疑似重复(%s)，并入或跳过" % topic
    if confidence == "high":
        return "进prompt_library+经验库08/09+生产常量(高置信自动)"
    if confidence == "medium":
        return "进prompt_library(medium)+经验库；生产常量待重复验证"
    return "仅经验库记录(low)；生产应用需runs>=2"


def _param_snapshot(exps):
    """已验证参数快照：pass 变体的 num_frames/frame_rate/negative/seed 聚合。

    P0-3 修复（2026-08-12）：原代码用 `is not None` 判断 negative/seed，
    对字符串和布尔值判断有误。改为 bool() + 类型检测，并记录实际值。
    """
    seen = {}
    for fp, d in exps:
        for v in (d.get("variants") or []):
            if v.get("verdict") != "pass":
                continue
            p = v.get("params") or {}
            key = (p.get("num_frames"), p.get("frame_rate"))
            if key not in seen:
                seen[key] = {
                    "count": 0,
                    "negative": False,         # 修复：默认 False
                    "negative_prompt": "",     # 新增：记录实际负面词
                    "seed_fixed": False,       # 修复：默认 False
                    "seed_value": None,        # 新增：记录 seed 值
                    "mode": p.get("mode"),
                    "exps": []
                }
            seen[key]["count"] += 1
            seen[key]["exps"].append(d.get("id"))
            # 修复：用类型感知的判断替代 is not None
            neg_val = p.get("negative")
            if neg_val is not None:
                if isinstance(neg_val, str):
                    seen[key]["negative"] = bool(neg_val.strip())
                    if seen[key]["negative"]:
                        seen[key]["negative_prompt"] = neg_val[:200]
                elif isinstance(neg_val, bool):
                    seen[key]["negative"] = neg_val
                else:
                    seen[key]["negative"] = bool(neg_val)
            # 修复：seed 检测
            seed_val = p.get("seed")
            if seed_val is not None and isinstance(seed_val, (int, float)):
                seen[key]["seed_fixed"] = True
                seen[key]["seed_value"] = seed_val
    return [{"num_frames": k[0], "frame_rate": k[1], **v} for k, v in seen.items()]


if __name__ == "__main__":
    main()
