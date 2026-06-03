# Resource Lock Policy

`resource-locks.json` enhances `path-locks.json` by tracking semantic resources, not only file paths.

Project-map relationship: `.zoo-agent/project-map.json` is the long-lived module/file/dependency fact source. `resource-locks.json` is the per-run/per-branch resource ownership projection derived from branch contracts, changed files, project-map module ownership, and codebase indexing/search. Do not treat resource locks as permanent project architecture.

Resource types:

- `path`
- `api_contract`
- `dto_schema`
- `database_table`
- `event`
- `queue`
- `feature_flag`
- `proc_data_source`
- `test_fixture`
- `release_note`
- `config`
- `unknown`

Lock types:

- `exclusive`
- `shared_requires_parent_approval`
- `read_only`
- `unknown`

Two branches may have non-overlapping files but still conflict if they modify the same API contract, DTO/schema, Proc/data-source semantics, fixture, feature flag, or provider/consumer contract. Unknown non-read-only resources block parallel execution unless GPT branch-manager approves.
