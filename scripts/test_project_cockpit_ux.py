#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AGENT = ROOT / 'scripts' / 'agent.py'
ABSOLUTE_PATH_RE = re.compile(r'[A-Za-z]:[\\/]')
FORBIDDEN = ['eval', 'governance', 'planner', 'verifier', 'scheduler', 'backend internals', 'pipeline_loop.py']


def run(cmd: list[str], cwd: Path, *, check: bool = True) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(cmd, cwd=cwd, text=True, encoding='utf-8', errors='replace', stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    print('$', ' '.join(str(item) for item in cmd))
    print(proc.stdout)
    if check and proc.returncode:
        raise AssertionError(f'command failed with {proc.returncode}: {cmd}')
    return proc


def payload(proc: subprocess.CompletedProcess[str]) -> dict:
    return json.loads(proc.stdout)


def assert_clean_output(text: str) -> None:
    assert not ABSOLUTE_PATH_RE.search(text), text
    lowered = text.lower()
    for term in FORBIDDEN:
        assert term not in lowered, f'forbidden term leaked: {term}'


def init_repo() -> Path:
    repo = Path(tempfile.mkdtemp(prefix='cockpit-ux-', dir=tempfile.gettempdir())).resolve()
    (repo / 'README.md').write_text('# Cockpit UX\n', encoding='utf-8')
    run(['git', 'init'], repo)
    run(['git', 'config', 'user.email', 'cockpit@example.local'], repo)
    run(['git', 'config', 'user.name', 'Cockpit UX Test'], repo)
    run(['git', 'add', 'README.md'], repo)
    run(['git', 'commit', '-m', 'init'], repo)
    return repo


def main() -> int:
    repo = init_repo()

    help_result = run([sys.executable, str(AGENT), '--help'], repo)
    assert 'agent cockpit' in help_result.stdout
    assert_clean_output(help_result.stdout)

    status_before = run([sys.executable, str(AGENT), 'status', '--workspace', str(repo), '--no-write'], repo)
    assert_clean_output(status_before.stdout)
    before = payload(status_before)
    assert '.zoo-agent/cockpit/index.html' in before['result']

    cockpit = run([sys.executable, str(AGENT), 'cockpit', '--workspace', str(repo)], repo)
    assert_clean_output(cockpit.stdout)
    cockpit_payload = payload(cockpit)
    assert cockpit_payload['task'] == 'project cockpit'
    assert cockpit_payload['mode'] == 'ready'
    assert 'Open: .zoo-agent/cockpit/index.html' in cockpit_payload['result']
    assert 'agent continue' in cockpit_payload['result']
    assert (repo / '.zoo-agent' / 'cockpit' / 'index.html').exists()
    assert (repo / '.zoo-agent' / 'cockpit' / 'cockpit_data.json').exists()

    status_after = run([sys.executable, str(AGENT), 'status', '--workspace', str(repo), '--no-write'], repo)
    assert_clean_output(status_after.stdout)
    after = payload(status_after)
    assert '.zoo-agent/cockpit/index.html' in after['result']

    print('project cockpit UX tests passed')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
