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
            display: inline-block;
            align-self: flex-start;
            font-size: 14px;
            line-height: 1.6;
        }}
        .assistant-bubble h1 {{
            font-size: 1.3em;
            margin: 0.4em 0 0.2em;
        }}
        .assistant-bubble h2 {{
            font-size: 1.15em;
            margin: 0.4em 0 0.2em;
        }}
        .assistant-bubble h3 {{
            font-size: 1.05em;
            margin: 0.3em 0 0.15em;
        }}
        .assistant-bubble h4, .assistant-bubble h5, .assistant-bubble h6 {{
            font-size: 1em;
            margin: 0.3em 0 0.1em;
        }}
        .assistant-bubble p {{
            margin: 0.3em 0;
        }}
        .assistant-bubble ul, .assistant-bubble ol {{
            margin: 0.3em 0;
            padding-left: 1.5em;
        }}
        .assistant-bubble li {{
            margin: 0.15em 0;
        }}
        .assistant-bubble pre {{
            position: relative;
            background-color: #0d1117;
            border: 1px solid {BORDER};
            border-radius: 6px;
            padding: 12px;
            padding-top: 32px;
            overflow-x: auto;
            white-space: pre;
            margin: 0.4em 0;
        }}
        .code-copy-btn {{
            position: absolute;
            top: 4px;
            right: 4px;
            background: transparent;
            border: 1px solid {BORDER};
            border-radius: 4px;
            color: {TEXT_SECONDARY};
            cursor: pointer;
            padding: 2px 6px;
            font-size: 12px;
            line-height: 1.4;
            display: flex;
            align-items: center;
            gap: 4px;
            transition: color 0.15s, border-color 0.15s;
        }}
        .code-copy-btn:hover {{
            color: {TEXT_PRIMARY};
            border-color: {TEXT_SECONDARY};
        }}
        .code-copy-btn.copied {{
            color: #3fb950;
            border-color: #3fb950;
        }}

        /* 消息整体复制按钮 */
        .msg-wrapper {{
            position: relative;
        }}
        .msg-copy-btn {{
            position: absolute;
            bottom: -4px;
            opacity: 0;
            background: {BG_CARD};
            border: 1px solid {BORDER};
            border-radius: 4px;
            color: {TEXT_SECONDARY};
            cursor: pointer;
            padding: 3px 5px;
            font-size: 12px;
            line-height: 1;
            display: flex;
            align-items: center;
            transition: opacity 0.15s, color 0.15s, border-color 0.15s;
        }}
        .msg-wrapper:hover .msg-copy-btn {{
            opacity: 1;
        }}
        .msg-copy-btn:hover {{
            color: {TEXT_PRIMARY};
            border-color: {TEXT_SECONDARY};
        }}
        .msg-copy-btn.copied {{
            color: #3fb950;
            border-color: #3fb950;
            opacity: 1;
        }}
        /* 用户消息：复制按钮在左侧 */
        .msg-wrapper:has(.user-bubble) .msg-copy-btn {{
            right: 0;
        }}
        /* 助手消息：复制按钮在左侧 */
        .msg-wrapper:has(.assistant-bubble) .msg-copy-btn {{
            left: 0;
        }}
        .assistant-bubble code {{
            font-size: 0.85em;
        }}
        .assistant-bubble p > code {{
            background-color: #0d1117;
            padding: 2px 6px;
            border-radius: 4px;
            border: 1px solid {BORDER};
        }}
        .assistant-bubble table {{
            border-collapse: collapse;
            margin: 0.4em 0;
            font-size: 0.9em;
        }}
        .assistant-bubble th, .assistant-bubble td {{
            border: 1px solid {BORDER};
            padding: 4px 8px;
        }}
        .assistant-bubble th {{
            background-color: #0d1117;
        }}
        .assistant-bubble blockquote {{
            border-left: 3px solid {ACCENT};
            margin: 0.3em 0;
            padding: 0.2em 0.8em;
            color: {TEXT_SECONDARY};
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
