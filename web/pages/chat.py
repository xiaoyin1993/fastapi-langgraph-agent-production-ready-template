import markdown

from nicegui import ui

from components.chat_input import ChatInput
from components.header import render_header
from components.message_list import MessageList
from components.session_sidebar import SessionSidebar
from services.api_client import ApiError, AuthenticationError, api_client
from services.sse_client import stream_chat
from state.auth import auth_state
from theme import BG_PAGE, TEXT_SECONDARY, apply_theme


@ui.page("/chat")
async def chat_page():
    # 未登录则跳回登录页
    if not auth_state.is_logged_in():
        ui.navigate.to("/")
        return

    apply_theme()

    # 组件实例
    message_list = MessageList()
    sidebar = SessionSidebar(on_session_select=lambda: _on_session_select(message_list))
    chat_input = ChatInput(on_send=lambda text: _on_send(text, message_list, chat_input))

    # 布局
    render_header()

    with ui.row().classes("w-full flex-grow no-wrap").style(
        f"height: calc(100vh - 56px); background-color: {BG_PAGE};"
    ):
        # 左侧边栏
        with ui.column().classes("h-full").style("width: 260px; min-width: 260px; flex-shrink: 0;"):
            sidebar.render()

        # 右侧聊天区
        with ui.column().classes("flex-grow h-full no-wrap"):
            message_list.render()
            chat_input.render()

    # 初始化加载
    await sidebar.load_sessions()

    # 如果有当前会话，加载消息
    if auth_state.has_session():
        await _load_messages(message_list)
    else:
        # 没有会话，自动创建一个
        user_token = auth_state.get_user_token()
        if user_token:
            try:
                sessions = await api_client.list_sessions(user_token)
                if sessions:
                    first = sessions[0]
                    auth_state.set_session(
                        first["session_id"],
                        first.get("name", "") or "新对话",
                        first.get("token", {}).get("access_token", ""),
                    )
                else:
                    result = await api_client.create_session(user_token)
                    auth_state.set_session(
                        result["session_id"],
                        result.get("name", "") or "新对话",
                        result.get("token", {}).get("access_token", ""),
                    )
                await sidebar.load_sessions()
                await _load_messages(message_list)
            except AuthenticationError:
                auth_state.logout()
                ui.navigate.to("/")
            except ApiError as e:
                ui.notify(f"初始化失败：{e.detail}", type="negative")


async def _on_session_select(message_list: MessageList):
    """切换会话时加载消息"""
    await _load_messages(message_list)


async def _load_messages(message_list: MessageList):
    """加载当前会话的消息历史"""
    session_token = auth_state.get_session_token()
    if not session_token:
        message_list.clear()
        return
    try:
        result = await api_client.get_messages(session_token)
        messages = result.get("messages", [])
        message_list.load_history(messages)
    except AuthenticationError:
        auth_state.logout()
        ui.navigate.to("/")
    except ApiError as e:
        ui.notify(f"加载消息失败：{e.detail}", type="negative")


async def _on_send(text: str, message_list: MessageList, chat_input: ChatInput):
    """发送消息并处理流式回复"""
    session_token = auth_state.get_session_token()
    if not session_token:
        ui.notify("没有活跃的会话，请先创建一个。", type="warning")
        return

    # 显示用户消息
    message_list.add_user_message(text)

    # 禁用输入
    chat_input.disable()

    # 显示 typing 动画
    typing_row = message_list.show_typing()

    try:
        # 构造消息列表
        messages = [{"role": "user", "content": text}]

        # 创建助手气泡（先移除 typing）
        full_content = ""
        bubble = None

        async for chunk in stream_chat(messages, session_token):
            if typing_row:
                message_list.remove_typing(typing_row)
                typing_row = None
                bubble = message_list.add_assistant_message("")

            full_content += chunk
            if bubble:
                # 渲染 Markdown
                html_content = markdown.markdown(
                    full_content,
                    extensions=["fenced_code", "codehilite", "tables"],
                )
                message_list.update_assistant_message(bubble, html_content)

        # 流结束后确保 typing 移除
        if typing_row:
            message_list.remove_typing(typing_row)
            typing_row = None

        # 如果没收到任何内容
        if not full_content and not bubble:
            message_list.add_assistant_message(
                '<span style="color: #8b949e; font-style: italic;">未收到回复</span>'
            )

    except AuthenticationError:
        if typing_row:
            message_list.remove_typing(typing_row)
        auth_state.logout()
        ui.navigate.to("/")
        return
    except Exception as e:
        if typing_row:
            message_list.remove_typing(typing_row)
        ui.notify(f"错误：{e}", type="negative")
        message_list.add_assistant_message(
            f'<span style="color: #f85149;">出错了：{e}</span>'
        )
    finally:
        chat_input.enable()
