# First-Run Launcher

The v3.3 package adds a user-level VS Code helper extension:

```text
launcher/vscode-zoo-agent-run-launcher/
```

It solves the “I do not want to type /agent-run every time I open a new project” problem without making Zoo Code unsafe.

## Behavior

- Activates after VS Code startup.
- Checks the first workspace folder.
- Prompts only for Git repositories by default.
- Prompts once per workspace by default.
- Button `启动治理流程` calls Zoo/Roo `startNewTask` with an expanded global `/agent-run` prompt.
- If the task API is unavailable, copies `/agent-run ...` to the clipboard and opens Zoo Code.

## Safety Boundary

The launcher does not edit files, run commands, create branches, read secrets, or mutate provider profiles. It only starts a Zoo Code task or falls back to clipboard + panel focus.

## Settings

```json
{
  "zooAgentLauncher.enabled": true,
  "zooAgentLauncher.onlyGitRepos": true,
  "zooAgentLauncher.promptMode": "oncePerWorkspace",
  "zooAgentLauncher.promptDelayMs": 2500,
  "zooAgentLauncher.requireAgentRunCommand": true,
  "zooAgentLauncher.defaultArgument": "对当前项目执行 first-run governance intake。先扫描项目结构、测试命令、Zoo Code 全局治理配置是否生效、现有 AGENTS.md/.roo/.roomodes 冲突；不要修改生产代码，不要执行破坏性命令。输出下一步建议。"
}
```

## Reset

Use Command Palette:

```text
Zoo Agent Launcher: Reset Current Workspace Prompt
```
