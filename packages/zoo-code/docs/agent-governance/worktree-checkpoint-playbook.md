# Worktree / Checkpoint Playbook

## Branch strategy

| 任务类型 | 隔离方式 | 原因 |
|---|---|---|
| 纯文档/配置 | branch | 低风险 |
| 单模块 feature/bugfix | worktree + branch | 隔离上下文和 diff |
| 跨模块 API/schema/migration | 独立 worktree + reviewer gate | 高回滚风险 |
| 多方案探索 | 多个 worktree | 方案互不污染 |

## 顺序
1. planner 生成 task spec。
2. branch-manager 建 branch-state。
3. 创建 worktree。
4. executor 实现。
5. checkpoint/diff 检查。
6. reviewer 审查。
7. integrator 合并。
8. curator 处理复发性失败。

## 命名
```text
worktree/<area>/<task-id>-<short-name>
agent/<parent-task>/<child-task>
review/<task-id>
evolution/<event-id>
```
