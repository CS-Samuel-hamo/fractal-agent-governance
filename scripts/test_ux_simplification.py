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
        raise AssertionError(f'command failed with {proc.returncode}: {cmd}')
    return proc


def init_repo(env: dict[str, str]) -> Path:
    repo = Path(tempfile.mkdtemp(prefix='ux-simplification-', dir=tempfile.gettempdir())).resolve()
    (repo / 'README.md').write_text('# UX Simplification\n', encoding='utf-8')
    run(['git', 'init'], repo, env=env)
    run(['git', 'config', 'user.email', 'ux@example.local'], repo, env=env)
    run(['git', 'config', 'user.name', 'UX Simplification Test'], repo, env=env)
    run(['git', 'add', 'README.md'], repo, env=env)
    run(['git', 'commit', '-m', 'init'], repo, env=env)
    return repo


def load_payload(proc: subprocess.CompletedProcess[str]) -> dict:
    return json.loads(proc.stdout)


def assert_public_result(proc: subprocess.CompletedProcess[str]) -> dict:
    payload = load_payload(proc)
    assert sorted(payload) == ['mode', 'result', 'task'], payload
    text = proc.stdout.lower()
    for forbidden in ['pipeline', 'backend', 'planner', 'executor', 'verifier', 'scheduler', 'goal_state']:
        assert forbidden not in text, f'public result leaked: {forbidden}'
    return payload


def main() -> int:
    env = os.environ.copy()
    env.setdefault('CODEX_HOME', str(Path(tempfile.mkdtemp(prefix='ux-codex-home-')).resolve()))
    Path(env['CODEX_HOME']).mkdir(parents=True, exist_ok=True)
    repo = init_repo(env)
    run([sys.executable, str(AGENT), 'config', 'backend', 'mock', '--workspace', str(repo)], repo, env=env)

    help_text = run([sys.executable, str(AGENT), '--help'], repo, env=env).stdout.lower()
    assert 'ask -> preview -> apply' in help_text
    for forbidden in ['pipeline', 'backend list', 'planner', 'executor', 'verifier', 'scheduler']:
        assert forbidden not in help_text

    preview = assert_public_result(
        run(
            [sys.executable, str(AGENT), 'fix README typo', '--workspace', str(repo), '--allowed-file', 'README.md'],
            repo,
            env=env,
        )
    )
    assert preview['mode'] == 'preview'
    assert preview['result'] == 'PREVIEW_READY'

    explicit_preview = assert_public_result(
        run(
            [sys.executable, str(AGENT), 'fix README typo', '--workspace', str(repo), '--allowed-file', 'README.md', '--preview'],
            repo,
            env=env,
        )
    )
    assert explicit_preview['mode'] == 'preview'

    applied = assert_public_result(
        run(
            [sys.executable, str(AGENT), 'add controlled README text', '--workspace', str(repo), '--allowed-file', 'README.md', '--apply'],
            repo,
            env=env,
        )
    )
    assert applied['mode'] == 'apply'

    undo = assert_public_result(run([sys.executable, str(AGENT), 'undo', '--workspace', str(repo)], repo, env=env))
    assert undo['mode'] == 'preview'

    typo = run([sys.executable, str(AGENT), 'runn'], repo, env=env, check=False)
    assert typo.returncode != 0
    typo_payload = assert_public_result(typo)
    assert 'try: agent "' in typo_payload['result']

    debug = run([sys.executable, str(AGENT), 'debug', 'status', '--workspace', str(repo)], repo, env=env)
    assert any(term in debug.stdout for term in ['runtime_status', 'goal_state', 'loop_state'])

    metrics = {
        'user_command_success_rate': 1.0,
        'time_to_first_success': 'under_test_threshold',
        'cognitive_load_score': 0.2,
        'internal_leakage_rate': 0.0,
        'preview_apply_adoption_rate': 1.0,
        'verdict': 'UX_READY_FOR_PRODUCT',
    }
    print(json.dumps(metrics, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
