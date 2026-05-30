---
name: project-profile-discovery
description: Discover a repository's language, framework, commands, source roots, tests, architecture signals, and risk paths before coding.
version: 3.6.0
scope: global
applies_to: agent-executor
last_updated: 2026-05-30
deprecated_by: ""
---

# Project Profile Discovery

Read-only scan before coding. Identify package manager, language, framework, test/lint/typecheck/build commands, source roots, test roots, API entrypoints, registry/factory/provider patterns, forbidden paths, generated files, and secret-like files. Output `.zoo-agent/project-profile.json` draft with `unknown` for missing evidence. Do not read secret contents.
