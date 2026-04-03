from nicegui import ui

from theme import TEXT_SECONDARY


class MessageList:
    def __init__(self):
        self.scroll_area = None
        self.container = None

    def render(self) -> ui.scroll_area:
        self.scroll_area = ui.scroll_area().classes("flex-grow w-full")
        with self.scroll_area:
            self.container = ui.column().classes("w-full gap-3 p-4")
        return self.scroll_area

    def clear(self):
        if self.container:
            self.container.clear()

    def _user_html(self, content: str) -> str:
        return (
            f'<div style="display:flex;justify-content:flex-end;">'
            f'<div class="user-bubble">{_escape(content)}</div>'
            f'</div>'
        )

    def _assistant_html(self, content: str) -> str:
        return (
            f'<div style="display:flex;justify-content:flex-start;">'
            f'<div class="assistant-bubble">{content}</div>'
            f'</div>'
        )

    def add_user_message(self, content: str):
        if not self.container:
            return
        with self.container:
            ui.html(self._user_html(content)).style("width:100%;overflow:hidden;")
        self._scroll_to_bottom()

    def add_assistant_message(self, content: str = "") -> ui.html:
        """添加助手消息气泡，返回 html 元素以便流式更新"""
        if not self.container:
            return None
        with self.container:
            bubble = ui.html(self._assistant_html(content)).style("width:100%;overflow:hidden;")
        self._scroll_to_bottom()
        return bubble

    def update_assistant_message(self, bubble: ui.html, content: str):
        """更新助手消息内容（用于流式）"""
        if bubble:
            bubble.set_content(self._assistant_html(content))
            self._scroll_to_bottom()

    def load_history(self, messages: list[dict]):
        """加载历史消息"""
        self.clear()
        if not self.container:
            return
        with self.container:
            if not messages:
                with ui.column().classes("w-full items-center py-16"):
                    ui.icon("chat", size="64px").style(f"color: {TEXT_SECONDARY}; opacity: 0.3;")
                    ui.label("开始对话吧").classes("text-lg mt-4").style(
                        f"color: {TEXT_SECONDARY};"
                    )
                return

            for msg in messages:
                role = msg.get("role", "")
                content = msg.get("content", "")
                if role == "user":
                    ui.html(self._user_html(content)).style("width:100%;overflow:hidden;")
                elif role == "assistant":
                    ui.html(self._assistant_html(content)).style("width:100%;overflow:hidden;")
        self._scroll_to_bottom()

    def show_typing(self) -> ui.html:
        """显示输入中动画"""
        if not self.container:
            return None
        with self.container:
            typing_el = ui.html(
                '<div style="display:flex;justify-content:flex-start;">'
                '<div class="assistant-bubble" style="padding: 12px 20px;">'
                '<div style="display:flex;gap:4px;align-items:center;">'
                '<span class="typing-dot" style="animation:blink 1.4s infinite both;animation-delay:0s;"></span>'
                '<span class="typing-dot" style="animation:blink 1.4s infinite both;animation-delay:0.2s;"></span>'
                '<span class="typing-dot" style="animation:blink 1.4s infinite both;animation-delay:0.4s;"></span>'
                '</div></div></div>'
            ).style("width:100%;")
            ui.add_head_html("""
            <style>
                .typing-dot {
                    width: 8px; height: 8px; border-radius: 50%;
                    background-color: #8b949e; display: inline-block;
                }
                @keyframes blink {
                    0%, 80%, 100% { opacity: 0.3; }
                    40% { opacity: 1; }
                }
            </style>
            """)
        self._scroll_to_bottom()
        return typing_el

    def remove_typing(self, typing_el):
        if typing_el and self.container:
            try:
                self.container.remove(typing_el)
            except Exception:
                pass

    def _scroll_to_bottom(self):
        if self.scroll_area:
            self.scroll_area.scroll_to(percent=1.0)


def _escape(text: str) -> str:
    """基本 HTML 转义，保留换行（由 CSS white-space: pre-wrap 处理）"""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
