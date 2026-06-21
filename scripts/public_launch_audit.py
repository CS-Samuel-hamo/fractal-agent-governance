#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from community_copy_linter import lint as lint_community  # noqa: E402
from feedback_template_validator import validate as validate_feedback  # noqa: E402
from first_user_flow_validator import validate as validate_first_user  # noqa: E402
from post_publish_smoke_test import smoke as run_smoke  # noqa: E402
from public_launch_packager import public_launch_dir, write_package  # noqa: E402
from runtime_common import project_root, utc_now, write_json  # noqa: E402


def audit(project: Path) -> dict[str, Any]:
    package = write_package(project)
    feedback = validate_feedback(project)
    community = lint_community(project)
    first_user = validate_first_user(project)
    smoke = run_smoke(project)
    feedback_score = float(feedback.get('feedback_template_score') or 0.0)
    community_score = float(community.get('community_copy_score') or 0.0)
    first_score = float(first_user.get('first_user_flow_score') or 0.0)
    smoke_score = 1.0 if smoke.get('post_publish_smoke_passed') else 0.0
    package_score = 1.0 if package.get('safe_to_launch') else 0.0
    scores = [feedback_score, community_score, first_score, smoke_score, package_score]
    public_launch_score = round(sum(scores) / len(scores), 3)
    must_fix: list[str] = []
    if feedback_score < 0.9 or feedback.get('recommendation') != 'pass':
        must_fix.append('feedback_templates')
    if community_score < 0.85 or community.get('recommendation') != 'pass':
        must_fix.append('community_copy')
    if first_score < 0.9 or first_user.get('recommendation') != 'pass':
        must_fix.append('first_user_flow')
    if smoke_score < 0.9:
        must_fix.append('post_publish_smoke')
    if not package.get('safe_to_launch'):
        must_fix.append('public_launch_package')
    safe_to_launch = public_launch_score >= 0.9 and not must_fix
    recommendation = 'pass' if safe_to_launch else 'fix_before_launch'
    if community.get('recommendation') == 'fail' or feedback.get('recommendation') == 'fail':
        recommendation = 'fail'
    payload = {
        'generated_at': utc_now(),
        'public_launch_score': public_launch_score,
        'feedback_readiness_score': feedback_score,
        'community_readiness_score': community_score,
        'first_user_flow_score': first_score,
        'post_publish_smoke_score': smoke_score,
        'safe_to_launch': safe_to_launch,
        'must_fix_before_launch': sorted(set(must_fix)),
        'recommendation': recommendation,
    }
    write_json(public_launch_dir(project) / 'public_launch_audit.json', payload)
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--workspace', default='.')
    args = parser.parse_args(argv)
    payload = audit(project_root(args.workspace))
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload.get('recommendation') == 'pass' else 1


if __name__ == '__main__':
    raise SystemExit(main())
