# Contributing

This repository is currently `0.4.0-local-alpha`.

## Development Rules

- Use temporary projects for tests.
- Keep changes reviewable and rollback-friendly.
- Do not commit `.codex`, `CODEX_HOME`, caches, temporary smoke repos, or secrets.
- Do not add product-document workflows, dashboards, or new runtime roles unless a design issue explicitly approves them.

## Test Commands

```powershell
python -m py_compile scripts\*.py
python scripts\validate_starter_pack.py
python scripts\test_cli_runtime_paths.py
python scripts\test_cli_local_alpha.py
python scripts\smoke_test.py
```

## Pull Request Checklist

- CLI entrypoints still work.
- Bootstrap remains idempotent.
- Fast path skips heavy governance.
- Parallel path denies unknown independence.
- Rollback defaults to dry-run.
- Public docs contain no personal absolute paths or secrets.
