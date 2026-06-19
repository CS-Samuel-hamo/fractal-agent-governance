# Semantic Resource Map

The semantic resource map is a lightweight resource inventory stored at `.zoo-agent/project-resource-map.json`.

It records inferred resources such as files, modules, public APIs, DTO/schema, database tables, fixtures, config keys, and documentation surfaces.

The first version is intentionally light and path/text based. It must not scan secrets or `.env` contents.

## JSON Shape

```json
{
  "project_root": "",
  "created_at": "",
  "confidence": "low|medium|high",
  "resources": [
    {
      "resource_id": "",
      "type": "file_path|module|public_api|internal_api|dto_schema|database_table|event|queue|feature_flag|proc_data_source|test_fixture|config_key|documentation_surface|unknown",
      "name": "",
      "paths": [],
      "providers": [],
      "consumers": [],
      "owner_hint": "",
      "risk_level": "low|medium|high|critical|unknown",
      "confidence": "low|medium|high",
      "notes": ""
    }
  ],
  "unknowns": []
}
```

## Policy

- File non-overlap is not enough for independence.
- Shared semantic resources block parallel actual execution.
- Unknown dependencies are treated as not independent.
- Low-confidence maps can support dry-run scheduling but not automatic parallel actual execution.
