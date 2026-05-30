# After: Governed Completion

The governed runtime records the field as a contract change and expands the work into explicit obligations.

Completed:

- `BranchSummaryDTO` includes optional `blockedReason`.
- Mapper copies `blockedReason` from the branch state source.
- API response fixture includes blocked and unblocked branches.
- Behavior tests cover present, null, and absent values.
- Compatibility rule keeps existing clients valid.

Classified:

- UI consumer: `maybe`, because the fixture does not include a UI package.
- Schema/validator: `maybe`, because schema presence must be discovered.
- Database migration: `not_applicable`, because the toy source is already branch state.
- Rollback note: `deferred` until release packaging.
- Multiple blocker semantics: `escalated` for product decision.

The important result is not more work for its own sake. The result is a visible ledger of what must be done, what might be needed, what is not applicable, what is deferred, and what requires human decision.
