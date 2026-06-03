# Codebase Indexing For Pattern Discovery

Use Zoo Code codebase indexing for semantic pattern discovery when available. Fall back to ripgrep/file search when indexing is unavailable.

Required discovery targets:

- similar feature
- existing Proc/Processor/Handler/Service
- registry/factory/provider
- domain model
- API entrypoint
- test fixture
- exports and module indexes
- shared semantic resources
- API/DTO/schema consumers and providers
- Proc/data-source semantics

Project profile must record `codebase_indexing_status`. Obligation ledger must record `discovery_method`.

Indexing or fallback search must feed obligation discovery, existing pattern mining, branch decomposition, resource-lock generation, and parallel safety decisions.

DeepSeek may draft pattern findings but must escalate when indexing is unavailable and the change creates shared type, shared utility, public API, Proc/data-source behavior, or architecture boundary changes.

DeepSeek must not treat a failed narrow `rg` search as proof that no existing implementation exists.

Project-map generation may use codebase indexing signals when available; otherwise it falls back to filename, import, and file-search heuristics. Missing project-map coverage for changed files is a governance warning for low-risk work and a blocker for multi-module or architecture-sensitive work.
