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
    proc = subprocess.run(cmd, cwd=cwd, text=True, encoding='utf-8', errors='replace', capture_output=True)
    if check and proc.returncode != 0:
        raise AssertionError(f'command failed: {" ".join(cmd)}\nstdout={proc.stdout}\nstderr={proc.stderr}')
    return proc


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding='utf-8-sig'))


def make_clean_repo(root: Path) -> None:
    (root / 'README.md').write_text('# PR Fixture\n', encoding='utf-8')
    (root / 'INSTALL.md').write_text('# Install\n', encoding='utf-8')
    (root / 'QUICKSTART.md').write_text('# Quickstart\n', encoding='utf-8')
    (root / 'LICENSE').write_text('MIT\n', encoding='utf-8')
    (root / 'tests').mkdir()
    (root / 'tests' / 'test_basic.py').write_text('def test_basic():\n    assert True\n', encoding='utf-8')
    (root / '.zoo-agent' / 'map').mkdir(parents=True, exist_ok=True)
    project_map = {
        'project_name': 'pr-fixture',
        'project_type': 'agent_runtime',
        'main_goal': 'public release',
        'modules': [],
        'capabilities': [
            {
                'capability_id': 'docs',
                'name': 'Docs ready',
                'status': 'verified',
                'evidence': [{'source': 'README.md'}],
                'related_modules': [],
            }
        ],
        'risks': [],
        'next_actions': [],
    }
    (root / '.zoo-agent' / 'map' / 'project_map.json').write_text(json.dumps(project_map, indent=2), encoding='utf-8')
    run(['git', 'init'], root)
    run(['git', 'config', 'user.email', 'pr@example.local'], root)
    run(['git', 'config', 'user.name', 'PR Test'], root)
    run(
        [
            'git',
            'add',
            'README.md',
            'INSTALL.md',
            'QUICKSTART.md',
            'LICENSE',
            'tests/test_basic.py',
            '.zoo-agent/map/project_map.json',
        ],
        root,
    )
    run(['git', 'commit', '-m', 'init'], root)


def main() -> int:
    with tempfile.TemporaryDirectory(prefix='pr-draft-safety-') as tmp:
        root = Path(tmp).resolve()
        make_clean_repo(root)
        for script in [
            'git_context_detector.py',
            'release_readiness_template_builder.py',
            'github_readiness_detector.py',
            'release_readiness_evaluator.py',
            'pr_plan_generator.py',
            'pr_draft_generator.py',
            'release_notes_generator.py',
            'changelog_draft_generator.py',
        ]:
            run([sys.executable, str(SCRIPTS / script), '--workspace', str(root)], root)

        plan = load(root / '.zoo-agent' / 'release' / 'pr_plan.json')
        assert plan['changed_areas'] == []
        draft = (root / '.zoo-agent' / 'release' / 'pr_draft.md').read_text(encoding='utf-8')
        assert 'Draft only; no code changes included yet.' in draft
        assert 'Not run in this workflow' in draft
        notes = (root / '.zoo-agent' / 'release' / 'release_notes_draft.md').read_text(encoding='utf-8')
        changelog = (root / '.zoo-agent' / 'release' / 'changelog_draft.md').read_text(encoding='utf-8')
        assert '1.0.0' not in notes and '1.0.0' not in changelog
        assert 'Unreleased' in changelog

    with tempfile.TemporaryDirectory(prefix='pr-safety-negative-') as tmp:
        root = Path(tmp).resolve()
        release_dir = root / '.zoo-agent' / 'release'
        release_dir.mkdir(parents=True)
        fake_abs_path = 'C:' + '\\Users\\someone\\repo'
        (release_dir / 'bad_artifact.md').write_text(
            f'PUSH_EXECUTED\nNETWORK_CALL\nhttps://user:secret@github.com/example/repo.git\n{fake_abs_path}\nRAW_BACKEND_LOG\n',
            encoding='utf-8',
        )
        proc = run(
            [sys.executable, str(SCRIPTS / 'github_workflow_safety_gate.py'), '--workspace', str(root)],
            root,
            check=False,
        )
        assert proc.returncode != 0
        safety = load(release_dir / 'github_workflow_safety_report.json')
        assert safety['safe'] is False
        assert safety['push_detected'] is True
        assert safety['network_call_detected'] is True
        assert safety['secret_leak_detected'] is True
        assert safety['absolute_path_leak_detected'] is True

    print('pr draft safety tests passed')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
