# -*- coding: utf-8 -*-
"""会议系统 Agent 客户端（含串行调度，可直接运行演示）

运行方式：
    python agent_client.py
    输入名字后用浏览器里的老板开 /开始提问 即可看到串行提问/接棒。

说明：
    - 串行控制（谁当前提问/谁接棒/评审角色）已落成真实逻辑。
    - gen_question / gen_plan / gen_review / gen_answer / gen_merge 是占位生成器，
      标注 TODO：接入 AI 模型后替换即可，不影响调度跑通。
"""
import os

# 读取 AGENT_NAME 在 reconfigure 之前，避免无 TTY 环境下 input() 被破坏
_NAME_ENV = os.environ.get("AGENT_NAME", "").strip()

import sys
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import requests
import time
import random
import re

SERVER = "http://localhost:5000"
ROOM = "meeting"
UID = f"agent_{random.randint(1000, 9999)}"
NAME = _NAME_ENV or f"Agent_{UID}"  # 必须通过环境变量 AGENT_NAME 传参
BOSS_UID = "boss"
PHASE_COMMANDS = {
    "asking": "/开始提问",
    "planning": "/出方案",
    "reviewing": "/互相评审",
    "done": "/结束会议",
}
MAX_ASK = 3      # 每人最多问几个
MAX_REVIEW = 3   # 每人最多质疑几条

# ---------------- 状态 ----------------
state = {
    "seq": 0,
    "phase": "waiting",
    "members": {},          # uid -> seq_num
    "my_uid": UID,
    "my_name": NAME,
    "my_seq": None,
    "boss_uid": BOSS_UID,
    "boss_topic": "",
    "all_docs": {},         # doc_url -> owner_name（从消息收集，供合并用）

    # asking
    "asked_done": set(),    # 已发"问完了"的 uid
    "my_ask_count": 0,
    "awaiting_answer": False,
    "my_doc": "",

    # planning
    "plan_done": False,
    "plan_doc": "",

    # reviewing（暂定 2 人一轮）
    "review_role": None,    # "challenger" / "defender"
    "my_review_count": 0,
    "review_round": 0,
    "challenger_uid": None,
    "defender_uid": None,
    "i_am_initial_challenger": False,
    "review_doc": "",

    # merge
    "merge_done": False,
}


# ---------------- 工具 ----------------
def join():
    r = requests.post(f"{SERVER}/api/room/{ROOM}/join", json={"uid": UID, "name": NAME})
    return r.json()


def poll(since_seq):
    r = requests.get(f"{SERVER}/api/room/{ROOM}/messages?since={since_seq}")
    return r.json()


def send(content, msg_type="text", title=None):
    body = {"uid": UID, "type": msg_type, "content": content}
    if title:
        body["title"] = title
    requests.post(f"{SERVER}/api/room/{ROOM}/message", json=body)


def upload_doc(content, title):
    r = requests.post(f"{SERVER}/api/doc/upload",
                      json={"room_id": ROOM, "uid": UID, "content": content, "title": title})
    return r.json()["url"]


def get_doc(room_id, doc_id):
    r = requests.get(f"{SERVER}/docs/{room_id}/{doc_id}.md")
    return r.text


def mentioned_me(msg):
    c = msg.get("content", "")
    return f"@{UID}" in c or f"@{NAME}" in c


def nonboss_uids():
    return [u for u in state["members"] if u != BOSS_UID]


def current_asker():
    """当前应提问者 = seq_num 最小且尚未提问完毕的非老板 uid；无则返回 None"""
    cands = [(u, s) for u, s in state["members"].items()
             if u != BOSS_UID and u not in state["asked_done"]]
    if not cands:
        return None
    cands.sort(key=lambda x: x[1])
    return cands[0][0]


# ---------------- 占位生成器（TODO 接 AI） ----------------
def gen_question(idx):
    # TODO: 接入 AI，基于 state["boss_topic"] 生成真实问题
    topic = state["boss_topic"] or "本项目"
    templates = [
        f"第{idx}问：关于「{topic}」，最核心的目标和边界是什么？",
        f"第{idx}问：技术选型上你倾向哪条路线，为什么？",
        f"第{idx}问：预期的交付时间和资源投入大概多少？",
    ]
    return templates[(idx - 1) % len(templates)]


def gen_plan():
    # TODO: 接入 AI，基于 state["my_doc"] 写方案
    return f"# 方案（{NAME}）\n\n## 依据提问\n{state['my_doc']}\n\n## 方案要点\n1. ...\n2. ...\n"


def gen_review(idx, target):
    # TODO: 接入 AI，基于对方文档生成质疑
    return f"质疑{idx}：你的方案在第{idx}个环节上有落地风险，请说明如何应对。"


