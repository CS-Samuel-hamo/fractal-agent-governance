#!/usr/bin/env python3
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from claude_code_worker_detector import claude_health
from codex_worker_adapter_hardened import codex_health
from task_profile_classifier import classify_task_profile
from worker_adapter_test_harness import run_contract_checks
from worker_installation_diagnostics import write_installation_diagnostics
from worker_registry import write_worker_registry
from worker_router import route_worker

AGENT = ROOT / 'scripts' / 'agent.py'


def run(command: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env.setdefault('CODEX_HOME', str(Path(tempfile.mkdtemp(prefix='adapter-hardening-codex-home-')).resolve()))
    proc = subprocess.run(
        command,
        cwd=cwd,
        env=env,
        text=True,
        encoding='utf-8',
        errors='replace',
        capture_output=True,
    )
    if proc.returncode != 0:
        raise AssertionError(f'command failed: {command}\nstdout={proc.stdout}\nstderr={proc.stderr}')
    return proc


def workspace() -> Path:
    root = Path(tempfile.mkdtemp(prefix='adapter-hardening-', dir=tempfile.gettempdir())).resolve()
    (root / 'README.md').write_text('# Adapter Hardening\n', encoding='utf-8')
    (root / 'src').mkdir()
    (root / 'src' / 'app.py').write_text('VALUE = 1\n', encoding='utf-8')
    (root / 'tests').mkdir()
    (root / 'tests' / 'test_app.py').write_text('def test_ok():\n    assert True\n', encoding='utf-8')
    run(['git', 'init'], root)
    run(['git', 'config', 'user.email', 'adapter@example.local'], root)
    run(['git', 'config', 'user.name', 'Adapter Hardening'], root)
    run(['git', 'add', 'README.md', 'src', 'tests'], root)
    run(['git', 'commit', '-m', 'init'], root)
    return root


def main() -> int:
    root = workspace()
    registry = write_worker_registry(root)
    names = {item['name'] for item in registry['workers']}
    assert {
        'mock_worker',
        'dry_run_worker',
        'local_scanner_worker',
        'codex_worker_existing_adapter',
        'claude_worker_stub',
        'local_worker_stub',
    } <= names
    for worker in registry['workers']:
        assert worker.get('contract'), worker.get('name')
        assert worker['contract']['reads_secrets'] is False
        if worker['contract']['supports_actual_execution'] is False:
            assert worker['supports_actual_execution'] is False
    contract_check = run_contract_checks(root)
    assert contract_check['passed'], contract_check

    codex = codex_health(root)
    assert codex['health'] in {'healthy', 'degraded', 'unavailable'}
    assert (root / '.zoo-agent' / 'workers' / 'codex_adapter_health.json').exists()
    claude = claude_health(root)
    assert claude['supports_actual_execution'] is False
    assert (root / '.zoo-agent' / 'workers' / 'claude_code_detection.json').exists()

    diagnostics = write_installation_diagnostics(root)
    assert 'diagnostic only; no installation performed' in diagnostics['actions_taken']
    assert 'no network download performed' in diagnostics['actions_taken']

    scan_profile = classify_task_profile(
        {
            'title': 'Refresh project map scan repo',
            'risk_level': 'low',
            'trust_zone': 'trusted',
            'execution_mode': 'auto',
            'target_files': [],
        }
    )
    scan_decision = route_worker(root, task_profile=scan_profile, requested_worker='auto', execution_mode='auto')
    assert scan_decision['selected_worker'] == 'local_scanner_worker'
    assert scan_decision['execution_mode'] == 'preview'

    code_profile = classify_task_profile(
        {
            'title': 'Adjust small source constant',
            'risk_level': 'low',
            'trust_zone': 'trusted',
            'execution_mode': 'auto',
            'target_files': ['src/app.py'],
        }
    )
    claude_decision = route_worker(root, task_profile=code_profile, requested_worker='claude', execution_mode='auto')
    assert claude_decision['selected_worker'] != 'claude_worker_stub'
    assert claude_decision['execution_allowed'] is True

    blocked_profile = classify_task_profile(
        {
            'title': 'Change auth secrets',
            'risk_level': 'high',
            'trust_zone': 'blocked',
            'execution_mode': 'auto',
            'target_files': ['auth/secrets.py'],
        }
    )
    blocked = route_worker(root, task_profile=blocked_profile, requested_worker='auto', execution_mode='auto')
    assert blocked['execution_allowed'] is False

    run([sys.executable, str(AGENT), 'cockpit', '--workspace', str(root)], root)
    cockpit = (root / '.zoo-agent' / 'cockpit' / 'index.html').read_text(encoding='utf-8')
    assert 'Worker Readiness' in cockpit
    assert 'Local Scanner' in cockpit
    assert 'raw backend' not in cockpit.lower()
    print('real worker adapter hardening tests passed')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
