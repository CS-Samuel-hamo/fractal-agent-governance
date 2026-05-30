---
name: implicit-work-discovery
description: Infer implicit propagation, verification, compatibility, operational, documentation, and rollback obligations before coding.
version: 3.6.0
scope: global
applies_to: agent-executor
last_updated: 2026-05-30
deprecated_by: ""
---

## Inputs
- explicit user request
- goal contract
- project profile
- existing patterns

## Output
Create or update the Obligation Ledger. Include explicit request, inferred obligations, source signals, candidate files or surfaces, status, verification, evidence, risk if omitted, and escalation flag.

Record `discovery_method` as `codebase_search`, `rg`, `manual`, or `unknown`. When Zoo Code codebase indexing is available, use it to find analogous features, Proc/Processor usage, registry/factory/provider wiring, API entrypoints, fixtures, and shared types before falling back to text search.

## Required Inference
For features infer wiring, validation, tests, docs, config, rollback. For behavior changes infer callers, compatibility, tests, error behavior, observability. For existing Proc/Processor use infer data-source semantics and old/new behavior tests.