def gen_answer(review_text):
    # TODO: 接入 AI，针对质疑给出调整
    return f"收到，我会调整方案以覆盖该风险，并在文档中补充说明。"


def gen_merge(docs):
    # TODO: 接入 AI，逐条分析合入/未合入
    parts = ["# 合并方案\n"]
    for owner, content in docs:
        parts.append(f"\n## 来自 {owner}\n{content[:200]}\n")
    parts.append("\n## 合入分析\n- 合入：X 条\n- 未合入：Y 条（原因：...）\n")
    return "\n".join(parts)


# ---------------- 阶段进入 ----------------
def on_phase_command(msg):
    content = msg["content"]
    for p, cmd in PHASE_COMMANDS.items():
        if content.startswith(cmd):
            state["phase"] = p
            print(f">> Phase 切换: {p}")
            if p == "asking":
                m = re.match(r"^/开始提问\s*(.*)$", content)
                state["boss_topic"] = m.group(1).strip() if m else ""
                state["asked_done"] = set()
                state["my_ask_count"] = 0
                state["awaiting_answer"] = False
                state["my_doc"] = f"# 提问记录（{NAME}）\n\n背景：{state['boss_topic']}\n\n"
            elif p == "planning":
                state["plan_done"] = False
                state["plan_doc"] = ""
            elif p == "reviewing":
                setup_review()
            elif p == "done":
                print(">> 会议结束，按 Ctrl+C 退出")
            return True
    return False


def setup_review():
    mb = [(u, s) for u, s in state["members"].items() if u != BOSS_UID]
    mb.sort(key=lambda x: x[1])
    if not mb:
        return
    first = mb[0][0]
    second = mb[1][0] if len(mb) > 1 else mb[0][0]
    # 暂定一轮 = 2 人互相质疑一次；多 Agent 需扩展
    state["i_am_initial_challenger"] = (first == UID)
    state["challenger_uid"] = first
    state["defender_uid"] = second if second != first else first
    state["review_role"] = "challenger" if state["i_am_initial_challenger"] else "defender"
    state["my_review_count"] = 0
    state["review_round"] = 0
    state["review_doc"] = state.get("plan_doc", "") or f"# 方案（{NAME}，评审后）\n"


def swap_review_role():
    state["challenger_uid"], state["defender_uid"] = state["defender_uid"], state["challenger_uid"]
    state["review_role"] = "challenger" if state["review_role"] == "defender" else "defender"
    state["my_review_count"] = 0
    state["review_round"] += 1


# ---------------- 消息处理（按 phase 分派） ----------------
def handle(msg):
    sender_uid = msg.get("from", {}).get("uid", "")
    if sender_uid == UID:
        return
    # 收集文档链接，供合并阶段拉取
    if msg.get("doc_url"):
        state["all_docs"][msg["doc_url"]] = msg.get("from", {}).get("name", "")
    content = msg["content"]

    if on_phase_command(msg):
        return
    if state["phase"] == "asking":
        handle_asking(msg, sender_uid, content)
    elif state["phase"] == "planning":
        pass  # planning 由 tick 自动出方案，不依赖他人消息
    elif state["phase"] == "reviewing":
        handle_reviewing(msg, sender_uid, content)


def handle_asking(msg, sender_uid, content):
    # 别的 agent 说"问完了"/"提问完毕" → 标记其完成
    if sender_uid != BOSS_UID and ("问完了" in content or "提问完毕" in content):
        state["asked_done"].add(sender_uid)
        print(f">> {sender_uid} 提问完毕，asked_done={sorted(state['asked_done'])}")
        return
    # boss 回答我（@我）且我在等回答 → 更新文档
    if sender_uid == BOSS_UID and mentioned_me(msg) and state["awaiting_answer"]:
        state["my_doc"] += f"\n## Q{state['my_ask_count']} 回答\n{content}\n"
        state["awaiting_answer"] = False
        print(">> 收到老板回答，已写入提问文档")


def handle_reviewing(msg, sender_uid, content):
    # 对方说"质疑完了" → 我是被质疑方，更新文档发链接；2人一轮收尾
    if "质疑完了" in content and sender_uid not in (UID, BOSS_UID):
        url = upload_doc(state["review_doc"] or f"# 方案（{NAME}）\n", f"{NAME} 方案（评审后）")
        print(f">> 对方质疑完了，我更新文档：{url}")
        if state["i_am_initial_challenger"] and state["review_round"] >= 1:
            send(f"方案已更新：{url}  @boss 评审完毕")
            print(">> 评审完毕，@boss")
        else:
            send(f"方案已更新：{url}")
        return
    # 对方 @我 质疑 → 我(defender)逐条回答
    if mentioned_me(msg) and sender_uid not in (UID, BOSS_UID) and state["review_role"] == "defender":
        ans = gen_answer(content)
        state["review_doc"] += f"\n- 回应：{content}\n  调整：{ans}\n"
        send(f"@{sender_uid} {ans}")
        print(f">> 我回答质疑：{ans}")


