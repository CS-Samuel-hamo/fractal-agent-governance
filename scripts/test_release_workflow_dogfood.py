#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from pr_draft_quality_gate import evaluate_pr_draft  # noqa: E402
from release_artifact_quality_gate import evaluate_release_artifacts  # noqa: E402
from release_workflow_dogfood_runner import base_fixture, run_release_flow, run_dogfood  # noqa: E402


AGENT = ROOT / 'scripts' / 'agent.py'


def run(cmd: list[str], cwd: Path, *, check: bool = True) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env.setdefault('CODEX_HOME', str(Path(tempfile.mkdtemp(prefix='release-dogfood-test-codex-home-')).resolve()))
    proc = subprocess.run(cmd, cwd=cwd, env=env, text=True, encoding='utf-8', errors='replace', stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if check and proc.returncode != 0:
        raise AssertionError(f"command failed: {' '.join(cmd)}\nstdout={proc.stdout}\nstderr={proc.stderr}")
    return proc


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding='utf-8-sig'))


def assert_trace(root: Path) -> None:
    trace = load(root / '.zoo-agent' / 'release_dogfood' / 'release_workflow_dogfood_trace.json')
    scenarios = {item['scenario']: item for item in trace.get('runs') or []}
    expected = {
        'clean_release_candidate',
        'missing_docs',
        'missing_tests',
        'dirty_worktree',
        'no_git_repo',
        'tokenized_remote_safety',
        'no_actual_diff_pr',
        'cockpit_release_view',
    }
    assert expected <= set(scenarios), sorted(set(scenarios))
    for name in expected:
        assert scenarios[name]['outcome'] == 'pass', name
        assert scenarios[name]['safety_gate_passed'] is True, name
        assert scenarios[name]['network_called'] is False, name
        assert scenarios[name]['push_detected'] is False, name
        assert scenarios[name]['merge_detected'] is False, name
        assert scenarios[name]['secret_leak_detected'] is False, name


def assert_negative_gates() -> None:
    with tempfile.TemporaryDirectory(prefix='release-quality-negative-') as tmp:
        root = Path(tmp).resolve()
        base_fixture(root)
        run_release_flow(root)
        notes = root / '.zoo-agent' / 'release' / 'release_notes_draft.md'
        notes.write_text(notes.read_text(encoding='utf-8') + '\nAll tests passed. Production ready.\n', encoding='utf-8')
        overclaim = evaluate_release_artifacts(root)
        assert overclaim['overclaim_detected'] is True
        assert overclaim['recommendation'] == 'fail'

    with tempfile.TemporaryDirectory(prefix='release-token-negative-') as tmp:
        root = Path(tmp).resolve()
        base_fixture(root)
        run_release_flow(root)
        fake_token = 'ghp_' + ('3' * 36)
        (root / '.zoo-agent' / 'release' / 'release_notes_draft.md').write_text(f'token {fake_token}\n', encoding='utf-8')
        leak = evaluate_release_artifacts(root)
        assert leak['secret_leak_detected'] is True
        assert leak['recommendation'] == 'fail'

    with tempfile.TemporaryDirectory(prefix='pr-fabrication-negative-') as tmp:
        root = Path(tmp).resolve()
        base_fixture(root)
        run_release_flow(root)
        draft = root / '.zoo-agent' / 'release' / 'pr_draft.md'
        text = draft.read_text(encoding='utf-8').replace('Not run in this workflow', 'All tests passed')
        draft.write_text(text, encoding='utf-8')
        fabricated = evaluate_pr_draft(root)
        assert fabricated['fabrication_detected'] is True
        assert fabricated['recommendation'] == 'fail'

    with tempfile.TemporaryDirectory(prefix='pr-fake-changed-negative-') as tmp:
        root = Path(tmp).resolve()
        base_fixture(root)
        run_release_flow(root)
        plan_path = root / '.zoo-agent' / 'release' / 'pr_plan.json'
        plan = load(plan_path)
        plan['changed_areas'] = ['src/fake_change.py']
        plan_path.write_text(json.dumps(plan, indent=2), encoding='utf-8')
        fake = evaluate_pr_draft(root)
        assert fake['fabrication_detected'] is True
        assert fake['recommendation'] == 'fail'


def main() -> int:
    with tempfile.TemporaryDirectory(prefix='release-dogfood-output-') as tmp:
        root = Path(tmp).resolve()
        result = run_dogfood(root)
        assert result['readiness_value'] == 'READY_FOR_099_PUBLIC_ALPHA_FREEZE'
        assert_trace(root)
        assert (root / '.zoo-agent' / 'release_dogfood' / 'release_workflow_replay.md').exists()
        assert (root / '.zoo-agent' / 'release_dogfood' / 'release_product_report.md').exists()
        readiness = load(root / '.zoo-agent' / 'release_dogfood' / 'readiness_for_099.json')
        assert readiness['readiness'] == 'READY_FOR_099_PUBLIC_ALPHA_FREEZE'

    assert_negative_gates()

    help_text = run([sys.executable, str(AGENT), '--help'], ROOT).stdout
    assert 'release --dogfood' not in help_text
    with tempfile.TemporaryDirectory(prefix='release-dogfood-cli-') as tmp:
        root = Path(tmp).resolve()
        proc = run([sys.executable, str(AGENT), 'release', '--dogfood', '--workspace', str(root)], root)
        payload = json.loads(proc.stdout)
        assert payload['task'] == 'release workflow dogfood'
        assert 'READY_FOR_099_PUBLIC_ALPHA_FREEZE' in payload['result']
        assert 'release_product_report.md' in payload['result']

    print('release workflow dogfood tests passed')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
