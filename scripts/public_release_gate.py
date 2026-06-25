#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from demo_fixture_packager import ensure_demo_fixture
from public_alpha_audit import run_audit
from public_docs_leakage_scanner import scan_project
from public_positioning_linter import lint_project
from public_release_packager import VERSION, public_release_dir, write_release_manifest
from runtime_common import project_root, utc_now, write_json

PUBLIC_HELP_FORBIDDEN = [
    'worker dogfood',
    'learning dogfood',
    'alpha audit',
    'release dogfood',
    'session dogfood',
    'eval',
    'governance',
    'planner',
    'verifier',
    'scheduler',
    'backend internals',
    'agent publish',
]

ALLOWED_RELEASE_CHANGES = (
    'VERSION',
    'GITHUB_RELEASE_DRAFT.md',
    'PUBLIC_RELEASE_CHECKLIST.md',
    'README.md',
    'QUICKSTART.md',
    'CLI_REFERENCE.md',
    'PRODUCT_POSITIONING.md',
    'ARCHITECTURE.md',
    'PRIVACY.md',
    'SAFETY_MODEL.md',
    'DEMO.md',
    'ROADMAP.md',
    'RELEASE_NOTES.md',
    'ALPHA_RELEASE_CHECKLIST.md',
    'PUBLIC_ALPHA_REPORT.md',
    'scripts/',
    'examples/demo_project/',
    '.github/',
    'FEEDBACK.md',
    'LAUNCH.md',
    'FIRST_USER_TEST_PLAN.md',
    'POST_RELEASE_SMOKE_TEST.md',
    'COMMUNITY_POSTS.md',
    'FAQ.md',
    'KNOWN_LIMITATIONS.md',
    'CONTRIBUTING.md',
    'SECURITY.md',
    'PUBLISHING.md',
    'BRANCHING.md',
    'POST_LAUNCH_STATUS.md',
)


def version_text(project: Path) -> str:
    path = project / 'VERSION'
    return path.read_text(encoding='utf-8-sig').strip() if path.exists() else ''


def git_dirty_files(project: Path) -> list[str]:
    try:
        proc = subprocess.run(
            ['git', 'status', '--porcelain'],
            cwd=project,
            text=True,
            encoding='utf-8',
            errors='replace',
            capture_output=True,
            timeout=8,
        )
    except Exception:
        return []
    files = []
    for line in proc.stdout.splitlines():
        rel = line[3:].strip()
        if ' -> ' in rel:
            rel = rel.split(' -> ', 1)[1].strip()
        files.append(rel.replace('\\', '/'))
    return files


def release_allowed_dirty(files: list[str]) -> bool:
    return all(
        any(path == allowed or path.startswith(allowed) for allowed in ALLOWED_RELEASE_CHANGES) for path in files
    )


def cli_surface(project: Path) -> dict[str, Any]:
    proc = subprocess.run(
        [sys.executable, str(project / 'scripts' / 'agent.py'), '--help'],
        cwd=project,
        text=True,
        encoding='utf-8',
        errors='replace',
        capture_output=True,
    )
    text = proc.stdout.lower()
    forbidden = [item for item in PUBLIC_HELP_FORBIDDEN if item in text]
    required = [
        'agent "<task>"',
        'agent start "<project goal>"',
        'agent status',
        'agent continue',
        'agent stop',
        'agent undo',
        'agent cockpit',
        'agent release',
        'agent pr',
    ]
    missing = [item for item in required if item not in proc.stdout]
    score = 1.0 if proc.returncode == 0 and not forbidden and not missing else 0.0
    return {'score': score, 'forbidden': forbidden, 'missing': missing}


def tracked_runtime_artifacts(project: Path) -> list[str]:
    proc = subprocess.run(
        ['git', 'ls-files', '.zoo-agent'],
        cwd=project,
        text=True,
        encoding='utf-8',
        errors='replace',
        capture_output=True,
    )
    return [line.strip() for line in proc.stdout.splitlines() if line.strip()]


