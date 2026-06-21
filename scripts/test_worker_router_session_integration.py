#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AGENT = ROOT / 'scripts' / 'agent.py'


def run(command: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env.setdefault('CODEX_HOME', str(Path(tempfile.mkdtemp(prefix='worker-session-codex-home-')).resolve()))
    proc = subprocess.run(command, cwd=cwd, env=env, text=True, encoding='utf-8', errors='replace', stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if proc.returncode:
        raise AssertionError(f'command failed: {command}\nstdout={proc.stdout}\nstderr={proc.stderr}')
    return proc


def repo() -> Path:
    root = Path(tempfile.mkdtemp(prefix='worker-session-', dir=tempfile.gettempdir())).resolve()
    (root / 'README.md').write_text('# Worker Session\n', encoding='utf-8')
    (root / 'docs').mkdir()
    (root / 'docs' / 'guide.md').write_text('# Guide\n', encoding='utf-8')
    run(['git', 'init'], root)
    run(['git', 'config', 'user.email', 'worker-session@example.local'], root)
    run(['git', 'config', 'user.name', 'Worker Session'], root)
    run(['git', 'add', 'README.md', 'docs'], root)
    run(['git', 'commit', '-m', 'init'], root)
    return root


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding='utf-8-sig'))


def main() -> int:
    root = repo()
    run([sys.executable, str(AGENT), 'config', 'backend', 'mock', '--workspace', str(root)], root)
    start = run([sys.executable, str(AGENT), 'start', 'prepare this project for public release', '--workspace', str(root)], root)
    assert 'Done.' in start.stdout or 'Needs attention.' in start.stdout

    routing = load(root / '.zoo-agent' / 'workers' / 'routing_decision.json')
    registry = load(root / '.zoo-agent' / 'workers' / 'worker_registry.json')
    fallback = load(root / '.zoo-agent' / 'workers' / 'fallback_trace.json')
    worker_result = load(root / '.zoo-agent' / 'workers' / 'worker_execution_result.json')
    history = load(root / '.zoo-agent' / 'session' / 'session_history.json')
    checkpoints = load(root / '.zoo-agent' / 'autopilot' / 'checkpoints.json')
    selected = load(root / '.zoo-agent' / 'autopilot' / 'selected_next_action.json')

    assert routing['execution_allowed'] is True
    assert routing['selected_worker']
    assert registry['workers']
    assert fallback['safe'] is True
    assert worker_result['safe_for_user_output'] is True
    assert worker_result['raw_log_path'] == '.zoo-agent/workers/worker_raw_log.json'
    assert selected['source'] == 'project_map.next_actions'
    assert checkpoints['checkpoints']
    steps = history.get('steps') or []
    assert steps
    assert steps[-1]['source'] == 'project_map.next_actions'
    assert steps[-1]['checkpoint_id']
    assert steps[-1]['worker_role']

    run([sys.executable, str(AGENT), 'cockpit', '--workspace', str(root)], root)
    data = load(root / '.zoo-agent' / 'cockpit' / 'cockpit_data.json')
    html = (root / '.zoo-agent' / 'cockpit' / 'index.html').read_text(encoding='utf-8')
    assert data['worker']['role']
    assert 'Worker' in html
    assert 'worker_raw_log' not in html
    assert 'backend internals' not in html.lower()

    help_text = run([sys.executable, str(AGENT), '--help'], root).stdout.lower()
    assert 'agent workers' not in help_text
    print('worker router session integration tests passed')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
