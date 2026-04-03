"""这个文件包含 Agent 使用的提示词。"""

import os
from datetime import datetime

from app.infrastructure.config import settings


def load_system_prompt(**kwargs):
    """从文件中加载系统提示词。"""
    with open(os.path.join(os.path.dirname(__file__), "system.md"), "r") as f:
        return f.read().format(
            agent_name=settings.PROJECT_NAME + " Agent",
            current_date_and_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            **kwargs,
        )
