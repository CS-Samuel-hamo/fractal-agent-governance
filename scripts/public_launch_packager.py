#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from public_release_packager import VERSION  # noqa: E402
from runtime_common import project_root, utc_now, write_json  # noqa: E402


RELEASE_TAG = f'v{VERSION}'
LAUNCH_DOCS = [
    'LAUNCH.md',
    'FEEDBACK.md',
    'FIRST_USER_TEST_PLAN.md',
    'POST_RELEASE_SMOKE_TEST.md',
    'COMMUNITY_POSTS.md',
    'FAQ.md',
    'KNOWN_LIMITATIONS.md',
    'CONTRIBUTING.md',
    'SECURITY.md',
]
FEEDBACK_TEMPLATES = [
    '.github/ISSUE_TEMPLATE/bug_report.md',
    '.github/ISSUE_TEMPLATE/feature_request.md',
    '.github/ISSUE_TEMPLATE/first_run_feedback.md',
    '.github/ISSUE_TEMPLATE/project_map_quality.md',
    '.github/ISSUE_TEMPLATE/autopilot_session_feedback.md',
    '.github/ISSUE_TEMPLATE/cockpit_feedback.md',
    '.github/ISSUE_TEMPLATE/release_pr_workflow_feedback.md',
    '.github/ISSUE_TEMPLATE/config.yml',
    '.github/PULL_REQUEST_TEMPLATE.md',
]


def public_launch_dir(project: Path) -> Path:
    return project / '.zoo-agent' / 'public_launch'


def build_package(project: Path) -> dict[str, Any]:
    launch_docs = [path for path in LAUNCH_DOCS if (project / path).exists()]
    feedback_templates = [path for path in FEEDBACK_TEMPLATES if (project / path).exists()]
    demo_assets = []
    demo_root = project / 'examples' / 'demo_project'
    if demo_root.exists():
        demo_assets = sorted(path.relative_to(project).as_posix() for path in demo_root.rglob('*') if path.is_file())
    manual_publish_commands = [
        f'git tag -a {RELEASE_TAG} -m "AI Project Operator {RELEASE_TAG}"',
        'git push origin main',
        f'git push origin {RELEASE_TAG}',
    ]
    post_publish_checks = [
        'agent launch --smoke',
        'agent --help',
        'agent cockpit',
        'agent release',
        'agent pr',
    ]
    safe_to_launch = len(launch_docs) == len(LAUNCH_DOCS) and len(feedback_templates) == len(FEEDBACK_TEMPLATES) and bool(demo_assets)
    payload = {
        'generated_at': utc_now(),
        'version': VERSION,
        'release_tag': RELEASE_TAG,
        'launch_docs': launch_docs,
        'feedback_templates': feedback_templates,
        'demo_assets': demo_assets,
        'manual_publish_commands': manual_publish_commands,
        'post_publish_checks': post_publish_checks,
        'manual_command_notice': [
            'These commands are manual.',
            'This tool did not push.',
            'This tool did not create a remote GitHub release.',
        ],
        'safe_to_launch': safe_to_launch,
    }
    return payload


def write_package(project: Path) -> dict[str, Any]:
    payload = build_package(project)
    write_json(public_launch_dir(project) / 'public_launch_package.json', payload)
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--workspace', default='.')
    args = parser.parse_args(argv)
    payload = write_package(project_root(args.workspace))
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload.get('safe_to_launch') else 1


if __name__ == '__main__':
    raise SystemExit(main())
