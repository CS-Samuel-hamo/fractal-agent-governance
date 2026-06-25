#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from demo_fixture_packager import ensure_demo_fixture
from public_alpha_audit import run_audit
from public_alpha_packager import CORE_SCRIPTS, CORE_TESTS, PUBLIC_DOCS, write_manifest
from public_alpha_report_generator import generate_report


def run(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(cmd, cwd=cwd, text=True, encoding='utf-8', errors='replace', capture_output=True)
    if proc.returncode != 0:
        raise AssertionError(f'command failed: {" ".join(cmd)}\nstdout={proc.stdout}\nstderr={proc.stderr}')
    return proc


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding='utf-8-sig'))


def test_demo_fixture_packager_manifest() -> None:
    manifest = ensure_demo_fixture(ROOT)
    assert manifest['safe_to_use'] is True, manifest
    assert 'examples/demo_project/README.md' in manifest['generated_artifacts'], manifest
    assert 'project_map_demo' in manifest['scenarios'], manifest


def test_public_alpha_packager_manifest() -> None:
    manifest = write_manifest(ROOT)
    assert manifest['safe_to_publish'] is True, manifest
    assert '.zoo-agent/' in manifest['ignored_runtime_artifacts'], manifest
    assert not any(path.startswith('.zoo-agent/') for path in manifest['included_files']), manifest
    for doc in PUBLIC_DOCS:
        assert doc in manifest['docs'], doc
    for script in CORE_SCRIPTS:
        assert script in manifest['scripts'], script
    for test in CORE_TESTS:
        assert test in manifest['tests'], test
    assert any(path.startswith('examples/demo_project/') for path in manifest['examples'])


def test_public_alpha_audit_and_report_ready() -> None:
    audit = run_audit(ROOT)
    assert audit['safe_to_publish'] is True, audit
    assert audit['recommendation'] == 'pass', audit
    payload = generate_report(ROOT)
    assert payload['status'] == 'READY_FOR_100_PUBLIC_ALPHA_RELEASE', payload
    readiness = load(ROOT / '.zoo-agent' / 'public_alpha' / 'readiness_for_100.json')
    assert readiness['readiness'] == 'READY_FOR_100_PUBLIC_ALPHA_RELEASE', readiness
    assert (ROOT / '.zoo-agent' / 'public_alpha' / 'public_alpha_report.md').exists()


def test_agent_alpha_audit_runs_and_help_hides_it() -> None:
    help_proc = run([sys.executable, str(ROOT / 'scripts' / 'agent.py'), '--help'], ROOT)
    assert 'alpha --audit' not in help_proc.stdout
    assert 'agent alpha' not in help_proc.stdout
    proc = run([sys.executable, str(ROOT / 'scripts' / 'agent.py'), 'alpha', '--audit', '--workspace', str(ROOT)], ROOT)
    assert '.zoo-agent/public_alpha/public_alpha_report.md' in proc.stdout
    assert 'READY_FOR_100_PUBLIC_ALPHA_RELEASE' in proc.stdout


def main() -> None:
    test_demo_fixture_packager_manifest()
    test_public_alpha_packager_manifest()
    test_public_alpha_audit_and_report_ready()
    test_agent_alpha_audit_runs_and_help_hides_it()
    print('public alpha packaging tests OK')


if __name__ == '__main__':
    main()
