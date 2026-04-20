import base64
import markdown as md
from nicegui import ui

from theme import ACCENT, TEXT_SECONDARY


def _b64(text: str) -> str:
    return base64.b64encode(text.encode()).decode()


# 流式生成指示器的 CSS（只注入一次）
_STREAM_CSS = (
    "<style>"
    ".thinking-indicator {"
    "    display: flex; align-items: center; gap: 6px;"
    "    padding: 4px 0;"
    "}"
    ".thinking-indicator .pulse-ring {"
    "    width: 8px; height: 8px; border-radius: 50%;"
    f"    background: {ACCENT};"
    "    animation: pulse-ring 1.2s cubic-bezier(.4,0,.6,1) infinite;"
    "}"
    ".thinking-indicator .pulse-ring:nth-child(2) { animation-delay: .15s; }"
    ".thinking-indicator .pulse-ring:nth-child(3) { animation-delay: .3s; }"
    ".thinking-indicator .thinking-text {"
    f"    font-size: 13px; color: {TEXT_SECONDARY};"
    "    animation: fade-pulse 1.6s ease-in-out infinite;"
    "}"
    "@keyframes pulse-ring {"
    "    0%,100% { transform: scale(.7); opacity:.35; }"
    "    50% { transform: scale(1); opacity:1; }"
    "}"
    "@keyframes fade-pulse {"
    "    0%,100% { opacity:.5; }"
    "    50% { opacity:1; }"
    "}"
    ".streaming-cursor::after {"
    "    content: '';"
    "    display: inline-block;"
    "    width: 2px; height: 1em;"
    f"    background: {ACCENT};"
    "    margin-left: 2px;"
    "    vertical-align: text-bottom;"
    "    animation: cursor-blink .6s steps(2) infinite;"
    "}"
    "@keyframes cursor-blink {"
    "    0% { opacity: 1; }"
    "    50% { opacity: 0; }"
    "}"
    ".done-indicator {"
    "    display: flex; align-items: center; gap: 4px;"
    "    padding: 4px 0 0 0;"
    "    animation: done-show .5s ease-out forwards;"
    "}"
    ".done-indicator svg {"
    "    width: 10px; height: 10px;"
    "}"
    ".done-indicator span {"
    f"    font-size: 11px; color: {TEXT_SECONDARY};"
    "}"
    "@keyframes done-show {"
    "    0%   { opacity:0; transform: translateY(4px); }"
    "    100% { opacity:1; transform: translateY(0); }"
    "}"
    "</style>"
)

_COPY_BTN_JS = """
<script>
window.__addCopyBtns = function() {
    document.querySelectorAll('.assistant-bubble pre').forEach(function(pre) {
        if (pre.querySelector('.code-copy-btn')) return;
        var btn = document.createElement('button');
        btn.className = 'code-copy-btn';
        btn.innerHTML = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1"/></svg><span>复制</span>';
        btn.onclick = function() {
            var code = pre.querySelector('code');
            var text = code ? code.textContent : pre.textContent;
            navigator.clipboard.writeText(text).then(function() {
                btn.classList.add('copied');
                btn.querySelector('span').textContent = '已复制';
                setTimeout(function() {
                    btn.classList.remove('copied');
                    btn.querySelector('span').textContent = '复制';
                }, 1500);
            });
        };
        pre.appendChild(btn);
    });
};
window.__addMsgCopyBtns = function() {
    document.querySelectorAll('.assistant-bubble, .user-bubble').forEach(function(bubble) {
        var wrapper = bubble.closest('.msg-wrapper');
        if (!wrapper || wrapper.querySelector('.msg-copy-btn')) return;
        var btn = document.createElement('button');
        btn.className = 'msg-copy-btn';
        btn.innerHTML = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1"/></svg>';
        btn.onclick = function(e) {
            e.stopPropagation();
            var raw = wrapper.getAttribute('data-raw');
            var text;
            if (raw) {
                try { text = decodeURIComponent(escape(atob(raw))); } catch(ex) { text = atob(raw); }
            } else {
                text = bubble.textContent || bubble.innerText;
            }
            navigator.clipboard.writeText(text.trim()).then(function() {
                btn.classList.add('copied');
                setTimeout(function() { btn.classList.remove('copied'); }, 1500);
            });
        };
        wrapper.appendChild(btn);
    });
};
</script>
"""

def _ensure_css():
    ui.add_head_html(_STREAM_CSS)
    ui.add_head_html(_COPY_BTN_JS)


