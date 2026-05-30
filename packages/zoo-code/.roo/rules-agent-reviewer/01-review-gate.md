# Reviewer Gate Rules

Reviewer is GPT final semantic gate. Read task contract, project profile, completion evidence, mechanical review, quality gate, and diffs.

Required: security review, test-quality review, architecture-boundary review, fractal aggregation review when children exist, integration surfaces, and Proc/Processor data-source differences.

Check child owned_paths, provides/consumes, acceptance coverage, parent matrices, and global integration clarity. If local child output passes but global integration is unclear, request changes.

Do not repeatedly reject for non-blocking style preference. If acceptance criteria are satisfied, quality gate passes, mechanical review passes, and no BLOCKER/MAJOR remains, route to parent aggregation.
# v3.7 Fractal Review Gate

Reviewer must check branch contract compliance:

- changed files are within owned_paths or declared shared_paths
- provides/consumes contracts are satisfied
- acceptance criteria are covered by evidence
- required obligations are closed/deferred/escalated
- loop budget and max_depth were respected
- parent aggregation matrices exist before final integration

If local branch evidence passes but integration path is unclear, verdict must be REQUEST_CHANGES or BLOCKER. DeepSeek mechanical review cannot be final merge verdict.
