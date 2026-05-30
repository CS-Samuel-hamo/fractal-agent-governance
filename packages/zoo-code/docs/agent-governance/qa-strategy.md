# QA Strategy

Non-trivial coding tasks require a Test Plan in the implementation contract. Select tests by change type: unit for local logic, integration for component boundaries, e2e for critical user flows, migration for schema changes, security negative tests for auth/permission changes, property-based for invariant-heavy logic, golden/snapshot for stable structured outputs, smoke for release readiness.

API changes require request/response tests. Permission changes require negative tests. Proc/Processor data-source differences require old/new source behavior tests. Each required verification obligation must map to a Test Plan item.
