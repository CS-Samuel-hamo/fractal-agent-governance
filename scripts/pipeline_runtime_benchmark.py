#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
AGENT = ROOT / 'scripts' / 'agent.py'
sys.path.insert(0, str(ROOT / 'scripts'))

from runtime_common import load_json, utc_now, write_json  # noqa: E402


TASKS = [
    {
        'name': 'simple',
        'task': "append the exact line 'Pipeline benchmark simple note.' to README.md",
        'allowed_files': ['README.md'],
    },
    {
        'name': 'medium',
        'task': "add a multiply(a, b) pure function in src/app.py and add a unit test in tests/test_app.py",
        'allowed_files': ['src/app.py', 'tests/test_app.py'],
    },
    {
        'name': 'complex',
        'task': "refactor src/app.py so add accepts numeric strings and update tests/test_app.py only",
        'allowed_files': ['src/app.py', 'tests/test_app.py'],
    },
]


def run(cmd: list[str], cwd: Path, *, timeout: int = 0) -> dict[str, Any]:
    started = time.monotonic()
    try:
        proc = subprocess.run(
            cmd,
            cwd=cwd,
            text=True,
            encoding='utf-8',
            errors='replace',
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout or None,
        )
        return {
            'command': [str(item) for item in cmd],
            'returncode': proc.returncode,
            'stdout': proc.stdout,
            'stderr': proc.stderr,
            'elapsed_seconds': round(time.monotonic() - started, 3),
            'timed_out': False,
        }
    except subprocess.TimeoutExpired as exc:
        return {
            'command': [str(item) for item in cmd],
            'returncode': 124,
            'stdout': exc.stdout or '',
            'stderr': exc.stderr or '',
            'elapsed_seconds': round(time.monotonic() - started, 3),
            'timed_out': True,
        }


def temp_repo(name: str) -> Path:
    base = Path('D:/AI_DEV/temp') if Path('D:/AI_DEV/temp').exists() else Path(tempfile.gettempdir())
    repo = Path(tempfile.mkdtemp(prefix=f'pipeline-benchmark-{name}-', dir=str(base))).resolve()
    (repo / 'README.md').write_text('# Pipeline Benchmark\n\nStart.\n', encoding='utf-8')
    (repo / 'src').mkdir()
    (repo / 'tests').mkdir()
    (repo / 'src' / 'app.py').write_text('def add(a, b):\n    return a + b\n', encoding='utf-8')
    (repo / 'tests' / 'test_app.py').write_text('from src.app import add\n\n\ndef test_add():\n    assert add(1, 2) == 3\n', encoding='utf-8')
    run(['git', 'init'], repo)
    run(['git', 'config', 'user.email', 'benchmark@example.local'], repo)
    run(['git', 'config', 'user.name', 'Pipeline Benchmark'], repo)
    run(['git', 'add', '.'], repo)
    run(['git', 'commit', '-m', 'init'], repo)
    (repo / '.zoo-agent').mkdir()
    (repo / '.zoo-agent' / 'bootstrap.lock').write_text('benchmark\n', encoding='utf-8')
    return repo


def parse_json_or_empty(text: str) -> dict[str, Any]:
    try:
        return json.loads(text)
    except Exception:
        return {}


def run_pipeline(repo: Path, task: dict[str, Any], *, dry_run: bool, allow_actual: bool, timeout_seconds: int, max_retries: int) -> dict[str, Any]:
    run_id = f"bench-{task['name']}-{'dry' if dry_run else 'actual'}"
    cmd = [
        sys.executable,
        str(AGENT),
        'pipeline',
        task['task'],
        '--workspace',
        str(repo),
        '--run-id',
        run_id,
        '--timeout-seconds',
        str(timeout_seconds),
        '--max-retries',
        str(max_retries),
    ]
    for item in task['allowed_files']:
        cmd.extend(['--allowed-file', item])
    if dry_run:
        cmd.append('--dry-run')
    if allow_actual and not dry_run:
        cmd.append('--allow-actual')
    result = run(cmd, repo, timeout=timeout_seconds + 180)
    loop_payload = parse_json_or_empty(result.get('stdout') or '')
    execution = load_json(repo / '.zoo-agent' / 'runs' / run_id / 'pipeline' / 'execution_result.json')
    final = load_json(repo / '.zoo-agent' / 'runs' / run_id / 'pipeline' / 'final_result.json')
    leaf_results = execution.get('leaf_results') or []
    over = any(item.get('denied_files_touched') or item.get('out_of_scope_files') for item in leaf_results)
    under = any(item.get('delivery_outcome') in {'no_delivery', 'blocked'} for item in leaf_results)
    backend_count = sum(1 for item in leaf_results if item.get('backend_invoked'))
    return {
        'run_id': run_id,
        'command_returncode': result['returncode'],
        'latency_seconds': result['elapsed_seconds'],
        'timed_out': result['timed_out'],
        'generated_by': loop_payload.get('generated_by', ''),
        'final_verdict': final.get('final_verdict', ''),
        'backend_execution_count': backend_count,
        'over_execution': over,
        'under_execution': under,
        'verifier_blocked': final.get('final_verdict') in {'BLOCKED', 'NO_DELIVERY'},
        'execution_result': execution,
        'final_result': final,
    }


