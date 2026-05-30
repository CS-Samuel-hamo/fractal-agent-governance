# Skill Versioning Policy

Every `SKILL.md` frontmatter supports:
- `name`
- `description`
- `version`
- `scope`
- `applies_to`
- `last_updated`
- `deprecated_by`

`name` must match the skill directory. `version` must exist and should change when behavior changes. Deprecated skills must not be default-invoked by `/agent-run`, mode routing, or default command flow.
