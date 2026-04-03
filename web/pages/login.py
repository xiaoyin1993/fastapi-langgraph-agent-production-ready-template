from nicegui import ui

from services.api_client import ApiError, api_client
from state.auth import auth_state
from theme import ACCENT, BG_CARD, BG_PAGE, BORDER, TEXT_PRIMARY, TEXT_SECONDARY, apply_theme


@ui.page("/")
async def login_page():
    # 已登录则跳转聊天页
    if auth_state.is_logged_in():
        ui.navigate.to("/chat")
        return

    apply_theme()

    # 居中布局
    with ui.column().classes("absolute-center items-center"):
        with ui.card().classes("w-96 p-0").style(
            f"background-color: {BG_CARD}; border: 1px solid {BORDER}; border-radius: 12px;"
        ):
            # 标题
            with ui.column().classes("w-full items-center pt-8 pb-4"):
                ui.icon("smart_toy", size="48px").style(f"color: {ACCENT};")
                ui.label("AI 智能助手").classes("text-xl font-bold mt-2").style(
                    f"color: {TEXT_PRIMARY};"
                )
                ui.label("登录后开始对话").classes("text-sm mt-1").style(
                    f"color: {TEXT_SECONDARY};"
                )

            # Tab 切换
            with ui.tabs().classes("w-full").props("dense") as tabs:
                login_tab = ui.tab("登录").style(f"color: {TEXT_PRIMARY};")
                register_tab = ui.tab("注册").style(f"color: {TEXT_PRIMARY};")

            with ui.tab_panels(tabs, value=login_tab).classes("w-full").style(
                f"background-color: {BG_CARD};"
            ):
                # 登录面板
                with ui.tab_panel(login_tab).classes("px-6 pb-6"):
                    login_email = ui.input("邮箱").classes("w-full").props(
                        'outlined dense type="email"'
                    )
                    login_password = ui.input("密码").classes("w-full mt-3").props(
                        "outlined dense type=password"
                    )
                    login_btn = ui.button("登 录", on_click=lambda: _login(login_email, login_password, login_btn)).classes(
                        "w-full mt-4"
                    ).style(
                        f"background-color: {ACCENT} !important; color: white; border-radius: 8px;"
                    )

                # 注册面板
                with ui.tab_panel(register_tab).classes("px-6 pb-6"):
                    reg_email = ui.input("邮箱").classes("w-full").props(
                        'outlined dense type="email"'
                    )
                    reg_password = ui.input("密码").classes("w-full mt-3").props(
                        "outlined dense type=password"
                    )
                    ui.label(
                        "至少 8 位，需包含大写、小写、数字和特殊字符"
                    ).classes("text-xs mt-1").style(f"color: {TEXT_SECONDARY};")
                    reg_btn = ui.button("注 册", on_click=lambda: _register(reg_email, reg_password, reg_btn)).classes(
                        "w-full mt-4"
                    ).style(
                        f"background-color: {ACCENT} !important; color: white; border-radius: 8px;"
                    )


async def _login(email_input, password_input, btn):
    email = email_input.value.strip()
    password = password_input.value.strip()
    if not email or not password:
        ui.notify("请填写所有字段", type="warning")
        return

    btn.disable()
    try:
        result = await api_client.login(email, password)
        token = result.get("access_token", "")
        auth_state.set_user(email, token)
        ui.notify("登录成功！", type="positive")
        ui.navigate.to("/chat")
    except ApiError as e:
        ui.notify(f"登录失败：{e.detail}", type="negative")
    finally:
        btn.enable()


async def _register(email_input, password_input, btn):
    email = email_input.value.strip()
    password = password_input.value.strip()
    if not email or not password:
        ui.notify("请填写所有字段", type="warning")
        return

    btn.disable()
    try:
        result = await api_client.register(email, password)
        token = result.get("token", {}).get("access_token", "")
        auth_state.set_user(email, token)
        ui.notify("注册成功！", type="positive")
        ui.navigate.to("/chat")
    except ApiError as e:
        ui.notify(f"注册失败：{e.detail}", type="negative")
    finally:
        btn.enable()
