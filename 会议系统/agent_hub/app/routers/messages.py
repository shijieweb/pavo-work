# -*- coding: utf-8 -*-
"""消息拉取、提交回复、已读状态。对应方案书 §5.1 #3/#4/#5/#6。"""
from fastapi import APIRouter, Query
from app.models.schemas import MessageSend, MessageReply
from app.services import message_store

router = APIRouter(prefix="/api/messages", tags=["messages"])


@router.get("/pull")
def pull(agent_name: str = Query(..., description="Agent 名字")):
    return {"messages": message_store.pull_messages(agent_name)}


@router.post("/reply")
def reply(body: MessageReply):
    return message_store.submit_reply(
        body.agent_name, body.content, body.reply_to_message_id, body.client_msg_id
    )


@router.post("/send")
def send(body: MessageSend):
    msg = message_store.send_user_message(
        body.content, body.target_type, body.target_agent_name, body.client_msg_id
    )
    return {"status": "ok", "message_id": msg["id"]}


@router.get("/history")
def history():
    return {"messages": message_store.get_history()}
