#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AGENT = ROOT / 'scripts' / 'agent.py'


def run(args: list[str], cwd: Path = ROOT, check: bool = True) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(args, cwd=cwd, text=True, encoding='utf-8', errors='replace', capture_output=True)
    if check and proc.returncode != 0:
        raise AssertionError(f'command failed: {args}\nstdout={proc.stdout}\nstderr={proc.stderr}')
    return proc


def test_help_prioritizes_two_command_flow() -> None:
    help_text = run([sys.executable, str(AGENT), '--help']).stdout
    assert 'Most of the time:' in help_text
    assert 'agent "prepare this project for public release"' in help_text
    assert 'agent\n' in help_text
    for hidden in ['workers --doctor', 'learning --build', 'feedback --report', 'postlaunch', 'publish --']:
        assert hidden not in help_text


def test_docs_prioritize_two_command_flow() -> None:
    for doc in ['README.md', 'QUICKSTART.md', 'CLI_REFERENCE.md', 'FAQ.md', 'DEMO.md', 'NEW_PROJECT_GUIDE.md']:
        text = (ROOT / doc).read_text(encoding='utf-8-sig')
        assert 'agent "<goal>"' in text or 'agent "prepare this project for public release"' in text
    combined = '\n'.join(
        (ROOT / doc).read_text(encoding='utf-8-sig')
        for doc in ['README.md', 'QUICKSTART.md', 'CLI_REFERENCE.md', 'FAQ.md', 'NEW_PROJECT_GUIDE.md']
    )
    assert 'not a Codex wrapper' in combined
    assert 'fully autonomous 24h' not in combined.lower()
    assert 'runs forever in the background' not in combined.lower()


def test_command_ux_linter_passes() -> None:
    proc = run([sys.executable, str(ROOT / 'scripts' / 'command_ux_linter.py'), '--workspace', str(ROOT)])
    payload = json.loads(proc.stdout)
    assert payload['recommendation'] == 'pass', payload
    readiness = json.loads(
        (ROOT / '.zoo-agent' / 'command_ux' / 'readiness_for_first_user_test.json').read_text(encoding='utf-8-sig')
    )
    assert readiness['readiness'] == 'BACKGROUND_JOB_UX_104_READY'


def main() -> int:
    test_help_prioritizes_two_command_flow()
    test_docs_prioritize_two_command_flow()
    test_command_ux_linter_passes()
    print('command simplification ux tests passed')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
