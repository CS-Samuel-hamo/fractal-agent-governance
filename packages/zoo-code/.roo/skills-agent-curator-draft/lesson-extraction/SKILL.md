---
name: lesson-extraction
description: Extract structured lesson candidates from events, postmortems, repeated review findings, and gate failures without approving governance changes.
version: 3.6.0
scope: global
applies_to: agent-integrator
last_updated: 2026-05-30
deprecated_by: ""
---

## Inputs
- event or postmortem
- run id and branch id
- failure type and severity
- recurrence evidence

## Output
Draft `.zoo-agent/lessons/<lesson-id>.json` and update lesson index. Keep status `candidate` unless GPT curator has approved it.

## Boundaries
Do not modify `.roo/rules*`, `.roo/skills*`, commands, scripts, model routing, security policy, or human exception policy. Do not approve lessons.
