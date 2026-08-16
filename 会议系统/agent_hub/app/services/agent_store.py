# -*- coding: utf-8 -*-
"""Agent 注册与查询逻辑。对应方案书 §5.3 register_agent / load_agents。"""
from .storage import read_json, write_json, now_iso

AGENTS_FILE = "agents.json"


def load_agents():
    return read_json(AGENTS_FILE, [])


def save_agents(agents):
    write_json(AGENTS_FILE, agents)


def register_agent(name):
    """注册 Agent；名字已存在则视为已注册，不重复添加。"""
    agents = load_agents()
    if not any(a.get("name") == name for a in agents):
        agents.append({"name": name, "registered_at": now_iso()})
        save_agents(agents)
    return agents


def list_agent_names():
    return [a.get("name") for a in load_agents() if a.get("name")]
