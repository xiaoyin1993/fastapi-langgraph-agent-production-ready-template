from nicegui import ui

import config

# 注册页面
import pages.login  # noqa: F401
import pages.chat  # noqa: F401

ui.run(
    title="AI 智能助手",
    port=8080,
    dark=True,
    reload=True,
    storage_secret=config.STORAGE_SECRET,
    favicon="🤖",
)
