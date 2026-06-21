#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AGENT = ROOT / 'scripts' / 'agent.py'


def run(cmd: list[str], cwd: Path, *, check: bool = True) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env.setdefault('CODEX_HOME', str(Path(tempfile.mkdtemp(prefix='release-test-codex-home-')).resolve()))
    proc = subprocess.run(
        cmd,
        cwd=cwd,
        env=env,
        text=True,
        encoding='utf-8',
        errors='replace',
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if check and proc.returncode != 0:
        raise AssertionError(f"command failed: {' '.join(cmd)}\nstdout={proc.stdout}\nstderr={proc.stderr}")
    return proc


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding='utf-8-sig'))


def make_repo(root: Path) -> None:
    (root / 'README.md').write_text('# Release Fixture\n\nUse `agent release`.\n', encoding='utf-8')
    (root / 'INSTALL.md').write_text('# Install\n\nRun locally.\n', encoding='utf-8')
    (root / 'QUICKSTART.md').write_text('# Quickstart\n\nRun `agent status`.\n', encoding='utf-8')
    (root / 'LICENSE').write_text('MIT\n', encoding='utf-8')
    (root / 'CHANGELOG.md').write_text('# Changelog\n\n## Unreleased\n', encoding='utf-8')
    (root / 'docs').mkdir()
    (root / 'docs' / 'guide.md').write_text('# Guide\n', encoding='utf-8')
    (root / 'tests').mkdir()
    (root / 'tests' / 'test_basic.py').write_text('def test_basic():\n    assert True\n', encoding='utf-8')
    (root / '.zoo-agent' / 'map').mkdir(parents=True)
    project_map = {
        'project_name': 'release-fixture',
        'project_type': 'agent_runtime',
        'main_goal': 'prepare this project for public release',
        'modules': [{'module_id': 'docs', 'name': 'Docs', 'status': 'mapped', 'confidence': 0.7, 'key_files': ['README.md'], 'evidence': [{'source': 'README.md'}]}],
        'capabilities': [{'capability_id': 'cli', 'name': 'CLI', 'status': 'verified', 'evidence': [{'source': 'README.md'}], 'related_modules': ['docs']}],
        'risks': [],
        'next_actions': [{'action_id': 'release-docs', 'title': 'Refresh release docs', 'why_now': 'Release docs are part of public readiness.', 'expected_impact': 'Clearer handoff.', 'risk_level': 'low', 'target_files': ['README.md'], 'autopilot_eligible': True, 'evidence': [{'source': 'README.md'}]}],
        'last_updated': '2026-01-01T00:00:00Z',
    }
    (root / '.zoo-agent' / 'map' / 'project_map.json').write_text(json.dumps(project_map, indent=2), encoding='utf-8')
    run(['git', 'init'], root)
    run(['git', 'config', 'user.email', 'release@example.local'], root)
    run(['git', 'config', 'user.name', 'Release Test'], root)
    fake_token = 'ghp_' + ('1' * 36)
    run(['git', 'remote', 'add', 'origin', f'https://user:{fake_token}@github.com/example/release-fixture.git'], root)
    run(['git', 'add', 'README.md', 'INSTALL.md', 'QUICKSTART.md', 'LICENSE', 'CHANGELOG.md', 'docs/guide.md', 'tests/test_basic.py'], root)
    run(['git', 'commit', '-m', 'init'], root)


def assert_no_sensitive_release_artifacts(root: Path) -> None:
    release_dir = root / '.zoo-agent' / 'release'
    text = '\n'.join(path.read_text(encoding='utf-8', errors='replace') for path in release_dir.glob('*') if path.is_file())
    assert 'ghp_' + ('1' * 36) not in text
    assert 'user:ghp_' not in text
    assert 'RAW_BACKEND_LOG' not in text
    assert str(root) not in text


def main() -> int:
    with tempfile.TemporaryDirectory(prefix='github-release-workflow-') as tmp:
        root = Path(tmp).resolve()
        make_repo(root)
        help_text = run([sys.executable, str(AGENT), '--help'], root).stdout
        assert 'agent release' in help_text
        assert 'agent pr' in help_text
        assert '--doctor' not in help_text and '--safety-check' not in help_text

        release_proc = run([sys.executable, str(AGENT), 'release', '--workspace', str(root)], root)
        release_payload = json.loads(release_proc.stdout)
        assert release_payload['task'] == 'release workflow'
        assert 'GITHUB_PR_RELEASE_WORKFLOW_098_READY' in release_payload['result']

        pr_proc = run([sys.executable, str(AGENT), 'pr', '--workspace', str(root)], root)
        pr_payload = json.loads(pr_proc.stdout)
        assert pr_payload['task'] == 'pr draft'
        assert '.zoo-agent/release/pr_draft.md' in pr_payload['result']

        release_dir = root / '.zoo-agent' / 'release'
        for name in [
            'git_context.json',
            'github_readiness.json',
            'release_readiness.json',
            'release_readiness_report.md',
            'pr_plan.json',
            'pr_draft.md',
            'release_notes_draft.md',
            'changelog_draft.md',
            'release_action_plan.json',
            'release_workflow_report.md',
            'github_workflow_safety_report.json',
            'readiness_for_0981.json',
        ]:
            assert (release_dir / name).exists(), name
        git_context = load(release_dir / 'git_context.json')
        assert git_context['remote']['provider'] == 'github'
        assert git_context['remote']['token_redacted'] is True
        assert '<redacted>' in git_context['remote']['sanitized_remote']
        assert load(release_dir / 'github_workflow_safety_report.json')['safe'] is True
        assert load(release_dir / 'readiness_for_0981.json')['readiness'] == 'GITHUB_PR_RELEASE_WORKFLOW_098_READY'

        cockpit = root / '.zoo-agent' / 'cockpit' / 'index.html'
        assert cockpit.exists()
        cockpit_text = cockpit.read_text(encoding='utf-8', errors='replace')
        assert 'Release / PR' in cockpit_text
        assert 'PR draft' in cockpit_text
        assert 'ghp_' not in cockpit_text
        assert_no_sensitive_release_artifacts(root)
    print('github pr release workflow tests passed')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
