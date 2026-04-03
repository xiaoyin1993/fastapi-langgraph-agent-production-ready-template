---
name: Claude Code 源码架构总览
description: Claude Code CLI 工具的完整架构分析，包括目录结构、核心流程、工具系统、权限模型等
type: reference
---

源码路径：`/Users/xiaoyin/Downloads/claude-code-main/src`

## 技术栈

TypeScript/Node.js，React Ink（终端 UI），Zod（Schema 校验），Zustand 风格状态管理，Commander.js（CLI 解析），MCP（工具集成），@anthropic-ai/sdk（Claude API）

## 顶层目录结构

```
src/
├── main.tsx              # 入口，启动性能分析
├── QueryEngine.ts        # 核心 AI 交互编排（1295 行）
├── query.ts              # 主查询/对话循环（1729 行）
├── Tool.ts               # 工具系统类型定义（792 行）
├── commands.ts           # CLI 命令注册（754 行）
├── Task.ts               # 后台任务系统
├── entrypoints/          # 入口变体（CLI、SDK）
├── commands/             # 100+ CLI 命令
├── tools/                # 45+ 工具（BashTool、FileEditTool、AgentTool 等）
├── tasks/                # 后台任务实现
├── state/                # 状态管理（AppState、AppStateStore）
├── context/              # React Context Providers
├── hooks/                # React Hooks（87 个文件）
├── services/             # 业务逻辑层
│   ├── api/              # API 交互与流式处理
│   ├── analytics/        # 遥测与 GrowthBook
│   ├── mcp/              # Model Context Protocol 客户端
│   ├── tools/            # 工具执行（StreamingToolExecutor）
│   ├── compact/          # 消息压缩策略
│   └── plugins/          # 插件管理
├── utils/                # 200+ 工具模块
├── components/           # React 组件（146 个目录）
├── skills/               # Skill 系统
├── plugins/              # 插件系统
├── bridge/               # REPL 桥接
└── ink/                  # 终端 UI
```

## 核心请求流程

```
用户输入 → processUserInput()
  → QueryEngine.query()
    → getSystemPrompt() + prepareMessages()
    → queryModelWithStreaming()（调用 Claude API）
    → StreamingToolExecutor（权限检查 + 执行工具）
    → 必要时压缩消息
    → 继续循环或终止
```
