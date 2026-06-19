#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime
import filecmp
import hashlib
import json
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_GLOBAL_ROO = Path.home() / '.roo'
DEFAULT_KIT = DEFAULT_GLOBAL_ROO / 'agent-governance-kit'

COMMAND_COPY_FILES = [
    '.roo/commands/agent-setup.md',
    '.roo/commands/agent-bootstrap.md',
    '.roo/commands/codex-task.md',
    '.roo/commands/codex-run.md',
    '.roo/commands/codex-ingest.md',
    '.roo/commands/codex-review.md',
]

ROO_COPY_FILES = [
    '.roo/rules/01-ai-native-zoo-entrypoints.md',
    '.roo/rules-agent-orchestrator/01-ai-native-dispatcher.md',
    '.roo/rules-agent-planner/03-fast-path-and-codex-routing.md',
    '.roo/rules-agent-codex-worker/01-codex-task-pack.md',
    '.roo/rules-agent-integrator/03-codex-worker-merge-policy.md',
    '.roo/rules-agent-reviewer/02-ai-native-review.md',
    '.roo/skills-agent-codex-worker/codex-task-pack-generation/SKILL.md',
    '.roo/skills-agent-codex-worker/codex-result-ingestion/SKILL.md',
]

KIT_COPY_FILES = [
    'PROMPT_FOR_CODEX_APP.md',
    'CHECKLIST.md',
    'scripts/setup_zoo_agent.py',
    'scripts/validate_starter_pack.py',
    'scripts/smoke_test.py',
    'scripts/runtime_common.py',
    'scripts/agent.py',
    'scripts/set_goal.py',
    'scripts/get_goal.py',
    'scripts/check_goal_alignment.py',
    'scripts/loop_controller.py',
    'scripts/task_classifier.py',
    'scripts/route_task.py',
    'scripts/update_runtime_metrics.py',
    'scripts/init_project_instructions.py',
    'scripts/check_project_map_alignment.py',
    'scripts/runtime_status.py',
    'scripts/rollback_task.py',
    'scripts/reroute_task.py',
    'scripts/runtime_review.py',
    'scripts/build_task_context.py',
    'scripts/agent_bootstrap.py',
    'scripts/execution_policy.py',
    'scripts/select_execution_path.py',
    'scripts/run_ai_native_task.py',
    'scripts/run_optimistic_worker.py',
    'scripts/run_codex_parallel_workers.py',
    'scripts/summarize_ai_native_run.py',
    'scripts/manage_resource_locks.py',
    'scripts/check_task_board_consistency.py',
    'scripts/update_risk_register.py',
    'scripts/run_quality_gate.py',
    'scripts/process_merge_queue.py',
    'scripts/generate_codex_task_pack.py',
    'scripts/run_codex_worker.py',
    'scripts/check_codex_worker_concurrency.py',
    'scripts/collect_codex_result.py',
    'scripts/check_codex_scope.py',
    'scripts/sync_zoo_entrypoints.py',
    'templates/codex/CODEX_TASK_PROMPT_FAST.md',
    'templates/codex/CODEX_TASK_PROMPT.md',
    'templates/codex/AGENTS.md',
    'templates/codex/TASKS.yaml',
    'templates/codex/ACCEPTANCE.md',
    'templates/codex/PROGRESS.md',
    'templates/codex/BLOCKERS.md',
    'docs/CLI_FIRST_AGENT_RUNTIME.md',
    'docs/AI_NATIVE_EXECUTION_LOOP.md',
    'docs/ARCHITECTURE_FEEDBACK_HARDENING.md',
    'docs/MACRO_RESEARCH_FIELD_FEEDBACK.md',
    'docs/UNIFIED_KIT_OPERATING_MODEL.md',
    'docs/FIELD_FEEDBACK_INTEGRATION_MATRIX.md',
    'docs/VIBE_CODING_CROSS_VALIDATION.md',
    'docs/CODEX_PARALLEL_WORKERS.md',
    'docs/GOVERNANCE_CLOSURE.md',
    'docs/USAGE.md',
    'docs/ZOO_COMMAND_ENTRYPOINTS.md',
    'README_EXECUTION_STEPS.md',
    'agent.cmd',
    'agent',
    'wrappers/agent.ps1',
    'wrappers/agent.sh',
    'wrappers/run_codex_worker.ps1',
    'wrappers/run_codex_worker.sh',
    'wrappers/run_optimistic_worker.ps1',
    'wrappers/run_optimistic_worker.sh',
    'wrappers/run_ai_native_task.ps1',
    'wrappers/run_ai_native_task.sh',
]

