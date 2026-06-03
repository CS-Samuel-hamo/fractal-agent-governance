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
- shared semantic resources
- provider/consumer relationships
- Proc/data-source semantics

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
  "discovery_method": "codebase_search|rg|file_search|manual|unknown"
}
```

Resource locks may use indexing to discover semantic overlaps. Reviewer must block high-risk new shared utility/type, Proc/data-source semantic changes, or API/DTO/schema changes when semantic pattern discovery and consumer/provider discovery are missing or unknown without explanation.

Project-map generation may also use indexing when available. The map records modules, files, entrypoints, tests, docs, and coarse dependencies. If indexing is unavailable, use ripgrep/file search and mark low-confidence or unknown boundaries instead of inventing architecture.
