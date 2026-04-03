---
name: Claude Code 核心设计模式
description: Claude Code 源码中使用的关键设计模式，可作为 Agent 应用架构参考
type: reference
---

源码路径：`/Users/xiaoyin/Downloads/claude-code-main/src`

## 1. 类型驱动架构

大量使用 discriminated union 和泛型：
- `Tool<Input, Output, ProgressData>` — 多态工具接口
- `Message = UserMessage | AssistantMessage | SystemMessage | ...` — 消息类型
- 编译器在编译时捕获错误，代码自文档化

## 2. 依赖注入 via Context

所有函数接收 `ToolUseContext` 对象：
```typescript
type ToolUseContext = {
  getAppState: () => AppState
  setAppState: (f: (prev) => AppState) => void
  options: { tools, agents, commands, ... }
}
```
易于测试（注入 mock）、松耦合、无全局状态

## 3. 流式 + 异步生成器

查询循环使用 `async function*`：
```typescript
async function* query(config): AsyncGenerator<Message | ProgressMessage> {
  yield startMessage
  for await (const chunk of response) { yield progress }
  for (const tool of tools) { yield await executeTool(tool) }
  yield finalMessage
}
```
支持背压控制、渐进渲染、内存高效

## 4. 懒加载 + Feature Gate

构建时死代码消除：
```typescript
const tool = feature('KAIROS') ? require('./path.js') : null
```
按需加载保持 bundle 小巧

## 5. 不可变状态更新

Zustand 风格 immer-like 模式：
```typescript
setAppState(prev => ({ ...prev, mode: 'bypassPermissions' }))
```

## 6. 事件驱动进度

工具通过回调发射进度：
```typescript
onProgress?.({ toolUseID, data: { type: 'bash_output', text: '...' } })
```
UI 订阅并立即渲染

## 7. 工厂函数构建复杂对象

```typescript
export const MyTool = buildTool({ name, inputSchema, call, checkPermissions })
```

## 8. 多层防御安全模型

权限模式 → 规则链 → Hook 动态权限 → 工具自身校验 → Transcript 分类器

## 9. 消息压缩策略

Token 预算跟踪 → 旧轮次微压缩 → 自动压缩 → 合并摘要消息

## 10. 并发安全标记

每个工具声明 `isConcurrencySafe`，StreamingToolExecutor 据此决定并行/串行执行
