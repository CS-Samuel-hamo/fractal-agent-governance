# Semantic Resource Map

The semantic resource map is a lightweight resource inventory stored at `.zoo-agent/project-resource-map.json`.

It records inferred resources such as files, modules, public APIs, DTO/schema, database tables, fixtures, config keys, and documentation surfaces.

The first version is intentionally light and path/text based. It must not scan secrets or `.env` contents.
