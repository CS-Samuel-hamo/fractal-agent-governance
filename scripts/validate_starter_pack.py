#!/usr/bin/env python3
from pathlib import Path
import sys
root = Path(__file__).resolve().parents[1]
required = [
 'README.md','INSTALL.md','QUICKSTART.md','EXAMPLES.md','ARCHITECTURE.md','CLI_REFERENCE.md','BACKEND_PLUGINS.md','RELEASE_NOTES_v0.9.1-alpha.md','PROMPT_FOR_CODEX_APP.md','README_EXECUTION_STEPS.md','CHECKLIST.md',
 '.roo/commands/agent-setup.md','.roo/commands/agent-bootstrap.md','.roo/commands/agent-run.md','.roo/commands/codex-task.md','.roo/commands/codex-run.md','.roo/commands/codex-ingest.md','.roo/commands/codex-review.md','.roo/commands/progress.md',
 '.roo/rules/01-ai-native-zoo-entrypoints.md','.roo/rules-agent-orchestrator/01-ai-native-dispatcher.md','.roo/rules-agent-planner/03-fast-path-and-codex-routing.md',
 '.roo/rules-agent-codex-worker/01-codex-task-pack.md','.roo/rules-agent-integrator/03-codex-worker-merge-policy.md','.roo/rules-agent-reviewer/02-ai-native-review.md',
 '.roo/skills-agent-codex-worker/codex-task-pack-generation/SKILL.md','.roo/skills-agent-codex-worker/codex-result-ingestion/SKILL.md',
 'templates/codex/AGENTS.md','templates/codex/TASKS.yaml','templates/codex/ACCEPTANCE.md','templates/codex/CODEX_TASK_PROMPT.md','templates/codex/CODEX_TASK_PROMPT_FAST.md',
 'scripts/runtime_common.py','scripts/agent.py','scripts/set_goal.py','scripts/get_goal.py','scripts/check_goal_alignment.py','scripts/loop_controller.py','scripts/update_loop_state.py','scripts/check_loop_convergence.py','scripts/task_classifier.py','scripts/route_task.py','scripts/pipeline_planner.py','scripts/pipeline_executor.py','scripts/pipeline_verifier.py','scripts/pipeline_loop.py','scripts/pipeline_authority_check.py','scripts/pipeline_runtime_benchmark.py','scripts/execution_result_model.py','scripts/execution_retry_controller.py','scripts/execution_level_splitter.py','scripts/execution_fallback_router.py','scripts/execution_health_scoring.py','scripts/execution_interface.py','scripts/backend_registry.py','scripts/codex_backend_plugin.py','scripts/mock_backend_plugin.py','scripts/runtime_core.py','scripts/test_pipeline_runtime.py','scripts/test_pipeline_authority.py','scripts/test_execution_resilience.py','scripts/test_runtime_productization.py','scripts/test_semantic_decoupling.py','scripts/test_product_alpha.py','scripts/test_product_surface_hardening.py','scripts/test_ux_simplification.py','scripts/update_runtime_metrics.py','scripts/init_project_instructions.py','scripts/check_project_map_alignment.py','scripts/runtime_status.py','scripts/rollback_task.py','scripts/reroute_task.py','scripts/runtime_review.py','scripts/detect_task_independence.py','scripts/schedule_parallel_execution.py','scripts/capture_task_baseline.py','scripts/compare_task_baseline.py','scripts/check_delivery_outcome.py','scripts/check_fast_path_gate.py','scripts/check_task_specificity.py','scripts/check_project_readiness.py','scripts/bootstrap_project.py','scripts/codex_exec_adapter.py','scripts/check_codex_worker_health.py','scripts/detect_codex_backend_profile.py','scripts/check_codex_backend_health.py','scripts/classify_codex_failure.py','scripts/render_codex_backend_report.py','scripts/test_codex_worker_stability.py','scripts/test_codex_backend_risk_model.py','scripts/test_goal_loop_runtime.py','scripts/test_cli_runtime_paths.py','scripts/test_cli_local_alpha.py','scripts/test_cli_real_usage_alpha.py',
 'scripts/check_codex_scope.py','scripts/generate_codex_task_pack.py','scripts/build_task_context.py','scripts/agent_bootstrap.py','scripts/setup_zoo_agent.py','scripts/execution_policy.py','scripts/select_execution_path.py','scripts/run_ai_native_task.py','scripts/summarize_ai_native_run.py','scripts/run_codex_worker.py','scripts/run_optimistic_worker.py','scripts/run_codex_parallel_workers.py','scripts/check_codex_worker_concurrency.py','scripts/manage_resource_locks.py','scripts/check_task_board_consistency.py','scripts/update_risk_register.py','scripts/run_quality_gate.py','scripts/process_merge_queue.py','scripts/collect_codex_result.py','scripts/sync_zoo_entrypoints.py','scripts/smoke_test.py',
 'scripts/run_governance_landing.py',
 'agent.cmd','agent','wrappers/agent.ps1','wrappers/agent.sh',
 'wrappers/run_codex_worker.ps1','wrappers/run_codex_worker.sh','wrappers/run_optimistic_worker.ps1','wrappers/run_optimistic_worker.sh','wrappers/run_ai_native_task.ps1','wrappers/run_ai_native_task.sh',
 'docs/README.md','docs/product-mind-model.md','templates/codex/config.safe.toml.example','templates/codex/rules.safe.example'
]
missing = [p for p in required if not (root/p).exists()]
if missing:
    print('Missing:')
    for m in missing: print(' -', m)
    sys.exit(1)
print('starter pack OK')
