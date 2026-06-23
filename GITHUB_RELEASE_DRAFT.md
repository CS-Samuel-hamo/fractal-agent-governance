# AI Project Operator v1.0.0-alpha.1

Tag: `v1.0.0-alpha.1`

## Summary

Project Map-backed Autopilot for AI-heavy developers.

Agent Runtime is a local-first AI Project Operator. Give it a project. It keeps moving it forward.

## What This Is

- Project-level Autopilot, not task-level coding agent.
- A local Project Map that tracks modules, capabilities, risks, and next actions.
- A long-running session runtime for project goals.
- A static local Cockpit for project progress.
- A worker-agnostic operator layer where coding tools are workers.
- Local release and PR draft generation.

## What This Is Not

- Not a Codex wrapper.
- Not a Claude Code replacement.
- Not a GitHub PR bot.
- Not a cloud service.
- Not an account system.
- Not a plugin marketplace.

## Core Capabilities

- Map a project locally.
- Start and continue a project session.
- Inspect project progress in Cockpit.
- Stop or inspect undo recovery points.
- Generate local release readiness reports.
- Generate local PR drafts, release notes drafts, and changelog drafts.

## Quickstart

```bash
agent "prepare this project for public release"
agent
agent do "show me an independent project overview"
agent release
agent pr
```

Prompt-only project bootstrap:

```bash
agent "read project_beginning_prompt.md"
agent
```

Independent one-off task:

```bash
agent do "explain how this workflow is wired"
```

## Demo Flow

```bash
cd examples/demo_project
agent cockpit
agent "prepare this demo project for public release"
agent
agent release
agent pr
```

## Post-alpha Patch: 1.0.8 Interaction Closure & New User Guidance

- Normal CLI output now uses a beginner-friendly summary: Result, Where you are,
  What changed, How to check, Next, If this is not what you wanted, and Details.
- Empty projects now show a Welcome guide instead of an empty or internal status.
- `agent do "<task>"` is available for independent one-off tasks that should not
  replace the current project goal.
- `agent continue` is recommended only when there is a real queued action to run.
- Project Map, landing proof, Project Rules, and Logic Check are visible in
  Details without forcing new users to learn internal architecture first.

## Post-alpha Patch: 1.0.7 Unified Prompt Execution Entry

- `agent "<prompt>"` is now the main user entry: understand the prompt, execute
  one safe step when possible, and report progress.
- Prompt intent routing distinguishes single-step edits, seed prompt execution,
  project goals, and unsafe requests.
- Preview-only or no-delivery jobs no longer trap users behind `Existing job found`.
- `--preview` and `--apply` remain compatibility flags, not the main product
  mental model.

## Post-alpha Patch: 1.0.6 Timeout-aware Worker Failover & Docs Apply

- Safe bounded docs writing is available for README and `docs/` `.md` / `.txt`
  updates.
- Actual execution timeouts or sandbox failures no longer report dry-run as a
  successful apply.
- Optional remote OpenAI worker adapter plumbing is present but disabled by
  default; API keys are read only from environment variables and never written to
  artifacts.
- Worker diagnostics now distinguish Codex timeout, sandbox, Unicode path, and
  unavailable-worker cases more clearly.

## Post-alpha Patch: 1.0.5 Intent-first Seed Prompt Bootstrap

- Prompt-only projects can now start from safe `.md` / `.txt` seed files.
- Seed prompts are used as user intent evidence, not system instructions.
- Job Inbox now explains reason, evidence, suggested next action, risk, and how to continue.
- Dangerous goals such as reading `.env`, deleting files, pushing, merging, or deploying remain blocked with a concrete reason.

## Post-alpha Patch: 1.0.5-alpha.2 Starter Docs Completion

- Safe seed prompt starter actions now create trusted starter docs instead of looping in preview.
- Completed starter docs jobs show `Completed` and no longer ask for repeated `agent continue`.
- `agent continue` after completion is harmless and does not overwrite existing starter docs.

## Post-alpha Patch: 1.0.5-alpha.3 Partial Starter Docs

- Existing starter docs are preserved.
- Missing trusted starter docs are still created.
- Preview-only is used only when all starter docs already exist.

## Post-alpha Patch: 1.0.5-alpha.4 Preview Job Supersede

- Preview-only starter jobs no longer block the next natural-language goal.
- Active jobs are still protected from accidental overwrite.
- Users can move from seed bootstrap preview to a concrete revision goal without manually stopping first.

## Post-alpha Patch: 1.0.5-alpha.5 Bounded Docs Apply Diagnostics

- Chinese bounded documentation edits like `?? project_beginning_prompt.md ?? docs/research_workflow.md...` now stay on the fast/small path.
- `--apply` now explains actual execution worker availability problems instead of returning a vague blocked result.
- `agent workers --doctor` is the recommended next step when actual code execution is unavailable.
- Windows debug/status output now handles Unicode diagnostics more safely.

## Post-alpha Patch: 1.0.5-alpha.6 Windows Codex Worker Resolution

- Windows Codex worker resolution now prefers `codex.cmd` / `codex.exe` over the extensionless Anaconda `codex` shim.
- `codex CLI permission denied` caused by Python subprocess command resolution is fixed.
- Codex worker health, backend health, and actual execution adapter now use consistent command resolution.
- Agent/pipeline subprocesses force UTF-8 Python output to support Chinese tasks on Windows consoles.

## Post-alpha Patch: 1.0.5-alpha.7 Non-Git Apply Codex Trust Check

- Non-Git prompt-only projects now pass Codex's git repo check bypass during bounded local execution.
- Actual execution failures that fall back to dry-run are reported as blocked, not `DRY_RUN_COMPLETE`.
- `agent "<task>" --apply` no longer implies success when no business file was changed.
- Added regression coverage for non-Git Codex command construction and actual-failure fallback verdicts.

## Privacy / Safety Guarantees

- The Agent Runtime product does not call GitHub APIs during normal release or PR workflows.
- No automatic push or merge.
- No remote GitHub PR creation by the product.
- No remote GitHub release creation by the product; this GitHub Release page is published manually by the maintainer.
- No cloud sync or telemetry.
- No `.env` content or API key reading.
- In-product release / PR workflow is local draft generation only.

## Known Limitations

- This release does not create remote GitHub PRs.
- The product itself does not publish releases or upload artifacts.
- Claude/local actual execution is not claimed as fully supported unless a real local adapter is detected.
- Human review remains required before publishing, pushing, merging, or deploying.

## Roadmap

- 1.0 public alpha: stable local Project Operator path.
- 1.1: stronger session recovery and Cockpit clarity.
- 1.2: optional explicit GitHub integration with user confirmation.
- Later: team and enterprise workflows.

## Feedback Requested

- Does the Project Map help you understand project state?
- Does the session flow feel useful for real project progress?
- Does the Cockpit make next actions clear?
- Are release and PR drafts useful before manual publishing?
