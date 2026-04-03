from nicegui import ui

from theme import ACCENT, BG_CARD, BORDER, TEXT_PRIMARY


class ChatInput:
    def __init__(self, on_send):
        self.on_send = on_send
        self.input_field = None
        self.send_btn = None
        self._disabled = False

    def render(self):
        with ui.row().classes("w-full items-end px-4 py-3 gap-2").style(
            f"background-color: {BG_CARD}; border-top: 1px solid {BORDER};"
        ):
            self.input_field = (
                ui.textarea(placeholder="输入消息...")
                .classes("flex-grow chat-input")
                .props("outlined dense autogrow rows=1 maxlength=3000")
                .style(f"color: {TEXT_PRIMARY};")
                .on("keydown.enter.prevent", self._handle_enter)
            )
            self.send_btn = (
                ui.button(icon="send", on_click=self._send)
                .props("round dense")
                .style(f"background-color: {ACCENT} !important; color: white;")
            )

    async def _handle_enter(self, e):
        """Enter 发送，Shift+Enter 换行"""
        # NiceGUI 的 keydown.enter.prevent 已经阻止默认行为
        # 这里直接发送
        await self._send()

    async def _send(self):
        if self._disabled or not self.input_field:
            return
        text = self.input_field.value.strip()
        if not text:
            return
        self.input_field.value = ""
        if self.on_send:
            await self.on_send(text)

    def disable(self):
        self._disabled = True
        if self.input_field:
            self.input_field.disable()
        if self.send_btn:
            self.send_btn.disable()

    def enable(self):
        self._disabled = False
        if self.input_field:
            self.input_field.enable()
        if self.send_btn:
            self.send_btn.enable()
