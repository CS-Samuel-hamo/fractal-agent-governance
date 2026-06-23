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


def init_repo() -> Path:
    repo = Path(tempfile.mkdtemp(prefix='background-job-'))
    (repo / 'README.md').write_text('# Demo\n', encoding='utf-8')
    run(['git', 'init'], repo)
    run(['git', 'config', 'user.email', 'job@example.local'], repo)
    run(['git', 'config', 'user.name', 'Job Test'], repo)
    run(['git', 'add', 'README.md'], repo)
    run(['git', 'commit', '-m', 'init'], repo)
    return repo


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding='utf-8-sig'))


def test_bare_agent_guidance_and_goal_starts_job() -> None:
    repo = init_repo()
    run([sys.executable, str(AGENT), 'config', 'backend', 'mock', '--workspace', str(repo)], repo)
    empty = run([sys.executable, str(AGENT)], repo)
    assert 'Welcome.' in empty.stdout
    assert 'Start in one of three ways:' in empty.stdout
    start = run([sys.executable, str(AGENT), 'prepare this project for public release', '--workspace', str(repo)], repo)
    assert 'Result:' in start.stdout
    assert 'Where you are:' in start.stdout
    assert 'Next:' in start.stdout
    job_path = repo / '.zoo-agent' / 'jobs' / 'current_job.json'
    session_path = repo / '.zoo-agent' / 'session' / 'session_state.json'
    assert job_path.exists()
    assert session_path.exists()
    job = read_json(job_path)
    session = read_json(session_path)
    assert job['goal'] == 'prepare this project for public release'
    assert job['linked_session_id'] == session['session_id']
    inbox = run([sys.executable, str(AGENT)], repo)
    assert 'Result:' in inbox.stdout
    assert 'Job details:' in inbox.stdout


def test_aliases_and_controls_update_job_state() -> None:
    repo = init_repo()
    run([sys.executable, str(AGENT), 'config', 'backend', 'mock', '--workspace', str(repo)], repo)
    run([sys.executable, str(AGENT), 'start', 'improve project readiness', '--workspace', str(repo)], repo)
    assert (repo / '.zoo-agent' / 'jobs' / 'current_job.json').exists()
    status = run([sys.executable, str(AGENT), 'status', '--workspace', str(repo)], repo)
    assert 'Result:' in status.stdout
    assert 'Tip: `agent` also shows this inbox.' in status.stdout
    run([sys.executable, str(AGENT), 'continue', '--workspace', str(repo)], repo)
    continued = read_json(repo / '.zoo-agent' / 'jobs' / 'current_job.json')
    assert continued['status'] in {'active', 'paused', 'needs_attention', 'completed', 'stopped'}
    run([sys.executable, str(AGENT), 'undo', '--workspace', str(repo)], repo)
    assert (repo / '.zoo-agent' / 'jobs' / 'job_digest.md').exists()
    run([sys.executable, str(AGENT), 'stop', '--workspace', str(repo)], repo)
    stopped = read_json(repo / '.zoo-agent' / 'jobs' / 'current_job.json')
    assert stopped['status'] == 'stopped'


def test_first_run_guidance_recommends_seed_prompt() -> None:
    repo = init_repo()
    (repo / 'project_beginning_prompt.md').write_text('Build a safe project workflow.', encoding='utf-8')
    empty = run([sys.executable, str(AGENT)], repo)
    assert 'Welcome.' in empty.stdout
    assert 'agent "read project_beginning_prompt.md"' in empty.stdout
    assert 'Detected project prompt:' in empty.stdout


def test_single_task_explicit_modes_still_work() -> None:
    repo = init_repo()
    run([sys.executable, str(AGENT), 'config', 'backend', 'mock', '--workspace', str(repo)], repo)
    preview = run([sys.executable, str(AGENT), 'fix README typo', '--workspace', str(repo), '--preview'], repo)
    assert json.loads(preview.stdout)['mode'] == 'preview'
    scoped = run([sys.executable, str(AGENT), 'fix README typo', '--workspace', str(repo), '-f', 'README.md'], repo)
    assert json.loads(scoped.stdout)['mode'] == 'preview'


def main() -> int:
    test_bare_agent_guidance_and_goal_starts_job()
    test_aliases_and_controls_update_job_state()
    test_first_run_guidance_recommends_seed_prompt()
    test_single_task_explicit_modes_still_work()
    print('background job mode tests passed')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
