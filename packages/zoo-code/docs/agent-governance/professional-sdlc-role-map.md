# Professional SDLC Role Map

This pack maps professional software delivery roles to bounded agent behavior, command artifacts, rules, and gates. Human ceremonies are not copied when an artifact or gate gives stronger evidence.

| Human Role | Agent/System Replacement | Final Authority | Required Artifacts |
| --- | --- | --- | --- |
| Product Manager | `/goal`, product intake template, goal coverage gate | Human or GPT planner for ambiguous tradeoffs | goal contract, success criteria, non-goals, fallback policy |
| Engineering Manager | orchestrator run state, loop budget, status board | GPT orchestrator for routing; human for staffing/business priority | run ledger, status.json, loop-state.json |
| Program / Delivery Manager | `/status`, delivery board, dependency/risk matrices | GPT branch-manager for cross-branch decisions | status.json, dependency matrix, integration order |
| Tech Lead | planner contract, branch-manager decomposition, reviewer final verdict | GPT planner/branch-manager/reviewer | implementation contract, branch tree, obligation ledger |
| Architect | ADR gate, architecture review policy | GPT architect/reviewer final decision; human for strategic tradeoffs | ADR, architecture review, rollback condition |
| Developer | DeepSeek executor on bounded work | GPT planner defines contract; GPT reviewer checks semantics | changed files, completion evidence, tests, obligation ledger |
| QA Engineer | test strategy planning, test adequacy review, quality gate | GPT reviewer for final adequacy | test plan, quality gate, coverage mapping |
| Security Engineer | security gate, threat model, human exception policy | GPT security review or human high-risk approval | threat model, security checklist, exception record |
| Release Manager | `/release`, release readiness gate | GPT integrator; human for high-risk release | release readiness report, rollback plan, changelog |
| SRE / Ops | operational readiness gate, runbook, observability checklist | GPT reviewer/integrator for final readiness | runbook, metrics/logging/tracing checklist |
| Incident Commander | `/incident`, postmortem template, curator event | Human or GPT curator final approval | incident record, timeline, mitigation, regression prompt |
| Documentation Owner | docs obligation category and release note check | GPT reviewer when public behavior changes | docs diff, release note, migration guide |
| Data / Analytics Owner | metrics policy and data classification gate | Human/GPT for data risk decisions | data classification, metrics plan, PII review |

## Roles That Do Not Need To Be Copied

Do not recreate daily standup, manual weekly reports, status sync meetings, manual follow-up chasing, repeated checklist review, or manual copying of release checklists. Replace them with machine-readable run artifacts, status summaries, gates, and final decision records.

## Human Judgments That Must Not Be Fully Automated

Product tradeoffs, architecture tradeoffs, security risk acceptance, release risk acceptance, requirement conflict arbitration, human exceptions, and final governance rule approval require GPT final decision and may require human gate.

## Authority Rules

DeepSeek V4 Flash may draft profiler, executor, clerk, mechanical review, status/risk, and obligation discovery outputs. It cannot approve its own output, close escalations, accept human exceptions, or make final architecture/security/release/governance decisions.
