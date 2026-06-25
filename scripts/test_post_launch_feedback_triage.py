#!/usr/bin/env python3
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from feedback_iteration_planner import plan
from feedback_priority_ranker import rank
from feedback_triage_engine import triage
from post_launch_feedback_report_generator import generate


def test_triage_priority_iteration_report() -> None:
    project = Path(tempfile.mkdtemp(prefix='feedback-triage-'))
    triage_report = triage(project)
    assert triage_report['triage_summary']['total'] >= 1
    assert triage_report['patch_candidates']
    priority = rank(project)
    assert priority['top_patch_items']
    iteration = plan(project)
    assert (project / 'V1_0_4_PATCH_PLAN.md').exists()
    assert (project / 'V1_1_ROADMAP_CANDIDATES.md').exists()
    assert iteration['patch_candidates']
    report = generate(project)
    assert report['status'] in {'READY_FOR_104_PATCH_PLANNING', 'COLLECT_MORE_FEEDBACK_FIRST'}
    assert (project / '.zoo-agent' / 'feedback' / 'post_launch_feedback_report.md').exists()
    readiness = project / '.zoo-agent' / 'feedback' / 'readiness_for_104_patch.json'
    assert readiness.exists()


def test_agent_feedback_hidden_command() -> None:
    project = Path(tempfile.mkdtemp(prefix='feedback-cli-'))
    help_proc = subprocess.run(
        [sys.executable, str(ROOT / 'scripts' / 'agent.py'), '--help'],
        cwd=ROOT,
        text=True,
        encoding='utf-8',
        errors='replace',
        capture_output=True,
    )
    assert help_proc.returncode == 0
    assert 'feedback' not in help_proc.stdout
    triage_proc = subprocess.run(
        [sys.executable, str(ROOT / 'scripts' / 'agent.py'), 'feedback', '--triage', '--workspace', str(project)],
        cwd=ROOT,
        text=True,
        encoding='utf-8',
        errors='replace',
        capture_output=True,
    )
    assert triage_proc.returncode == 0, triage_proc.stdout + triage_proc.stderr
    report_proc = subprocess.run(
        [sys.executable, str(ROOT / 'scripts' / 'agent.py'), 'feedback', '--report', '--workspace', str(project)],
        cwd=ROOT,
        text=True,
        encoding='utf-8',
        errors='replace',
        capture_output=True,
    )
    assert report_proc.returncode == 0, report_proc.stdout + report_proc.stderr
    assert 'READY_FOR_104_PATCH_PLANNING' in report_proc.stdout or 'COLLECT_MORE_FEEDBACK_FIRST' in report_proc.stdout


def main() -> int:
    test_triage_priority_iteration_report()
    test_agent_feedback_hidden_command()
    print('post launch feedback triage tests passed')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
