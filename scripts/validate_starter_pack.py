#!/usr/bin/env python3
from pathlib import Path
import sys
root = Path(__file__).resolve().parents[1]
required = [
 'PROMPT_FOR_CODEX_APP.md','README_EXECUTION_STEPS.md','CHECKLIST.md',
 '.roo/commands/agent-setup.md','.roo/commands/agent-bootstrap.md','.roo/commands/agent-run.md','.roo/commands/codex-task.md','.roo/commands/codex-run.md','.roo/commands/codex-ingest.md','.roo/commands/codex-review.md','.roo/commands/progress.md',
 '.roo/rules/01-ai-native-zoo-entrypoints.md','.roo/rules-agent-orchestrator/01-ai-native-dispatcher.md','.roo/rules-agent-planner/03-fast-path-and-codex-routing.md',
 '.roo/rules-agent-codex-worker/01-codex-task-pack.md','.roo/rules-agent-integrator/03-codex-worker-merge-policy.md','.roo/rules-agent-reviewer/02-ai-native-review.md',
 '.roo/skills-agent-codex-worker/codex-task-pack-generation/SKILL.md','.roo/skills-agent-codex-worker/codex-result-ingestion/SKILL.md',
 'templates/codex/AGENTS.md','templates/codex/TASKS.yaml','templates/codex/ACCEPTANCE.md','templates/codex/CODEX_TASK_PROMPT.md','templates/codex/CODEX_TASK_PROMPT_FAST.md',
 'scripts/runtime_common.py','scripts/agent.py','scripts/set_goal.py','scripts/get_goal.py','scripts/check_goal_alignment.py','scripts/loop_controller.py','scripts/task_classifier.py','scripts/route_task.py','scripts/update_runtime_metrics.py','scripts/init_project_instructions.py','scripts/check_project_map_alignment.py','scripts/runtime_status.py','scripts/rollback_task.py','scripts/reroute_task.py','scripts/runtime_review.py','scripts/detect_task_independence.py','scripts/schedule_parallel_execution.py','scripts/test_cli_runtime_paths.py','scripts/test_cli_local_alpha.py',
 'scripts/check_codex_scope.py','scripts/generate_codex_task_pack.py','scripts/build_task_context.py','scripts/agent_bootstrap.py','scripts/setup_zoo_agent.py','scripts/execution_policy.py','scripts/select_execution_path.py','scripts/run_ai_native_task.py','scripts/summarize_ai_native_run.py','scripts/run_codex_worker.py','scripts/run_optimistic_worker.py','scripts/run_codex_parallel_workers.py','scripts/check_codex_worker_concurrency.py','scripts/manage_resource_locks.py','scripts/check_task_board_consistency.py','scripts/update_risk_register.py','scripts/run_quality_gate.py','scripts/process_merge_queue.py','scripts/collect_codex_result.py','scripts/sync_zoo_entrypoints.py','scripts/smoke_test.py',
 'scripts/run_governance_landing.py',
 'agent.cmd','agent','wrappers/agent.ps1','wrappers/agent.sh',
 'wrappers/run_codex_worker.ps1','wrappers/run_codex_worker.sh','wrappers/run_optimistic_worker.ps1','wrappers/run_optimistic_worker.sh','wrappers/run_ai_native_task.ps1','wrappers/run_ai_native_task.sh',
 'docs/CLI_FIRST_AGENT_RUNTIME.md','docs/AI_NATIVE_EXECUTION_LOOP.md','docs/USAGE.md','docs/ZOO_COMMAND_ENTRYPOINTS.md','docs/ARCHITECTURE_FEEDBACK_HARDENING.md','docs/MACRO_RESEARCH_FIELD_FEEDBACK.md','docs/UNIFIED_KIT_OPERATING_MODEL.md','docs/FIELD_FEEDBACK_INTEGRATION_MATRIX.md','docs/VIBE_CODING_CROSS_VALIDATION.md','docs/CODEX_PARALLEL_WORKERS.md','docs/GOVERNANCE_CLOSURE.md'
]
missing = [p for p in required if not (root/p).exists()]
if missing:
    print('Missing:')
    for m in missing: print(' -', m)
    sys.exit(1)
print('starter pack OK')
