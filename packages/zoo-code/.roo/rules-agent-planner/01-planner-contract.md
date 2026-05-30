# Planner Mode Rules

Planner mode must convert vague user intent into implementation contracts that weak executor models can follow without inference.

## Required Detail Level
A planner task is incomplete unless it specifies exact behavioral change, analogous existing features, surfaces to update, negative requirements, compatibility constraints, expected data source for each logic segment, and observable acceptance criteria.

## Delegation Prompt Shape
```markdown
Task: <one-line goal>
Context: <why this exists>
Files to inspect first: <paths or search terms>
Existing patterns to follow: <symbols/features>
Must update: <integration surfaces>
Must not change: <non-goals>
Data-source constraints: <explicit>
Acceptance criteria: <numbered>
Verification: <commands/checks>
Return format: Completion Evidence
```
