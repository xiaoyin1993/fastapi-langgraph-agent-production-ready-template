"""Agent 注册表 — 装饰器 + 工厂 + 自动发现。

两阶段注册：
1. 声明阶段（import 时）：@agent 装饰器将构建函数注册到 _factories
2. 运行阶段（启动时）：initialize_all() 调用所有工厂函数，构建并存入 _instances

新增 Agent 只需在 agents/ 目录下新建文件，用 @agent 装饰器标注构建函数。
"""

import importlib
import pkgutil
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from langgraph.graph.state import CompiledStateGraph
from langgraph.pregel import Pregel

from app.infrastructure.logging import logger
from app.schemas.agent import AgentInfo

AgentGraph = CompiledStateGraph | Pregel

DEFAULT_AGENT = "assistant"


@dataclass
class AgentFactory:
    """Agent 工厂定义（声明阶段，import 时注册）。"""

    key: str
    description: str
    builder: Callable  # async def(checkpointer, store) -> graph | (graph, extras)


@dataclass
class AgentInstance:
    """Agent 运行实例（初始化后）。"""

    key: str
    description: str
    graph: AgentGraph
    extras: dict[str, Any] = field(default_factory=dict)


# ── 两阶段存储 ──────────────────────────────────────────────
_factories: dict[str, AgentFactory] = {}
_instances: dict[str, AgentInstance] = {}


# ── 装饰器 ──────────────────────────────────────────────────
def agent(key: str, description: str):
    """装饰器：注册 Agent 构建工厂。

    被装饰函数签名：async def build(checkpointer, store) -> graph | (graph, extras_dict)

    extras_dict 用于存放 agent 特有引用（如 LangGraphAgent 实例，供 mem0ai 使用）。

    Example::

        @agent("translator", description="多语言翻译 Agent")
        async def build_translator(checkpointer, store):
            graph = build_my_graph(checkpointer=checkpointer)
            if store:
                graph.store = store
            return graph
    """

    def decorator(fn: Callable) -> Callable:
        _factories[key] = AgentFactory(key=key, description=description, builder=fn)
        logger.info("agent_factory_registered", agent_key=key)
        return fn

    return decorator


# ── 生命周期 ────────────────────────────────────────────────
def discover_agents() -> None:
    """自动发现并导入 agents/ 目录下所有模块，触发 @agent 装饰器注册。"""
    import app.core.graph.agents as agents_pkg

    for _, module_name, _ in pkgutil.iter_modules(agents_pkg.__path__):
        full_name = f"app.core.graph.agents.{module_name}"
        importlib.import_module(full_name)
        logger.info("agent_module_discovered", module=full_name)


async def initialize_all(checkpointer, store) -> None:
    """构建所有已注册的 Agent。由 AgentManager.initialize() 在启动时调用。"""
    for key, factory in _factories.items():
        result = await factory.builder(checkpointer=checkpointer, store=store)
        if isinstance(result, tuple):
            graph, extras = result
        else:
            graph, extras = result, {}
        _instances[key] = AgentInstance(
            key=key, description=factory.description, graph=graph, extras=extras
        )
        logger.info("agent_initialized", agent_key=key, has_extras=bool(extras))


# ── 查询 API ───────────────────────────────────────────────
def get_agent(agent_id: str) -> AgentGraph:
    """根据 agent_id 获取编译后的图。

    Raises:
        KeyError: Agent 未注册时抛出。
    """
    if agent_id not in _instances:
        available = list(_instances.keys())
        raise KeyError(f"Agent '{agent_id}' not found. Available agents: {available}")
    return _instances[agent_id].graph


def get_agent_extras(agent_id: str) -> dict[str, Any]:
    """获取 Agent 的 extras 字典（存放 agent 特有引用）。

    Raises:
        KeyError: Agent 未注册时抛出。
    """
    if agent_id not in _instances:
        available = list(_instances.keys())
        raise KeyError(f"Agent '{agent_id}' not found. Available agents: {available}")
    return _instances[agent_id].extras


def get_all_agents_info() -> list[AgentInfo]:
    """获取所有已注册 Agent 的信息列表。"""
    return [AgentInfo(key=inst.key, description=inst.description) for inst in _instances.values()]
