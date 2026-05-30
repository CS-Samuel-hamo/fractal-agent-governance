---
name: project-profile-discovery
description: Discover a repository's profile in read-only profiler mode and draft .zoo-agent/project-profile.json.
version: 3.6.0
scope: global
applies_to: agent-project-profiler
last_updated: 2026-05-30
deprecated_by: ""
---

# Project Profiler Discovery

DeepSeek V4 Flash profiler scans read-only, may draft `.zoo-agent/project-profile.json`, does not modify production code, does not read secrets, writes unknown for missing evidence, and escalates unclear architecture/security/migration/data-source mismatch to GPT.

Record `codebase_indexing_status` as `available`, `unavailable`, or `unknown`. If indexing is available, use it for semantic pattern discovery signals; if unavailable, record fallback to `rg`/file search.
