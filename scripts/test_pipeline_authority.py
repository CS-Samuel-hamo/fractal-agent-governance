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
        cmd,
        cwd=cwd,
        text=True,
        encoding='utf-8',
        errors='replace',
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    print('$', ' '.join(str(item) for item in cmd))
    print(proc.stdout)
    if check and proc.returncode:
        raise AssertionError(f'command failed with {proc.returncode}: {cmd}')
    return proc


def temp_repo() -> Path:
    base = Path(tempfile.gettempdir())
    repo = Path(tempfile.mkdtemp(prefix='pipeline-authority-', dir=str(base))).resolve()
    (repo / 'README.md').write_text('# Pipeline Authority\n', encoding='utf-8')
    run(['git', 'init'], repo)
    run(['git', 'config', 'user.email', 'authority@example.local'], repo)
    run(['git', 'config', 'user.name', 'Pipeline Authority Test'], repo)
    run(['git', 'add', 'README.md'], repo)
    run(['git', 'commit', '-m', 'init'], repo)
    (repo / '.zoo-agent').mkdir()
    (repo / '.zoo-agent' / 'bootstrap.lock').write_text('test\n', encoding='utf-8')
    return repo


def parse_json(stdout: str) -> dict:
    return json.loads(stdout)


def main() -> int:
    os.environ.setdefault('CODEX_HOME', str(Path(tempfile.mkdtemp(prefix='authority-codex-home-')).resolve()))
    authority = parse_json(run([sys.executable, str(ROOT / 'scripts' / 'pipeline_authority_check.py')], ROOT).stdout)
    assert authority['authority'] == 'pipeline'
    assert not authority['conflicts']

    repo = temp_repo()
    run_report = parse_json(
        run(
            [
                sys.executable,
                str(AGENT),
                'run',
                'add a small README note',
                '--workspace',
                str(repo),
                '--run-id',
                'run-default',
                '--allowed-file',
                'README.md',
                '--dry-run',
            ],
            repo,
        ).stdout
    )
    assert run_report == {'goal': 'add a small README note', 'progress': 'complete', 'result': 'DRY_RUN_COMPLETE'}
    assert 'stages' not in run_report
    assert 'planner' not in run_report
    assert 'executor' not in run_report
    assert 'verifier' not in run_report
    assert (repo / '.zoo-agent' / 'runs' / 'run-default' / 'pipeline' / 'final_result.json').exists()

    route_report = parse_json(
        run(
            [
                sys.executable,
                str(ROOT / 'scripts' / 'route_task.py'),
                'add a small README note',
                '--workspace',
                str(repo),
                '--run-id',
                'route-default',
                '--allowed-file',
                'README.md',
                '--dry-run',
            ],
            repo,
        ).stdout
    )
    assert route_report['generated_by'] == 'pipeline_loop.py'

    legacy_report = parse_json(
        run(
            [
                sys.executable,
                str(AGENT),
                'run',
                'add a small README note',
                '--workspace',
                str(repo),
                '--run-id',
                'run-legacy',
                '--task-id',
                'task-legacy',
                '--allowed-file',
                'README.md',
                '--dry-run',
                '--legacy-runtime',
            ],
            repo,
        ).stdout
    )
    assert legacy_report['generated_by'] == 'route_task.py'
    assert legacy_report['execution']['status'] == 'dry_run'
    print('pipeline authority tests passed')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
