#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from runtime_common import load_json, project_root, utc_now, write_json  # noqa: E402


PASSING_TEST_STATUSES = {'passed', 'skipped_with_reason', 'not_applicable'}
ACCEPTED_OUTCOMES = {'delivered', 'no_op_with_evidence'}


def run_delivery_check(project: Path, run_id: str, task_id: str) -> dict[str, Any]:
    command = [
        sys.executable,
        str(ROOT / 'scripts' / 'check_delivery_outcome.py'),
        '--workspace',
        str(project),
        '--run-id',
        run_id,
        '--task-id',
        task_id,
    ]
    proc = subprocess.run(
        command,
        cwd=ROOT,
        text=True,
        encoding='utf-8',
        errors='replace',
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    payload = load_json(project / '.zoo-agent' / 'runs' / run_id / 'delivery-outcome.json')
    payload['_check_returncode'] = proc.returncode
    payload['_check_stdout'] = proc.stdout
    payload['_check_stderr'] = proc.stderr
    return payload


def accepted_tests_status(status: str) -> bool:
    normalized = status or 'not_run'
    return normalized in PASSING_TEST_STATUSES


def build_gate(project: Path, run_id: str, task_id: str, *, output: Path | None = None) -> tuple[int, dict[str, Any]]:
    run_dir = project / '.zoo-agent' / 'runs' / run_id
    outcome = load_json(run_dir / 'delivery-outcome.json')
    if not outcome or str(outcome.get('task_id') or task_id) != task_id:
        outcome = run_delivery_check(project, run_id, task_id)

    route = str(outcome.get('route') or '')
    delivery = str(outcome.get('delivery_outcome') or '')
    task_type = str(outcome.get('task_type') or '')
    scope_status = str(outcome.get('scope_guard_status') or '')
    tests_status = str(outcome.get('tests_status') or '')
    denied = outcome.get('denied_files_touched') if isinstance(outcome.get('denied_files_touched'), list) else []

    checks = {
        'route_is_fast': route == 'fast',
        'scope_guard_pass': scope_status == 'pass',
        'delivery_accepted': delivery in ACCEPTED_OUTCOMES,
        'tests_policy_accepted': accepted_tests_status(tests_status),
        'result_collected': bool(outcome.get('result_collected')),
        'no_denied_files_touched': not denied,
    }
    blockers: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    if not checks['route_is_fast']:
        blockers.append({'id': 'not_fast_route', 'message': 'Fast path gate only applies to route=fast.'})
    if not checks['scope_guard_pass']:
        blockers.append({'id': 'scope_guard_not_pass', 'message': f'Scope guard status is {scope_status or "missing"}.'})
    if delivery == 'no_delivery':
        blockers.append({'id': 'fast_no_delivery', 'message': 'Codex or worker ran but produced no accepted business diff.'})
    elif delivery == 'unsafe':
        blockers.append({'id': 'fast_unsafe', 'message': 'Denied files were touched or scope guard failed.'})
    elif delivery == 'blocked':
        blockers.append({'id': 'fast_blocked', 'message': 'Execution was blocked or failed.'})
    elif delivery not in ACCEPTED_OUTCOMES:
        blockers.append({'id': 'delivery_not_accepted', 'message': f'Delivery outcome is {delivery or "missing"}.'})
    if not checks['tests_policy_accepted']:
        blockers.append({'id': 'tests_policy_not_accepted', 'message': f'Tests status is {tests_status or "missing"}.'})
    if not checks['result_collected']:
        blockers.append({'id': 'result_not_collected', 'message': 'No result evidence was collected.'})
    if denied:
        blockers.append({'id': 'denied_files_touched', 'message': 'Denied files were touched.', 'files': denied})
    if task_type == 'docs' and tests_status == 'not_applicable':
        warnings.append({'id': 'docs_tests_not_applicable', 'message': 'Docs-only fast path does not require tests.'})

    if delivery == 'delivered' and not blockers:
        verdict = 'FAST_DELIVERED'
        status = 'pass'
        next_action = 'review_diff_before_merge'
    elif delivery == 'no_op_with_evidence' and not blockers:
        verdict = 'FAST_NO_OP_ACCEPTED'
        status = 'pass'
        next_action = 'accept_no_op_or_clarify_task'
    elif delivery == 'no_delivery':
        verdict = 'FAST_NO_DELIVERY'
        status = 'blocked'
        next_action = 'clarify_task_or_specify_file_and_change'
    elif delivery == 'unsafe':
        verdict = 'FAST_UNSAFE'
        status = 'blocked'
        next_action = 'stop_and_review_scope'
    else:
        verdict = 'FAST_BLOCKED'
        status = 'blocked'
        next_action = 'inspect_fast_path_evidence'

    payload = {
        'schema_version': '1.0',
        'generated_by': 'check_fast_path_gate.py',
        'generated_at': utc_now(),
        'run_id': run_id,
        'task_id': task_id,
        'workspace': str(project),
        'gate_profile': 'fast_path',
        'route': route,
        'task_type': task_type,
        'delivery_outcome': delivery,
        'verdict': verdict,
        'gate_status': status,
        'checks': checks,
        'blockers': blockers,
        'warnings': warnings,
        'delivery_outcome_path': str(run_dir / 'delivery-outcome.json'),
        'next_action': next_action,
        'skipped_governed_requirements': [
            'task_board_evidence',
            'parent_aggregation',
            'implementation_queue',
            'governed_reviewer',
            'curator',
            'eval_suite',
            'release_readiness',
            'operational_readiness',
            'full_test_matrix',
            'product_docs',
        ],
    }
    output_path = output or run_dir / 'fast-path-gate.json'
    write_json(output_path, payload)
    print(json.dumps(payload, ensure_ascii=True, indent=2))
    return (0 if status == 'pass' else 20), payload


def main() -> int:
    parser = argparse.ArgumentParser(description='Run the lightweight fast path gate.')
    parser.add_argument('--workspace', required=True)
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--task-id', required=True)
    parser.add_argument('--output', default='')
    args = parser.parse_args()

    project = project_root(args.workspace)
    output = Path(args.output).resolve() if args.output else None
    code, _ = build_gate(project, args.run_id, args.task_id, output=output)
    return code


if __name__ == '__main__':
    raise SystemExit(main())
