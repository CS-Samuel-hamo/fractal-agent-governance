# Agent Runtime v0.9.0-alpha

Agent Runtime is a CLI-first AI runtime with a small user model:

```text
goal -> run -> result
```

This alpha is intended for local, controlled use and public GitHub evaluation.

## Highlights

- Product CLI surface:
  - `agent run "<task>"`
  - `agent pipeline "<task>"`
  - `agent goal "<goal>"`
  - `agent status`
  - `agent backend list`
  - `agent backend switch <backend>`
- Replaceable execution backends.
- Clean default output with debug details hidden from normal users.
- Fresh clone flow validated with the deterministic `mock` backend.
- Release package cleaned of local runtime artifacts and research notes.

## Install

```powershell
git clone <repo-url>
cd agent-runtime
.\bin\agent.cmd --version
agent backend list
agent backend switch mock
agent run "add a short README note" --dry-run
```

## Safety Notes

- No automatic merge.
- No automatic push.
- No deployment or production migration.
- No secret, API key, token, or `.env` content reading.
- Start with `mock` or `dry_run`; switch to a real backend only for low-risk, reviewed tasks.

## Release Validation

Validated before tagging:

- required public docs exist
- fresh clone install path succeeds
- first run succeeds
- backend switch succeeds
- default CLI output stays concise
- tracked files contain no local runtime artifacts
- public docs contain no local machine paths or internal runtime terms

## Alpha Caveat

This is an alpha release. Review results before applying generated work to important projects.
