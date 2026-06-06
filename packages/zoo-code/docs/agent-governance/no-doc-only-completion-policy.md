# No Doc-Only Completion Policy

Coding work is not complete when it only creates or rewrites product documents,
plans, task breakdowns, or architecture suggestions.

## Coding Task Completion

A coding task must satisfy at least one completion condition:

- code diff exists
- test diff exists
- config diff exists
- generated Codex Task Pack exists and execution is pending
- task is explicitly classified as non-coding
- task is blocked with a precise blocker and next action

## Invalid Completion For Coding Tasks

The following are not completion evidence for a coding task:

- product documentation only
- task-board rewrite only
- architecture recommendation only
- planning artifact only
- task decomposition only
- local optimization proposal only
- follow-up backlog only

If a coding task only has documents, run `check-doc-only-completion.py` and
generate or refresh the implementation queue.
