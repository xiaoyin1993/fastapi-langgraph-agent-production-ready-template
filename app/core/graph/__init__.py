"""LangGraph 智能体包，提供多 Agent 管理和注册。"""

from app.core.graph.agent import LangGraphAgent
from app.core.graph.manager import AgentManager, agent_manager
from app.core.graph.registry import (
    DEFAULT_AGENT,
    agent,
    discover_agents,
    get_agent,
    get_agent_extras,
    get_all_agents_info,
    initialize_all,
)

__all__ = [
    "LangGraphAgent",
    "AgentManager",
    "agent_manager",
    "DEFAULT_AGENT",
    "agent",
    "discover_agents",
    "get_agent",
    "get_agent_extras",
    "get_all_agents_info",
    "initialize_all",
]
