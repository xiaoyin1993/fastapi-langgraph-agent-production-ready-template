---
name: Claude Code 权限与安全模型
description: Claude Code 的多层权限系统设计，包括权限模式、规则链、Hook 动态权限等
type: reference
---

源码路径：`/Users/xiaoyin/Downloads/claude-code-main/src`

## 五层防御架构

### 第一层：权限模式（`types/permissions.ts`）

```typescript
type PermissionMode =
  | 'default'              // 请求批准
  | 'acceptEdits'          // 自动批准编辑，其他需确认
  | 'bypassPermissions'    // 全部自动批准
  | 'dontAsk'              // 静默拒绝
  | 'plan'                 // 计划模式
  | 'auto'                 // 基于 Transcript 分类器
  | 'bubble'               // Supervisor 模式
```

### 第二层：权限规则（`utils/permissions/`）

规则来源优先级：CLI 参数 → 用户设置 → 项目设置 → Policy 限制 → Hooks

```typescript
type PermissionRule = {
  source: 'userSettings' | 'projectSettings' | 'policy' | 'cliArg'
  ruleBehavior: 'allow' | 'deny' | 'ask'
  ruleValue: { toolName: string, ruleContent?: string }
}
```

### 第三层：权限检查（`hooks/useCanUseTool.tsx`）

```
hasPermissionsToUseTool(tool, input, context)
  → 检查规则链：allow → ask → deny
  → 如果 'ask'：显示交互式权限对话框
  → 记录决策 + 发送分析
```

### 第四层：Hook 动态权限（`utils/hooks.ts`）

- `PreToolUse` hook：可修改输入、改变权限决策
- `PermissionRequest` hook：异步外部审批
- `PermissionDenied` hook：记录/响应拒绝事件

### 第五层：工具自身逻辑

每个工具的 `checkPermissions()` 实现额外校验（路径遍历、远程仓库白名单等）

## 权限上下文（不可变，传递给每个工具）

```typescript
type ToolPermissionContext = DeepImmutable<{
  mode: PermissionMode
  alwaysAllowRules, alwaysDenyRules, alwaysAskRules
  additionalWorkingDirectories: Map<string, ...>
  shouldAvoidPermissionPrompts?: boolean  // 后台 Agent 用
}>
```
