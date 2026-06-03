# Project Profile Schema

Path: `.zoo-agent/project-profile.json`.

Fields: schema_version, generated_by, project_root, codebase_indexing_status, project_charter_path, project_charter_md, project_map_path, architecture_boundaries_path, package_manager, languages, frameworks, commands.test/lint/typecheck/build, source_roots, test_roots, api_entrypoints, patterns.registries/factories/providers/processors, forbidden_paths, generated_files, risk_paths, notes. Missing evidence is `unknown`; secret-like files are never read.

`project-profile.json` is the technology profile. It is intentionally smaller than the architecture map. Use `.zoo-agent/project-map.json` for module/file/dependency facts and `.zoo-agent/architecture-boundaries.json` for dependency direction.
