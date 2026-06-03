# Parallel Denial Reasons

Standard denial reasons:

- `owned_paths_overlap`
- `shared_resource_conflict`
- `provides_contract_unstable`
- `consumes_unstable_provider`
- `high_or_critical_risk`
- `security_auth_payment_pii_migration`
- `missing_acceptance_criteria`
- `missing_verification_plan`
- `missing_worktree_isolation`
- `resource_lock_conflict`
- `parent_aggregation_missing`
- `branch_not_leaf`
- `branch_status_not_executable`
- `user_redirect_pending`
- `test_strategy_unknown`
- `data_source_semantics_unknown`
- `architecture_boundary_unknown`

Every denial should include blocking resources, blocking dependencies, and how to make the work parallel-safe.
