# Codex CLI Sandbox Policy

Default sandbox:

```bash
codex exec --cd <worktree> --sandbox workspace-write
```

Allowed defaults:

- `read-only` for inspection or review
- `workspace-write` for bounded implementation in an approved worktree

Disallowed by default:

- `danger-full-access`
- `--dangerously-bypass-approvals-and-sandbox`

Danger bypass may be used only in a one-time isolated temporary test repository and only after explicit user approval. It must never be used against a business repository or production worktree.
