#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AGENT = ROOT / 'scripts' / 'agent.py'


def run(args: list[str], cwd: Path, check: bool = True) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(args, cwd=cwd, text=True, encoding='utf-8', errors='replace', stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if check and proc.returncode != 0:
        raise AssertionError(f'command failed: {args}\nstdout={proc.stdout}\nstderr={proc.stderr}')
    return proc


def test_first_run_guidance_without_zoo_agent() -> None:
    repo = Path(tempfile.mkdtemp(prefix='first-run-job-'))
    (repo / 'README.md').write_text('# Demo\n', encoding='utf-8')
    run(['git', 'init'], repo)
    run(['git', 'config', 'user.email', 'first@example.local'], repo)
    run(['git', 'config', 'user.name', 'First Run'], repo)
    run(['git', 'add', 'README.md'], repo)
    run(['git', 'commit', '-m', 'init'], repo)
    output = run([sys.executable, str(AGENT)], repo).stdout
    assert 'No active project job yet.' in output
    assert 'agent "map this project and suggest the next action"' in output
    report = repo / '.zoo-agent' / 'command_ux' / 'first_run_guidance_report.json'
    assert report.exists()
    payload = json.loads(report.read_text(encoding='utf-8-sig'))
    assert payload['has_job'] is False
    assert payload['is_git_repo'] is True


def test_cockpit_without_job_does_not_crash() -> None:
    repo = Path(tempfile.mkdtemp(prefix='cockpit-no-job-'))
    (repo / 'README.md').write_text('# Demo\n', encoding='utf-8')
    run(['git', 'init'], repo)
    run(['git', 'config', 'user.email', 'cockpit@example.local'], repo)
    run(['git', 'config', 'user.name', 'Cockpit'], repo)
    run(['git', 'add', 'README.md'], repo)
    run(['git', 'commit', '-m', 'init'], repo)
    cockpit = run([sys.executable, str(AGENT), 'cockpit', '--workspace', str(repo)], repo)
    assert 'project cockpit' in cockpit.stdout
    assert (repo / '.zoo-agent' / 'cockpit' / 'index.html').exists()


def test_no_secret_content_is_read_into_job_artifacts() -> None:
    repo = Path(tempfile.mkdtemp(prefix='job-secret-safety-'))
    (repo / 'README.md').write_text('# Demo\n', encoding='utf-8')
    (repo / '.env').write_text('TOKEN=secret-value\n', encoding='utf-8')
    run(['git', 'init'], repo)
    run(['git', 'config', 'user.email', 'safe@example.local'], repo)
    run(['git', 'config', 'user.name', 'Safe'], repo)
    run(['git', 'add', 'README.md'], repo)
    run(['git', 'commit', '-m', 'init'], repo)
    run([sys.executable, str(AGENT)], repo)
    artifacts = list((repo / '.zoo-agent').rglob('*.json')) + list((repo / '.zoo-agent').rglob('*.md'))
    joined = '\n'.join(path.read_text(encoding='utf-8-sig', errors='replace') for path in artifacts)
    assert 'secret-value' not in joined


def main() -> int:
    test_first_run_guidance_without_zoo_agent()
    test_cockpit_without_job_does_not_crash()
    test_no_secret_content_is_read_into_job_artifacts()
    print('first run job guidance tests passed')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
