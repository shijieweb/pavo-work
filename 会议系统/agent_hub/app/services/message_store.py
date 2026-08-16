# -*- coding: utf-8 -*-
"""消息、已读回执、回复逻辑。对应方案书 §5.2 / §5.3。

核心差异点（相对 B 系统）：
- 服务端按 target_type 路由（single/all）；Agent 只拉到@自己的消息。
- 显式 MessageRead 实体 + read_by 数组 -> 前端展示"✓已读 / N/N 已读"。
- submit_reply 响应捎带该 Agent 剩余未读（减轮询）。
- client_msg_id 幂等去重（防网络重试重复保存）。
"""
import uuid

from .storage import read_json, write_json, now_iso
from .agent_store import load_agents


def gen_id(prefix="msg"):
    return f"{prefix}_{uuid.uuid4().hex[:10]}"


MESSAGES_FILE = "messages.json"
READS_FILE = "reads.json"


def load_messages():
    return read_json(MESSAGES_FILE, [])


def save_messages(msgs):
    write_json(MESSAGES_FILE, msgs)


def load_reads():
    return read_json(READS_FILE, [])


def save_reads(reads):
    write_json(READS_FILE, reads)


def _dup_by_client_msg_id(msgs, client_msg_id):
    if not client_msg_id:
        return None
    for m in msgs:
        if m.get("client_msg_id") == client_msg_id:
            return m
    return None


def send_user_message(content, target_type, target_agent_name=None, client_msg_id=None):
    """前端发送用户消息：写消息 + 为目标 Agent 建未读回执。对应方案书 §5.3 send_user_message。"""
    msgs = load_messages()
    dup = _dup_by_client_msg_id(msgs, client_msg_id)
    if dup:
        return dup

    msg = {
        "id": gen_id("msg"),
        "content": content,
        "sender_type": "user",
        "sender_agent_name": None,
        "target_type": target_type,
        "target_agent_name": target_agent_name if target_type == "single" else None,
        "created_at": now_iso(),
        "client_msg_id": client_msg_id,
        "read_by": [],
    }
    msgs.append(msg)
    save_messages(msgs)

    reads = load_reads()
    if target_type == "single":
        if target_agent_name:
            reads.append({"message_id": msg["id"], "agent_name": target_agent_name, "read_at": None})
    elif target_type == "all":
        for a in load_agents():
            reads.append({"message_id": msg["id"], "agent_name": a["name"], "read_at": None})
    save_reads(reads)
    return msg


def pull_messages(agent_name):
    """Agent 拉取@自己且未读的消息，并标记为已读。对应方案书 §5.3 pull_messages。"""
    msgs = load_messages()
    reads = load_reads()
    unread = []
    changed = False
    for msg in msgs:
        if msg["sender_type"] != "user":
            continue
        targeted = (
            (msg["target_type"] == "single" and msg["target_agent_name"] == agent_name)
            or msg["target_type"] == "all"
        )
        if not targeted:
            continue
        rec = next(
            (r for r in reads if r["message_id"] == msg["id"] and r["agent_name"] == agent_name),
            None,
        )
        if rec and rec["read_at"] is None:
            unread.append(msg)
            rec["read_at"] = now_iso()
            changed = True
    if changed:
        save_reads(reads)
    return unread


def submit_reply(agent_name, content, reply_to_message_id=None, client_msg_id=None):
    """Agent 提交回复：保存回复，并捎带返回该 Agent 剩余未读消息。对应方案书 §5.3 submit_reply。"""
    msgs = load_messages()
    dup = _dup_by_client_msg_id(msgs, client_msg_id)
    if dup:
        return {"status": "ok", "new_messages": [], "duplicate": True}

    reply = {
        "id": gen_id("msg"),
        "content": content,
        "sender_type": "agent",
        "sender_agent_name": agent_name,
        "target_type": "user",
        "target_agent_name": None,
        "created_at": now_iso(),
        "client_msg_id": client_msg_id,
        "read_by": [],
    }
    msgs.append(reply)
    save_messages(msgs)
    new_messages = pull_messages(agent_name)  # 捎带返回新未读
    return {"status": "ok", "new_messages": new_messages}


def get_history():
    """返回全部消息（用户消息附带 read_by 列表）。对应方案书 §5.1 获取聊天历史。"""
    msgs = load_messages()
    reads = load_reads()
    out = []
    for m in msgs:
        d = dict(m)
        if m["sender_type"] == "user":
            d["read_by"] = [
                r["agent_name"]
                for r in reads
                if r["message_id"] == m["id"] and r["read_at"] is not None
            ]
        else:
            d["read_by"] = []
        out.append(d)
    return out
