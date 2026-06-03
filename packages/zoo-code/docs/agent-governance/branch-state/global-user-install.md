# Branch State: global-user-install

- branch_id: global-user-install
- parent_branch_id: root
- worktree_path: $env:USERPROFILE\zoo-global-agent-kit\zoo-code-agent-governance-kit-v3.3-global-launcher
- git_branch: n/a
- owner_agent: agent-executor
- executor_agent: agent-executor
- reviewer_agent: agent-reviewer
- status: approved

## Objective
Install the Zoo Code Agent Governance Kit v3.3 as a user-level global configuration and verify that global assets, modes, and the VS Code/Cursor launcher are available without modifying business projects or touching API keys.

## Scope Boundary
In scope: dry-run, formal global installation, launcher installation, post-install checks, and install evidence. Out of scope: API key/profile setup, business repository modifications, architecture changes, and marketplace packaging.

## Recursion Exit Condition
Stop after post-install evidence confirms the requested global assets and launcher are installed or after a concrete blocker is identified.

## Child Branches
| branch_id | scope | status | dependency | summary |
|---|---|---|---|---|

## Evidence Log
| date | agent | evidence |
|---|---|---|
| 2026-05-30 | agent-executor | Package validation script passed; package.json JSON validation passed; launcher extension.js Node syntax check passed. |
| 2026-05-30 | agent-executor | Dry-run targeted only `$env:USERPROFILE\.roo`, VS Code/Cursor extension dirs, and Zoo Code global custom modes. |
| 2026-05-30 | agent-executor | Formal install completed and post-install checks confirmed global command, rules, skills, launcher directories, and required mode slugs. |
| 2026-05-30 | agent-executor | Installer updated and re-run so global copy avoids editor `settings.json` parsing and generated Python cache copying. |

## Risks
| risk | severity | owner | mitigation |
|---|---|---|---|
| Selected global modes path may be a fallback if Zoo Code custom storage is not discoverable. | medium | agent-executor | Report the selected path and whether manual Zoo Code profile/storage configuration remains needed. |
| VS Code/Cursor may need reload before local extension and global modes are picked up. | low | user | Report reload requirement. |

## Parent Summary
Global installation completed. User should reload VS Code/Cursor so the local launcher extension and merged global modes are picked up.
