#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from task_profile_classifier import classify_task_profile  # noqa: E402
from worker_fallback_engine import fallback_for_result  # noqa: E402
from worker_router import route_worker  # noqa: E402


def run(command: list[str], cwd: Path) -> None:
    proc = subprocess.run(command, cwd=cwd, text=True, encoding='utf-8', errors='replace', stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if proc.returncode:
        raise AssertionError(f'command failed: {command}\nstdout={proc.stdout}\nstderr={proc.stderr}')


def repo() -> Path:
    root = Path(tempfile.mkdtemp(prefix='worker-fallback-', dir=tempfile.gettempdir())).resolve()
    (root / 'README.md').write_text('# Worker Fallback\n', encoding='utf-8')
    run(['git', 'init'], root)
    run(['git', 'config', 'user.email', 'fallback@example.local'], root)
    run(['git', 'config', 'user.name', 'Worker Fallback'], root)
    run(['git', 'add', 'README.md'], root)
    run(['git', 'commit', '-m', 'init'], root)
    return root


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding='utf-8-sig'))


def main() -> int:
    root = repo()
    docs_profile = classify_task_profile({'title': 'Add README note', 'risk_level': 'low', 'trust_zone': 'trusted', 'execution_mode': 'auto', 'target_files': ['README.md']})
    decision = route_worker(root, task_profile=docs_profile, requested_worker='codex', execution_mode='auto')
    assert decision['selected_worker'] != 'claude_worker_stub'
    assert decision['execution_allowed'] is True
    assert 'dry_run_worker' in decision['fallback_workers']
    trace = load(root / '.zoo-agent' / 'workers' / 'fallback_trace.json')
    assert trace['safe'] is True
    assert trace['final_mode'] in {'auto', 'preview'}

    failed_worker = {
        'worker_name': decision['selected_worker'],
        'worker_type': decision['selected_worker_type'],
        'provider': decision['selected_provider'],
        'status': 'no_delivery',
        'changed_files': [],
        'summary': 'no delivery',
        'confidence': 0.1,
        'error_type': 'no_delivery',
        'safe_for_user_output': True,
    }
    fallback_trace = fallback_for_result(root, routing_decision=decision, worker_result=failed_worker)
    assert fallback_trace['safe'] is True
    assert fallback_trace['final_mode'] in {'preview', 'needs_attention'}
    assert len(fallback_trace['fallback_chain']) <= len(decision['fallback_workers'])

    blocked_profile = classify_task_profile({'title': 'Modify .env token', 'risk_level': 'high', 'trust_zone': 'blocked', 'execution_mode': 'auto', 'target_files': ['.env']})
    blocked = route_worker(root, task_profile=blocked_profile, requested_worker='mock', execution_mode='auto')
    assert blocked['execution_allowed'] is False
    blocked_trace = load(root / '.zoo-agent' / 'workers' / 'fallback_trace.json')
    assert blocked_trace['safe'] is True
    assert blocked_trace['final_mode'] == 'needs_attention'
    assert blocked_trace['final_worker'] == ''
    print('worker router fallback tests passed')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
