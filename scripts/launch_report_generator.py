#!/usr/bin/env python3
from __future__ import annotations

import argparse
import contextlib
import io
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from public_launch_audit import audit  # noqa: E402
from public_launch_packager import RELEASE_TAG, VERSION, public_launch_dir  # noqa: E402
from runtime_common import load_json, project_root, utc_now, write_json  # noqa: E402


def status_from_audit(payload: dict[str, Any]) -> str:
    if payload.get('recommendation') == 'pass' and payload.get('safe_to_launch'):
        return 'READY_FOR_MANUAL_GITHUB_PUBLISH'
    if payload.get('recommendation') == 'fail':
        return 'NOT_READY'
    return 'FIX_BEFORE_LAUNCH'


def generate(project: Path) -> dict[str, Any]:
    with contextlib.redirect_stdout(io.StringIO()):
        audit_payload = audit(project)
    out = public_launch_dir(project)
    package = load_json(out / 'public_launch_package.json')
    feedback = load_json(out / 'feedback_template_report.json')
    community = load_json(out / 'community_copy_report.json')
    first_user = load_json(out / 'first_user_flow_report.json')
    smoke = load_json(out / 'post_publish_smoke_report.json')
    status = status_from_audit(audit_payload)
    commands = package.get('manual_publish_commands') or []
    report = '\n'.join(
        [
            '# Public Launch Report',
            '',
            f'Generated: {utc_now()}',
            '',
            f'Release version: `v{VERSION}`',
            '',
            '## Final Recommendation',
            '',
            status,
            '',
            '## Product Positioning',
            '',
            '- AI Project Operator',
            '- Give it a project. It keeps moving it forward.',
            '- Project-level Autopilot, not task-level coding agent.',
            '',
            '## Manual Publish Commands',
            '',
            'These are manual commands. This tool did not push or create a remote GitHub release.',
            '',
            '```bash',
            *commands,
            '```',
            '',
            '## First User Flow',
            '',
            f"- score: {first_user.get('first_user_flow_score')}",
            f"- recommendation: {first_user.get('recommendation')}",
            '',
            '## Feedback Collection',
            '',
            f"- score: {feedback.get('feedback_template_score')}",
            f"- templates found: {len(feedback.get('templates_found') or [])}",
            '',
            '## Community Launch Copy',
            '',
            f"- score: {community.get('community_copy_score')}",
            f"- codex wrapper risk: {community.get('codex_wrapper_risk')}",
            '',
            '## Issue Templates',
            '',
            f"- missing templates: {len(feedback.get('missing_templates') or [])}",
            '',
            '## Demo Status',
            '',
            '- demo project: examples/demo_project/',
            '',
            '## Post-publish Smoke Plan',
            '',
            f"- smoke passed: {smoke.get('post_publish_smoke_passed')}",
            '',
            '## Known Launch Risks',
            '',
            '- Public alpha; feedback loop is intentionally lightweight.',
            '- No remote GitHub PR creation or GitHub API automation.',
            '- External workers may be unavailable locally.',
            '',
        ]
    )
    (out / 'public_launch_report.md').write_text(report, encoding='utf-8')
    readiness = {
        'generated_at': utc_now(),
        'readiness': status,
        'version': VERSION,
        'release_tag': RELEASE_TAG,
        'safe_to_launch': audit_payload.get('safe_to_launch'),
        'manual_publish_commands': commands,
        'must_fix_before_launch': audit_payload.get('must_fix_before_launch') or [],
    }
    write_json(out / 'readiness_for_public_launch.json', readiness)
    payload = {'status': status, 'report_path': '.zoo-agent/public_launch/public_launch_report.md', 'readiness': readiness}
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--workspace', default='.')
    args = parser.parse_args(argv)
    payload = generate(project_root(args.workspace))
    return 0 if payload.get('status') == 'READY_FOR_MANUAL_GITHUB_PUBLISH' else 1


if __name__ == '__main__':
    raise SystemExit(main())
