# Fractal Decomposition Playbook

CRUD feature: root add CRUD; children API, persistence, tests; API consumes service, repository provides persistence; order model -> repository -> service -> API -> tests; exit request/response tests pass.

API + UI feature: children backend API, client contract, UI state, e2e; API provides DTO, UI consumes client; order API -> client -> UI -> e2e.

Proc/Processor data-source mismatch: children source analysis, adapter, processor wiring, parity tests; adapter provides normalized data, processor consumes it; old and new source tests required.

Database migration: children migration, model/DTO, data access, tests; schema provides repository contract; migration test and rollback note required.

Cross-module refactor: children inventory, shared contract, module updates, regression tests; shared package provides API, modules consume; exit no ownership conflicts and regression gate passes.