def is_merge_command(msg):
    return msg["content"].startswith("/合方案") and mentioned_me(msg)


def handle_merge(msg, sender_uid):
    if state["merge_done"]:
        return
    docs = []
    for url, owner in state["all_docs"].items():
        doc_id = url.rstrip("/").split("/")[-1].replace(".md", "")
        try:
            docs.append((owner, get_doc(ROOM, doc_id)))
        except Exception:
            pass
    merged = gen_merge(docs)
    url = upload_doc(merged, "合并方案")
    send(f"@boss 合并完成：合入X条，未合入Y条。文档：{url}")
    state["merge_done"] = True
    print(f">> 合并完成：{url}")


# ---------------- 自动动作（tick） ----------------
def tick():
    """根据状态执行当前应发消息的动作，返回是否发出过消息"""
    if state["phase"] == "asking":
        return tick_asking()
    if state["phase"] == "planning":
        return tick_planning()
    if state["phase"] == "reviewing":
        return tick_reviewing()
    return False


def tick_asking():
    if UID in state["asked_done"]:
        return False
    if current_asker() != UID:
        return False
    if state["awaiting_answer"]:
        return False
    if state["my_ask_count"] < MAX_ASK:
        q = gen_question(state["my_ask_count"] + 1)
        state["my_ask_count"] += 1
        state["my_doc"] += f"\n## Q{state['my_ask_count']}\n{q}\n"
        state["awaiting_answer"] = True
        send(f"@{BOSS_UID} {q}")
        print(f">> 我提问 Q{state['my_ask_count']}: {q}")
        return True
    # 问完了：上传文档，先广播，再单独 tick 判定是否最后一人
    url = upload_doc(state["my_doc"], f"{NAME} 提问记录")
    send(f"提问文档：{url} 问完了")
    state["asked_done"].add(UID)
    print(f">> 我提问完毕；文档：{url}")
    # 等 boss 收到"问完了"后推进 /出方案；最后一个人额外发"@boss 提问完毕"触发 boss
    if len(state["asked_done"]) == len(nonboss_uids()):
        send(f"@boss 提问完毕")
        print(">> 我是最后一人，已通知 boss 推进到出方案")
    return True


def tick_planning():
    if state["plan_done"]:
        return False
    plan = gen_plan()
    state["plan_doc"] = plan
    url = upload_doc(plan, f"{NAME} 方案")
    send(f"方案完成：{url}")
    state["plan_done"] = True
    print(f">> 我出方案，文档：{url}")
    return True


def tick_reviewing():
    if state["review_role"] != "challenger":
        return False
    if state["my_review_count"] < MAX_REVIEW:
        target = state["defender_uid"]
        r = gen_review(state["my_review_count"] + 1, target)
        state["my_review_count"] += 1
        send(f"@{target} {r}")
        print(f">> 我质疑 {target} #{state['my_review_count']}: {r}")
        return True
    # 质疑完了 → 交换角色（双方都会 swap，保持同步）
    send("质疑完了")
    print(">> 我质疑完了")
    swap_review_role()
    return True


# ---------------- 主循环 ----------------
def main():
    info = join()
    state["seq"] = info["seq"]
    state["my_seq"] = info["seq_num"]
    state["members"] = {m["uid"]: m["seq_num"] for m in info["members"]}
    state["phase"] = info["phase"]
    state["boss_uid"] = info.get("boss_uid", BOSS_UID)
    print(f"上线成功！你是第{state['my_seq']}个，在线: {[m['name'] for m in info['members']]}")

    while True:
        data = poll(state["seq"])
        if data["messages"]:
            for msg in data["messages"]:
                sender = msg["from"]["name"]
                content = msg["content"]
                print(f"\n[{sender}] {content}")
                if msg.get("doc_url"):
                    print(f"  📄 {msg['doc_url']}")
                # 合并命令单独拦截（任意 phase 都可能收到）
                if is_merge_command(msg):
                    handle_merge(msg, msg.get("from", {}).get("uid", ""))
                else:
                    handle(msg)
            state["seq"] = data["seq"]
            if data.get("members"):
                state["members"] = {m["uid"]: m["seq_num"] for m in data["members"]}

        sent = tick()
        if sent:
            time.sleep(0.5)   # 刚发出 → 立即再拉
        else:
            time.sleep(5)     # 空闲 → 5 秒轮询


if __name__ == "__main__":
    main()
