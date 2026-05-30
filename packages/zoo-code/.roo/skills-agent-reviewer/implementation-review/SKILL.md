---
name: implementation-review
description: Review an executor implementation against a task contract, focusing on missing integration surfaces, data-source mismatches, tests, and regression risk.
version: 3.6.0
scope: global
applies_to: agent-reviewer
last_updated: 2026-05-30
deprecated_by: ""
---

# Implementation Review Skill
1. Read task contract.
2. Inspect changed files and diff.
3. Search analogous features.
4. Search for integration surfaces that should have changed but did not.
5. Verify tests and diagnostics.
6. Produce severity-classified findings and a verdict.
7. Emit an event if the failure should update governance.
