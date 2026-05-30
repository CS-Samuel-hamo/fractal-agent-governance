# 分形 Branch Agent 契约

## Branch Node 字段

- branch_id
- parent_branch_id
- objective
- non_goals
- scope_boundary
- inputs / outputs
- dependencies
- acceptance_criteria
- merge_contract
- recursion_exit_condition
- risk_register
- child_branches
- review_status

## 拆分条件

仅当拆分能降低复杂度、隔离风险、支持并行、降低上下文误读，或需要不同模型/权限时，才创建 child branch。

## 子节点返回给父节点的摘要

```markdown
## Child Summary
- branch_id:
- objective:
- outcome: success | partial | blocked | failed
- changed_files:
- checks_run:
- acceptance_mapping:
- unresolved_risks:
- parent_actions_required:
- merge_recommendation:
```

## 父节点聚合规则

父节点不得信任“已完成”的口头声明；必须基于验收证据、diff、测试、review verdict、风险记录聚合。
