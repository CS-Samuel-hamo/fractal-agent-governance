---
name: architecture-boundary-review
description: Review dependency direction, module boundaries, layering violations, and architecture drift against the project profile.
version: 3.6.0
scope: global
applies_to: agent-reviewer
last_updated: 2026-05-30
deprecated_by: ""
---

# Architecture Boundary Review

Check domain/application/infrastructure/api/ui boundaries, service/repository access patterns, env/IO/network leakage, monorepo package boundaries, and shared type/export impact. If boundary is unknown, report `unknown` and request planner or branch-manager decision.
