# Codex Backend Risk Model

The CLI runtime treats Codex CLI as an execution backend, not as a guaranteed stable control plane.

The runtime records Codex risks once in `.zoo-agent/backend/codex-backend-profile.json` and lets task routing consume that cached profile. Fast path must stay light: it reads the profile and cached health instead of re-running long checks for every task.

Known risks tracked in the profile:

- local_command_execution_risk
- full_access_danger
- sandbox_complexity
- network_access_risk
- windows_sandbox_fragility
- wsl_windows_path_split
- cloud_model_capacity
- timeout_or_slow_thinking
- context_compaction_loss
- agents_md_drift
- config_precedence_complexity
- mcp_experimental_surface
- auth_data_policy_complexity
- install_update_supply_chain_risk
- token_cost_uncertainty

Backend failure is not task failure. Timeout, stream disconnect, capacity, sandbox spawn, and local configuration failures must be routed to dry-run/manual task pack or human remediation instead of being counted as delivery failure.
