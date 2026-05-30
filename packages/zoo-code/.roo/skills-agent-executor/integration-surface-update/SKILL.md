---
name: integration-surface-update
description: Ensure a feature implementation is propagated to interfaces, route/task registration, branch dispatch, enums, exports, tests, docs, and configuration.
version: 3.6.0
scope: global
applies_to: agent-executor
last_updated: 2026-05-30
deprecated_by: ""
---

# Integration Surface Update Skill
Use after implementing core logic but before final response.

## Checklist
- Public API/interface updated.
- Caller sites updated.
- Route/task/command/branch dispatch updated.
- Registry/factory/provider registration updated.
- Enum/constants/type definitions updated.
- Serialization/DTO/schema/validator/mapper updated.
- Module exports/index files updated.
- Tests and fixtures updated.
- Docs/config/migrations/telemetry updated if relevant.

## Verification Queries
```bash
rg "<NewSymbol>|<NewEnum>|<NewRoute>|<TaskName>" src test docs .
rg "register|registry|route|dispatch|branch|factory|provider|adapter" src test .
rg "export .*<Symbol>|from .*<module>" src test .
```
