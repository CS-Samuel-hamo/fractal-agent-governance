# Project Map Schema

Path: `.zoo-agent/project-map.json`.

The project map is a machine-readable index of modules and file locations. It is a project fact source, not a coding standard and not a run plan.

```json
{
  "schema_version": "1.0",
  "generated_by": "generate-project-map.py",
  "project_root": "",
  "module_count": 0,
  "scanned_file_count": 0,
  "modules": [
    {
      "module_id": "src/api",
      "name": "Src Api",
      "owned_paths": ["src/api"],
      "source_files": ["src/api/server.ts"],
      "test_files": ["tests/api.test.ts"],
      "docs": ["docs/api.md"],
      "configs": [],
      "entrypoints": ["src/api/server.ts"],
      "provides": ["unknown"],
      "consumes": ["unknown"],
      "risk_level": "low|medium|high|critical|unknown",
      "architecture_notes": "unknown"
    }
  ],
  "dependencies": [
    {
      "from": "src/api",
      "to": "src/domain",
      "type": "internal|external",
      "evidence": ["src/api/server.ts"],
      "allowed": "true|false|unknown"
    }
  ],
  "unknowns": [],
  "notes": []
}
```

Required fields:

- `module_id`
- `owned_paths`
- `source_files`
- `test_files`
- `docs`
- `entrypoints`
- `risk_level`

Unknown is acceptable when evidence is missing. Do not invent module ownership or dependency direction.

The human-readable sibling is `.zoo-agent/project-map.md`.
