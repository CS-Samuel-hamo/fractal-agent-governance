# Release Notes

## v1.0.0-alpha.1 Public Alpha Release Gate

This release packages Agent Runtime as a public alpha AI Project Operator.

### Added

- VERSION file set to `1.0.0-alpha.1`.
- GitHub release draft for manual publishing.
- Public release checklist for safe manual release.
- Public release gate, package manifest, fresh clone verifier, demo flow verifier, tag preflight, and release report generation.
- Branch-aware publishing notes for the `release/v1.0.0-alpha.1` alpha branch.
- Post-launch remote verification and branch hygiene reports.

### Confirmed

- Public positioning remains AI Project Operator.
- Core differentiation remains Project-level Autopilot, not task-level coding agent.
- Public commands remain focused on task, session, Cockpit, release, and PR draft flows.
- Release and PR workflow remains local draft generation only.
- Published alpha content is verified by release branch, tag, tree equality, and empty file diff.

### Known Limitations

- This release does not create remote GitHub PRs.
- Product release and PR workflows do not call GitHub APIs.
- The public alpha branch and tag were completed with a manual GitHub Git Data API fallback after Git HTTPS push reset; this does not mean a GitHub Release object was created.
- This release does not push, merge, deploy, or create a remote release.
- Claude/local actual execution is not claimed as fully supported unless real local adapters are detected.
- Human review is required before publishing.

## 0.99 Public Alpha Packaging

This alpha packages Agent Runtime as an AI Project Operator.

## Added

- Public positioning: AI Project Operator.
- Public command surface for tasks, sessions, Cockpit, release packs, and PR drafts.
- Public docs for quickstart, CLI, positioning, privacy, safety, demo, roadmap, and architecture.
- Local public alpha audit tooling.
- Safe demo project fixture.

## Changed

- Documentation now emphasizes project-level autopilot instead of task-level coding.
- Codex, Claude Code, local scanner, mock, and dry-run are described as workers, not the product.
- Release and PR flows are presented as local draft generation, not remote publishing automation.

## Known Limitations

- The public alpha does not create remote pull requests.
- It does not push, merge, deploy, or call GitHub APIs.
- Real external worker availability depends on local installation and diagnostics.
- Local learning is advisory and does not train a model.
- Human review remains required before publishing or deploying.

## Not Included

- Cloud sync
- account system
- payment
- plugin marketplace
- VS Code extension
- Electron app
- remote telemetry
