# -*- coding: utf-8 -*-
"""Agent 注册、列表。对应方案书 §5.1 #1/#2。"""
from fastapi import APIRouter
from app.models.schemas import AgentRegister
from app.services import agent_store

router = APIRouter(prefix="/api/agents", tags=["agents"])


@router.post("/register")
def register(body: AgentRegister):
    # T-REG-02 / T-PERM-01：区分新注册与已存在，重注册提示唯一性
    agents, created = agent_store.register_agent(body.name)
    if created:
        return {"status": "ok", "message": "Agent registered successfully"}
    return {"status": "ok", "message": "Agent already registered", "already_exists": True}


@router.get("")
def list_agents():
    return {"agents": agent_store.list_agent_names()}
