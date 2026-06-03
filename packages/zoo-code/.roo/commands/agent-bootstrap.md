# Agent Bootstrap

Project-only bootstrap for both new and existing projects.

For the usual "open a project and make everything ready" flow, prefer
`agent-setup`. It updates global `.roo`, the installed `agent-governance-kit`,
and then runs this project bootstrap step.

Use this command to assemble the minimum Zoo AI-native project setup:

- project facts and readiness under `.zoo-agent/`
- local project rules under `.roo/rules/`
- inactive proposals under `.zoo-agent/bootstrap/proposals/`
- architecture compatibility report and upgrade guardrails under `.zoo-agent/`
- command bridge files under `.roo/commands/`
- backups for local command files before bridge injection

## Policy

- Run one unified bootstrap wrapper.
- Preserve project-specific local command and rule text.
- Do not overwrite existing project rules; existing rules may produce `.new` proposals.
- Move inactive `.new` or patch proposals into `.zoo-agent/bootstrap/proposals/`.
- Do not trust refreshed profile, project map, Graph DB, or runtime readiness
  claims until `.zoo-agent/architecture-compatibility-report.md` is reviewed.
- Back up changed local command files.
- After bootstrap, reload the project so Roo/Zoo re-reads command and rule files.

## Command Shape

Prefer the installed global wrapper so old projects do not depend on stale local scripts.

```powershell
$workspace = "<workspace>"
$bootstrap = "$env:USERPROFILE\.roo\agent-governance-kit\scripts\agent_bootstrap.py"
if (-not (Test-Path $bootstrap)) {
  $bootstrap = if (Test-Path ".\scripts\agent_bootstrap.py") { ".\scripts\agent_bootstrap.py" } else { "" }
}
if (-not $bootstrap) {
  throw "Missing agent_bootstrap.py in global kit and workspace scripts."
}

python $bootstrap `
  --project $workspace `
  --mode auto
```

Optional inputs:

```powershell
--goal "<project goal>"
--stack "<stack hint>"
--codex-home "D:\AI_DEV\codex_home"
--dry-run
```

## Expected Effects

- `.zoo-agent/project-profile.json`, `project-readiness.json`, `bootstrap-report.md`, and project map artifacts are created or refreshed
- `.zoo-agent/agent-bootstrap-report.md` records the combined bootstrap steps
- `.zoo-agent/bootstrap/proposals/` contains inactive proposal files that were not applied
- `.zoo-agent/architecture-compatibility-report.md` records profile downgrade,
  generated-path contamination, source-of-truth, and native dependency findings
- `.zoo-agent/bootstrap/scan-policy.json` records generated/runtime paths that
  should be excluded before project mapping
- `.zoo-agent/bootstrap/source-of-truth-resolver.json` records precedence between
  `.zoo-agent`, `.steward`, docs, plans, and archives
- `.zoo-agent/bootstrap/migration-report.md` and `rollback-anchor.md` record the
  governance-kit upgrade boundary
- `.roo/commands/agent-run.md` gets the `AI_NATIVE_DISPATCHER_OVERRIDE` block
- `.roo/commands/progress.md` gets the `AI_NATIVE_PROGRESS_SUMMARY` block
- `.roo/rules/00-ai-native-global-bridge.md` is added
- missing lower-level Codex commands and skills are copied in
- existing local custom command text is preserved
