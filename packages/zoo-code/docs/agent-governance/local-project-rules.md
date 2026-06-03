# Local Project Rules Layer

Do not copy the full governance kit into a business project. Global rules provide methodology. Local rules provide project facts. `.zoo-agent` stores run state. `AGENTS.md` stores human-readable local conventions.

Allowed lightweight files are `AGENTS.md`, `docs/project-charter.md`, selected `.roo/rules/*project*.md`, selected role-specific project rules, `.zoo-agent/project-charter.json`, `.zoo-agent/project-profile.json`, `.zoo-agent/project-map.json`, `.zoo-agent/project-map.md`, and `.zoo-agent/architecture-boundaries.json`. Generation must be based on project charter/profile/map, must not read secrets, and must not overwrite existing human-authored local rules without explicit approval.

Keep responsibilities separate: project-charter files contain durable mission and decision boundaries; project-map files contain module facts; `AGENTS.md` and local rules contain conventions and policy; run artifacts contain current task state.
