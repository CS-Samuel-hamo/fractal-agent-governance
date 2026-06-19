#!/usr/bin/env python3
from __future__ import annotations

import datetime
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def run(command: list[str], cwd: Path, *, timeout: int = 0, env: dict[str, str] | None = None) -> dict[str, Any]:
    started = time.monotonic()
    try:
        proc = subprocess.run(
            command,
            cwd=cwd,
            text=True,
            encoding='utf-8',
            errors='replace',
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout or None,
            env=env,
        )
        return {
            'command': [str(item) for item in command],
            'cwd': str(cwd),
            'returncode': proc.returncode,
            'stdout': proc.stdout,
            'stderr': proc.stderr,
            'elapsed_seconds': round(time.monotonic() - started, 3),
            'timed_out': False,
        }
    except subprocess.TimeoutExpired as exc:
        return {
            'command': [str(item) for item in command],
            'cwd': str(cwd),
            'returncode': 124,
            'stdout': exc.stdout or '',
            'stderr': exc.stderr or '',
            'elapsed_seconds': round(time.monotonic() - started, 3),
            'timed_out': True,
        }


def load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding='utf-8-sig'))
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')


def temp_root() -> Path:
    candidate = Path('D:/AI_DEV/temp')
    if candidate.exists():
        return candidate
    return Path(os.environ.get('TEMP') or os.environ.get('TMP') or '.').resolve()


def git_init(repo: Path) -> None:
    repo.mkdir(parents=True, exist_ok=True)
    run(['git', 'init'], repo)
    run(['git', 'config', 'user.name', 'local-alpha'], repo)
    run(['git', 'config', 'user.email', 'local-alpha@example.com'], repo)


def git_commit_all(repo: Path, message: str) -> None:
    run(['git', 'add', 'README.md'], repo)
    result = run(['git', 'commit', '-m', message], repo)
    if result['returncode'] != 0:
        raise AssertionError(result['stderr'] or result['stdout'])


def create_fake_codex(fake_dir: Path) -> Path:
    fake_dir.mkdir(parents=True, exist_ok=True)
    fake_py = fake_dir / 'fake_codex.py'
    fake_py.write_text(
        r'''
from __future__ import annotations
import os
import sys
import time
from pathlib import Path

mode = os.environ.get("FAKE_CODEX_MODE", "success")
args = sys.argv[1:]
out = ""
if "--output-last-message" in args:
    try:
        out = args[args.index("--output-last-message") + 1]
    except Exception:
        out = ""
if mode == "timeout":
    time.sleep(10)
    sys.exit(0)
if mode == "invalid":
    sys.stdout.buffer.write(b"stdout-\xff-\xfe\n")
    sys.stderr.buffer.write(b"stderr-\xff-\xfe\n")
else:
    print("fake stdout")
    print("fake stderr", file=sys.stderr)
if out:
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    Path(out).write_text("Fake final OK\n", encoding="utf-8")
if mode == "nonzero":
    sys.exit(1)
sys.exit(0)
'''.lstrip(),
        encoding='utf-8',
    )
    fake_cmd = fake_dir / 'codex.cmd'
    fake_cmd.write_text(f'@echo off\r\n"{sys.executable}" "%~dp0fake_codex.py" %*\r\nexit /b %ERRORLEVEL%\r\n', encoding='utf-8')
    return fake_cmd


def run_fake_adapter(root: Path, fake_cmd: Path, mode: str, *, timeout_seconds: int = 20) -> dict[str, Any]:
    workspace = root / f'fake-workspace-{mode}'
    task_dir = root / f'fake-task-{mode}'
    workspace.mkdir(parents=True, exist_ok=True)
    task_dir.mkdir(parents=True, exist_ok=True)
    prompt = task_dir / 'prompt.md'
    prompt.write_text('Say OK.\n', encoding='utf-8')
    status = task_dir / 'codex-worker-status.json'
    env = os.environ.copy()
    env['FAKE_CODEX_MODE'] = mode
    result = run(
        [
            sys.executable,
            str(ROOT / 'scripts' / 'codex_exec_adapter.py'),
            '--workspace',
            str(workspace),
            '--task-dir',
            str(task_dir),
            '--prompt-file',
            str(prompt),
            '--output-last-message',
            str(task_dir / 'codex-final-message.md'),
            '--sandbox',
            'read-only',
            '--timeout-seconds',
            str(timeout_seconds),
            '--no-output-timeout-seconds',
            '20',
            '--stdout-log',
            str(task_dir / 'codex-stdout.log'),
            '--stderr-log',
            str(task_dir / 'codex-stderr.log'),
            '--status-json',
            str(status),
            '--codex-command',
            str(fake_cmd),
        ],
        ROOT,
        timeout=timeout_seconds + 30,
        env=env,
    )
    payload = load_json(status)
    payload['_command_result'] = result
    return payload


