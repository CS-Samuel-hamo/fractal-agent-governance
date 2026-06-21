#!/usr/bin/env python3
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from post_publish_report_generator import generate as generate_report  # noqa: E402
from publishing_command_linter import lint_project  # noqa: E402
from test_post_publish_remote_verification import make_repo  # noqa: E402


def run(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=cwd, text=True, encoding='utf-8', errors='replace', stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def test_public_docs_are_branch_aware() -> None:
    payload = lint_project(ROOT)
    assert payload['publishing_command_lint_passed'] is True, payload
    assert payload['hardcoded_main_push_detected'] is False
    assert payload['force_push_detected'] is False


def test_postlaunch_hidden_cli_and_report() -> None:
    repo, _remote = make_repo()
    help_result = run([sys.executable, str(ROOT / 'scripts' / 'agent.py'), '--help'], ROOT)
    assert help_result.returncode == 0
    assert 'postlaunch' not in help_result.stdout
    verify_result = run([sys.executable, str(ROOT / 'scripts' / 'agent.py'), 'postlaunch', '--verify', '--workspace', str(repo)], ROOT)
    assert verify_result.returncode == 0, verify_result.stderr + verify_result.stdout
    report = generate_report(repo)
    assert report['status'] == 'READY_FOR_POST_LAUNCH_FEEDBACK_TRIAGE', report
    status_path = repo / 'POST_LAUNCH_STATUS.md'
    assert status_path.exists()
    text = status_path.read_text(encoding='utf-8')
    assert 'release/v1.0.0-alpha.1' in text
    assert 'git push origin main' not in text
    assert ':\\' not in text


def main() -> int:
    test_public_docs_are_branch_aware()
    test_postlaunch_hidden_cli_and_report()
    print('publishing docs no main assumption tests passed')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
