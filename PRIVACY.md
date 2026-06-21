# Privacy

Agent Runtime is local-first.

## What Stays Local

- Project Map
- session history
- Cockpit data
- worker diagnostics
- release and PR drafts
- local learning artifacts

These are stored under `.zoo-agent/` unless explicitly generated as public demo files.

## What Is Not Uploaded

- source code
- `.env` contents
- API keys
- tokens
- raw worker logs
- private runtime traces
- release or PR artifacts

The public alpha does not use cloud sync, remote telemetry, accounts, or GitHub API calls.

## Secret Handling

The local scanner and release workflow skip secret-like files. They may record that a file was skipped, but they must not save secret file contents.

Examples of skipped files:

- `.env`
- private keys
- certificates
- credential files
- token dumps

## Paths And Remotes

Public reports should use repo-relative or sanitized paths. Git remotes are sanitized so credentials are not stored.

## Release / PR Workflow

`agent release` and `agent pr` generate local drafts only. They do not call GitHub, create a PR, push, merge, or read a GitHub token.
