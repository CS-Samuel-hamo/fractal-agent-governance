# Codex Worker

Codex CLI is the execution backend.

It is responsible for:

- executing bounded code tasks
- generating patches
- producing worker output
- allowing the harness to run scope guard and tests

It is not responsible for:

- planning
- orchestration
- final merge decisions
- deployment or release

Keep `CODEX_HOME` outside business project source and do not commit it.