AGENT_RUN_BLOCK = """## CLI-First Runtime Override

This section supersedes older Zoo-first or dispatcher-first routing instructions below when they conflict.

Runtime resolution:

- Prefer `agent run <input>`.
- If invoking scripts directly and `<workspace>/scripts/route_task.py` exists, use it.
- Otherwise use `C:\\Users\\sheng\\.roo\\agent-governance-kit\\scripts\\route_task.py`.
- If neither exists, stop and report the missing CLI router.

Routing:

- Fast: `agent run --fast <input>` maps to the bounded Codex backend, scope guard, tests, and result collection. No planning, decomposition, product doc expansion, or task splitting.
- Parallel: `agent run --parallel <input>` is allowed only for independent tasks with disjoint conflict keys and separate worktrees/output paths.
- Governed: `agent run --governed <input>` records goal alignment, decomposition, implementation queue, Codex workers, reconciliation, parent aggregation, merge queue evidence, and GPT review.
- Status: `agent status --run-id <run-id>` summarizes run, map, standards, metrics, worktree, and gate state.
- Rollback: `agent rollback --run-id <run-id> --task-id <task-id> --dry-run` inspects managed worktree rollback targets before deletion.
- Reroute: `agent reroute --run-id <run-id> --task-id <task-id> --path <path>` preserves old evidence and launches the selected path again.
- Map: `agent map check` verifies active project-map alignment and generated/runtime path exclusion.
- Review: `agent review --run-id <run-id>` records evidence closure and merge-readiness blockers.

Run status source:

- `.zoo-agent/runs/<run-id>/cli-runtime/<task-id>.json`
- `.zoo-agent/runs/<run-id>/goal-alignment/<task-id>.json`
- `.zoo-agent/runs/<run-id>/loop_state.json`
- `.zoo-agent/metrics/agent-runtime-v4.json`
- `.zoo-agent/runs/<run-id>/executor-selection.json`
- `.zoo-agent/runs/<run-id>/dispatcher-runs/<task-id>.json`
- `.zoo-agent/runs/<run-id>/task-contexts/<task-id>.json`
- `.zoo-agent/runs/<run-id>/ai-native-summary.json`
- `.zoo-agent/runs/<run-id>/task-board-consistency.json`
- `.zoo-agent/runs/<run-id>/risk-register.json`
- `.zoo-agent/runs/<run-id>/quality-gate.json`
- `.zoo-agent/runs/<run-id>/merge-queue-processing.json`
- `.zoo-agent/locks/resource-locks.json`
- `.zoo-agent/runs/<run-id>/runtime-status.json`
- `.zoo-agent/runs/<run-id>/runtime-review.json`
- `.zoo-agent/runs/<run-id>/rollback/<task-id>.json`
- `.zoo-agent/runs/<run-id>/route-audit/<task-id>.json`

Context handling:

- Every CLI task must bind to a `goal_id`.
- `.zoo-agent/goals/<goal-id>.json` is the goal source of truth.
- `.zoo-agent/loop_state.json` prevents infinite planning or optimization loops.
- Project charter, goal contract, project profile, and project map are read-only background unless the user explicitly requests a durable update.

Execution graph:

- `task_classifier.py` emits `fast | parallel | governed` plus independence evidence.
- Backend `executor-selection.json.execution_graph` remains execution evidence.
- Schedule leaves in parallel only when conflict keys do not overlap.

Closure:

- After worker execution, run `check_task_board_consistency.py` and `run_quality_gate.py`.
- Prefer `agent review --run-id <run-id>` for the standard closure bundle.
- Use `agent rollback --run-id <run-id> --task-id <task-id>` only to discard managed worktrees and release task locks.
- `run_quality_gate.py` checks goal-alignment artifacts by default.
- Use `update_risk_register.py` when risks are known.
- Use `process_merge_queue.py` only after quality gate authorization.
- If older sections mention `generate-resource-locks.py`, `check-resource-locks.py`, `generate-branch-schedule.py`, or `schedule-parallel-branches.py`, use `check_codex_worker_concurrency.py`, `run_codex_parallel_workers.py`, and `manage_resource_locks.py` for the current Codex worker bridge.
"""

PROGRESS_BLOCK = """## AI-Native Run Summary

For AI-native dispatcher runs, refresh progress with:

```powershell
$summary = if (Test-Path ".\\scripts\\summarize_ai_native_run.py") { ".\\scripts\\summarize_ai_native_run.py" } else { "C:\\Users\\sheng\\.roo\\agent-governance-kit\\scripts\\summarize_ai_native_run.py" }
python $summary `
  --run-id "<run-id>" `
  --workspace "<workspace>"
```

Read `.zoo-agent/runs/<run-id>/ai-native-summary.json` before retry, decomposition, review, or merge-candidate decisions.

For closure-sensitive decisions, also inspect:

- `.zoo-agent/runs/<run-id>/task-board-consistency.json`
- `.zoo-agent/runs/<run-id>/risk-register.json`
- `.zoo-agent/runs/<run-id>/quality-gate.json`
- `.zoo-agent/runs/<run-id>/merge-queue-processing.json`
- `.zoo-agent/locks/resource-locks.json`
"""

