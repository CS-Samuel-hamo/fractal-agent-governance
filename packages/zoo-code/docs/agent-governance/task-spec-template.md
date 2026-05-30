# Task Spec / Implementation Contract

## Metadata
- task_id:
- branch_id:
- parent_branch_id:
- owner_mode: agent-executor
- reviewer_mode: agent-reviewer
- target_branch:
- status: draft | ready_for_execution | in_progress | review | approved | merged | blocked

## Objective

## Non-goals

## User-visible Behavior
- 输入：
- 输出：
- 错误行为：
- 边界条件：

## Affected Surfaces

### Must inspect before edit
- Analogous features:
- APIs / interfaces:
- Task branch / route / command dispatch:
- Registries / factories / providers:
- Enums / constants / types:
- DTO / schema / validators / mappers:
- Existing utilities:
- Existing `Proc*` / `Processor*` / `Handler*` / services:
- Tests / fixtures:
- Docs / config / migrations / telemetry:

### Must change
| Surface | File/Symbol | Required change | Evidence expected |
|---|---|---|---|
| Core logic |  |  |  |
| Interface/API |  |  |  |
| Registration/dispatch |  |  |  |
| Tests |  |  |  |

## Proc / Processor Data-source Clause
- Existing processor:
- Existing data source:
- New data source:
- Data-shape difference:
- Required design: provider injection | selector param | adapter/wrapper | helper extraction | explicit fork
- Tests proving old source still works:
- Tests proving new source works:

## Acceptance Criteria
1.
2.
3.

## Verification Plan
```bash
# targeted tests
# typecheck/lint/diagnostics
# broader regression if needed
```

## Rollback Plan
