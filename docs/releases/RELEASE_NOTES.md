# Release Notes

## v1.1.0-alpha.1 Session & Cockpit Improvement Release

This release delivers the first batch of v1.1 roadmap improvements: stronger session
recovery, meaningful undo (preview + apply), and a richer Cockpit experience.

### Added

- **Undo apply**: `agent undo --apply --yes` now performs `git checkout` to restore
  files to checkpoint state, with automatic stash of uncommitted changes.
- **Undo preview**: shows affected files, diff stat summary, and checkpoint commit
  hash before applying.
- **Session diagnostics**: `--verify` mode validates session file integrity; lock
  PID and age are reported in recovery diagnostics.
- **Cockpit timeline**: completed and blocked actions are now merged into a single
  chronological list (up to 20 entries), with duration and file change counts.
- **Attention panel**: severity badges (blocking/warning/info), related modules,
  and affected file paths.
- **Engineering infrastructure**: pyproject.toml, ruff configuration, pytest
  integration, pre-commit hooks, and GitHub Actions CI workflow.

### Fixed

- Cockpit sync failure no longer blocks session continuation. The session can
  continue with a warning that the visual dashboard may be outdated.
- `agent.py` split from 3072 lines into 5 focused modules
  (`agent_utils.py`, `agent_commands.py`, `agent_commands_ux.py`,
  `agent_commands_release.py`) with clean module boundaries.
- All 336 Python files unified under ruff format and lint (zero errors).
- Root documentation reorganized from 44 files to 22, with subdirectories
  `docs/{releases,alpha,planning,feedback}/`.

### Changed

- Version updated from `v1.0.0-alpha.2` to `v1.1.0-alpha.1`.
- Pre-commit hooks active for automated quality checks.
- Test helpers consolidated into `test_helpers.py` and `conftest.py`.

### Safety

- Undo apply requires explicit `--yes` confirmation.
- Uncommitted changes are stashed before undo, never discarded.
- Checkpoint ancestry is verified before undo is offered.
- All local-first guarantees preserved: no push, merge, deploy, or API calls.

This patch release packages the post-alpha improvements from 1.0.6 through
1.0.8 into a source release. It is the recommended public alpha build for users
who want the simplified AI Project Operator interaction loop.

### Included

- Timeout-aware worker failover and bounded docs apply behavior from 1.0.6.
- Unified prompt execution entry from 1.0.7.
- Beginner-friendly interaction closure and new user guidance from 1.0.8.

### User-facing change

Most usage now centers on:

```bash
agent "<project goal>"
agent
agent do "<independent one-off task>"
agent cockpit
agent undo
```

Every normal result is expected to explain what happened, where the project is,
what changed, how to check it, what to do next, and how to undo or change
direction.

### Safety

- No automatic push, merge, deployment, or remote PR creation.
- No `.env` content or API key reading.
- GitHub release publishing remains a maintainer action, not an in-product
  automatic workflow.

