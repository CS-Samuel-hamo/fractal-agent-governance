# Public Alpha Report

This checked-in report describes the intended public alpha posture. The generated audit report lives at `.zoo-agent/public_alpha/public_alpha_report.md`.

## Summary

Agent Runtime is packaged as an AI Project Operator:

- project-level autopilot
- durable local sessions
- local Cockpit
- worker-agnostic execution roles
- local release and PR workflow pack

## Public Surface

Public commands:

```bash
agent "<task>"
agent "<task>" --preview
agent "<task>" --apply
agent start "<project goal>"
agent status
agent continue
agent stop
agent undo
agent cockpit
agent release
agent pr
```

## Safety Statement

The alpha is local-first. It does not call GitHub APIs, push, merge, create remote PRs, deploy, read `.env` contents, or upload code.

## Expected Generated Judgment

READY_FOR_100_PUBLIC_ALPHA_RELEASE
