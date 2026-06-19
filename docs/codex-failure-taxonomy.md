# Codex Failure Taxonomy

Failure categories are split so backend instability does not pollute task delivery metrics.

P0 backend blockers:

- codex_not_installed
- codex_not_logged_in
- codex_home_unavailable
- disk_full
- trusted_directory_rejected
- sandbox_spawn_failed
- windows_sandbox_failed
- permission_denied
- config_invalid

Execution failures:

- timeout
- no_output_timeout
- response_stream_disconnected
- model_capacity
- model_error
- network_unavailable
- command_failed
- output_last_message_missing
- subprocess_spawn_failed

Governance failures:

- scope_violation
- denied_files_touched
- no_delivery
- unsafe_delivery
- tests_failed
- delivery_gate_failed

Context failures:

- ambiguous_task
- missing_goal
- missing_project_profile
- stale_agents_md
- conflicting_instructions
- context_compaction_suspected

Rules:

- Backend failure is not task failure.
- Scope violation means governance worked.
- No delivery is a task delivery failure, not backend failure.
- Timeout, capacity, and stream disconnect should retry or fall back to dry-run/manual task pack.
- Sandbox/full-access/network issues require configuration remediation, not automatic privilege escalation.
