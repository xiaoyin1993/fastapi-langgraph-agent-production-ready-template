from nicegui import ui

from services.api_client import ApiError, api_client
from state.auth import auth_state
from theme import ACCENT, BG_SIDEBAR, BORDER, TEXT_PRIMARY, TEXT_SECONDARY


class SessionSidebar:
    def __init__(self, on_session_select):
        self.on_session_select = on_session_select
        self.sessions: list[dict] = []
        self.container = None

    def render(self) -> ui.column:
        with ui.column().classes("h-full w-full p-0").style(
            f"background-color: {BG_SIDEBAR}; border-right: 1px solid {BORDER};"
        ) as sidebar:
            # 新建会话按钮
            with ui.row().classes("w-full px-3 pt-3 pb-2"):
                ui.button(
                    "新建对话",
                    icon="add",
                    on_click=self._create_session,
                ).classes("w-full").props("outline dense").style(
                    f"color: {ACCENT}; border-color: {BORDER}; border-radius: 8px;"
                )

            ui.separator().style(f"background-color: {BORDER};")

            # 会话列表容器
            with ui.scroll_area().classes("flex-grow w-full"):
                self.container = ui.column().classes("w-full gap-0 px-2 py-1")

        return sidebar

    async def load_sessions(self):
        """加载会话列表"""
        user_token = auth_state.get_user_token()
        if not user_token:
            return
        try:
            self.sessions = await api_client.list_sessions(user_token)
        except ApiError:
            self.sessions = []
        self._render_session_list()

    def _render_session_list(self):
        if not self.container:
            return
        self.container.clear()
        current_session_id = auth_state.get_session_id()

        with self.container:
            if not self.sessions:
                ui.label("暂无对话").classes("text-sm px-3 py-4 text-center").style(
                    f"color: {TEXT_SECONDARY};"
                )
                return

            for session in self.sessions:
                sid = session.get("session_id", "")
                name = session.get("name", "") or "新对话"
                token = session.get("token", {}).get("access_token", "")
                is_active = sid == current_session_id

                with ui.row().classes(
                    f"w-full items-center session-item {'active' if is_active else ''}"
                ):
                    # 可点击的会话名区域
                    with ui.row().classes("flex-grow items-center overflow-hidden").on(
                        "click", lambda _, s=sid, n=name, t=token: self._select_session(s, n, t)
                    ):
                        ui.icon("chat_bubble_outline", size="18px").style(
                            f"color: {ACCENT if is_active else TEXT_SECONDARY};"
                        )
                        ui.label(name).classes("text-sm truncate ml-2").style(
                            f"color: {TEXT_PRIMARY if is_active else TEXT_SECONDARY};"
                        )
                    # 操作菜单（独立于点击区域，阻止冒泡）
                    menu_btn = ui.button(icon="more_vert").props("flat dense round size=xs").style(
                        f"color: {TEXT_SECONDARY};"
                    )
                    menu_btn.on("click.stop", lambda e: None)
                    with menu_btn:
                        with ui.menu():
                            async def make_rename(s=sid, t=token):
                                await self._rename_dialog(s, t)

                            async def make_delete(s=sid, t=token):
                                await self._delete_dialog(s, t)

                            ui.menu_item("重命名", on_click=make_rename)
                            ui.menu_item("删除", on_click=make_delete)

    async def _select_session(self, session_id: str, name: str, token: str):
        auth_state.set_session(session_id, name, token)
        self._render_session_list()
        if self.on_session_select:
            await self.on_session_select()

    async def _create_session(self):
        user_token = auth_state.get_user_token()
        if not user_token:
            return
        try:
            result = await api_client.create_session(user_token)
            sid = result.get("session_id", "")
            name = result.get("name", "") or "新对话"
            token = result.get("token", {}).get("access_token", "")
            auth_state.set_session(sid, name, token)
            await self.load_sessions()
            if self.on_session_select:
                await self.on_session_select()
        except ApiError as e:
            ui.notify(f"创建会话失败：{e.detail}", type="negative")

    async def _rename_dialog(self, session_id: str, session_token: str):
        with ui.dialog() as dialog, ui.card().style(f"background-color: #1c2128; border: 1px solid {BORDER};"):
            ui.label("重命名会话").classes("text-lg font-bold").style(f"color: {TEXT_PRIMARY};")
            name_input = ui.input("新名称").classes("w-full").props("outlined dense")

            with ui.row().classes("w-full justify-end gap-2 mt-3"):
                ui.button("取消", on_click=dialog.close).props("flat").style(f"color: {TEXT_SECONDARY};")

                async def do_rename():
                    await self._do_rename(dialog, session_id, name_input.value, session_token)

                ui.button(
                    "保存",
                    on_click=do_rename,
                ).style(f"background-color: {ACCENT} !important; color: white;")
        dialog.open()

    async def _do_rename(self, dialog, session_id: str, name: str, session_token: str):
        if not name.strip():
            ui.notify("名称不能为空", type="warning")
            return
        try:
            result = await api_client.rename_session(session_id, name.strip(), session_token)
            # rename 返回新 token，需更新
            new_token = result.get("token", {}).get("access_token", "")
            if auth_state.get_session_id() == session_id and new_token:
                auth_state.set_session(session_id, name.strip(), new_token)
            dialog.close()
            await self.load_sessions()
        except ApiError as e:
            ui.notify(f"重命名失败：{e.detail}", type="negative")

    async def _delete_dialog(self, session_id: str, session_token: str):
        with ui.dialog() as dialog, ui.card().style(f"background-color: #1c2128; border: 1px solid {BORDER};"):
            ui.label("确认删除？").classes("text-lg font-bold").style(f"color: {TEXT_PRIMARY};")
            ui.label("此操作将永久删除该对话记录。").classes("text-sm").style(
                f"color: {TEXT_SECONDARY};"
            )
            with ui.row().classes("w-full justify-end gap-2 mt-3"):
                ui.button("取消", on_click=dialog.close).props("flat").style(f"color: {TEXT_SECONDARY};")

                async def do_delete():
                    await self._do_delete(dialog, session_id, session_token)

                ui.button(
                    "删除",
                    on_click=do_delete,
                ).style("background-color: #da3633 !important; color: white;")
        dialog.open()

    async def _do_delete(self, dialog, session_id: str, session_token: str):
        try:
            await api_client.delete_session(session_id, session_token)
            if auth_state.get_session_id() == session_id:
                auth_state.clear_session()
            dialog.close()
            await self.load_sessions()
            if self.on_session_select:
                await self.on_session_select()
        except ApiError as e:
            ui.notify(f"删除失败：{e.detail}", type="negative")
