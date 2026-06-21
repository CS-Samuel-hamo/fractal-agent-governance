#!/usr/bin/env python3
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from post_publish_smoke_test import smoke  # noqa: E402


def run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(cmd, cwd=ROOT, text=True, encoding='utf-8', errors='replace', stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if proc.returncode != 0:
        raise AssertionError(f"command failed: {' '.join(cmd)}\nstdout={proc.stdout}\nstderr={proc.stderr}")
    return proc


def test_post_publish_smoke_runs() -> None:
    report = smoke(ROOT)
    assert report['post_publish_smoke_passed'] is True, report
    assert report['safe'] is True, report
    assert not report['failed_checks'], report


def test_agent_launch_smoke_runs_and_help_hides_launch() -> None:
    help_proc = run([sys.executable, str(ROOT / 'scripts' / 'agent.py'), '--help'])
    assert 'agent launch' not in help_proc.stdout
    assert 'launch --smoke' not in help_proc.stdout
    proc = run([sys.executable, str(ROOT / 'scripts' / 'agent.py'), 'launch', '--smoke', '--workspace', str(ROOT)])
    assert '.zoo-agent/public_launch/post_publish_smoke_report.json' in proc.stdout


def main() -> None:
    test_post_publish_smoke_runs()
    test_agent_launch_smoke_runs_and_help_hides_launch()
    print('post publish smoke tests passed')


if __name__ == '__main__':
    main()
