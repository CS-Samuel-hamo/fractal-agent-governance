# Metrics Policy

Each run appends `.zoo-agent/metrics/run-metrics.jsonl` with ids, task type, model route, fractal depth, branch count, obligation counts, quality gate status, review verdict, rework loops, escalation/fallback/human gate use, open risks, final status, estimated GPT calls, estimated DeepSeek calls, and timestamps.

Metrics must not contain secrets or business-sensitive prose. They measure routing effectiveness, implicit obligation discovery, fractal depth, rework, fallback rate, and quality gate pass rate.
