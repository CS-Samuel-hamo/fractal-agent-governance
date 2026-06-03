# Agent Rules

- Work only within assigned task scope.
- Do not modify secrets, .env, credentials, production config.
- Do not change architecture unless explicitly approved.
- Do not add dependencies unless explicitly approved.
- Do not change database schema unless explicitly approved.
- Do not change auth/security/public API unless explicitly approved.
- Do not run git push.
- Do not run git reset --hard.
- Do not delete files unless explicitly instructed.
- In Zoo/Roo project chat, route every ordinary user request through /agent-run even when the slash command is omitted.
- If ambiguous, stop and ask.
- Before finishing, run scope guard and relevant tests.