def capture_baseline(repo: Path, run_id: str, task_id: str) -> Path:
    result = run(
        [
            sys.executable,
            str(ROOT / 'scripts' / 'capture_task_baseline.py'),
            '--workspace',
            str(repo),
            '--run-id',
            run_id,
            '--task-id',
            task_id,
            '--route',
            'fast',
            '--task-type',
            'docs',
            '--input-text',
            'update README.md',
            '--allowed-file',
            'README.md',
        ],
        ROOT,
    )
    if result['returncode'] != 0:
        raise AssertionError(result['stderr'] or result['stdout'])
    payload = json.loads(result['stdout'])
    return Path(payload['path'])


def compare_baseline(repo: Path, baseline: Path) -> Path:
    result = run([sys.executable, str(ROOT / 'scripts' / 'compare_task_baseline.py'), '--workspace', str(repo), '--baseline', str(baseline)], ROOT)
    if result['returncode'] != 0:
        raise AssertionError(result['stderr'] or result['stdout'])
    payload = json.loads(result['stdout'])
    return Path(payload['path'])


def write_optimistic_attempt(repo: Path, run_id: str, task_id: str, worker_status: dict[str, Any], final_message: str = '') -> None:
    task_dir = repo / '.zoo-agent' / 'runs' / run_id / 'codex-tasks' / task_id
    task_dir.mkdir(parents=True, exist_ok=True)
    status_path = task_dir / 'codex-worker-status.json'
    write_json(status_path, worker_status)
    if final_message:
        (task_dir / 'codex-final-message.md').write_text(final_message, encoding='utf-8')
    report = {
        'schema_version': '1.0',
        'status': 'merge_candidate' if worker_status.get('status') == 'succeeded' else 'retryable_worker_failure',
        'attempts': [
            {
                'attempt': 1,
                'task_id': task_id,
                'worker_status': worker_status,
                'worker_status_path': str(status_path),
                'collected_result': {
                    'scope_guard': {'status': 'pass'},
                    'worker_status': worker_status,
                    'worker_status_path': str(status_path),
                    'final_message': final_message,
                },
            }
        ],
    }
    write_json(repo / '.zoo-agent' / 'runs' / run_id / 'optimistic-runs' / f'{task_id}.json', report)


def delivery_case(root: Path, name: str, worker_status: dict[str, Any], *, modify_readme: bool = False, final_message: str = '') -> dict[str, Any]:
    repo = root / f'delivery-{name}'
    git_init(repo)
    (repo / 'README.md').write_text('# Demo\n\nInitial.\n', encoding='utf-8')
    git_commit_all(repo, 'init')
    run_id = f'run-{name}'
    task_id = f'task-{name}'
    baseline = capture_baseline(repo, run_id, task_id)
    if modify_readme:
        (repo / 'README.md').write_text('# Demo\n\nInitial.\n\nAgent runtime worker stability OK\n', encoding='utf-8')
    delta = compare_baseline(repo, baseline)
    write_optimistic_attempt(repo, run_id, task_id, worker_status, final_message=final_message)
    outcome = run(
        [
            sys.executable,
            str(ROOT / 'scripts' / 'check_delivery_outcome.py'),
            '--workspace',
            str(repo),
            '--run-id',
            run_id,
            '--task-id',
            task_id,
            '--route',
            'fast',
            '--task-type',
            'docs',
            '--input-text',
            'update README.md',
            '--task-delta',
            str(delta),
        ],
        ROOT,
    )
    payload = load_json(repo / '.zoo-agent' / 'runs' / run_id / 'delivery-outcome.json')
    payload['_returncode'] = outcome['returncode']
    gate = run([sys.executable, str(ROOT / 'scripts' / 'check_fast_path_gate.py'), '--workspace', str(repo), '--run-id', run_id, '--task-id', task_id], ROOT)
    payload['_fast_gate'] = load_json(repo / '.zoo-agent' / 'runs' / run_id / 'fast-path-gate.json')
    payload['_fast_gate_returncode'] = gate['returncode']
    return payload


