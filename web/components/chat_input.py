from nicegui import ui

from theme import ACCENT, BG_CARD, BORDER, TEXT_PRIMARY


class ChatInput:
    def __init__(self, on_send):
        self.on_send = on_send
        self.input_field = None
        self.send_btn = None
        self.stop_btn = None
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
            self.stop_btn = (
                ui.button(icon="stop", on_click=self._on_stop_click)
                .props("round dense")
                .style("background-color: #da3633 !important; color: white;")
            )
            self.stop_btn.set_visibility(False)

        self._stop_callback = None

    async def _handle_enter(self, e):
        """Enter 发送，Shift+Enter 换行"""
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

    def _on_stop_click(self):
        if self._stop_callback:
            self._stop_callback()

    def show_stop(self, on_stop):
        """流式生成中：隐藏发送按钮，显示停止按钮"""
        self._stop_callback = on_stop
        if self.send_btn:
            self.send_btn.set_visibility(False)
        if self.stop_btn:
            self.stop_btn.set_visibility(True)

    def show_send(self):
        """流式结束：隐藏停止按钮，显示发送按钮"""
        self._stop_callback = None
        if self.stop_btn:
            self.stop_btn.set_visibility(False)
        if self.send_btn:
            self.send_btn.set_visibility(True)

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
