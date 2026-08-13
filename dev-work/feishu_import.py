#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
feishu_import.py - 从本地 dev-work 解析任务，生成飞书多维表格记录

被 feishu_board.py 的 sync 命令调用：build_records() -> [ {字段字典}, ... ]
字段键与 feishu_board.BOARD_FIELDS 对齐（任务ID/标题/状态/负责人/优先级/类型/...）。

数据源：
  - dev-work/current_state.md 的「操作审计」表（各任务最终状态 + 操作者）
  - dev-work/tasks/<T-ID>/PRD.md（任务标题，取首个一级标题或目录名）
"""
import os
import re

DEV_WORK = os.path.dirname(os.path.abspath(__file__))
CURRENT_STATE = os.path.join(DEV_WORK, "current_state.md")


# 状态变更串 -> 规范状态（取末尾节点，映射到看板六态之一）
def _canon_status(change: str) -> str:
    change = change.strip()
    # 取最后一个箭头后的 token
    last = change.split("→")[-1].strip() if "→" in change else change
    mapping = {
        "完成": "完成",
        "已完成": "完成",
        "已验证": "已验证",
        "已验证→完成": "完成",
        "派验收": "已验证",
        "派测试": "已验证",
        "派测试(已验证进行中)": "已验证",
        "Round2": "已验证",
        "待验证": "待验证",
        "进行中": "进行中",
        "待办": "待办",
        "挂起": "挂起",
        "阻塞": "阻塞",
    }
    if last in mapping:
        return mapping[last]
    # 退化：含关键字则识别
    for k, v in mapping.items():
        if k in last:
            return v
    return "待办"


def _priority(name: str) -> str:
    m = re.search(r"P[0-3]", name)
    return m.group(0) if m else "P2"


def _title_from_prd(task_id: str) -> str:
    prd = os.path.join(DEV_WORK, "tasks", task_id, "PRD.md")
    if not os.path.exists(prd):
        return task_id
    try:
        with open(prd, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith("# "):
                    return line[2:].strip()
    except Exception:
        pass
    return task_id


def build_records() -> list:
    """返回任务记录列表（字段字典）。"""
    if not os.path.exists(CURRENT_STATE):
        return []
    with open(CURRENT_STATE, encoding="utf-8") as f:
        lines = f.read().splitlines()

    # 1) 解析「操作审计」表，按任务ID保留最后一行（最终状态）
    latest = {}
    for line in lines:
        s = line.strip()
        if not (s.startswith("| 2026-08-") and "操作者" not in s and "---" not in s):
            continue
        cells = [c.strip() for c in s.strip("|").split("|")]
        if len(cells) < 5:
            continue
        task_raw, status_change, operator = cells[2], cells[3], cells[1]
        m = re.match(r"(T-\d{8}-\d+)", task_raw)
        if not m:
            continue
        tid = m.group(1)
        latest[tid] = {
            "task_id": tid,
            "name": task_raw,
            "operator": operator,
            "status_change": status_change,
        }

    # 2) 也解析「当前任务」表（带 状态/开发/测试 列），补充负责人与状态
    owners = {}
    for line in lines:
        s = line.strip()
        if not (s.startswith("| T-") and "状态" not in s and "---" not in s):
            continue
        cells = [c.strip() for c in s.strip("|").split("|")]
        if len(cells) < 5:
            continue
        task_raw = cells[0]
        m = re.match(r"(T-\d{8}-\d+)", task_raw)
        if m:
            owners[m.group(1)] = {
                "dev": cells[2], "test": cells[3],
                "name": task_raw, "status": _canon_status(cells[1]),
            }

    # 3) 合并为记录
    records = []
    for tid, info in latest.items():
        name = owners.get(tid, {}).get("name") or info["name"]
        owner = info["operator"]
        status = _canon_status(info["status_change"])
        rec = {
            "任务ID": tid,
            "标题": _title_from_prd(tid),
            "状态": status,
            "负责人": owner,
            "优先级": _priority(name),
            "类型": "主任务",
            "父任务": "",
            "截止": "",
            "完成时间": info.get("time", "").split(" ")[0] if status == "完成" else "",
            "备注": (info["status_change"] + " | " + name)[-200:],
            "关联文档": f"dev-work/tasks/{tid}/PRD.md",
        }
        records.append(rec)

    # 4) 补充 tasks 目录下有 PRD 但未出现在审计表的任务（默认 待办）
    tasks_dir = os.path.join(DEV_WORK, "tasks")
    if os.path.isdir(tasks_dir):
        for d in sorted(os.listdir(tasks_dir)):
            m = re.match(r"(T-\d{8}-\d+)", d)
            if not m or m.group(1) in latest:
                continue
            tid = m.group(1)
            if os.path.exists(os.path.join(tasks_dir, d, "PRD.md")):
                ow = owners.get(tid, {})
                records.append({
                    "任务ID": tid,
                    "标题": _title_from_prd(tid),
                    "状态": ow.get("status", "待办"),
                    "负责人": ow.get("dev", "") or ow.get("test", ""),
                    "优先级": _priority(d),
                    "类型": "主任务",
                    "父任务": "",
                    "截止": "",
                    "完成时间": "",
                    "备注": ow.get("name", "未在状态台登记"),
                    "关联文档": f"dev-work/tasks/{tid}/PRD.md",
                })
    return records


if __name__ == "__main__":
    recs = build_records()
    print(f"解析到 {len(recs)} 条任务：")
    for r in recs[:20]:
        print(f"  {r['任务ID']:18} | {r['状态']:4} | {r['负责人']:12} | {r['标题'][:30]}")
    if len(recs) > 20:
        print(f"  ... 共 {len(recs)} 条")