def real_codex_actual(root: Path) -> dict[str, Any]:
    health = run([sys.executable, str(ROOT / 'scripts' / 'check_codex_worker_health.py'), '--codex-home', os.environ.get('CODEX_HOME', ''), '--timeout-seconds', '240', '--no-output-timeout-seconds', '120'], ROOT, timeout=360)
    latest = load_json(ROOT / '.tmp' / 'codex-worker-health-latest.json')
    if latest.get('verdict') not in {'HEALTHY', 'HEALTHY_WITH_WARNINGS'}:
        return {'status': 'REAL_CODEX_SKIPPED', 'reason': 'health_not_ok', 'health': latest, 'health_command': health}
    repo = root / 'real-codex-actual'
    git_init(repo)
    (repo / 'README.md').write_text('# Worker Stability\n\nInitial.\n', encoding='utf-8')
    git_commit_all(repo, 'init')
    boot = run([sys.executable, str(ROOT / 'scripts' / 'agent.py'), 'bootstrap', '--workspace', str(repo)], ROOT, timeout=120)
    if boot['returncode'] != 0:
        return {'status': 'REAL_CODEX_UNSTABLE', 'reason': 'bootstrap_failed', 'bootstrap': boot}
    task = 'append exact line "Agent runtime worker stability OK" to README.md and do not modify any other business files'
    actual = run(
        [
            sys.executable,
            str(ROOT / 'scripts' / 'agent.py'),
            'run',
            task,
            '--workspace',
            str(repo),
            '--allowed-file',
            'README.md',
            '--allow-ambiguous-fast',
            '--timeout-seconds',
            '900',
            '--no-output-timeout-seconds',
            '600',
        ],
        ROOT,
        timeout=1080,
    )
    runs_dir = repo / '.zoo-agent' / 'runs'
    reports = sorted(runs_dir.glob('*/delivery-outcome.json'), key=lambda path: path.stat().st_mtime, reverse=True) if runs_dir.exists() else []
    outcome = load_json(reports[0]) if reports else {}
    if actual['returncode'] == 0 and outcome.get('delivery_outcome') == 'delivered':
        return {'status': 'REAL_CODEX_DELIVERED', 'agent_run': actual, 'delivery_outcome': outcome}
    return {'status': 'REAL_CODEX_UNSTABLE', 'agent_run': actual, 'delivery_outcome': outcome}


def main() -> int:
    timestamp = datetime.datetime.utcnow().strftime('%Y%m%d%H%M%S')
    root = temp_root() / f'agent-codex-worker-stability-{timestamp}'
    root.mkdir(parents=True, exist_ok=True)
    fake_cmd = create_fake_codex(root / 'fake-bin')
    failures: list[str] = []
    warnings: list[str] = []

    success = run_fake_adapter(root, fake_cmd, 'success')
    if success.get('status') != 'succeeded' or success.get('returncode') != 0 or not success.get('output_last_message_exists'):
        failures.append('fake_succeeded_worker_failed')

    nonzero = run_fake_adapter(root, fake_cmd, 'nonzero')
    if nonzero.get('status') != 'failed' or nonzero.get('returncode') != 1:
        failures.append('fake_nonzero_worker_status_wrong')
    nonzero_delivery = delivery_case(root, 'nonzero', {'status': 'failed', 'returncode': 1})
    if nonzero_delivery.get('delivery_outcome') != 'blocked':
        failures.append('nonzero_delivery_not_blocked')

    timeout = run_fake_adapter(root, fake_cmd, 'timeout', timeout_seconds=1)
    if timeout.get('status') != 'timeout':
        failures.append('fake_timeout_worker_status_wrong')
    timeout_delivery = delivery_case(root, 'timeout', {'status': 'timeout', 'returncode': 124})
    if timeout_delivery.get('delivery_outcome') != 'blocked':
        failures.append('timeout_delivery_not_blocked')

    invalid = run_fake_adapter(root, fake_cmd, 'invalid')
    if invalid.get('status') != 'succeeded':
        failures.append('fake_invalid_unicode_crashed')

    delivered = delivery_case(root, 'delivered', {'status': 'succeeded', 'returncode': 0}, modify_readme=True)
    if delivered.get('delivery_outcome') != 'delivered' or delivered.get('_fast_gate', {}).get('verdict') != 'FAST_DELIVERED':
        failures.append('delivered_readme_not_fast_delivered')

    no_delivery = delivery_case(root, 'no-delivery', {'status': 'succeeded', 'returncode': 0})
    if no_delivery.get('delivery_outcome') != 'no_delivery' or no_delivery.get('_fast_gate', {}).get('verdict') != 'FAST_NO_DELIVERY':
        failures.append('returncode_zero_no_diff_not_no_delivery')

    noop = delivery_case(
        root,
        'noop',
        {'status': 'succeeded', 'returncode': 0},
        final_message='I checked README.md and did not find the specified typo, so no changes were needed.',
    )
    if noop.get('delivery_outcome') != 'no_op_with_evidence':
        failures.append('no_op_with_evidence_not_accepted')

    real = real_codex_actual(root)
    if real.get('status') == 'REAL_CODEX_UNSTABLE':
        warnings.append('REAL_CODEX_UNSTABLE')

    report = {
        'schema_version': '1.0',
        'generated_by': 'test_codex_worker_stability.py',
        'generated_at': datetime.datetime.utcnow().isoformat() + 'Z',
        'root': str(root),
        'failures': failures,
        'warnings': warnings,
        'real_codex_actual': real.get('status'),
    }
    write_json(ROOT / '.tmp' / f'codex-worker-stability-test-{timestamp}.json', report)
    if failures:
        print(json.dumps(report, ensure_ascii=True, indent=2))
        print('codex worker stability test fail')
        return 1
    print(json.dumps(report, ensure_ascii=True, indent=2))
    print('codex worker stability test pass')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
