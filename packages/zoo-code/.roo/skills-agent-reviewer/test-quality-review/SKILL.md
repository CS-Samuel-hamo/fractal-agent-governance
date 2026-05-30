---
name: test-quality-review
description: Review whether tests cover behavior, regressions, integration surfaces, edge cases, and project-specific quality gates.
version: 3.6.0
scope: global
applies_to: agent-reviewer
last_updated: 2026-05-30
deprecated_by: ""
---

# Test Quality Review

Verify behavior coverage, request/response tests for API changes, negative tests for permission changes, old/new-source tests for Proc/Processor data-source differences, edge cases, failure paths, and meaningful integration-surface coverage. Reject existence-only tests when behavior should be proven.
