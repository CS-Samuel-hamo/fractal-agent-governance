# Self-Evolution Governance

The governance system may evolve, but only through evidence-bound corrections.

## Allowed Evolution Targets
- `.roo/rules/**`
- `.roo/rules-{modeSlug}/**`
- `.roo/skills-{modeSlug}/**`
- `AGENTS.md`
- `.roomodes`
- `docs/agent-governance/**`
- governance validation scripts

## Forbidden Direct Evolution
- Do not allow execution agents to directly rewrite governance rules after their own failure.
- Do not use a single anecdote to overfit broad rules unless the risk is severe.
- Do not add vague rules such as “be careful” or “think harder”. Rules must create observable behavior.
- Do not weaken review, rollback, checkpoint, worktree, security, data-source, or integration-surface gates without explicit human approval.

## Evidence Required
Every governance change must cite at least one review finding, failed check/test, user correction, branch drift event, missed integration surface, duplicated logic discovery, or postmortem record.

## Evolution Loop
1. Observe event.
2. Classify failure.
3. Determine root cause.
4. Decide intervention type: rule, skill, template, checklist, script, model routing, or branch protocol.
5. Apply smallest effective governance patch.
6. Add a regression prompt/check.
7. Review the governance patch.
8. Track recurrence.
