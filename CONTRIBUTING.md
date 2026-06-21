# Contributing

Thanks for helping test Agent Runtime, the AI Project Operator.

## Product Positioning

Please keep the public positioning consistent:

- AI Project Operator
- Give it a project. It keeps moving it forward.
- Project-level Autopilot, not task-level coding agent.

Codex, Claude Code, and local tools are workers. The product is the project operator.

## Good Contributions

- Clear bug reports from first runs.
- Project Map quality feedback.
- Autopilot session feedback.
- Cockpit readability feedback.
- Release / PR workflow feedback.
- Documentation fixes.
- Safe local test fixtures.

## Before Opening A PR

- Do not include `.zoo-agent/` runtime artifacts.
- Do not include secrets, API keys, tokens, raw logs, or local absolute paths.
- Do not claim cloud sync, remote PR creation, or GitHub API automation.
- Do not describe this as a Codex wrapper or Claude Code replacement.

## Local Checks

```bash
python scripts/validate_starter_pack.py
python scripts/test_public_release_gate.py
python scripts/test_public_launch_ops.py
```

## Pull Requests

Use `.github/PULL_REQUEST_TEMPLATE.md`. Keep the change focused and explain how it supports the AI Project Operator path.
