# Zoo Code Agent Governance Kit v3.8 Global Install

This pack installs globally into user-level Zoo/Roo configuration:

- `~/.roo/commands`
- `~/.roo/rules*`
- `~/.roo/skills*`
- `~/.roo/agent-governance-kit`
- Zoo/Roo global `custom_modes.yaml`
- VS Code/Cursor local launcher extension

Reload VS Code/Cursor after installation. Configure GPT/DeepSeek API profiles in the Zoo Code UI if needed; this installer does not read or install API keys.

For Codex CLI Worker Bridge, set `CODEX_HOME` to a user-owned state directory when C drive space is low, for example `D:\AI_DEV\codex_home`. This directory may contain config, auth, logs, sessions, skills, and cache; do not commit it to Git or print auth/token/config contents. Restart PowerShell, VS Code, Zoo Launcher, and Codex App after changing the user-level environment variable.
