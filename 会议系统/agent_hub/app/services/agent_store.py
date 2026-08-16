# -*- coding: utf-8 -*-
"""Agent 注册与查询逻辑。对应方案书 §5.3 register_agent / load_agents。"""
from .storage import read_json, write_json, now_iso

AGENTS_FILE = "agents.json"


def load_agents():
    return read_json(AGENTS_FILE, [])


def save_agents(agents):
    write_json(AGENTS_FILE, agents)


def register_agent(name):
    """注册 Agent；名字已存在则视为已注册，不重复添加。

    返回 (agents, created)：created=True 表示本次新注册，False 表示已存在。
    满足方案书 §7 T-REG-02 / T-PERM-01（重注册需提示唯一性）。
    """
    agents = load_agents()
    if any(a.get("name") == name for a in agents):
        return agents, False
    agents.append({"name": name, "registered_at": now_iso()})
    save_agents(agents)
    return agents, True


def agent_exists(name):
    """目标/回复 Agent 是否存在（用于发送/回复前的存在性校验）。"""
    return any(a.get("name") == name for a in load_agents())


def list_agent_names():
    return [a.get("name") for a in load_agents() if a.get("name")]
