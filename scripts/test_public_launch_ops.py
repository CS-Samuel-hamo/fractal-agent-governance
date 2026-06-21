#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from community_copy_linter import lint as lint_community  # noqa: E402
from first_user_flow_validator import validate as validate_first_user  # noqa: E402
from launch_report_generator import generate as generate_launch_report  # noqa: E402
from public_launch_audit import audit  # noqa: E402
from public_launch_packager import RELEASE_TAG, VERSION, write_package  # noqa: E402


def run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(cmd, cwd=ROOT, text=True, encoding='utf-8', errors='replace', stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if proc.returncode != 0:
        raise AssertionError(f"command failed: {' '.join(cmd)}\nstdout={proc.stdout}\nstderr={proc.stderr}")
    return proc


def test_community_copy_is_positioned_correctly() -> None:
    assert (ROOT / 'COMMUNITY_POSTS.md').exists()
    report = lint_community(ROOT)
    assert report['recommendation'] == 'pass', report
    assert report['codex_wrapper_risk'] == 'low', report
    assert report['overclaim_detected'] is False, report


def test_first_user_flow_validator_runs() -> None:
    report = validate_first_user(ROOT)
    assert report['recommendation'] == 'pass', report
    assert report['first_user_flow_score'] >= 0.9, report
    assert 'agent --help' in report['commands_verified'], report
    assert not report['friction_points'], report


def test_public_launch_packager_manual_commands_only() -> None:
    package = write_package(ROOT)
    assert package['version'] == VERSION
    assert package['release_tag'] == RELEASE_TAG
    assert package['safe_to_launch'] is True, package
    assert package['manual_publish_commands'], package
    notice = ' '.join(package['manual_command_notice']).lower()
    assert 'manual' in notice
    assert 'did not push' in notice
    assert 'did not create a remote github release' in notice


def test_public_launch_audit_and_report_ready() -> None:
    report = audit(ROOT)
    assert report['recommendation'] == 'pass', report
    assert report['safe_to_launch'] is True, report
    payload = generate_launch_report(ROOT)
    assert payload['status'] == 'READY_FOR_MANUAL_GITHUB_PUBLISH', payload
    readiness = json.loads((ROOT / '.zoo-agent' / 'public_launch' / 'readiness_for_public_launch.json').read_text(encoding='utf-8-sig'))
    assert readiness['readiness'] == 'READY_FOR_MANUAL_GITHUB_PUBLISH', readiness


def test_agent_launch_audit_runs_and_help_hides_it() -> None:
    help_proc = run([sys.executable, str(ROOT / 'scripts' / 'agent.py'), '--help'])
    lowered = help_proc.stdout.lower()
    for hidden in ['agent launch', 'launch --audit', 'worker dogfood', 'learning dogfood', 'alpha audit', 'session dogfood']:
        assert hidden not in lowered
    proc = run([sys.executable, str(ROOT / 'scripts' / 'agent.py'), 'launch', '--audit', '--workspace', str(ROOT)])
    assert '.zoo-agent/public_launch/public_launch_audit.json' in proc.stdout
    assert 'recommendation: pass' in proc.stdout


def test_no_runtime_artifacts_tracked() -> None:
    proc = subprocess.run(['git', 'ls-files', '.zoo-agent'], cwd=ROOT, text=True, encoding='utf-8', errors='replace', stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    assert proc.stdout.strip() == ''


def main() -> None:
    test_community_copy_is_positioned_correctly()
    test_first_user_flow_validator_runs()
    test_public_launch_packager_manual_commands_only()
    test_public_launch_audit_and_report_ready()
    test_agent_launch_audit_runs_and_help_hides_it()
    test_no_runtime_artifacts_tracked()
    print('public launch ops tests passed')


if __name__ == '__main__':
    main()
