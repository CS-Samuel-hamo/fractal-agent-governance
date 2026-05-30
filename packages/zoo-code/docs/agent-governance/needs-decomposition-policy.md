# Needs Decomposition Policy

`needs_decomposition` is a controlled return state, not a failure to hide.

Executor must stop and return `needs_decomposition` when:

- scope exceeds branch contract
- existing patterns conflict
- test strategy is unknown
- architecture boundary is unknown
- data-source mismatch is unknown
- integration surface is unclear
- required obligation cannot be closed
- diff risk exceeds branch threshold

The executor must include:

- branch_id
- exact blocker
- evidence gathered
- owned_paths touched or not touched
- proposed child boundaries
- risks if continuing locally

Branch-manager/GPT decides whether to split, re-scope, research, escalate, fallback, or abort.
