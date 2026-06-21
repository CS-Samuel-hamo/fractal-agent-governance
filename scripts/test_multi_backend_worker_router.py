#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from task_profile_classifier import classify_task_profile  # noqa: E402
from worker_registry import write_worker_registry  # noqa: E402
from worker_router import route_worker  # noqa: E402


AGENT = ROOT / 'scripts' / 'agent.py'


def run(command: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env.setdefault('CODEX_HOME', str(Path(tempfile.mkdtemp(prefix='worker-router-codex-home-')).resolve()))
    proc = subprocess.run(command, cwd=cwd, env=env, text=True, encoding='utf-8', errors='replace', stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if proc.returncode != 0:
        raise AssertionError(f'command failed: {command}\nstdout={proc.stdout}\nstderr={proc.stderr}')
    return proc


def repo() -> Path:
    root = Path(tempfile.mkdtemp(prefix='worker-router-', dir=tempfile.gettempdir())).resolve()
    (root / 'README.md').write_text('# Worker Router\n', encoding='utf-8')
    (root / 'docs').mkdir()
    (root / 'docs' / 'guide.md').write_text('# Guide\n', encoding='utf-8')
    (root / 'tests').mkdir()
    (root / 'tests' / 'test_sample.py').write_text('def test_ok():\n    assert True\n', encoding='utf-8')
    (root / 'src').mkdir()
    (root / 'src' / 'app.py').write_text('VALUE = 1\n', encoding='utf-8')
    run(['git', 'init'], root)
    run(['git', 'config', 'user.email', 'router@example.local'], root)
    run(['git', 'config', 'user.name', 'Worker Router'], root)
    run(['git', 'add', 'README.md', 'docs', 'tests', 'src'], root)
    run(['git', 'commit', '-m', 'init'], root)
    return root


def main() -> int:
    root = repo()
    registry = write_worker_registry(root)
    names = {item['name'] for item in registry['workers']}
    assert {'mock_worker', 'dry_run_worker', 'codex_worker_existing_adapter', 'claude_worker_stub', 'local_worker_stub'} <= names
    worker_by_name = {item['name']: item for item in registry['workers']}
    assert worker_by_name['mock_worker']['available'] is True
    assert worker_by_name['dry_run_worker']['available'] is True
    assert worker_by_name['claude_worker_stub']['available'] is False
    assert worker_by_name['local_worker_stub']['available'] is False

    docs_profile = classify_task_profile(
        {
            'selected_action_id': 'docs',
            'title': 'Clarify documentation guide wording',
            'risk_level': 'low',
            'trust_zone': 'trusted',
            'execution_mode': 'auto',
            'target_files': ['docs/guide.md'],
        }
    )
    assert docs_profile['task_type'] == 'docs_update'
    docs_decision = route_worker(root, task_profile=docs_profile, requested_worker='auto', execution_mode='auto')
    assert docs_decision['execution_allowed'] is True
    assert docs_decision['selected_worker']

    test_profile = classify_task_profile({'title': 'Add test coverage', 'risk_level': 'low', 'trust_zone': 'trusted', 'execution_mode': 'auto', 'target_files': ['tests/test_sample.py']})
    assert test_profile['task_type'] == 'test_update'
    code_profile = classify_task_profile({'title': 'Adjust small source constant', 'risk_level': 'low', 'trust_zone': 'trusted', 'execution_mode': 'auto', 'target_files': ['src/app.py']})
    assert code_profile['task_type'] == 'code_edit'
    scan_profile = classify_task_profile({'title': 'Refresh project map release readiness', 'risk_level': 'low', 'trust_zone': 'trusted', 'execution_mode': 'preview', 'target_files': []})
    scan_decision = route_worker(root, task_profile=scan_profile, requested_worker='auto', execution_mode='preview')
    assert scan_decision['selected_worker'] == 'dry_run_worker'
    assert scan_decision['execution_mode'] == 'preview'

    blocked_profile = classify_task_profile({'title': 'Change auth token handling', 'risk_level': 'high', 'trust_zone': 'blocked', 'execution_mode': 'auto', 'target_files': ['auth/secrets.py']})
    blocked = route_worker(root, task_profile=blocked_profile, requested_worker='auto', execution_mode='auto')
    assert blocked['execution_allowed'] is False
    assert blocked['execution_mode'] == 'needs_attention'

    fallback = route_worker(root, task_profile=docs_profile, requested_worker='claude', execution_mode='auto')
    assert fallback['selected_worker'] != 'claude_worker_stub'
    assert fallback['execution_allowed'] is True
    assert 'requested_worker_fallback' in fallback['routing_reason']

    help_text = run([sys.executable, str(AGENT), '--help'], root).stdout.lower()
    assert 'workers --doctor' not in help_text
    assert 'agent workers' not in help_text
    doctor = run([sys.executable, str(AGENT), 'workers', '--doctor', '--workspace', str(root)], root)
    payload = json.loads(doctor.stdout)
    assert payload['task'] == 'workers doctor'
    assert '.zoo-agent/workers/worker_registry.json' in payload['result']
    print('multi backend worker router tests passed')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
