# Core Agent Contract

These rules apply to every mode.

## Primary Objective
Maintain project coherence. A correct local patch that leaves interfaces, registration, tests, branch state, parent summaries, or self-evolution records inconsistent is incomplete.

## Work Classification
Before acting, classify the task:
- `ASK`: explanation only; no edits.
- `PLAN`: produce task contract; no product code edits.
- `IMPLEMENT`: code/docs/config edits after a contract exists.
- `REVIEW`: inspect diff and issue verdict; source read-only.
- `INTEGRATE`: merge/reconcile approved work.
- `BRANCH-MANAGE`: update branch state, child tasks, or summaries.
- `CURATE`: evolve rules/skills/templates based on postmortem evidence.

## Implicit Agent Run Dispatch
In project chat, treat every ordinary user request as `/agent-run <verbatim user request>` even if the slash command is omitted.

Do not pre-classify whether the request is coding, planning, review, explanation, or discussion before routing. `/agent-run` is the default workflow bus and performs classification after dispatch.

Only bypass this default when the user explicitly invokes another slash command or explicitly says not to use `/agent-run`.

If the project has not been bootstrapped, recommend `/agent-bootstrap` or `Agent: Bootstrap Project` before implementation unless the user explicitly requests a quick one-off.

## Mandatory Stop Conditions
Stop and escalate when:
1. Requirements conflict with existing architecture.
2. A data-source variation is ambiguous.
3. The change requires cross-branch API semantics.
4. Security, migration, billing, authorization, or destructive data changes are involved and the contract is silent.
5. Required test infrastructure is missing or broken.
6. A governance change would weaken review/version/safety controls.

## Evidence Standard
Claims must be grounded in repository evidence: file paths, symbols, tests, diagnostics, command output, review finding, or postmortem event.
