# Codex Config Safe Baseline

This repository does not automatically edit `~/.codex/config.toml`.

Recommended baseline:

- Default sandbox: `workspace-write`.
- Do not default to `danger-full-access`.
- Default network: disabled.
- Approval policy: avoid `never` for risky work.
- High-risk tasks: use read-only or dry-run first.
- Recommended `CODEX_HOME`: `<CODEX_HOME>`.
- Do not store API keys in config files.
- Windows sandbox and output behavior should be checked with `agent codex-health`.
- WSL and Windows paths should be kept explicit.
- MCP and experimental tools should not be enabled by default.
- Full access requires explicit one-time human confirmation.
