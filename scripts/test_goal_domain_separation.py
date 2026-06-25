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


def run(cmd: list[str], cwd: Path, *, check: bool = True) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(
        cmd, cwd=cwd, text=True, encoding='utf-8', errors='replace', stdout=subprocess.PIPE, stderr=subprocess.STDOUT
    )
    print('$', ' '.join(str(item) for item in cmd))
    print(proc.stdout)
    if check and proc.returncode:
        raise AssertionError(f'command failed with {proc.returncode}: {cmd}')
    return proc


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding='utf-8-sig'))


def temp_repo(name: str) -> Path:
    base = Path(tempfile.gettempdir())
    repo = Path(tempfile.mkdtemp(prefix=f'{name}-', dir=str(base))).resolve()
    (repo / 'README.md').write_text('# Goal Domain Separation\n', encoding='utf-8')
    run(['git', 'init'], repo)
    run(['git', 'config', 'user.email', 'domain@example.local'], repo)
    run(['git', 'config', 'user.name', 'Goal Domain Test'], repo)
    run(['git', 'add', '.'], repo)
    run(['git', 'commit', '-m', 'init'], repo)
    (repo / '.zoo-agent').mkdir()
    (repo / '.zoo-agent' / 'bootstrap.lock').write_text('test\n', encoding='utf-8')
    return repo


def set_goal(
    repo: Path, goal_id: str, text: str, priority: int, *, resource: str = 'README.md', no_activate: bool = False
) -> None:
    cmd = [
        sys.executable,
        str(AGENT),
        'goal',
        'set',
        text,
        '--workspace',
        str(repo),
        '--goal-id',
        goal_id,
        '--priority',
        str(priority),
        '--resource',
        resource,
        '--success-criteria',
        f'{goal_id} criteria',
        '--non-goal',
        'Do not merge or push.',
    ]
    if no_activate:
        cmd.append('--no-activate')
    run(cmd, repo)


def test_goal_domain_classification_and_filtering() -> None:
    repo = temp_repo('goal-domain')
    set_goal(repo, 'system-bootstrap', 'Bootstrap runtime maintenance for scheduler self-check', 100)
    set_goal(repo, 'production-readme', 'Improve README onboarding wording for users', 20, no_activate=True)
    set_goal(repo, 'diagnostic-smoke', 'Controlled diagnostic dry-run validation test', 90, no_activate=True)

    run([sys.executable, str(ROOT / 'scripts' / 'filter_system_goals.py'), '--workspace', str(repo)], repo)
    filtered = json.loads(
        run([sys.executable, str(ROOT / 'scripts' / 'filter_system_goals.py'), '--workspace', str(repo)], repo).stdout
    )
    eligible = {item['goal_id']: item for item in filtered['eligible_goals']}
    excluded = {item['goal_id']: item for item in filtered['excluded_goals']}
    assert 'production-readme' in eligible
    assert excluded['system-bootstrap']['goal_type'] == 'system_goal'
    assert excluded['diagnostic-smoke']['goal_type'] == 'diagnostic_goal'

    run([sys.executable, str(AGENT), 'goal', 'schedule', '--workspace', str(repo)], repo)
    schedule = load(repo / '.zoo-agent' / 'goal' / 'goal-schedule.json')
    state = load(repo / '.zoo-agent' / 'goal' / 'goal_state.json')
    assert schedule['active_goal_id'] == 'production-readme'
    assert [item['goal_id'] for item in schedule['eligible_goals']] == ['production-readme']
    assert 'system-bootstrap' in schedule['exclusion_reason']
    assert 'diagnostic-smoke' in schedule['exclusion_reason']
    goals = {item['goal_id']: item for item in state['goals']}
    assert goals['system-bootstrap']['status'] != 'active'
    assert goals['production-readme']['status'] == 'active'


def main() -> int:
    os.environ.setdefault('CODEX_HOME', str(Path(tempfile.mkdtemp(prefix='agent-runtime-codex-home-')).resolve()))
    test_goal_domain_classification_and_filtering()
    print('goal domain separation tests passed')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
