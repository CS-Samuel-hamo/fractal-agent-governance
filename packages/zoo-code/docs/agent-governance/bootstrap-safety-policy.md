# Bootstrap Safety Policy

Project Bootstrap follows these constraints:

- Do not modify business code.
- Do not read, print, or write API keys, tokens, secrets, credentials, or `.env` contents.
- Do not overwrite existing `AGENTS.md`, `.roo/rules`, or `.zoo-agent/project-profile.json`.
- Generate `.new` or `.patch` files for existing projects.
- Do not commit, push, merge, reset, clean, deploy, publish, or run production migrations.
- Do not copy the full global governance kit into a project.
- Mark missing test commands, stack, and entrypoints as `unknown`.

For non-empty non-Git directories, bootstrap reports recommendations and does not run `git init` unless the user explicitly chooses new project initialization.
