# Task Spec / Implementation Contract

## Metadata
- task_id: global-user-install-20260530
- branch_id: global-user-install
- parent_branch_id: root
- owner_mode: agent-executor
- reviewer_mode: agent-reviewer
- target_branch: n/a
- status: approved

## Objective
Install the current Zoo Code Agent Governance Kit v3.3 directory as a user-level global governance configuration, including global rules, skills, slash command, modes, and the local VS Code/Cursor launcher extension, without copying the kit into business repositories or touching API keys.

## Non-goals
- Do not modify business project files.
- Do not read, write, export, or configure API keys.
- Do not change the kit architecture or launcher behavior.
- Do not create child branches.

## User-visible Behavior
- Input: user runs or requests installation from the extracted kit root.
- Output: global Zoo/Roo assets installed under user-level configuration directories, launcher installed under VS Code-family extension directories, and final installation evidence reported.
- Error behavior: stop if dry-run points at a business project or if required package assets are missing.
- Boundary conditions: if Zoo Code provider profiles are missing, report that they must be configured in the Zoo Code UI by the user.

## Affected Surfaces

### Must inspect before edit
- Analogous features: `GLOBAL_INSTALL_README.md`, `CODEX_GLOBAL_INSTALL_PROMPT.md`, `docs/agent-governance/INSTALLATION_AND_OPERATION.md`, `docs/agent-governance/first-run-launcher.md`.
- APIs / interfaces: Zoo/Roo `startNewTask` launcher API usage in `launcher/vscode-zoo-agent-run-launcher/extension.js`.
- Task branch / route / command dispatch: `.roo/commands/agent-run.md`, launcher contributed commands in `package.json`.
- Registries / factories / providers: VS Code extension contribution metadata and Zoo/Roo extension IDs.
- Enums / constants / types: mode slugs in `.roomodes` and `KIT_MODE_SLUGS`.
- DTO / schema / validators / mappers: `package.json` VS Code contribution schema, global `custom_modes.yaml` merge format.
- Existing utilities: `scripts/install-global-zoo-agent-kit.py`, `scripts/validate-zoo-agent-kit.py`.
- Existing `Proc*` / `Processor*` / `Handler*` / services: none found in this package.
- Tests / fixtures: validation script, JSON validation, Node syntax check, post-install filesystem checks.
- Docs / config / migrations / telemetry: global `.roo` assets, VS Code/Cursor extension folders, Zoo/Roo global modes file.

### Must change
| Surface | File/Symbol | Required change | Evidence expected |
|---|---|---|---|
| Global assets | `~/.roo/**` | Install rules, skills, commands, canonical governance resources | Dry-run and post-install existence checks |
| Launcher | VS Code-family extension dirs | Install `local.zoo-agent-run-launcher-0.3.3` | Directory existence checks |
| Modes | Zoo/Roo global `custom_modes.yaml` | Merge `agent-*` modes | Search for required mode slugs |
| API keys | n/a | No key access or writes | No commands target key files or provider profile files |

## Proc / Processor Data-source Clause
- Existing processor: n/a
- Existing data source: n/a
- New data source: n/a
- Data-shape difference: n/a
- Required design: n/a
- Tests proving old source still works: n/a
- Tests proving new source works: n/a

## Acceptance Criteria
1. Dry-run completes and reports only user-global targets.
2. Formal installation completes.
3. `~/.roo/commands/agent-run.md` exists.
4. `~/.roo/rules-agent-executor/` exists.
5. `~/.roo/skills-agent-executor/impact-analysis/SKILL.md` exists.
6. A VS Code-family extension directory contains `local.zoo-agent-run-launcher-0.3.3`.
7. The selected global `custom_modes.yaml` contains `agent-orchestrator`, `agent-executor`, and `agent-reviewer`.
8. No business repository receives a copied governance kit.
9. No API key files or provider profiles are read or written.

## Verification Plan
```bash
python scripts/validate-zoo-agent-kit.py
python -m json.tool launcher/vscode-zoo-agent-run-launcher/package.json
node --check launcher/vscode-zoo-agent-run-launcher/extension.js
python scripts/install-global-zoo-agent-kit.py --dry-run
python scripts/install-global-zoo-agent-kit.py
# targeted post-install filesystem and mode-slug checks
```

## Rollback Plan
Use the timestamped backups under `~/.roo/backups/` for overwritten global files. Remove `local.zoo-agent-run-launcher-0.3.3` from VS Code-family extension directories if launcher rollback is needed.

## Completion Evidence
- Dry-run completed with user-global targets only.
- Formal installation completed.
- Post-install checks confirmed global command, executor rules, executor impact-analysis skill, VS Code Launcher, Cursor Launcher, and required mode slugs.
- Installer script was updated to avoid parsing editor `settings.json`; custom storage discovery now uses explicit input, environment override, existing globalStorage mode files, or fallback only.
- Installer script skips `__pycache__` and `.pyc` files when copying resources.
- No API key or provider profile path was intentionally read or written.
