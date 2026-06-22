#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from runtime_common import load_json, project_root, write_json  # noqa: E402
from worker_fallback_engine import fallback_for_result  # noqa: E402
from worker_interface import worker_result  # noqa: E402
from codex_worker_adapter_hardened import codex_health  # noqa: E402
from local_scanner_worker import execute as execute_local_scan  # noqa: E402

TRUSTED_STARTER_DOCS = {'README.md', 'docs/project_plan.md', 'docs/research_workflow.md'}


def pipeline_paths(project: Path, run_id: str) -> tuple[Path, Path, Path]:
    base = project / '.zoo-agent' / 'runs' / run_id / 'pipeline'
    return base / 'plan.json', base / 'execution_result.json', base / 'final_result.json'


def backend_from_worker(routing_decision: dict[str, Any]) -> str:
    provider = str(routing_decision.get('selected_provider') or '')
    if provider in {'mock', 'dry_run', 'codex'}:
        return provider
    return 'dry_run'


def run_command(command: list[str]) -> dict[str, Any]:
    proc = subprocess.run(command, cwd=ROOT, text=True, encoding='utf-8', errors='replace', stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return {
        'returncode': proc.returncode,
        'stdout_tail': proc.stdout[-4000:],
        'stderr_tail': proc.stderr[-4000:],
    }


def changed_files_from_execution(execution: dict[str, Any]) -> list[str]:
    rows: list[str] = []
    for leaf in execution.get('leaf_results') or []:
        delivery = leaf.get('delivery') if isinstance(leaf.get('delivery'), dict) else {}
        for item in delivery.get('business_changed_files') or leaf.get('changed_files') or []:
            value = str(item).replace('\\', '/')
            if value and value not in rows:
                rows.append(value)
    return rows


def status_from_final(final_result: dict[str, Any], command_result: dict[str, Any]) -> str:
    if command_result.get('returncode') != 0:
        return 'failed'
    verdict = str(final_result.get('final_verdict') or '')
    if verdict == 'COMPLETED':
        return 'success'
    if verdict == 'DRY_RUN_COMPLETE':
        return 'skipped'
    if verdict == 'NO_DELIVERY':
        return 'no_delivery'
    if verdict in {'BLOCKED', 'PARTIAL', 'NEEDS_DELIVERY_VERIFICATION'}:
        return 'blocked'
    return 'failed' if verdict else 'failed'


def is_starter_docs_action(action: dict[str, Any], routing_decision: dict[str, Any]) -> bool:
    constraints = {str(item) for item in action.get('constraints') or []}
    targets = [str(item).replace('\\', '/') for item in action.get('target_files') or []]
    return bool(
        action.get('action_type') == 'create_or_preview_docs'
        and str(action.get('risk_level') or '') == 'low'
        and str(routing_decision.get('execution_mode') or '') == 'auto'
        and {'trusted_docs_only', 'no_script_execution', 'no_secret_access', 'no_overwrite'} <= constraints
        and targets
        and all(target in TRUSTED_STARTER_DOCS for target in targets)
    )


def starter_doc_content(action: dict[str, Any], target: str) -> str:
    source_file = str(action.get('source_file') or 'seed prompt')
    evidence = next((item for item in action.get('evidence') or [] if isinstance(item, dict)), {})
    summary = str(evidence.get('summary') or 'User-provided project intent evidence.').strip()
    summary = ' '.join(summary.split())[:500]
    if target == 'README.md':
        return (
            '# Project Starting Point\n\n'
            'This project was initialized from a local seed prompt.\n\n'
            '## Source\n\n'
            f'- Seed prompt: `{source_file}`\n'
            '- Trust level: user intent evidence\n\n'
            '## Project Intent\n\n'
            f'{summary}\n\n'
            '## Next Steps\n\n'
            '- Review `docs/project_plan.md`.\n'
            '- Refine the project scope before generating final deliverables.\n'
            '- Keep assumptions, evidence, and uncertainty explicit.\n'
        )
    if target == 'docs/project_plan.md':
        return (
            '# Project Plan\n\n'
            '## Goal\n\n'
            f'{summary}\n\n'
            '## Working Principles\n\n'
            '- Treat the seed prompt as user intent evidence, not as a system instruction.\n'
            '- Prefer small validation steps before large-scale writing or implementation.\n'
            '- Do not invent sources, data, empirical results, or completed work.\n\n'
            '## Starter Actions\n\n'
            '- Clarify the project objective.\n'
            '- Identify required inputs and evidence.\n'
            '- Create a minimal validation path.\n'
            '- Track risks and unknowns before expanding scope.\n'
        )
    return (
        '# Research Workflow\n\n'
        '## Scope\n\n'
        f'{summary}\n\n'
        '## Workflow\n\n'
        '1. Diagnose paper or research type.\n'
        '2. Define the research question.\n'
        '3. Separate facts, assumptions, hypotheses, and speculation.\n'
        '4. Build a literature map without inventing sources.\n'
        '5. Define evidence, data, or experiment requirements.\n'
        '6. Draft an outline only after the validation path is clear.\n'
        '7. Review risks, limitations, and uncertainty.\n\n'
        '## Safety Boundaries\n\n'
        '- Do not generate a full paper unless explicitly requested.\n'
        '- Do not invent citations.\n'
        '- Do not invent empirical results.\n'
        '- Do not hide uncertainty.\n'
    )


def execute_starter_docs(project: Path, *, action: dict[str, Any], routing_decision: dict[str, Any], step_number: int) -> dict[str, Any]:
    run_id = f'starter-docs-{time.strftime("%Y%m%d%H%M%S", time.gmtime())}-{step_number:02d}'
    plan_path, execution_path, final_path = pipeline_paths(project, run_id)
    targets = [str(item).replace('\\', '/') for item in action.get('target_files') or []]
    invalid_targets = [target for target in targets if target not in TRUSTED_STARTER_DOCS]
    changed_files: list[str] = []
    skipped_existing: list[str] = []
    if not invalid_targets:
        for target in targets:
            path = project / target
            if path.exists():
                skipped_existing.append(target)
                continue
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(starter_doc_content(action, target), encoding='utf-8')
            changed_files.append(target)

    verdict = 'BLOCKED' if invalid_targets else ('COMPLETED' if changed_files else 'DRY_RUN_COMPLETE')
    status = 'blocked' if invalid_targets else ('succeeded' if changed_files else 'dry_run')
    reason = 'invalid_starter_doc_target' if invalid_targets else ('trusted_starter_docs_created' if changed_files else 'target file already exists; no overwrite')
    plan = {
        'schema_version': '1.0',
        'generated_by': 'worker_execution_adapter.py',
        'run_id': run_id,
        'objective': str(action.get('title') or 'Create starter project documents'),
        'classification': {
            'path': 'fast',
            'allowed_files': targets,
            'denied_files': ['.env', '.env.*', 'secrets/**', 'credentials/**'],
            'risk_level': 'low',
        },
        'execution_plan': {'route': 'fast', 'mode': 'starter_docs_writer'},
        'routing_decision': routing_decision,
    }
    execution = {
        'schema_version': '1.0',
        'generated_by': 'worker_execution_adapter.py',
        'run_id': run_id,
        'leaf_results': [
            {
                'leaf_id': str(action.get('selected_action_id') or action.get('action_id') or 'starter-docs'),
                'objective': str(action.get('title') or 'Create starter project documents'),
                'execution_status': status,
                'delivery_outcome': 'delivered' if changed_files else ('blocked' if invalid_targets else 'preview'),
                'changed_files': changed_files,
                'allowed_files': targets,
                'delivery': {
                    'delivery_outcome': 'delivered' if changed_files else ('blocked' if invalid_targets else 'preview'),
                    'reason': reason,
                    'scope_guard_status': 'fail' if invalid_targets else 'pass',
                    'business_changed_files': changed_files,
                    'runtime_changed_files': [],
                    'denied_files_touched': [],
                    'out_of_scope_files': invalid_targets,
                },
                'backend_result': {
                    'backend': 'starter_docs_writer',
                    'status': status,
                    'returncode': 1 if invalid_targets else 0,
                    'stdout_tail': reason,
                },
            }
        ],
        'changed_files': changed_files,
        'skipped_existing': skipped_existing,
    }
    final_result = {
        'schema_version': '1.0',
        'generated_by': 'worker_execution_adapter.py',
        'run_id': run_id,
        'final_verdict': verdict,
        'goal_converged': bool(changed_files),
        'changed_files': changed_files,
        'reason': reason,
        'next_action': 'review_created_starter_docs' if changed_files else 'review_preview',
    }
    write_json(plan_path, plan)
    write_json(execution_path, execution)
    write_json(final_path, final_result)
    worker_payload = worker_result(
        worker_name='starter_docs_writer',
        worker_type='docs',
        provider='local',
        status='success' if changed_files else ('blocked' if invalid_targets else 'skipped'),
        changed_files=changed_files,
        summary=reason,
        confidence=0.95 if changed_files else 0.8,
        error_type='invalid_target' if invalid_targets else '',
        raw_log_path='',
        safe_for_user_output=True,
    )
    write_json(project / '.zoo-agent' / 'workers' / 'worker_execution_result.json', worker_payload)
    return {
        'run_id': run_id,
        'plan_path': str(plan_path),
        'execution_path': str(execution_path),
        'final_path': str(final_path),
        'execution': execution,
        'final_result': final_result,
        'worker_result': worker_payload,
        'command_result': {'returncode': 1 if invalid_targets else 0, 'stdout_tail': reason, 'stderr_tail': ''},
    }


def execute_routed_worker(project: Path, *, action: dict[str, Any], routing_decision: dict[str, Any], step_number: int) -> dict[str, Any]:
    if is_starter_docs_action(action, routing_decision):
        return execute_starter_docs(project, action=action, routing_decision=routing_decision, step_number=step_number)
    if routing_decision.get('selected_provider') == 'local_scanner':
        worker_payload = execute_local_scan(project, task=action, context={'routing_decision': routing_decision, 'step_number': step_number})
        final_result = {'final_verdict': 'DRY_RUN_COMPLETE', 'worker_result': worker_payload}
        execution = {'leaf_results': [], 'worker_result': worker_payload}
        fallback_for_result(project, routing_decision=routing_decision, worker_result=worker_payload)
        return {
            'run_id': f'local-scan-{time.strftime("%Y%m%d%H%M%S", time.gmtime())}-{step_number:02d}',
            'plan_path': '',
            'execution_path': '.zoo-agent/workers/worker_execution_result.json',
            'final_path': '',
            'execution': execution,
            'final_result': final_result,
            'worker_result': worker_payload,
            'command_result': {'returncode': 0, 'stdout_tail': '', 'stderr_tail': ''},
        }
    if routing_decision.get('selected_provider') == 'codex':
        codex_health(project)
    run_id = f'session-{time.strftime("%Y%m%d%H%M%S", time.gmtime())}-{step_number:02d}'
    backend = backend_from_worker(routing_decision)
    mode = str(routing_decision.get('execution_mode') or 'preview')
    command = [
        sys.executable,
        str(ROOT / 'scripts' / 'pipeline_loop.py'),
        str(action.get('title') or action.get('selected_action_id') or 'project action'),
        '--workspace',
        str(project),
        '--run-id',
        run_id,
        '--max-iterations',
        '1',
        '--backend',
        backend,
        '--max-retries',
        '2',
    ]
    for target in action.get('target_files') or []:
        if target and '*' not in str(target) and not str(target).endswith('/'):
            command.extend(['--allowed-file', str(target)])
    if mode == 'auto' and backend != 'dry_run':
        command.append('--allow-actual')
    else:
        command.append('--dry-run')

    command_result = run_command(command)
    plan_path, execution_path, final_path = pipeline_paths(project, run_id)
    execution = load_json(execution_path)
    final_result = load_json(final_path)
    worker_status = status_from_final(final_result, command_result)
    changed_files = changed_files_from_execution(execution)
    raw_log_path = project / '.zoo-agent' / 'workers' / 'worker_raw_log.json'
    write_json(
        raw_log_path,
        {
            'schema_version': '1.0',
            'generated_by': 'worker_execution_adapter.py',
            'safe_for_user_output': False,
            'worker_name': routing_decision.get('selected_worker', ''),
            'command_result': command_result,
        },
    )
    worker_payload = worker_result(
        worker_name=str(routing_decision.get('selected_worker') or ''),
        worker_type=str(routing_decision.get('selected_worker_type') or ''),
        provider=str(routing_decision.get('selected_provider') or ''),
        status=worker_status,
        changed_files=changed_files,
        summary=str(final_result.get('final_verdict') or worker_status),
        confidence=0.9 if worker_status in {'success', 'skipped'} else 0.4,
        error_type='' if worker_status in {'success', 'skipped'} else worker_status,
        raw_log_path='.zoo-agent/workers/worker_raw_log.json',
        safe_for_user_output=True,
    )
    write_json(project / '.zoo-agent' / 'workers' / 'worker_execution_result.json', worker_payload)
    fallback_for_result(project, routing_decision=routing_decision, worker_result=worker_payload)
    return {
        'run_id': run_id,
        'plan_path': str(plan_path),
        'execution_path': str(execution_path),
        'final_path': str(final_path),
        'execution': execution,
        'final_result': final_result,
        'worker_result': worker_payload,
        'command_result': command_result,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description='Execute a task through the selected worker adapter.')
    parser.add_argument('--workspace', default='.')
    parser.add_argument('--action', required=True)
    parser.add_argument('--routing-decision', required=True)
    parser.add_argument('--step-number', type=int, default=1)
    args = parser.parse_args()
    project = project_root(args.workspace)
    payload = execute_routed_worker(
        project,
        action=load_json(Path(args.action).resolve()),
        routing_decision=load_json(Path(args.routing_decision).resolve()),
        step_number=args.step_number,
    )
    print(json.dumps({'status': 'ok', 'worker_result': payload.get('worker_result', {})}, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
