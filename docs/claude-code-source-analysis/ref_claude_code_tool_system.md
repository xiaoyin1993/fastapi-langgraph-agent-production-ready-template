---
name: Claude Code 工具系统设计
description: Claude Code 的工具注册、权限校验、并发执行等核心设计模式，可作为 Agent 工具系统参考
type: reference
---

源码路径：`/Users/xiaoyin/Downloads/claude-code-main/src`

## Tool 接口设计（`src/Tool.ts`）

多态泛型接口 `Tool<Input, Output, ProgressData>`，核心方法：

- **身份**：name、aliases、searchHint
- **执行**：`call(input, context, canUseTool, parentMessage, onProgress)`
- **校验**：inputSchema（Zod）、inputJSONSchema、validateInput()
- **权限**：`checkPermissions(input, context)` → PermissionResult
- **并发**：`isConcurrencySafe(input)` — 标记是否可并行执行
- **分类**：`isReadOnly(input)`、`isDestructive(input)`、`isSearchOrReadCommand(input)`
- **UI 渲染**：description()、prompt()、renderToolResultMessage()

## 工具注册（`src/tools.ts`）

注册表模式 + Feature Gate：
```typescript
function getAllBaseTools(): Tools {
  return [
    AgentTool, BashTool, FileEditTool, GlobTool, ...
    // 条件加载
    ...(feature('KAIROS') ? [SendUserFileTool] : []),
    ...(feature('AGENT_TRIGGERS') ? [CronCreateTool] : []),
  ]
}
```

## 工具目录组织（以 BashTool 为例）

```
BashTool/
├── BashTool.tsx          # 主定义
├── bashPermissions.ts    # 权限匹配器
├── bashSecurity.ts       # 安全解析
├── commandSemantics.ts   # 命令语义理解
├── pathValidation.ts     # 路径安全检查
├── readOnlyValidation.ts # 只读模式执行
├── sedEditParser.ts      # Sed 命令解析
├── shouldUseSandbox.ts   # 沙箱判断
└── UI.tsx                # React 组件
```

## 并发执行模型（`StreamingToolExecutor`）

- `isConcurrencySafe: true` 的工具可并行执行
- 不安全的工具独占执行
- 结果按接收顺序发出
- 进度消息立即发射

## 工具构建工厂

```typescript
export const MyTool = buildTool({
  name: 'MyTool',
  inputSchema: myInputSchema,
  call: async (input, context) => { ... },
  checkPermissions: async (input, context) => { ... },
})
```
