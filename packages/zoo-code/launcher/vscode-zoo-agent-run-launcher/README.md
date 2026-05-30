# Zoo Agent Run Launcher

A small local VS Code helper extension for the Zoo Code Agent Governance Kit.

Behavior:

- Activates after VS Code startup.
- In a Git workspace, shows a one-time prompt: “启动 Zoo Agent 治理流程？”
- On click, it tries to call Zoo/Roo's exported `startNewTask` API with the expanded global `/agent-run` workflow.
- If the API is unavailable, it copies `/agent-run ...` to the clipboard and opens/focuses Zoo Code as a fallback.
- It does not edit files, run shell commands, or read secrets.

Settings are under `zooAgentLauncher.*`.
