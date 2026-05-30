---
name: existing-pattern-mining
description: Search and mine existing repository patterns before adding new functions, enums, processors, handlers, services, utilities, APIs, or tests.
version: 3.6.0
scope: global
applies_to: agent-executor
last_updated: 2026-05-30
deprecated_by: ""
---

# Existing Pattern Mining Skill
Use when a task asks for a new feature or change that may resemble existing functionality.

## Search Strategy
Search domain nouns/verbs, analogous endpoint/task names, suffix patterns (`Proc`, `Processor`, `Handler`, `Service`, `Repository`, `Adapter`, `Mapper`, `Validator`, `Factory`), tests, fixtures, exports, and module indexes.

Use Zoo Code codebase indexing first when available. Record `codebase_indexing_status` from project-profile and the discovery method used. If indexing is unavailable, fall back to `rg` and file search. Do not conclude that no existing implementation exists from a single failed search.

## Decision Rule
Reuse if semantics match; extend if semantics match but inputs/data-source vary; wrap/adapt if a boundary differs; create new only if no existing pattern fits.
