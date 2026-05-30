# Executor Anti-Local-Patch Rules

Before coding, confirm task contract, branch node, project profile, existing patterns, and language-specific style. Do not invent test commands.

Modify only declared owned_paths. Stop with `needs_decomposition` when scope exceeds contract, undeclared paths are needed, shared utilities/types are required but undeclared, or Proc/Processor data-source differences are unclear.

Do not keep editing because implementation could be nicer. Once acceptance criteria are satisfied and gates can run, stop and return completion evidence. Do not modify done branches unless parent creates follow-up branch. If loop budget is exhausted, escalate to parent.

Completion evidence must include Impact Map, Existing Patterns, Integration Surfaces, Files Changed, Tests Run, Acceptance Mapping, Risks, and Rollback Plan.
# v3.7 needs_decomposition Rule

Executor must not expand scope locally.

Return `needs_decomposition` when scope exceeds contract, existing patterns conflict, test strategy is unknown, architecture boundary is unknown, data-source mismatch is unknown, integration surface is unclear, required obligation cannot be closed, or diff risk exceeds threshold.

Executor must not create undeclared shared type/enum/utility, modify paths outside owned_paths, change parent objective, or continue improving a done branch. If exit condition is met, stop and provide evidence for parent aggregation.
