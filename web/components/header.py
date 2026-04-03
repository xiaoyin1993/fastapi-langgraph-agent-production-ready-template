from nicegui import ui

from state.auth import auth_state
from theme import ACCENT, BG_CARD, BORDER, TEXT_PRIMARY, TEXT_SECONDARY


def render_header():
    """顶栏：应用名 + 用户邮箱 + 退出"""
    with ui.header().classes("items-center justify-between px-6").style(
        f"background-color: {BG_CARD}; border-bottom: 1px solid {BORDER}; height: 56px;"
    ):
        ui.label("AI 智能助手").classes("text-lg font-bold").style(f"color: {ACCENT};")

        with ui.row().classes("items-center gap-3"):
            email = auth_state.get_user_email() or ""
            ui.label(email).classes("text-sm").style(f"color: {TEXT_SECONDARY};")
            ui.button(
                icon="logout",
                on_click=_logout,
            ).props("flat dense round").style(f"color: {TEXT_PRIMARY};").tooltip("退出登录")


async def _logout():
    auth_state.logout()
    ui.navigate.to("/")
