#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / 'scripts'


def run(cmd: list[str], cwd: Path, *, check: bool = True) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(cmd, cwd=cwd, text=True, encoding='utf-8', errors='replace', stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if check and proc.returncode != 0:
        raise AssertionError(f"command failed: {' '.join(cmd)}\nstdout={proc.stdout}\nstderr={proc.stderr}")
    return proc


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding='utf-8-sig'))


def write_blocked_map(root: Path) -> None:
    (root / '.zoo-agent' / 'map').mkdir(parents=True, exist_ok=True)
    payload = {
        'project_name': 'blocked-fixture',
        'project_type': 'agent_runtime',
        'main_goal': 'public release',
        'modules': [],
        'capabilities': [],
        'risks': [{'risk_id': 'auth', 'description': 'Auth and secret area touched', 'severity': 'high', 'affected_files': ['auth/secrets.py'], 'evidence': [{'source': 'fixture'}]}],
        'next_actions': [
            {
                'action_id': 'blocked',
                'title': 'Update auth deployment secrets',
                'why_now': 'Fixture high-risk action.',
                'expected_impact': 'Unsafe release path.',
                'risk_level': 'high',
                'target_files': ['auth/secrets.py'],
                'autopilot_eligible': True,
                'evidence': [{'source': 'fixture'}],
            }
        ],
    }
    (root / '.zoo-agent' / 'map' / 'project_map.json').write_text(json.dumps(payload, indent=2), encoding='utf-8')


def main() -> int:
    with tempfile.TemporaryDirectory(prefix='release-readiness-non-git-') as tmp:
        non_git = Path(tmp).resolve()
        git_context = json.loads(run([sys.executable, str(SCRIPTS / 'git_context_detector.py'), '--workspace', str(non_git)], non_git).stdout)
        assert git_context['is_git_repo'] is False
        assert (non_git / '.zoo-agent' / 'release' / 'git_context.json').exists()

    with tempfile.TemporaryDirectory(prefix='release-readiness-missing-') as tmp:
        root = Path(tmp).resolve()
        run(['git', 'init'], root)
        write_blocked_map(root)
        run([sys.executable, str(SCRIPTS / 'git_context_detector.py'), '--workspace', str(root)], root)
        run([sys.executable, str(SCRIPTS / 'release_readiness_template_builder.py'), '--workspace', str(root)], root)
        run([sys.executable, str(SCRIPTS / 'github_readiness_detector.py'), '--workspace', str(root)], root)
        readiness_proc = run([sys.executable, str(SCRIPTS / 'release_readiness_evaluator.py'), '--workspace', str(root)], root)
        readiness = json.loads(readiness_proc.stdout)
        github = load(root / '.zoo-agent' / 'release' / 'github_readiness.json')
        assert 'README missing' in github['blockers']
        assert 'tests or test notes missing' in github['blockers']
        assert 'license decision missing' in github['blockers']
        assert 'README missing' in readiness['must_fix']
        assert readiness['recommended_sequence'], 'learning release template was not consumed'

        run([sys.executable, str(SCRIPTS / 'release_action_plan_generator.py'), '--workspace', str(root)], root)
        action_plan = load(root / '.zoo-agent' / 'release' / 'release_action_plan.json')
        assert action_plan['blocked_actions'], 'blocked zone was not captured'
        assert all(not item.get('autopilot_eligible') for item in action_plan['blocked_actions'])
        assert not any(item.get('action') == 'Update auth deployment secrets' and item.get('autopilot_eligible') for item in action_plan['next_actions'])

        report = (root / '.zoo-agent' / 'release' / 'release_readiness_report.md').read_text(encoding='utf-8')
        assert 'Release Readiness Report' in report
        assert 'planner' not in report.lower() and 'verifier' not in report.lower()

    print('release readiness workflow tests passed')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
