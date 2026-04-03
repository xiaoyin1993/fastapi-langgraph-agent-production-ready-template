---
name: Claude Code Agent/子Agent 系统
description: Claude Code 的 Agent 生命周期、类型、上下文隔离和扩展点设计
type: reference
---

源码路径：`/Users/xiaoyin/Downloads/claude-code-main/src`

## Agent 类型

1. **LocalAgentTask** — 主进程内运行
2. **RemoteAgentTask** — 远程执行器上运行
3. **InProcessTeammateTask** — 共享内存、并发执行
4. **DreamTask** — 后台推测性执行

## Agent 生命周期（`tools/AgentTool/runAgent.ts`）

```
AgentTool.call()
  ├─ 校验 Agent 配置
  ├─ 解析目标 + 系统提示词
  ├─ 创建隔离上下文
  │  └─ 过滤工具列表（CUSTOM_AGENT_DISALLOWED_TOOLS）
  │  └─ 设置 Agent ID + 类型
  ├─ 启动任务（Local/Remote/InProcess）
  ├─ 流式接收 Agent 消息
  ├─ 处理 Agent 的工具调用
  ├─ 发射进度更新
  └─ 收集最终结果
```

## Agent 定义

```typescript
type AgentDefinition = {
  name: string
  description: string
  objectives: string[]
  systemPrompt?: string
  model?: string
  maxTurns?: number
  allowedTools?: string[]
  isBuiltIn?: boolean
}
```

Agent 加载来源：
- 内置：`src/tools/AgentTool/built-in/`
- 用户自定义：`~/.claude/agents/`
- 项目级别：`.claude/agents/`

## 上下文隔离

每个 Agent 获得独立的：
- 工作目录（可选不同）
- 过滤后的工具列表
- 过滤后的命令列表
- Agent ID 标签（用于遥测）
- 权限模式（通常更严格）
- 克隆的 AppState
- 可选的记忆快照
