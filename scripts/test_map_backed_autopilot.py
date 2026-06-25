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


def run(cmd: list[str], cwd: Path, *, env: dict[str, str], check: bool = True) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(
        cmd,
        cwd=cwd,
        text=True,
        encoding='utf-8',
        errors='replace',
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        env=env,
    )
    print('$', ' '.join(str(item) for item in cmd))
    print(proc.stdout)
    if check and proc.returncode:
        raise AssertionError(f'command failed: {cmd}')
    return proc


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding='utf-8-sig'))


def init_repo(prefix: str) -> Path:
    repo = Path(tempfile.mkdtemp(prefix=prefix, dir=tempfile.gettempdir())).resolve()
    (repo / 'README.md').write_text('# Autopilot\n', encoding='utf-8')
    (repo / 'docs').mkdir()
    (repo / 'docs' / 'guide.md').write_text('# Guide\n', encoding='utf-8')
    run(['git', 'init'], repo, env=os.environ.copy())
    run(['git', 'config', 'user.email', 'autopilot@example.local'], repo, env=os.environ.copy())
    run(['git', 'config', 'user.name', 'Autopilot Test'], repo, env=os.environ.copy())
    run(['git', 'add', 'README.md', 'docs/guide.md'], repo, env=os.environ.copy())
    run(['git', 'commit', '-m', 'init'], repo, env=os.environ.copy())
    return repo


def env() -> dict[str, str]:
    payload = os.environ.copy()
    payload.setdefault('CODEX_HOME', str(Path(tempfile.mkdtemp(prefix='autopilot-codex-home-')).resolve()))
    Path(payload['CODEX_HOME']).mkdir(parents=True, exist_ok=True)
    return payload


def test_standard_executes_trusted_zone() -> None:
    repo = init_repo('map-autopilot-standard-')
    test_env = env()
    run([sys.executable, str(AGENT), 'config', 'backend', 'mock', '--workspace', str(repo)], repo, env=test_env)
    result = run(
        [
            sys.executable,
            str(AGENT),
            'start',
            'improve project readiness',
            '--workspace',
            str(repo),
            '--mode',
            'standard',
        ],
        repo,
        env=test_env,
    )
    assert 'Done.' in result.stdout
    assert 'Undo:' in result.stdout
    assert 'Mock backend delivered.' in (repo / 'README.md').read_text(encoding='utf-8')
    assert (repo / '.zoo-agent' / 'map' / 'project_map.json').exists()
    assert (repo / '.zoo-agent' / 'autopilot' / 'selected_next_action.json').exists()
    checkpoints = load(repo / '.zoo-agent' / 'autopilot' / 'checkpoints.json')
    assert checkpoints['checkpoints'], 'checkpoint required before execution'
    history = load(repo / '.zoo-agent' / 'autopilot' / 'action_history.json')
    assert len(history['actions']) == 1


def test_blocked_zone_pauses() -> None:
    repo = init_repo('map-autopilot-blocked-')
    test_env = env()
    map_dir = repo / '.zoo-agent' / 'map'
    map_dir.mkdir(parents=True, exist_ok=True)
    (map_dir / 'project_map.json').write_text(
        json.dumps(
            {
                'project_name': repo.name,
                'project_type': 'unknown',
                'main_goal': 'avoid unsafe work',
                'modules': [],
                'capabilities': [],
                'risks': [],
                'next_actions': [
                    {
                        'action_id': 'blocked-secret',
                        'title': 'Edit secret configuration',
                        'why_now': 'Unsafe test fixture.',
                        'expected_impact': 'none',
                        'risk_level': 'low',
                        'target_files': ['.env'],
                        'autopilot_eligible': True,
                        'evidence': [
                            {'kind': 'test', 'path': '<hidden>', 'summary': 'blocked action fixture', 'confidence': 1.0}
                        ],
                    }
                ],
                'last_updated': 'test',
            },
            indent=2,
        ),
        encoding='utf-8',
    )
    result = run(
        [sys.executable, str(AGENT), 'start', 'avoid unsafe work', '--workspace', str(repo), '--mode', 'standard'],
        repo,
        env=test_env,
    )
    assert 'Needs attention.' in result.stdout
    attention = load(repo / '.zoo-agent' / 'autopilot' / 'attention_required.json')
    assert attention['status'] == 'needs_attention'
    assert not (repo / '.env').exists()


def test_autopilot_multiple_low_risk_steps() -> None:
    repo = init_repo('map-autopilot-multi-')
    test_env = env()
    run([sys.executable, str(AGENT), 'config', 'backend', 'mock', '--workspace', str(repo)], repo, env=test_env)
    run(
        [
            sys.executable,
            str(AGENT),
            'start',
            'improve project readiness',
            '--workspace',
            str(repo),
            '--mode',
            'autopilot',
            '--max-steps',
            '2',
        ],
        repo,
        env=test_env,
    )
    history = load(repo / '.zoo-agent' / 'autopilot' / 'action_history.json')
    assert len(history['actions']) == 2
    checkpoints = load(repo / '.zoo-agent' / 'autopilot' / 'checkpoints.json')
    assert len(checkpoints['checkpoints']) == 2
    assert (repo / '.zoo-agent' / 'map' / 'project_state.json').exists()


def test_no_delivery_pauses_session() -> None:
    repo = init_repo('map-autopilot-nodelivery-')
    test_env = env()
    run([sys.executable, str(AGENT), 'config', 'backend', 'dry_run', '--workspace', str(repo)], repo, env=test_env)
    run(
        [
            sys.executable,
            str(AGENT),
            'start',
            'improve project readiness',
            '--workspace',
            str(repo),
            '--mode',
            'standard',
        ],
        repo,
        env=test_env,
    )
    session = load(repo / '.zoo-agent' / 'autopilot' / 'session.json')
    assert session['status'] == 'needs_attention'
    attention = load(repo / '.zoo-agent' / 'autopilot' / 'attention_required.json')
    assert attention['status'] == 'needs_attention'


def main() -> int:
    test_standard_executes_trusted_zone()
    test_blocked_zone_pauses()
    test_autopilot_multiple_low_risk_steps()
    test_no_delivery_pauses_session()
    print('map backed autopilot tests passed')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
