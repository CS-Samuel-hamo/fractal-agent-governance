# Quickstart

This guide shows the simplest path for the public alpha.

## Most Usage Is Two Commands

```bash
agent "prepare this project for public release"
agent
```

The first command gives the operator a goal and lets it execute one safe, reviewable batch. The second command shows the Project Overview: current phase, what changed, whether anything is blocked, why the operator stopped, and what choices you have next.

The core loop is:

```text
goal -> safe batch -> overview -> choice
```

This is the main product difference from a normal coding CLI. Agent Runtime is meant to manage project progress through a Project Map, not just answer one command.

Every normal result starts with seven beginner-friendly sections:

```text
Result
Where you are
What changed
How to check
Next
If this is not what you wanted
Details
```

Read `Result`, `What changed`, and `Next` first. Open `Details` mentally only when you want the Project Map, Landing proof, Project Rules, and Logic Check.

When you need a separate one-off task that should not replace the current project goal, use:

```bash
agent do "<one-off task>"
```

## 1. Start A Project Job

```bash
agent "prepare this project for public release"
```

This creates a durable job backed by the existing session runtime. It does not start a true daemon or OS service. It makes one safe bounded step, saves state, and lets you come back later.

If the project starts from a single prompt file, use the same command style:

```bash
agent "read project_beginning_prompt.md"
```

Safe root-level or `docs/` `.md` / `.txt` files are treated as seed intent
evidence. The operator should produce a clear next state: a starter docs action,
a preview, or a specific blocked reason. It should not show a vague `blocked
zone` with no explanation.

## 2. Check Later

```bash
agent
```

This shows the current job, project phase, progress, latest changes, attention items, Cockpit path, and suggested choices.

`agent status` still works, but it is now just the explicit form of `agent`.

## 3. Open The Cockpit

```bash
agent cockpit
```

The Cockpit is a static local page. It does not require a server or network.

## 4. Steer When Needed

```bash
agent continue
agent stop
agent undo
```

Use `agent continue` only when the overview says there is a planned batch ready to continue. Otherwise, give the next goal directly:

```bash
agent "continue improving the release documentation"
```

Use `agent stop` to stop the current job safely, and `agent undo` to return to the latest recoverable state.

Important: `agent continue` is not a button to press forever. Use it only when `Next` explicitly recommends it. If the current batch is complete, give a new natural-language goal instead.

## 5. Run Independent One-off Tasks

Use `agent do` for temporary explanations, examples, reviews, or bounded document edits that should not change the current project job.

```bash
agent do "show me how the current workflow is wired"
agent do "extend docs/research_workflow.md with evidence validation steps"
```

If the one-off task names a safe docs target, Agent may update that document. If it looks like a project-level goal, Agent keeps it separate and writes a temporary preview artifact under `.zoo-agent/previews/`.

## 6. Prepare Release And PR Artifacts

```bash
agent release
agent pr
```

These commands generate local artifacts only:

- release readiness report
- release notes draft
- changelog draft
- release action plan
- PR plan
- PR draft

They do not call GitHub, push, merge, create a remote PR, read tokens, or read `.env` contents.

## Advanced Preview / Apply Flags

For compatibility, explicit preview/apply flags are still available:

```bash
agent "fix README typo" --preview
agent "fix README typo" --apply
```

Use `-f README.md` when you want to keep a one-off edit scoped to a file.
If `--apply` says actual execution is unavailable, run `agent workers --doctor`
to see whether a real code worker is available on this machine.

## Where To Use It

- CLI is the primary interface.
- AI IDEs are good editing environments.
- Codex App can assist by running, inspecting, and explaining agent commands.
- Codex, Claude, local scanner, mock, and dry-run are workers, not the product.

## What The Overview Means

Every normal output should make the project state visible:

- `Product model`: confirms this is the AI Project Operator path.
- `Project`: names the inferred project or workflow.
- `Project Map`: explains that progress is tracked through project state, phases, evidence, and next actions.
- `Current position`: tells you where the project is in the plan.
- `Landing proof`: shows changed files, local verification command, Cockpit status, and whether the result is done or needs review.
- `Blocked`: tells you whether the operator is stuck.
- `Recommended next move`: tells you what to do next.
- `Choices`: gives concrete commands you can run.
- `Project Rules`: shows whether project instructions and code standards are available.
- `Logic Check`: shows whether mapped modules form a connected workflow, whether quality gates are covered, and where links are weak or missing.
