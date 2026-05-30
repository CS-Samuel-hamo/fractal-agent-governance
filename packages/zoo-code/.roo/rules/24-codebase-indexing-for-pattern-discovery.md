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

Project profile must record `codebase_indexing_status`. Obligation ledger must record `discovery_method`.

DeepSeek may draft pattern findings but must escalate when indexing is unavailable and the change creates shared type, shared utility, public API, Proc/data-source behavior, or architecture boundary changes.
