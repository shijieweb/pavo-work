#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""board.db 状态中文迁移（T-20260813-07）· 一次性幂等脚本

用法: python migrate_status_zh.py [board.db路径]   # 默认 shared_board/board.db
- 只改 tasks.status：todo→待办 / doing→进行中 / blocked→阻塞 / done→完成
- 兜底：任何非 5 态(+阻塞) 残留（含 NULL/历史乱值）归位 待办
- 幂等：可重复执行；第二次无英文值可改则无操作
- 执行前必须已备份 board.db（cp 到带时间戳文件）——见 design §3.4 / §7
"""
import os, sqlite3, sys

HERE = os.path.dirname(os.path.abspath(__file__))
DB = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "board.db")

# 已知英文值 → 中文映射（顺序无依赖，仅 UPDATE 命中）
MAPPING = [
    ("todo", "待办"),
    ("doing", "进行中"),
    ("blocked", "阻塞"),
    ("done", "完成"),
]
# 最终合法枚举（5 态 + 阻塞旁路），用于兜底与校验
STATUS_ENUM = {"待办", "进行中", "待验证", "已验证", "完成", "阻塞"}


def main():
    if not os.path.isfile(DB):
        print("[ERROR] 数据库不存在: %s" % DB)
        sys.exit(1)
    c = sqlite3.connect(DB)
    try:
        before = dict(c.execute("SELECT status, COUNT(*) FROM tasks GROUP BY status").fetchall())
        print("迁移前状态分布: %s" % before)
        for en, zh in MAPPING:
            cur = c.execute("UPDATE tasks SET status=? WHERE status=?", (zh, en))
            if cur.rowcount:
                print("  映射 %s -> %s : %d 行" % (en, zh, cur.rowcount))
        # 兜底：非 5 态(+阻塞) 残留（含 NULL）归位待办
        cur = c.execute(
            "UPDATE tasks SET status='待办' "
            "WHERE status IS NULL OR status NOT IN ('待办','进行中','待验证','已验证','完成','阻塞')"
        )
        if cur.rowcount:
            print("  兜底归位待办: %d 行" % cur.rowcount)
        c.commit()
        after = dict(c.execute("SELECT status, COUNT(*) FROM tasks GROUP BY status").fetchall())
        print("迁移后状态分布: %s" % after)
        bad = [k for k in after if k not in STATUS_ENUM]
        if bad:
            print("[ERROR] 仍有非法状态残留: %s" % bad)
            sys.exit(2)
        print("[OK] 迁移完成，英文/乱值状态 0 残留")
    finally:
        c.close()


if __name__ == "__main__":
    main()
