#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from public_release_gate import evaluate_gate  # noqa: E402
from public_release_packager import VERSION, write_release_manifest  # noqa: E402


def run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(cmd, cwd=ROOT, text=True, encoding='utf-8', errors='replace', stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if proc.returncode != 0:
        raise AssertionError(f"command failed: {' '.join(cmd)}\nstdout={proc.stdout}\nstderr={proc.stderr}")
    return proc


def test_version_file_exists() -> None:
    assert (ROOT / 'VERSION').read_text(encoding='utf-8').strip() == VERSION


def test_readme_keeps_operator_positioning() -> None:
    first_viewport = '\n'.join((ROOT / 'README.md').read_text(encoding='utf-8').splitlines()[:20])
    assert 'AI Project Operator' in first_viewport
    assert 'Give it a project. It keeps moving it forward.' in first_viewport
    assert 'Codex wrapper' in first_viewport
    assert 'not a Codex wrapper' in first_viewport


def test_public_release_package_manifest_excludes_runtime_artifacts() -> None:
    manifest = write_release_manifest(ROOT)
    assert manifest['version'] == VERSION
    assert manifest['safe_to_package'] is True, manifest
    assert not any(path.startswith('.zoo-agent/') for path in manifest['included_files'])
    assert '.zoo-agent/' in manifest['excluded_runtime_artifacts']
    assert 'VERSION' in manifest['included_files']
    assert 'GITHUB_RELEASE_DRAFT.md' in manifest['included_files']
    assert 'PUBLIC_RELEASE_CHECKLIST.md' in manifest['included_files']


def test_public_release_gate_passes() -> None:
    gate = evaluate_gate(ROOT)
    assert gate['version'] == VERSION
    assert gate['recommendation'] == 'pass', gate
    assert gate['release_gate_score'] >= 0.95, gate
    assert gate['safe_to_release'] is True, gate


def test_agent_publish_preflight_runs_and_help_hides_it() -> None:
    help_proc = run([sys.executable, str(ROOT / 'scripts' / 'agent.py'), '--help'])
    forbidden = ['agent publish', 'publish --preflight', 'worker dogfood', 'learning dogfood', 'alpha audit', 'release dogfood', 'session dogfood']
    for item in forbidden:
        assert item not in help_proc.stdout.lower()
    proc = run([sys.executable, str(ROOT / 'scripts' / 'agent.py'), 'publish', '--preflight', '--workspace', str(ROOT)])
    assert '.zoo-agent/public_release/public_release_gate.json' in proc.stdout
    assert 'recommendation: pass' in proc.stdout


def main() -> None:
    test_version_file_exists()
    test_readme_keeps_operator_positioning()
    test_public_release_package_manifest_excludes_runtime_artifacts()
    test_public_release_gate_passes()
    test_agent_publish_preflight_runs_and_help_hides_it()
    print('public release gate tests passed')


if __name__ == '__main__':
    main()