PROJECT_BRIDGE_RULE = """# AI-Native Global Bridge Shim

This project has local `.roo` files, so global Roo/Zoo rules may be shadowed.
This shim preserves local project rules while restoring the CLI-first runtime bridge.

- Use `agent run <input>` as the primary runtime entrypoint.
- Resolve direct script routing from `<workspace>/scripts/route_task.py` first, then `C:\\Users\\sheng\\.roo\\agent-governance-kit\\scripts\\route_task.py`.
- Bind every task to a `goal_id` and inspect goal alignment evidence before review or integration claims.
- Maintain `.zoo-agent/loop_state.json` and escalate to governed/GPT review when the loop diverges.
- Route fast, parallel, and governed work through the CLI runtime; use Codex CLI only as the execution backend.
- Use `agent status`, `agent rollback`, `agent reroute`, `agent map check`, and `agent review` for daily operations instead of ad hoc file inspection.
- Keep project charter, goal contract, project profile, and project map read-only unless the user explicitly requests a durable update.
- Before claiming completion or merge readiness, refresh task-board consistency, risk register, quality gate, and merge queue processing evidence when applicable.
- Treat planner, orchestrator, reviewer, and integrator as governed-path responsibilities, not extra runtime entrypoints.
"""


def marker(name: str) -> tuple[str, str]:
    return f'<!-- BEGIN {name} -->', f'<!-- END {name} -->'


def safe_label(path: Path, max_len: int = 64) -> str:
    text = str(path).replace(':', '').replace('\\', '_').replace('/', '_')
    label = ''.join(ch if ch.isalnum() or ch in '._-' else '_' for ch in text)
    if len(label) <= max_len:
        return label
    digest = hashlib.sha1(label.encode('utf-8')).hexdigest()[:12]
    return f'{label[: max_len - 13]}-{digest}'


def read_text(path: Path) -> str:
    return path.read_text(encoding='utf-8') if path.exists() else ''


def backup_file(path: Path, backup_root: Path, actions: list[dict]) -> None:
    if not path.exists():
        return
    backup_path = backup_root / safe_label(path)
    backup_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, backup_path)
    actions.append({'action': 'backup', 'source': str(path), 'target': str(backup_path)})


def write_with_backup(path: Path, text: str, backup_root: Path, actions: list[dict], dry_run: bool) -> None:
    old = read_text(path)
    if old == text:
        actions.append({'action': 'unchanged', 'target': str(path)})
        return
    actions.append({'action': 'write', 'target': str(path)})
    if dry_run:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    backup_file(path, backup_root, actions)
    path.write_text(text, encoding='utf-8')


def inject_block(path: Path, block_name: str, block: str, backup_root: Path, actions: list[dict], dry_run: bool) -> None:
    begin, end = marker(block_name)
    wrapped = f'{begin}\n{block.rstrip()}\n{end}\n'
    text = read_text(path)
    if begin in text and end in text:
        before = text.split(begin, 1)[0]
        after = text.split(end, 1)[1]
        if after.startswith('\n'):
            after = after[1:]
        new_text = before + wrapped + after
    else:
        if text.startswith('---'):
            parts = text.split('---', 2)
            if len(parts) >= 3:
                new_text = '---' + parts[1] + '---\n\n' + wrapped + '\n' + parts[2].lstrip('\n')
            else:
                new_text = wrapped + '\n' + text
        else:
            new_text = wrapped + '\n' + text
    write_with_backup(path, new_text, backup_root, actions, dry_run)


def copy_file(src_rel: str, target_root: Path, backup_root: Path, actions: list[dict], dry_run: bool) -> None:
    src = ROOT / src_rel
    dst = target_root / src_rel
    if not src.exists():
        actions.append({'action': 'missing_source', 'source': str(src)})
        return
    if dst.exists() and filecmp.cmp(src, dst, shallow=False):
        actions.append({'action': 'unchanged', 'target': str(dst)})
        return
    actions.append({'action': 'copy', 'source': str(src), 'target': str(dst)})
    if dry_run:
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    backup_file(dst, backup_root, actions)
    shutil.copy2(src, dst)


def copy_file_if_missing(src_rel: str, target_root: Path, backup_root: Path, actions: list[dict], dry_run: bool) -> None:
    src = ROOT / src_rel
    dst = target_root / src_rel
    if not src.exists():
        actions.append({'action': 'missing_source', 'source': str(src)})
        return
    if dst.exists():
        if filecmp.cmp(src, dst, shallow=False):
            actions.append({'action': 'unchanged', 'target': str(dst)})
        else:
            actions.append({'action': 'local_override_preserved', 'target': str(dst), 'source': str(src)})
        return
    actions.append({'action': 'copy_missing', 'source': str(src), 'target': str(dst)})
    if dry_run:
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    backup_file(dst, backup_root, actions)
    shutil.copy2(src, dst)


