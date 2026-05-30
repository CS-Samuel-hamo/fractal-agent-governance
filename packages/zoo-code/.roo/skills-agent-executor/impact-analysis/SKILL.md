---
name: impact-analysis
description: Perform pre-edit impact analysis for a code change, including analogous feature search, integration surfaces, enums, utilities, tests, and docs.
version: 3.6.0
scope: global
applies_to: agent-executor
last_updated: 2026-05-30
deprecated_by: ""
---

# Impact Analysis Skill
Use before editing code for any non-trivial feature, bug fix, refactor, or behavior change.

## Procedure
1. Restate intended behavior and non-goals.
2. Search analogous features and domain terms.
3. Identify integration surfaces: API/interface, route/task registration, DI/factory/provider, enum/constants/types, DTO/schema/validator/mapper, exports, tests, docs/config/migration/observability.
4. Produce an Impact Map with `Must Change`, `May Need Change`, `Must Not Change`, `Existing Patterns`.
5. Only then edit.
