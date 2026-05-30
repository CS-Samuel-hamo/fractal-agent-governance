---
name: language-specific-code-style
description: Apply stack-specific coding standards for TypeScript, Python, Go, Java, Rust, and mixed repositories.
version: 3.6.0
scope: global
applies_to: agent-executor
last_updated: 2026-05-30
deprecated_by: ""
---

# Language Specific Code Style

TypeScript: strict typing, no `any` expansion, schema/DTO sync, async error handling, barrel export policy. Python: type hints, ruff/mypy/pytest, pydantic/dataclass boundaries, sync/async boundaries. Go: context propagation, error wrapping, interface ownership, table-driven tests. Java/Kotlin: layering, exception mapping, Spring boundary, test slices. Rust: Result/error type, ownership clarity, feature flags, tests. Unknown stack: follow existing style only.
