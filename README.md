# Zoo Codex Worker Bridge

CLI-first AI coding runtime with Codex execution backend and optional Zoo Code UI.

Status: `0.4.0-local-alpha`. This project is experimental and not production-ready.

## Architecture

```text
User
-> agent CLI
-> goal + loop + classifier
-> fast | parallel | governed
-> Codex CLI / GPT / Zoo Code
```

- CLI Runtime: control plane for bootstrap, run, status, rollback, reroute, map, standards, and review.
- Codex CLI: execution backend only.
- GPT: final decision layer for governed work and merge/readiness decisions.
- DeepSeek: cheap analysis and mechanical assistant.
- Zoo Code: optional UI layer.

## Quickstart

```powershell
agent bootstrap
agent "fix typo in README"
```

Run `agent` with no subcommand to enter interactive mode:

```text
agent>
```

Natural-language input in the prompt is treated as `agent run "<input>"`.

## Existing Project

```powershell
agent bootstrap --workspace <existing-git-repo>
agent status --workspace <existing-git-repo>
agent "fix typo in README" --workspace <existing-git-repo>
```

Bootstrap scans metadata only, writes reviewable `.zoo-agent` runtime files, and does not edit business source directories.

## New Project

In an empty directory:

```powershell
agent bootstrap
agent "create a small README improvement"
```

Bootstrap initializes git, creates starter runtime files, and does not generate business modules unless explicitly requested later.

## Safety Boundaries

- Scope guard checks assigned file boundaries.
- No automatic merge, push, deploy, release, or production database migration.
- No reading or printing secrets, API keys, tokens, `.env` contents, or credential files.
- Worktree isolation is used for worker execution and rollback planning.
- Rollback defaults to dry-run and does not use `git reset --hard`.

## Useful Commands

```powershell
agent --help
agent --version
agent bootstrap
agent status --no-write
agent run "<task>"
agent "<task>"
agent rollback --run-id <run-id> --task-id <task-id> --dry-run
agent reroute --run-id <run-id> --task-id <task-id> --path governed
agent map check
agent standards check
agent review --run-id <run-id>
```

See [docs/quickstart.md](docs/quickstart.md) and [docs/cli-usage.md](docs/cli-usage.md).
