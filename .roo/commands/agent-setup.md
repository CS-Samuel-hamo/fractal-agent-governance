# Agent Setup

One-touch setup for both global kit state and the current project.

For ordinary CLI-first initialization, prefer `agent bootstrap`. Use this
command when global `.roo` entrypoints or legacy project bootstrap artifacts
also need repair.

Use this when opening either a new project or an existing project and you want
the global `.roo` entrypoints, installed `agent-governance-kit`, and local
project bootstrap state to be aligned in one operation.

## Command Shape

Prefer the currently installed global script when available. If you are
developing the kit itself, the workspace script can run the same flow.

```powershell
$workspace = "<workspace>"
$setup = "<USER_HOME>\.roo\agent-governance-kit\scripts\setup_zoo_agent.py"
if (-not (Test-Path $setup)) {
  $setup = if (Test-Path ".\scripts\setup_zoo_agent.py") { ".\scripts\setup_zoo_agent.py" } else { "" }
}
if (-not $setup) {
  throw "Missing setup_zoo_agent.py in global kit and workspace scripts."
}

python $setup `
  --project $workspace `
  --mode auto
```

Optional inputs:

```powershell
--goal "<project goal>"
--stack "<stack hint>"
--codex-home "<CODEX_HOME>"
--dry-run
--skip-global-sync
--skip-project-bootstrap
```

## Expected Effects

1. Validate the starter pack in the source kit.
2. Sync global `.roo` commands/rules and `<USER_HOME>\.roo\agent-governance-kit`.
3. Back up changed global files under `.roo\backups\one-touch-setup-*`.
4. Run project bootstrap and local entrypoint repair.
5. Write `.zoo-agent/one-touch-setup-report.md`.
6. Write or refresh `.zoo-agent/architecture-compatibility-report.md`.

After setup, reload the project so local `.roo` command and rule files are
re-read. Review the architecture compatibility report before trusting refreshed
profile, project-map, runtime readiness, or merge-readiness claims.

