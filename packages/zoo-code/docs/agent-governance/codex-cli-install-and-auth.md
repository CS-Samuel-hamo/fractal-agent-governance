# Codex CLI Install and Auth

This kit does not install Codex CLI credentials and does not write `~/.codex/config.toml`.

Operators should install and authenticate Codex CLI outside the governance kit, then verify:

```bash
codex --version
```

If Codex CLI is missing, Zoo may still generate Task Packs, dry-run worker commands, and collect manually produced results. Real `codex exec` runs are skipped until the CLI is available.

`templates/codex/config.toml.example` documents optional profile shape. Users must explicitly decide whether to copy any settings into their real Codex config.
