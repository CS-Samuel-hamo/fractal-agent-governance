# Executor Benchmark Policy

Executor benchmark runs compare Zoo, DeepSeek, Codex CLI, GPT, and hybrid paths under consistent cases and metrics.

Metrics:

- wall time
- tool call count
- changed file count
- scope violation count
- tests pass
- quality gate pass
- review blocker count
- manual intervention count
- architecture drift
- final status
- executor used

Benchmarks are governance evals. They are not required after every ordinary `/agent-run`.
