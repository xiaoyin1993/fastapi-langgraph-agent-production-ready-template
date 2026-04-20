import asyncio

import markdown
from nicegui import ui

from components.chat_input import ChatInput
from components.header import load_agents, render_header
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

    # 每个页面实例独立的流式状态
    # gen: 代际计数器，切换会话时递增，旧流式循环检测到后跳过 UI 更新
    page_state = {"stream_task": None, "gen": 0}

    # 组件实例
    message_list = MessageList()
    sidebar = SessionSidebar(
        on_session_select=lambda: _on_session_select(message_list, chat_input, page_state)
    )
    chat_input = ChatInput(
        on_send=lambda text: _on_send(text, message_list, chat_input, page_state)
    )

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
        await load_agents()
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
                await load_agents()
            except AuthenticationError:
                auth_state.logout()
                ui.navigate.to("/")
            except ApiError as e:
                ui.notify(f"初始化失败：{e.detail}", type="negative")


async def _on_session_select(message_list: MessageList, chat_input: ChatInput, page_state: dict):
    """切换会话：脱离当前流式（后台继续跑让后端保存），加载新会话消息。"""
    task = page_state.get("stream_task")
    if task and not task.done():
        # 递增代际 → 旧 _consume 检测到后跳过 UI 更新，但继续消费流
        page_state["gen"] += 1
        page_state["stream_task"] = None
        try:
            chat_input.show_send()
            chat_input.enable()
        except RuntimeError:
            pass
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
    except RuntimeError:
        pass
    except AuthenticationError:
        auth_state.logout()
        ui.navigate.to("/")
    except ApiError as e:
        try:
            ui.notify(f"加载消息失败：{e.detail}", type="negative")
        except RuntimeError:
            pass


async def _on_send(text: str, message_list: MessageList, chat_input: ChatInput, page_state: dict):
    """发送消息并处理流式回复"""
    session_token = auth_state.get_session_token()
    if not session_token:
        ui.notify("没有活跃的会话，请先创建一个。", type="warning")
        return

    origin_session_id = auth_state.get_session_id()
    agent_id = auth_state.get_selected_agent()

    # 递增代际，使旧流式脱离 UI
    page_state["gen"] += 1
    my_gen = page_state["gen"]

    message_list.reset_auto_scroll()
    message_list.add_user_message(text)
    chat_input.disable()

    typing_row = message_list.show_typing()
    full_content = ""
    bubble = None

    async def _consume():
        nonlocal typing_row, full_content, bubble
        async for chunk in stream_chat(
            messages=[{"role": "user", "content": text}],
            session_token=session_token,
            agent_id=agent_id,
        ):
            # 代际不匹配 → 已脱离（会话切换），继续消费流但跳过 UI
            if page_state["gen"] != my_gen:
                continue

            if typing_row:
                message_list.remove_typing(typing_row)
                typing_row = None
                bubble = message_list.add_assistant_message("", streaming=True)

            full_content += chunk
            if bubble:
                html_content = markdown.markdown(
                    full_content,
                    extensions=["fenced_code", "codehilite", "tables"],
                )
                message_list.update_assistant_message(bubble, html_content, streaming=True, raw_md=full_content)

    def on_stop():
        """停止按钮：用 task.cancel() 即时取消流式。"""
        task = page_state.get("stream_task")
        if task and not task.done():
            task.cancel()

    chat_input.show_stop(on_stop)

    cancelled = False
    try:
        task = asyncio.create_task(_consume())
        page_state["stream_task"] = task
        await task
    except asyncio.CancelledError:
        cancelled = True
    except AuthenticationError:
        if typing_row:
            message_list.remove_typing(typing_row)
        auth_state.logout()
        ui.navigate.to("/")
        return
    except RuntimeError:
        return
    except Exception as e:
        if typing_row:
            message_list.remove_typing(typing_row)
        try:
            ui.notify(f"错误：{e}", type="negative")
            message_list.add_assistant_message(
                f'<span style="color: #f85149;">出错了：{e}</span>'
            )
        except RuntimeError:
            pass
        return
    finally:
        # 只在仍是活跃代际时清理 UI 状态
        if page_state["gen"] == my_gen:
            page_state["stream_task"] = None
            try:
                chat_input.show_send()
                chat_input.enable()
            except RuntimeError:
                pass

    # 已脱离（会话切换），不操作 UI
    if page_state["gen"] != my_gen:
        return

    # 清理思考指示器
    if typing_row:
        message_list.remove_typing(typing_row)

    if cancelled:
        # 用户点了停止按钮
        if full_content and bubble:
            html_content = markdown.markdown(
                full_content,
                extensions=["fenced_code", "codehilite", "tables"],
            )
            message_list.finalize_assistant_message(bubble, html_content, raw_md=full_content)
        else:
            message_list.add_assistant_message(
                '<span style="color: #8b949e; font-style: italic;">已停止生成</span>'
            )
    else:
        # 正常完成
        if full_content and bubble:
            html_content = markdown.markdown(
                full_content,
                extensions=["fenced_code", "codehilite", "tables"],
            )
            message_list.finalize_assistant_message(bubble, html_content, raw_md=full_content)
        elif not full_content and not bubble:
            message_list.add_assistant_message(
                '<span style="color: #8b949e; font-style: italic;">未收到回复</span>'
            )
