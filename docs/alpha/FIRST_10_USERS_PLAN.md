# First 10 Users Plan

Goal: learn whether users understand and can use the AI Project Operator path.

## Target Users

1. AI-heavy solo developer
2. Indie hacker
3. Open-source maintainer
4. Small-team tech lead
5. Vibe-coding heavy user

## Tasks For Each User

Ask each user to try:

1. Install or clone the repo.
2. Run first command:
   ```bash
   agent cockpit
   ```
3. Start a project session:
   ```bash
   agent start "prepare this project for public release"
   ```
4. Check status:
   ```bash
   agent status
   ```
5. Open Cockpit and explain what the project state means.
6. Generate local release pack:
   ```bash
   agent release
   ```
7. Generate local PR draft:
   ```bash
   agent pr
   ```
8. File feedback using the closest GitHub issue template.

## Questions To Ask

- Did you understand that this is an AI Project Operator?
- Did it feel different from a task-level coding agent?
- Did Project Map or Cockpit help?
- Did the session flow feel too passive or too automatic?
- Did release/PR artifacts feel useful?
- Did anything look like a Codex wrapper?
