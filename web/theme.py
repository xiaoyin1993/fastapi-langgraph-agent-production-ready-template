from nicegui import ui

# 配色
BG_PAGE = "#0d1117"
BG_CARD = "#161b22"
BG_SIDEBAR = "#161b22"
BG_USER_BUBBLE = "#1f6feb"
BG_ASSISTANT_BUBBLE = "#21262d"
TEXT_PRIMARY = "#e6edf3"
TEXT_SECONDARY = "#8b949e"
ACCENT = "#58a6ff"
BORDER = "#30363d"


def apply_theme():
    """注入全局暗色主题 CSS"""
    ui.add_head_html(f"""
    <style>
        body {{
            background-color: {BG_PAGE} !important;
            color: {TEXT_PRIMARY} !important;
        }}
        /* Quasar 暗色覆盖 */
        .q-page, .q-layout, .q-drawer, .q-header {{
            background-color: {BG_PAGE} !important;
        }}
        .q-card {{
            background-color: {BG_CARD} !important;
            color: {TEXT_PRIMARY} !important;
        }}
        .q-field__control {{
            color: {TEXT_PRIMARY} !important;
        }}
        .q-field__label, .q-field__native, .q-field__input {{
            color: {TEXT_PRIMARY} !important;
        }}
        .q-tab__label {{
            color: {TEXT_SECONDARY} !important;
        }}
        .q-tab--active .q-tab__label {{
            color: {ACCENT} !important;
        }}
        .q-btn {{
            text-transform: none !important;
        }}

        /* 聊天气泡 */
        .user-bubble {{
            background-color: {BG_USER_BUBBLE};
            color: white;
            border-radius: 18px 18px 4px 18px;
            padding: 10px 16px;
            max-width: 70%;
            word-wrap: break-word;
            white-space: pre-wrap;
            display: inline-block;
            align-self: flex-end;
        }}
        .assistant-bubble {{
            background-color: {BG_ASSISTANT_BUBBLE};
            color: {TEXT_PRIMARY};
            border-radius: 18px 18px 18px 4px;
            padding: 10px 16px;
            max-width: 70%;
            word-wrap: break-word;
            white-space: pre-wrap;
            display: inline-block;
            align-self: flex-start;
        }}
        .assistant-bubble pre {{
            background-color: #0d1117;
            border: 1px solid {BORDER};
            border-radius: 6px;
            padding: 12px;
            overflow-x: auto;
        }}
        .assistant-bubble code {{
            font-size: 0.85em;
        }}
        .assistant-bubble p {{
            margin: 0.3em 0;
        }}

        /* 侧边栏会话项 */
        .session-item {{
            padding: 10px 14px;
            border-radius: 8px;
            cursor: pointer;
            transition: background-color 0.15s;
            color: {TEXT_SECONDARY};
        }}
        .session-item:hover {{
            background-color: #21262d;
        }}
        .session-item.active {{
            background-color: #1f2937;
            color: {TEXT_PRIMARY};
        }}

        /* 滚动条 */
        ::-webkit-scrollbar {{
            width: 6px;
        }}
        ::-webkit-scrollbar-track {{
            background: transparent;
        }}
        ::-webkit-scrollbar-thumb {{
            background: {BORDER};
            border-radius: 3px;
        }}
        ::-webkit-scrollbar-thumb:hover {{
            background: {TEXT_SECONDARY};
        }}

        /* Agent 选择器 */
        .agent-select .q-field__control {{
            background-color: {BG_PAGE} !important;
            border: 1px solid {BORDER};
            border-radius: 8px;
            min-height: 32px !important;
            padding: 0 8px;
        }}
        .agent-select .q-field__native {{
            color: {TEXT_PRIMARY} !important;
            font-size: 0.85em;
            padding: 0 !important;
            min-height: 32px !important;
        }}
        .agent-select .q-field__append {{
            color: {TEXT_SECONDARY} !important;
        }}
        .agent-select .q-field__control:focus-within {{
            border-color: {ACCENT};
        }}

        /* 消息列表 */
        .message-container {{
            display: flex;
            flex-direction: column;
            gap: 12px;
            padding: 16px;
        }}

        /* 输入框 */
        .chat-input .q-field__control {{
            background-color: {BG_CARD} !important;
            border: 1px solid {BORDER};
            border-radius: 12px;
        }}
        .chat-input .q-field__control:focus-within {{
            border-color: {ACCENT};
        }}
    </style>
    """)