def run_legacy_dry(repo: Path, task: dict[str, Any], timeout_seconds: int) -> dict[str, Any]:
    run_id = f"legacy-{task['name']}-dry"
    cmd = [
        sys.executable,
        str(AGENT),
        'run',
        task['task'],
        '--workspace',
        str(repo),
        '--run-id',
        run_id,
        '--task-id',
        f"task-{task['name']}",
        '--dry-run',
        '--legacy-runtime',
    ]
    for item in task['allowed_files']:
        cmd.extend(['--allowed-file', item])
    result = run(cmd, repo, timeout=timeout_seconds)
    payload = parse_json_or_empty(result.get('stdout') or '')
    return {
        'run_id': run_id,
        'latency_seconds': result['elapsed_seconds'],
        'returncode': result['returncode'],
        'route': payload.get('route', ''),
        'generated_by': payload.get('generated_by', ''),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description='Benchmark the three-stage pipeline against legacy dry-run routing.')
    parser.add_argument('--allow-actual', action='store_true', help='Allow real backend actual execution in temp repositories.')
    parser.add_argument('--timeout-seconds', type=int, default=360)
    parser.add_argument('--max-retries', type=int, default=2)
    parser.add_argument('--json-output', default='')
    args = parser.parse_args()

    authority_run = run([sys.executable, str(ROOT / 'scripts' / 'pipeline_authority_check.py')], ROOT, timeout=30)
    authority = parse_json_or_empty(authority_run.get('stdout') or '')
    if authority.get('authority') != 'pipeline':
        report = {
            'schema_version': '1.0',
            'generated_by': 'pipeline_runtime_benchmark.py',
            'generated_at': utc_now(),
            'authority_status': authority.get('authority', 'unknown'),
            'status': 'blocked_authority_conflict',
            'authority_report': authority,
        }
        if args.json_output:
            write_json(Path(args.json_output).resolve(), report)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 10

    results = []
    for task in TASKS:
        repo = temp_repo(task['name'])
        dry = run_pipeline(repo, task, dry_run=True, allow_actual=False, timeout_seconds=args.timeout_seconds, max_retries=args.max_retries)
        actual = run_pipeline(repo, task, dry_run=False, allow_actual=args.allow_actual, timeout_seconds=args.timeout_seconds, max_retries=args.max_retries)
        legacy = run_legacy_dry(repo, task, timeout_seconds=args.timeout_seconds)
        results.append({'task_class': task['name'], 'task': task['task'], 'dry_run': dry, 'actual_run': actual, 'legacy_dry_run': legacy})

    pipeline_latencies = [row['dry_run']['latency_seconds'] for row in results]
    legacy_latencies = [row['legacy_dry_run']['latency_seconds'] for row in results]
    actual_rows = [row['actual_run'] for row in results]
    report = {
        'schema_version': '1.0',
        'generated_by': 'pipeline_runtime_benchmark.py',
        'generated_at': utc_now(),
        'authority_status': authority.get('authority'),
        'actual_enabled': args.allow_actual,
        'pipeline_latency': {
            'dry_run_seconds_total': round(sum(pipeline_latencies), 3),
            'dry_run_seconds_avg': round(sum(pipeline_latencies) / max(len(pipeline_latencies), 1), 3),
        },
        'legacy_latency': {
            'dry_run_seconds_total': round(sum(legacy_latencies), 3),
            'dry_run_seconds_avg': round(sum(legacy_latencies) / max(len(legacy_latencies), 1), 3),
        },
        'backend_execution_count': sum(row.get('backend_execution_count', 0) for row in actual_rows),
        'over_execution_rate': round(sum(1 for row in actual_rows if row.get('over_execution')) / max(len(actual_rows), 1), 4),
        'under_execution_rate': round(sum(1 for row in actual_rows if row.get('under_execution')) / max(len(actual_rows), 1), 4),
        'verifier_block_rate': round(sum(1 for row in actual_rows if row.get('verifier_blocked')) / max(len(actual_rows), 1), 4),
        'results': results,
    }
    out = Path(args.json_output).resolve() if args.json_output else ROOT / '.tmp' / f"pipeline-runtime-benchmark-{time.strftime('%Y%m%d-%H%M%S', time.gmtime())}.json"
    write_json(out, report)
    report['report_path'] = str(out)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
