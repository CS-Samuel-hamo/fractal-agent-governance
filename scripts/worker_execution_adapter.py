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


def execute_routed_worker(project: Path, *, action: dict[str, Any], routing_decision: dict[str, Any], step_number: int) -> dict[str, Any]:
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
