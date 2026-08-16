# -*- coding: utf-8 -*-
"""Agent 注册、列表。对应方案书 §5.1 #1/#2。"""
from fastapi import APIRouter
from app.models.schemas import AgentRegister
from app.services import agent_store

router = APIRouter(prefix="/api/agents", tags=["agents"])


@router.post("/register")
def register(body: AgentRegister):
    agent_store.register_agent(body.name)
    return {"status": "ok", "message": "Agent registered successfully"}


@router.get("")
def list_agents():
    return {"agents": agent_store.list_agent_names()}
