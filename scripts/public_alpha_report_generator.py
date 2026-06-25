#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from public_alpha_audit import run_audit
from public_alpha_packager import public_alpha_dir
from runtime_common import load_json, project_root, utc_now, write_json


def status_from_audit(audit: dict[str, Any]) -> str:
    if audit.get('recommendation') == 'pass' and audit.get('safe_to_publish'):
        return 'READY_FOR_100_PUBLIC_ALPHA_RELEASE'
    if audit.get('recommendation') == 'fail':
        return 'NOT_READY'
    return 'FIX_BEFORE_100'


def generate_report(project: Path, *, refresh: bool = True) -> dict[str, Any]:
    out = public_alpha_dir(project)
    audit = run_audit(project) if refresh else load_json(out / 'public_alpha_audit.json')
    manifest = load_json(out / 'public_alpha_package_manifest.json')
    positioning = load_json(out / 'public_positioning_report.json')
    safety = load_json(out / 'public_docs_safety_report.json')
    demo = load_json(out / 'demo_fixture_manifest.json')
    status = status_from_audit(audit)
    report = '\n'.join(
        [
            '# Public Alpha Report',
            '',
            f'Generated: {utc_now()}',
            '',
            '## Final Judgment',
            '',
            status,
            '',
            '## Scores',
            '',
            f'- public alpha: {audit.get("public_alpha_score")}',
            f'- positioning: {audit.get("positioning_score")}',
            f'- docs safety: {audit.get("docs_safety_score")}',
            f'- packaging: {audit.get("packaging_score")}',
            f'- demo: {audit.get("demo_score")}',
            f'- test coverage: {audit.get("test_coverage_score")}',
            '',
            '## Positioning',
            '',
            '- Product identity: AI Project Operator',
            '- Tagline: Give it a project. It keeps moving it forward.',
            f'- Codex wrapper risk: {positioning.get("codex_wrapper_risk")}',
            '',
            '## Safety',
            '',
            f'- docs safe: {safety.get("safe")}',
            '- local-first release and PR workflow',
            '- no GitHub API, push, merge, remote PR, deployment, token read, or `.env` content read',
            '',
            '## Package',
            '',
            f'- docs: {len(manifest.get("docs") or [])}',
            f'- demo artifacts: {len(demo.get("generated_artifacts") or [])}',
            f'- safe to publish: {audit.get("safe_to_publish")}',
            '',
            '## Must Fix Before 1.0',
            '',
            *(f'- {item}' for item in (audit.get('must_fix_before_100') or ['none'])),
            '',
        ]
    )
    report_path = out / 'public_alpha_report.md'
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report, encoding='utf-8')
    readiness = {
        'generated_at': utc_now(),
        'readiness': status,
        'public_alpha_score': audit.get('public_alpha_score'),
        'safe_to_publish': audit.get('safe_to_publish'),
        'must_fix_before_100': audit.get('must_fix_before_100') or [],
        'recommended_next_steps': ['prepare v1.0 public alpha release notes']
        if status == 'READY_FOR_100_PUBLIC_ALPHA_RELEASE'
        else ['fix failed public alpha audit checks'],
    }
    write_json(out / 'readiness_for_100.json', readiness)
    payload = {
        'status': status,
        'report_path': '.zoo-agent/public_alpha/public_alpha_report.md',
        'readiness': readiness,
    }
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--workspace', default='.')
    parser.add_argument('--no-refresh', action='store_true')
    args = parser.parse_args(argv)
    project = project_root(args.workspace)
    payload = generate_report(project, refresh=not args.no_refresh)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload.get('status') == 'READY_FOR_100_PUBLIC_ALPHA_RELEASE' else 1


if __name__ == '__main__':
    raise SystemExit(main())