def sync_roo_tree(roo_root: Path, backup_root: Path, actions: list[dict], dry_run: bool) -> None:
    inject_block(roo_root / 'commands' / 'agent-run.md', 'AI_NATIVE_DISPATCHER_OVERRIDE', AGENT_RUN_BLOCK, backup_root, actions, dry_run)
    inject_block(roo_root / 'commands' / 'progress.md', 'AI_NATIVE_PROGRESS_SUMMARY', PROGRESS_BLOCK, backup_root, actions, dry_run)
    for rel in COMMAND_COPY_FILES + ROO_COPY_FILES:
        copy_file(rel, roo_root.parent if rel.startswith('.roo/') else roo_root, backup_root, actions, dry_run)


def sync_kit(kit_root: Path, backup_root: Path, actions: list[dict], dry_run: bool) -> None:
    sync_roo_tree(kit_root / '.roo', backup_root, actions, dry_run)
    for rel in KIT_COPY_FILES:
        copy_file(rel, kit_root, backup_root, actions, dry_run)


def sync_project_roo(project_root: Path, backup_root: Path, actions: list[dict], dry_run: bool) -> None:
    roo_root = project_root / '.roo'
    actions.append({'action': 'project_roo_sync', 'target': str(project_root), 'roo_root': str(roo_root)})
    inject_block(roo_root / 'commands' / 'agent-run.md', 'AI_NATIVE_DISPATCHER_OVERRIDE', AGENT_RUN_BLOCK, backup_root, actions, dry_run)
    inject_block(roo_root / 'commands' / 'progress.md', 'AI_NATIVE_PROGRESS_SUMMARY', PROGRESS_BLOCK, backup_root, actions, dry_run)

    for rel in COMMAND_COPY_FILES:
        copy_file_if_missing(rel, roo_root.parent, backup_root, actions, dry_run)

    write_with_backup(roo_root / 'rules' / '00-ai-native-global-bridge.md', PROJECT_BRIDGE_RULE, backup_root, actions, dry_run)

    for rel in [
        '.roo/skills-agent-codex-worker/codex-task-pack-generation/SKILL.md',
        '.roo/skills-agent-codex-worker/codex-result-ingestion/SKILL.md',
    ]:
        copy_file_if_missing(rel, roo_root.parent, backup_root, actions, dry_run)


def main() -> int:
    ap = argparse.ArgumentParser(description='Sync AI-native Zoo/Roo entrypoints into installed global targets with backups.')
    ap.add_argument('--global-roo', default=str(DEFAULT_GLOBAL_ROO))
    ap.add_argument('--kit-root', default=str(DEFAULT_KIT))
    ap.add_argument('--project-root', action='append', default=[], help='Optional business project root whose local .roo overrides should be patched')
    ap.add_argument('--project-only', action='store_true', help='Patch only --project-root targets; skip global and kit sync')
    ap.add_argument('--backup-root', default='')
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()

    timestamp = datetime.datetime.utcnow().strftime('%Y%m%d%H%M%S')
    backup_root = Path(args.backup_root).resolve() if args.backup_root else DEFAULT_GLOBAL_ROO / 'backups' / f'ai-native-sync-{timestamp}'
    global_roo = Path(args.global_roo).resolve()
    kit_root = Path(args.kit_root).resolve()
    actions: list[dict] = []

    if args.project_only and not args.project_root:
        actions.append({'action': 'missing_project_root', 'reason': '--project-only requires at least one --project-root'})
    if not args.project_only and global_roo.exists():
        sync_roo_tree(global_roo, backup_root / 'global-roo', actions, args.dry_run)
    elif not args.project_only:
        actions.append({'action': 'missing_target', 'target': str(global_roo)})

    if not args.project_only and kit_root.exists():
        sync_kit(kit_root, backup_root / 'agent-governance-kit', actions, args.dry_run)
    elif not args.project_only:
        actions.append({'action': 'missing_target', 'target': str(kit_root)})

    for raw_project in args.project_root:
        project_root = Path(raw_project).resolve()
        if project_root.exists():
            sync_project_roo(project_root, backup_root / 'projects' / safe_label(project_root), actions, args.dry_run)
        else:
            actions.append({'action': 'missing_project_root', 'target': str(project_root)})

    report = {
        'dry_run': args.dry_run,
        'global_roo': str(global_roo),
        'kit_root': str(kit_root),
        'project_roots': [str(Path(item).resolve()) for item in args.project_root],
        'project_only': args.project_only,
        'backup_root': str(backup_root),
        'actions': actions,
    }
    print(json.dumps(report, ensure_ascii=True, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
