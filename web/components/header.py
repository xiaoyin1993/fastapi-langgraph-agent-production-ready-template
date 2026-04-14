from nicegui import ui

from services.api_client import ApiError, api_client
from state.auth import auth_state
from theme import ACCENT, BG_CARD, BORDER, TEXT_PRIMARY, TEXT_SECONDARY


def render_header(on_agent_change=None):
    """顶栏：应用名 + Agent 选择器 + 用户邮箱 + 退出

    Args:
        on_agent_change: Agent 切换时的回调函数。
    """
    with ui.header().classes("items-center justify-between px-6").style(
        f"background-color: {BG_CARD}; border-bottom: 1px solid {BORDER}; height: 56px;"
    ):
        with ui.row().classes("items-center gap-4"):
            ui.label("AI 智能助手").classes("text-lg font-bold").style(f"color: {ACCENT};")

            # Agent 选择器
            agent_select = ui.select(
                options=[],
                value=None,
                on_change=lambda e: _on_agent_select(e.value, on_agent_change),
            ).props(
                'outlined dense options-dense hide-bottom-space'
            ).classes("agent-select").style(
                f"min-width: 160px; color: {TEXT_PRIMARY};"
            ).tooltip("选择 Agent")

            # 存储 select 引用以便后续更新
            ui.context.client.agent_select = agent_select

        with ui.row().classes("items-center gap-3"):
            email = auth_state.get_user_email() or ""
            ui.label(email).classes("text-sm").style(f"color: {TEXT_SECONDARY};")
            ui.button(
                icon="logout",
                on_click=_logout,
            ).props("flat dense round").style(f"color: {TEXT_PRIMARY};").tooltip("退出登录")


async def load_agents():
    """从后端加载 Agent 列表并更新选择器。"""
    session_token = auth_state.get_session_token()
    if not session_token:
        return

    try:
        result = await api_client.list_agents(session_token)
        agents = result.get("agents", [])
        default_agent = result.get("default_agent", "assistant")

        options = {agent["key"]: agent["description"] for agent in agents}

        agent_select = getattr(ui.context.client, "agent_select", None)
        if agent_select:
            agent_select.options = options
            # 恢复之前选择的 agent，或用默认值
            saved = auth_state.get_selected_agent()
            if saved and saved in options:
                agent_select.value = saved
            else:
                agent_select.value = default_agent
                auth_state.set_selected_agent(default_agent)
            agent_select.update()
    except ApiError:
        pass


def _on_agent_select(agent_key: str, callback=None):
    """Agent 切换处理。"""
    if agent_key:
        auth_state.set_selected_agent(agent_key)
        if callback:
            callback(agent_key)


async def _logout():
    auth_state.logout()
    ui.navigate.to("/")
