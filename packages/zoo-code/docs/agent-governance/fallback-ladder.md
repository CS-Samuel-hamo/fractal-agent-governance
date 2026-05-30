# Fallback Ladder

When fractal decomposition cannot make progress, automatic splitting stops and `/fallback` selects one bounded option:
- continue: only when evidence shows convergence
- re_scope: reduce scope while preserving root goal intent
- research_spike: answer unknowns before implementation
- redesign: return to planner/architect for a new approach
- de_scope: explicitly remove lower-value requirements
- human_decision: ask for product/risk tradeoff
- abort_archive: stop and preserve evidence

Fallback reports live under `.zoo-agent/fallback/`. DeepSeek may draft; GPT or human decides options that change scope, risk, design, or abort status.
