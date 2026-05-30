# Codebase Indexing Integration

Zoo Code codebase indexing is a semantic pattern discovery signal.

Use it first when available to find:

- similar feature
- existing pattern
- related Proc/Processor
- domain model
- registry/factory/provider
- API entrypoint
- test fixture

If indexing is unavailable, fallback to ripgrep/file search. DeepSeek must not claim no existing implementation merely because `rg` found nothing.

Project profile must record:

```json
{
  "codebase_indexing_status": "available|unavailable|unknown"
}
```

Obligation ledger must record:

```json
{
  "discovery_method": "codebase_search|rg|manual|unknown"
}
```

Reviewer must block high-risk new shared utility/type when semantic pattern discovery is missing or unknown without explanation.
