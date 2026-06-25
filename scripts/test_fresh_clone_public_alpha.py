#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from demo_flow_verifier import verify as verify_demo_flow
from fresh_clone_verifier import verify as verify_fresh_clone
from public_release_report_generator import generate_report


def run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(cmd, cwd=ROOT, text=True, encoding='utf-8', errors='replace', capture_output=True)
    if proc.returncode != 0:
        raise AssertionError(f'command failed: {" ".join(cmd)}\nstdout={proc.stdout}\nstderr={proc.stderr}')
    return proc


def test_fresh_clone_verifier_runs() -> None:
    payload = verify_fresh_clone(ROOT)
    assert payload['fresh_clone_passed'] is True, payload
    assert payload['unsafe_behavior_detected'] is False, payload
    assert '.zoo-agent/cockpit/index.html' in payload['artifacts_generated'], payload
    assert '.zoo-agent/release/pr_draft.md' in payload['artifacts_generated'], payload


def test_demo_flow_verifier_runs() -> None:
    payload = verify_demo_flow(ROOT)
    assert payload['demo_flow_passed'] is True, payload
    assert payload['unsafe_behavior_detected'] is False, payload
    assert '.zoo-agent/cockpit/index.html' in payload['generated_outputs'], payload
    assert '.zoo-agent/release/pr_draft.md' in payload['generated_outputs'], payload


def test_public_release_report_generates_clear_readiness() -> None:
    payload = generate_report(ROOT, run_fresh_clone=False, run_demo=False)
    assert payload['status'] == 'READY_TO_PUBLISH_GITHUB_ALPHA', payload
    readiness = json.loads(
        (ROOT / '.zoo-agent' / 'public_release' / 'readiness_for_github_publish.json').read_text(encoding='utf-8-sig')
    )
    assert readiness['readiness'] == 'READY_TO_PUBLISH_GITHUB_ALPHA', readiness
    assert (ROOT / '.zoo-agent' / 'public_release' / 'public_release_report.md').exists()


def test_agent_publish_report_runs() -> None:
    proc = run([sys.executable, str(ROOT / 'scripts' / 'agent.py'), 'publish', '--report', '--workspace', str(ROOT)])
    assert '.zoo-agent/public_release/public_release_report.md' in proc.stdout
    assert 'READY_TO_PUBLISH_GITHUB_ALPHA' in proc.stdout


def main() -> None:
    test_fresh_clone_verifier_runs()
    test_demo_flow_verifier_runs()
    test_public_release_report_generates_clear_readiness()
    test_agent_publish_report_runs()
    print('fresh clone public alpha tests passed')


if __name__ == '__main__':
    main()
