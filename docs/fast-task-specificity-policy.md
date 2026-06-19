# Fast Task Specificity Policy

Fast path requires a small, clear task before actual execution.

The specificity check looks for:

- an explicit file or directory
- a clear modification intent
- an acceptance cue
- no high-risk words
- no architecture decision requirement

Ambiguous tasks are not executed by default:

- `fix README`
- `improve docs`
- `optimize code`
- `clean up project`

Dry-run result: `NEEDS_CLARIFICATION`.
Non-interactive actual run: `no_execution`, with no Codex call.
Interactive mode should ask at most three clarifying questions.

`fix typo in README` is allowed as a bounded probe. If no typo is found, the worker must return
`no_op_with_evidence`; a zero return code with no diff and no evidence is `no_delivery`.

Users may pass `--allow-ambiguous-fast` to intentionally try an ambiguous fast task, but the
delivery gate still applies.