class MessageList:
    def __init__(self):
        self.scroll_area = None
        self.container = None
        self._scroll_id = None  # scroll 容器的 DOM id

    def render(self) -> ui.scroll_area:
        _ensure_css()
        self.scroll_area = ui.scroll_area().classes("flex-grow w-full")
        self._scroll_id = f"c{self.scroll_area.id}"
        with self.scroll_area:
            self.container = ui.column().classes("w-full gap-3 p-4")

        # 注入全局 JS：监听滚动事件，维护 window.__chatPinned 状态
        ui.run_javascript(f'''(() => {{
            window.__chatPinned = false;
            // 延迟绑定，等 DOM 渲染完成
            setTimeout(() => {{
                const sa = document.getElementById("{self._scroll_id}");
                const el = sa && sa.querySelector(".q-scrollarea__container");
                if (!el) return;
                el.addEventListener("scroll", () => {{
                    const atBottom = (el.scrollHeight - el.scrollTop - el.clientHeight) < 50;
                    window.__chatPinned = !atBottom;
                }});
            }}, 300);
        }})()''')

        return self.scroll_area

    def clear(self):
        if self.container:
            self.container.clear()

    def _user_html(self, content: str) -> str:
        raw = _b64(content)
        return (
            f'<div class="msg-wrapper" style="display:flex;justify-content:flex-end;position:relative;" data-raw="{raw}">'
            f'<div class="user-bubble">{_escape(content)}</div>'
            f'</div>'
        )

    @staticmethod
    def _assistant_html(content: str, streaming: bool = False, raw_md: str = "") -> str:
        cursor_cls = ' streaming-cursor' if streaming else ''
        raw_attr = f' data-raw="{_b64(raw_md)}"' if raw_md else ''
        return (
            f'<div class="msg-wrapper" style="display:flex;justify-content:flex-start;position:relative;"{raw_attr}>'
            f'<div class="assistant-bubble{cursor_cls}">{content}</div>'
            f'</div>'
        )

    def add_user_message(self, content: str):
        if not self.container:
            return
        with self.container:
            ui.html(self._user_html(content)).style("width:100%;overflow:hidden;")
        self._scroll_to_bottom()
        self._inject_copy_buttons()

    def add_assistant_message(self, content: str = "", streaming: bool = False, raw_md: str = "") -> ui.html:
        """添加助手消息气泡，返回 html 元素以便流式更新"""
        if not self.container:
            return None
        with self.container:
            bubble = ui.html(self._assistant_html(content, streaming=streaming, raw_md=raw_md)).style(
                "width:100%;overflow:hidden;"
            )
        self._scroll_to_bottom()
        return bubble

    def update_assistant_message(self, bubble: ui.html, content: str, streaming: bool = False, raw_md: str = ""):
        """更新助手消息内容（用于流式）"""
        if bubble:
            try:
                bubble.set_content(self._assistant_html(content, streaming=streaming, raw_md=raw_md))
                self._scroll_to_bottom()
            except RuntimeError:
                pass

    def finalize_assistant_message(self, bubble: ui.html, content: str, raw_md: str = ""):
        """流式结束：移除光标，追加完成标记。"""
        if not bubble:
            return
        done_mark = (
            '<div class="done-indicator">'
            f'<svg viewBox="0 0 16 16" fill="{ACCENT}" width="10" height="10" style="width:10px;height:10px;min-width:10px;">'
            '<path d="M13.78 4.22a.75.75 0 010 1.06l-7.25 7.25a.75.75 0 01-1.06 0'
            'L2.22 9.28a.75.75 0 011.06-1.06L6 10.94l6.72-6.72a.75.75 0 011.06 0z"/>'
            '</svg>'
            '<span>已完成</span>'
            '</div>'
        )
        try:
            bubble.set_content(self._assistant_html(content, streaming=False, raw_md=raw_md) + done_mark)
            self._scroll_to_bottom()
            self._inject_copy_buttons()
        except RuntimeError:
            pass

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
                    html_content = md.markdown(
                        content,
                        extensions=["fenced_code", "codehilite", "tables"],
                    )
                    ui.html(self._assistant_html(html_content, raw_md=content)).style("width:100%;overflow:hidden;")
        self._force_scroll_to_bottom()
        self._inject_copy_buttons()

    def show_typing(self) -> ui.html:
        """显示「思考中」指示器"""
        if not self.container:
            return None
        with self.container:
            typing_el = ui.html(
                '<div style="display:flex;justify-content:flex-start;">'
                '<div class="assistant-bubble" style="padding: 12px 20px;">'
                '<div class="thinking-indicator">'
                '<span class="pulse-ring"></span>'
                '<span class="pulse-ring"></span>'
                '<span class="pulse-ring"></span>'
                '<span class="thinking-text">思考中...</span>'
                '</div></div></div>'
            ).style("width:100%;")
        self._scroll_to_bottom()
        return typing_el

    def remove_typing(self, typing_el):
        if typing_el and self.container:
            try:
                self.container.remove(typing_el)
            except Exception:
                pass

    def _scroll_to_bottom(self):
        """仅在用户没有手动上滚时滚到底部。"""
        if not self._scroll_id:
            return
        try:
            ui.run_javascript(f'''(() => {{
                if (window.__chatPinned) return;
                const sa = document.getElementById("{self._scroll_id}");
                const el = sa && sa.querySelector(".q-scrollarea__container");
                if (el) el.scrollTop = el.scrollHeight;
            }})()''')
        except RuntimeError:
            pass

    def _force_scroll_to_bottom(self):
        """强制滚到底部（加载历史、发新消息时）。"""
        if not self._scroll_id:
            return
        try:
            ui.run_javascript(f'''(() => {{
                window.__chatPinned = false;
                const sa = document.getElementById("{self._scroll_id}");
                const el = sa && sa.querySelector(".q-scrollarea__container");
                if (el) el.scrollTop = el.scrollHeight;
            }})()''')
        except RuntimeError:
            pass

    def reset_auto_scroll(self):
        """发送新消息时重置并强制滚到底部。"""
        self._force_scroll_to_bottom()

    def _inject_copy_buttons(self):
        try:
            ui.run_javascript(
                "setTimeout(function(){ "
                "if(window.__addCopyBtns) window.__addCopyBtns(); "
                "if(window.__addMsgCopyBtns) window.__addMsgCopyBtns(); "
                "}, 50);"
            )
        except RuntimeError:
            pass


def _escape(text: str) -> str:
    """基本 HTML 转义，保留换行（由 CSS white-space: pre-wrap 处理）"""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
