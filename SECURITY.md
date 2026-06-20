# Security

This project is local-alpha software. Do not use it as a production deployment, release, or secrets-management system.

## Boundaries

- Do not read or print `.env`, credentials, API keys, tokens, private keys, provider profiles, or secret stores.
- Do not run automatic merge, push, deploy, release, or production database migration.
- Do not run `git reset --hard`, destructive clean commands, or unreviewed worktree deletion.
- Keep `CODEX_HOME` outside business project source and outside commits.

## Reporting

Open a private security report with:

- affected command or script
- reproduction steps using a temporary project
- expected safe behavior
- observed unsafe behavior

Do not include real secrets in reports.
