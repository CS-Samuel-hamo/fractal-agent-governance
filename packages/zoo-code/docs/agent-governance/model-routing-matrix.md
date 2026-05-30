# 模型路由矩阵

| 阶段 | Zoo mode | 推荐模型 | 温度 | 工具权限 | 主要产物 |
|---|---|---:|---:|---|---|
| 规划 | `agent-planner` | GPT / 高推理 | 0.2-0.5 | read + 治理文档 edit | implementation contract |
| 分支治理 | `agent-branch-manager` | GPT / 高推理 | 0.2-0.4 | read + branch docs edit | branch-state、child contracts |
| 执行 | `agent-executor` | DeepSeek | 0.0-0.3 | read/edit/command | diff、tests、completion evidence |
| 审查 | `agent-reviewer` | GPT / 高推理 | 0.0-0.2 | read/command + review docs edit | review report、verdict |
| 集成 | `agent-integrator` | GPT / 强模型 | 0.0-0.2 | read/edit/command | merge evidence、rollback |
| 治理进化 | `agent-curator` | GPT / 高推理 | 0.0-0.3 | governance edit only | rule/skill/template patches |

## 路由原则

- DeepSeek 只执行边界明确、有合同、有检查清单的任务。
- GPT 负责规划、审查、集成与规则进化。
- 安全、迁移、权限、账务、跨模块 API 语义变更，必须回 planner。
- 同类失败重复出现两次，必须触发 curator。
