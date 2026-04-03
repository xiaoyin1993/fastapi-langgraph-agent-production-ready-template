---
name: Claude Code Hooks/Skills/插件系统
description: Claude Code 的 Hook 事件机制、Skill 扩展系统和插件架构
type: reference
---

源码路径：`/Users/xiaoyin/Downloads/claude-code-main/src`

## Hooks 系统（`utils/hooks.ts`）

Shell 脚本或 HTTP 回调，在生命周期各节点触发。

### Hook 事件

- **生命周期**：Setup、SessionStart、SessionEnd、CwdChanged
- **每轮交互**：UserPromptSubmit、PreToolUse、PostToolUse、PostToolUseFailure
- **权限**：PermissionRequest、PermissionDenied
- **其他**：SubagentStart、FileChanged、Notification、Stop

### Hook 配置（settings.json）

```json
{
  "hooks": {
    "setup": "/path/to/script",
    "preToolUse": "http://localhost:3000/hooks/pre"
  }
}
```

### Hook 执行流程

1. 从 settings.json 加载 hook 配置
2. Shell 脚本：spawn 进程，通过 stdin 传入 JSON 输入
3. HTTP：POST 请求，等待响应
4. 解析 stdout JSON 输出
5. 应用变更（修改工具输入、更新权限、继续/停止）

### Hook 输出格式

```typescript
type HookJSONOutput = {
  continue?: boolean
  suppressOutput?: boolean
  decision?: 'approve' | 'block'
  hookSpecificOutput: {
    permissionDecision?: 'allow' | 'deny' | 'ask'
    updatedInput?: Record<string, unknown>
  }
}
```

## Skills 系统（`skills/`）

npm 包或本地脚本扩展 Claude Code。

```
skill/
├── index.ts          # 主入口
├── skill.json        # 元数据
└── commands/         # 可选的斜杠命令
    └── my-cmd.ts
```

- 内置：`src/skills/bundled/`
- 用户级：`~/.claude/skills/`

## 插件系统（`plugins/`）

启动时加载的 bundled 模块：
- MCP Server 支持
- Workflow Scripts（WORKFLOW_SCRIPTS feature gate）

## 扩展点汇总

1. **添加工具**：创建 `src/tools/MyTool/`，实现 Tool 接口，注册到 `src/tools.ts`
2. **添加命令**：创建 `src/commands/my-cmd.ts`，导出 Command 对象，注册到 `src/commands.ts`
3. **添加 Skill**：创建 npm 包 + `skill.json`，放入 `~/.claude/skills/`
4. **添加 Hook**：编写脚本或 HTTP 端点，在 `settings.json` 注册
