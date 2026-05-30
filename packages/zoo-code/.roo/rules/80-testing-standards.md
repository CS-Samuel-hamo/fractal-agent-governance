# Testing Standards

Tests must verify behavior, not mere existence.

Use unit tests for pure logic; integration tests for APIs, services, repositories, DI, routing, adapters; e2e tests for user workflows; migration tests for schema/data migrations; property-based tests for parsers/state machines/invariants; golden tests for stable generated output.

API changes require request/response tests. Permission changes require negative tests. Proc/Processor data-source differences require old-source and new-source behavior tests. Existence-only tests do not satisfy behavior coverage.
