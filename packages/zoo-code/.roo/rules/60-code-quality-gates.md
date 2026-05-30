# Code Quality Gates

Executor completion must provide completion evidence. Record test, lint, typecheck, and build commands and results. If a command cannot be discovered, write `unknown`; never invent command evidence.

Reviewer must read quality gate results. Integrator may merge only gate pass or documented human exception.

Escalate to human review for auth, authorization, payment, PII, migrations, production config, destructive commands, security controls, or broad shared modules.
