---
name: proc-adapter-variation
description: Handle requirements where an existing Proc/Processor/Handler class should be reused but one segment must read from a different data source.
version: 3.6.0
scope: global
applies_to: agent-executor
last_updated: 2026-05-30
deprecated_by: ""
---

# Proc Adapter Variation Skill
Use when a task mentions existing `Proc*`, `Processor*`, `Handler*`, or service reuse with a changed data source, context, or upstream input.

## Anti-Pattern
Do not copy the existing processor and change a few lines without tests. Do not ignore the data-source variation.

## Preferred Designs
1. Provider Injection
2. Source Selector Parameter
3. Adapter/Wrapper
4. Pure Helper Extraction
5. Explicit Fork only when state, side effects, or lifecycle differ materially

## Required Evidence
Existing behavior understood, data-source difference represented in code, tests cover old and new source, callers and registrations updated.
