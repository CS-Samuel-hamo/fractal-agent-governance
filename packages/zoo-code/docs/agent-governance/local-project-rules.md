# Local Project Rules Layer

Do not copy the full governance kit into a business project. Global rules provide methodology. Local rules provide project facts. `.zoo-agent` stores run state. `AGENTS.md` stores human-readable local conventions.

Allowed lightweight files are `AGENTS.md`, selected `.roo/rules/*project*.md`, selected role-specific project rules, and `.zoo-agent/project-profile.json`. Generation must be based on project profile, must not read secrets, and must not overwrite existing files without explicit approval.
