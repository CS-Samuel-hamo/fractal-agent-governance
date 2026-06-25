#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from demo_fixture_packager import ensure_demo_fixture
from public_alpha_packager import public_alpha_dir, write_manifest
from public_docs_leakage_scanner import scan_project
from public_positioning_linter import lint_project
from runtime_common import project_root, utc_now, write_json


def score_packaging(manifest: dict[str, Any]) -> float:
    required_groups = [
        bool(manifest.get('docs')),
        bool(manifest.get('examples')),
        bool(manifest.get('scripts')),
        bool(manifest.get('tests')),
        bool(manifest.get('safe_to_publish')),
    ]
    return round(sum(1 for item in required_groups if item) / len(required_groups), 3)


def score_demo(demo: dict[str, Any]) -> float:
    required = {'project_map_demo', 'session_start_demo', 'cockpit_demo', 'release_pack_demo', 'pr_draft_demo'}
    scenarios = set(demo.get('scenarios') or [])
    base = len(required & scenarios) / len(required)
    if not demo.get('safe_to_use'):
        base -= 0.5
    return round(max(0.0, min(1.0, base)), 3)


def run_audit(project: Path) -> dict[str, Any]:
    demo = ensure_demo_fixture(project)
    manifest = write_manifest(project)
    positioning = lint_project(project)
    docs_safety = scan_project(project)

    packaging_score = score_packaging(manifest)
    demo_score = score_demo(demo)
    positioning_score = float(positioning.get('positioning_score') or 0.0)
    docs_safety_score = 1.0 if docs_safety.get('safe') else 0.0
    test_coverage_score = 1.0 if all((project / path).exists() for path in manifest.get('tests', [])) else 0.0
    scores = [positioning_score, docs_safety_score, packaging_score, demo_score, test_coverage_score]
    public_alpha_score = round(sum(scores) / len(scores), 3)

    must_fix: list[str] = []
    if positioning.get('recommendation') != 'pass':
        must_fix.append('public_positioning')
    if not docs_safety.get('safe'):
        must_fix.append('public_docs_safety')
    if not manifest.get('safe_to_publish'):
        must_fix.append('package_manifest')
    if demo_score < 0.85:
        must_fix.append('demo_fixture')
    if test_coverage_score < 1.0:
        must_fix.append('public_alpha_tests')

    safe_to_publish = (
        public_alpha_score >= 0.9
        and positioning_score >= 0.9
        and docs_safety_score == 1.0
        and packaging_score >= 0.9
        and demo_score >= 0.85
        and not must_fix
    )
    recommendation = 'pass' if safe_to_publish else 'fix_before_100'
    if docs_safety_score == 0.0 or positioning.get('recommendation') == 'fail':
        recommendation = 'fail'
    audit = {
        'generated_at': utc_now(),
        'public_alpha_score': public_alpha_score,
        'positioning_score': positioning_score,
        'docs_safety_score': docs_safety_score,
        'packaging_score': packaging_score,
        'demo_score': demo_score,
        'test_coverage_score': test_coverage_score,
        'safe_to_publish': safe_to_publish,
        'must_fix_before_100': must_fix,
        'recommendation': recommendation,
    }
    write_json(public_alpha_dir(project) / 'public_alpha_audit.json', audit)
    return audit


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--workspace', default='.')
    args = parser.parse_args(argv)
    project = project_root(args.workspace)
    audit = run_audit(project)
    print(json.dumps(audit, ensure_ascii=False, indent=2))
    return 0 if audit.get('recommendation') == 'pass' else 1


if __name__ == '__main__':
    raise SystemExit(main())
