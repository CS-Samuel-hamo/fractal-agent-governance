#!/usr/bin/env python3
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from public_positioning_linter import lint_project, lint_texts


def run(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(cmd, cwd=cwd, text=True, encoding='utf-8', errors='replace', capture_output=True)
    if proc.returncode != 0:
        raise AssertionError(f'command failed: {" ".join(cmd)}\nstdout={proc.stdout}\nstderr={proc.stderr}')
    return proc


def test_public_docs_use_project_operator_positioning() -> None:
    report = lint_project(ROOT)
    assert report['recommendation'] == 'pass', report
    assert report['positioning_score'] >= 0.9, report
    assert report['operator_positioning_score'] >= 0.9, report
    assert report['codex_wrapper_risk'] == 'low', report


def test_readme_first_viewport_is_operator_led() -> None:
    first_viewport = '\n'.join((ROOT / 'README.md').read_text(encoding='utf-8').splitlines()[:20]).lower()
    assert 'ai project operator' in first_viewport
    assert 'give it a project. it keeps moving it forward.' in first_viewport
    assert 'safer codex wrapper' not in first_viewport


def test_linter_detects_codex_wrapper_risk() -> None:
    report = lint_texts({'README.md': 'This is a Codex wrapper for coding tasks.'})
    assert report['codex_wrapper_risk'] == 'high', report
    assert report['recommendation'] == 'fail', report


def test_linter_detects_unsupported_overclaim() -> None:
    report = lint_texts(
        {
            'README.md': (
                'AI Project Operator. Give it a project. It keeps moving it forward. '
                'Project-level Autopilot with Project Map, Cockpit, release and PR. '
                'It automatically creates remote PRs.'
            )
        }
    )
    assert report['overclaim_detected'] is True, report
    assert report['recommendation'] in {'fix_before_100', 'fail'}, report


def test_agent_help_hides_alpha_command() -> None:
    proc = run([sys.executable, str(ROOT / 'scripts' / 'agent.py'), '--help'], ROOT)
    assert 'agent alpha' not in proc.stdout
    assert 'alpha --audit' not in proc.stdout


def main() -> None:
    test_public_docs_use_project_operator_positioning()
    test_readme_first_viewport_is_operator_led()
    test_linter_detects_codex_wrapper_risk()
    test_linter_detects_unsupported_overclaim()
    test_agent_help_hides_alpha_command()
    print('public positioning tests OK')


if __name__ == '__main__':
    main()
