# No Delivery Policy

`no_delivery` means Codex or another worker ran but did not produce a business diff that satisfies the task type.

Examples:

- route is `fast`, task type is coding/docs/edit, and no business files changed
- only `.zoo-agent/**` runtime evidence changed
- only generated cache files changed
- coding task changed only documentation
- docs task changed no README/docs file

`no_delivery` is not mergeable, even if the worker return code is zero and the scope guard passes.

Valid no-op requires `no_op_with_evidence`:

- the final message clearly says why no change was needed
- the message names checked files or directories
- the explanation is specific, not generic

Recommended recovery:

- clarify the task
- name the target file or exact change
- rerun a dry-run
- inspect the Codex final message
