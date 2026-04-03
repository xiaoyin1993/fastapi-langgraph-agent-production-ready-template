"""这个文件包含 Agent 使用的提示词。"""

import os
from datetime import datetime

from app.infrastructure.config import settings

_PROMPTS_DIR = os.path.dirname(__file__)


def _load_prompt(filename: str, **kwargs) -> str:
    """从文件中加载提示词模板并格式化。"""
    with open(os.path.join(_PROMPTS_DIR, filename), "r") as f:
        return f.read().format(**kwargs)


def load_system_prompt(**kwargs):
    """加载系统提示词。"""
    return _load_prompt(
        "system.md",
        agent_name=settings.PROJECT_NAME + " Agent",
        current_date_and_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        **kwargs,
    )


def load_router_prompt(user_message: str) -> str:
    """加载意图分类提示词。"""
    return _load_prompt("router.md", user_message=user_message)


def load_intent_prompt(intent: str, **kwargs) -> str:
    """根据意图加载对应的提示词。"""
    filename = f"{intent}.md"
    filepath = os.path.join(_PROMPTS_DIR, filename)
    if not os.path.exists(filepath):
        return load_system_prompt(**kwargs)
    return _load_prompt(
        filename,
        agent_name=settings.PROJECT_NAME + " Agent",
        current_date_and_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        **kwargs,
    )
