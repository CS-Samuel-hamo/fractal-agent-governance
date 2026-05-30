# Improve GitHub Action validation

Labels: `github-action`, `validation`

## Goal

Improve the lightweight GitHub Action without adding API keys or heavy dependencies.

## Ideas

- Check issue template YAML syntax.
- Check eval case required fields.
- Check generated docs links.
- Add secret-pattern scanning that reports only file path and type.

## Acceptance Criteria

- Action remains lightweight.
- No external credentials are required.
- No secrets or matched values are printed.
- `python scripts/validate-open-source-package.py` still passes locally.

## Non-goals

- Do not call model APIs.
- Do not install unnecessary dependencies.
- Do not publish artifacts externally.
