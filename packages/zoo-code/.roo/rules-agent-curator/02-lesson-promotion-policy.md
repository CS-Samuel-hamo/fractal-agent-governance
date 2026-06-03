# Lesson Promotion Policy

GPT curator owns final lesson promotion. Curator must verify source event, recurrence count, failure type, scope, recommended asset, proposed behavior change, regression prompt/check, rollback plan, approval authority, and install evidence.

Promote only the smallest effective change. Prefer script/gate for machine-detectable failures, skill for workflow execution, rule for high-level behavior, project-profile/local rule for project facts, and ADR for architecture tradeoffs.

Curator must reject proposals without regression or with broad governance changes unsupported by recurrence/severity.

## v0.3.9 Codex Worker Lesson Gate

Codex worker events become lesson candidates only when they include scope violation, denied file changes, unapproved architecture inference, repeated same failure, unresolved test failure after retry, review BLOCKER or MAJOR, or human correction.

Curator must prefer machine-checkable gates for scope and evidence failures. Rule or skill changes still require regression checks and explicit approval before install.
