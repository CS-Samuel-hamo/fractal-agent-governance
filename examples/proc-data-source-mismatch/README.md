# Demo 3: Proc/Data Source Mismatch

This demo shows why "reuse the existing proc" is not always safe.

Task:

> Use existing ProcBranchSummary, but one segment must read from live branch-state instead of cached branch-state.

The governed runtime detects that the requested behavior changes the data source semantics. It creates an obligation instead of blindly calling the existing procedure.

The correct path is to choose a source selector, adapter, or provider injection pattern, then test old-source and new-source behavior separately.

All names are toy names and do not refer to a real system.