def evaluate_gate(project: Path) -> dict[str, Any]:
    ensure_demo_fixture(project)
    alpha_audit = run_audit(project)
    positioning = lint_project(project)
    docs_safety = scan_project(project)
    package = write_release_manifest(project)
    cli = cli_surface(project)
    dirty = git_dirty_files(project)
    version = version_text(project)
    release_notes = (
        (project / 'RELEASE_NOTES.md').read_text(encoding='utf-8-sig', errors='replace')
        if (project / 'RELEASE_NOTES.md').exists()
        else ''
    )
    readme = (
        (project / 'README.md').read_text(encoding='utf-8-sig', errors='replace')
        if (project / 'README.md').exists()
        else ''
    )
    demo_safe = (
        bool((project / 'examples' / 'demo_project' / 'README.md').exists())
        and not (project / 'examples' / 'demo_project' / '.env').exists()
    )
    runtime_tracked = tracked_runtime_artifacts(project)

    must_fix: list[str] = []
    if version != VERSION:
        must_fix.append('version_mismatch')
    if f'v{VERSION}' not in release_notes and VERSION not in release_notes:
        must_fix.append('release_notes_missing_version')
    if 'AI Project Operator' not in readme.split('\n', 12)[0:12]:
        first_lines = '\n'.join(readme.splitlines()[:12])
        if 'AI Project Operator' not in first_lines:
            must_fix.append('readme_positioning')
    if positioning.get('positioning_score', 0) < 0.95:
        must_fix.append('positioning_score')
    if not docs_safety.get('safe'):
        must_fix.append('docs_safety')
    if cli['score'] < 1.0:
        must_fix.append('cli_surface')
    if not demo_safe:
        must_fix.append('demo_fixture')
    if not package.get('safe_to_package'):
        must_fix.append('package_manifest')
    if runtime_tracked:
        must_fix.append('tracked_runtime_artifacts')
    if dirty and not release_allowed_dirty(dirty):
        must_fix.append('unexpected_dirty_worktree')
    if alpha_audit.get('recommendation') != 'pass':
        must_fix.append('public_alpha_audit')

    positioning_score = float(positioning.get('positioning_score') or 0.0)
    docs_safety_score = 1.0 if docs_safety.get('safe') else 0.0
    cli_surface_score = float(cli['score'])
    demo_score = 1.0 if demo_safe else 0.0
    test_score = (
        1.0
        if all(
            (project / path).exists()
            for path in [
                'scripts/test_public_release_gate.py',
                'scripts/test_fresh_clone_public_alpha.py',
                'scripts/test_github_release_draft.py',
            ]
        )
        else 0.0
    )
    component_scores = [
        positioning_score,
        docs_safety_score,
        cli_surface_score,
        demo_score,
        test_score,
        1.0 if package.get('safe_to_package') else 0.0,
    ]
    release_gate_score = round(sum(component_scores) / len(component_scores), 3)
    safe_to_release = (
        release_gate_score >= 0.95
        and positioning_score >= 0.95
        and docs_safety_score == 1.0
        and cli_surface_score == 1.0
        and not must_fix
    )
    recommendation = 'pass' if safe_to_release else 'fix_before_publish'
    if docs_safety_score == 0.0 or positioning.get('recommendation') == 'fail':
        recommendation = 'fail'
    payload = {
        'generated_at': utc_now(),
        'release_gate_score': release_gate_score,
        'version': VERSION,
        'positioning_score': positioning_score,
        'docs_safety_score': docs_safety_score,
        'cli_surface_score': cli_surface_score,
        'demo_score': demo_score,
        'test_score': test_score,
        'safe_to_release': safe_to_release,
        'must_fix': sorted(set(must_fix)),
        'recommendation': recommendation,
        'dirty_files': dirty,
        'tracked_runtime_artifacts': runtime_tracked,
    }
    write_json(public_release_dir(project) / 'public_release_gate.json', payload)
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--workspace', default='.')
    args = parser.parse_args(argv)
    payload = evaluate_gate(project_root(args.workspace))
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload.get('recommendation') == 'pass' else 1


if __name__ == '__main__':
    raise SystemExit(main())
