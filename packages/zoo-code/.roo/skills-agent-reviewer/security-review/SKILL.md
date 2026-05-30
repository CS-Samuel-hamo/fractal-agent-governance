---
name: security-review
description: Review code changes for security, secret handling, authz, validation, injection, SSRF, XSS, and destructive operation risks.
version: 3.6.0
scope: global
applies_to: agent-reviewer
last_updated: 2026-05-30
deprecated_by: ""
---

# Security Review

Check secret handling, auth/authz, PII, input validation, SQL/NoSQL injection, SSRF, XSS, path traversal, unsafe filesystem operations, destructive commands, and supply-chain risk. Require human gate for auth, payment, PII, production config, destructive operations, or secrets.
