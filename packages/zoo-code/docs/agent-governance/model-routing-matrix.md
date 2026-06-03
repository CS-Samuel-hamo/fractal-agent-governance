# Model Routing Matrix

| Phase | Visible Zoo mode | Model profile | Permissions | Main artifact |
| --- | --- | --- | --- | --- |
| Workflow routing | `agent-orchestrator` | GPT for final routing; DeepSeek may draft status/profile summaries | read + governance state | run-ledger, executor-selection, bootstrap/readiness |
| Planning / architecture / branch governance | `agent-planner` | GPT final; DeepSeek may draft low-risk contracts | read + governance artifacts | implementation contract, branch plan, obligation/test strategy |
| Execution / Codex Worker | `agent-executor` | DeepSeek or Codex for bounded implementation | read/edit/command | diff, tests, Codex Task Pack, completion evidence |
| Debug / review / quality gate | `agent-reviewer` | GPT final; DeepSeek may draft mechanical checks | read/command + review artifacts | review report, quality gate, scope guard verdict |
| Integration / release / governance evolution | `agent-integrator` | GPT final; DeepSeek may draft summaries/proposals | read/edit/command | merge evidence, release readiness, lesson/governance proposal |

Retired visible modes are internal capabilities now: project profiler, plan drafter, branch clerk, branch manager, mechanical reviewer, integration clerk, curator draft, curator, and codex worker.
