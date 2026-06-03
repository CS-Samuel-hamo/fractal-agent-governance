---
name: project-profile-discovery
description: Discover a repository's profile and project architecture map in read-only profiler mode.
version: 3.6.0
scope: global
applies_to: agent-orchestrator
last_updated: 2026-05-30
deprecated_by: ""
---

# Project Profiler Discovery

DeepSeek V4 Flash profiler scans read-only, may draft `.zoo-agent/project-charter.json`, `docs/project-charter.md`, `.zoo-agent/project-profile.json`, `.zoo-agent/project-map.json`, `.zoo-agent/project-map.md`, and `.zoo-agent/architecture-boundaries.json`, does not modify production code, does not read secrets, writes unknown for missing evidence, and escalates unclear mission/architecture/security/migration/data-source mismatch to GPT.

Record `codebase_indexing_status` as `available`, `unavailable`, or `unknown`. If indexing is available, use it for semantic pattern discovery signals; if unavailable, record fallback to `rg`/file search.

Keep project facts and policy separate: project-map files describe modules, files, entrypoints, tests, docs, and dependencies; `AGENTS.md` or local project rules describe coding conventions.
