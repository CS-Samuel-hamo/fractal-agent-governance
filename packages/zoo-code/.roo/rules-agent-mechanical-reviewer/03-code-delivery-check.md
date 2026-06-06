# Code Delivery Check

Mechanical review must check:

- `code-delivery-gate.json` exists for coding branches
- implementation queue item status is reviewable
- no doc-only completion for coding tasks
- scope guard passed or has precise blocker
- tests result exists or unknown reason is recorded
- Codex result was collected when a Codex task pack was run
- expected artifacts exist or missing artifacts are blockers

If a coding branch has only documentation and no valid no-code reason, return
`DOC_ONLY_NOT_ACCEPTED`.
