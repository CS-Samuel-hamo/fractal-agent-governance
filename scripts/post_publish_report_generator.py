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

from branch_hygiene_audit import audit as branch_audit  # noqa: E402
from default_branch_advisor import advise  # noqa: E402
from post_launch_status_generator import generate as generate_status  # noqa: E402
from post_publish_remote_verifier import verify  # noqa: E402
from publishing_command_linter import lint_project  # noqa: E402
from runtime_common import project_root, utc_now, write_json  # noqa: E402


POST_LAUNCH_DIR = Path('.zoo-agent') / 'post_launch'


def final_readiness(remote: dict[str, Any], branch: dict[str, Any], lint: dict[str, Any]) -> str:
    content_verified = bool(remote.get('tree_equal') and remote.get('local_remote_diff_empty'))
    if not content_verified or not remote.get('remote_tag_exists') or not remote.get('remote_branch_exists'):
        return 'NOT_VERIFIED'
    if not lint.get('publishing_command_lint_passed') or branch.get('recommendation') == 'fix_docs':
        return 'FIX_BRANCH_DOCS_FIRST'
    return 'READY_FOR_POST_LAUNCH_FEEDBACK_TRIAGE'


def build_report(remote: dict[str, Any], branch: dict[str, Any], lint: dict[str, Any], default: dict[str, Any], readiness: str) -> str:
    return '\n'.join(
        [
            '# Post Publish Report',
            '',
            f'Generated: {utc_now()}',
            '',
            '## Final Recommendation',
            '',
            readiness,
            '',
            '## Remote Publish Verification',
            '',
            f"- release branch verified: {remote.get('remote_branch_exists')}",
            f"- tag verified: {remote.get('remote_tag_exists')}",
            f"- content tree verified: {remote.get('tree_equal')}",
            f"- local/remote file diff empty: {remote.get('local_remote_diff_empty')}",
            f"- commit SHA differs but tree equal: {remote.get('commit_sha_differs_but_tree_equal')}",
            f"- GitHub Release object verified: {remote.get('github_release_object_verified')}",
            '',
            '## Branch Hygiene',
            '',
            f"- current branch: `{branch.get('current_branch')}`",
            f"- main exists: {branch.get('main_exists')}",
            f"- master exists: {branch.get('master_exists')}",
            f"- release branch exists: {branch.get('release_branch_exists')}",
            f"- master fast-forward safe: {branch.get('master_fast_forward_safe')}",
            f"- force push risk: {branch.get('force_push_risk')}",
            f"- branch hygiene recommendation: {branch.get('recommendation')}",
            '',
            '## Publishing Command Corrections',
            '',
            f"- lint passed: {lint.get('publishing_command_lint_passed')}",
            f"- hardcoded main push detected: {lint.get('hardcoded_main_push_detected')}",
            f"- force push detected: {lint.get('force_push_detected')}",
            f"- unsafe GitHub write detected: {lint.get('unsafe_github_write_detected')}",
            '',
            '## Default Branch Recommendation',
            '',
            f"- current default branch: `{default.get('current_default_branch')}`",
            f"- recommended default branch: `{default.get('recommended_default_branch')}`",
            f"- manual action needed: {default.get('should_change_default_branch')}",
            '- manual path: GitHub Settings -> Branches -> Default branch',
            '',
            '## Remaining Manual Steps',
            '',
            '- Decide whether to switch the GitHub default branch to `release/v1.0.0-alpha.1`.',
            '- Run post-publish smoke checks after any manual GitHub settings change.',
            '- Start first-user feedback triage.',
            '',
        ]
    )


def generate(project: Path) -> dict[str, Any]:
    remote = verify(project)
    branch = branch_audit(project)
    lint = lint_project(project)
    default = advise(project)
    with contextlib.redirect_stdout(io.StringIO()):
        generate_status(project)
    readiness = final_readiness(remote, branch, lint)
    manual_actions = []
    if default.get('should_change_default_branch'):
        manual_actions.append('Optionally change GitHub default branch to release/v1.0.0-alpha.1 in Settings -> Branches.')
    must_fix = []
    if readiness == 'FIX_BRANCH_DOCS_FIRST':
        must_fix.append('remove unsafe or hardcoded publishing commands')
    if readiness == 'NOT_VERIFIED':
        must_fix.append('verify release branch, tag, and tree equality')

    report = build_report(remote, branch, lint, default, readiness)
    out = project / POST_LAUNCH_DIR
    out.mkdir(parents=True, exist_ok=True)
    (out / 'post_publish_report.md').write_text(report, encoding='utf-8')
    readiness_payload = {
        'generated_at': utc_now(),
        'readiness': readiness,
        'remote_verification_passed': remote.get('remote_verification_passed'),
        'branch_hygiene_score': branch.get('branch_hygiene_score'),
        'publishing_command_lint_passed': lint.get('publishing_command_lint_passed'),
        'default_branch_manual_action_needed': default.get('should_change_default_branch'),
        'content_verified': bool(remote.get('tree_equal') and remote.get('local_remote_diff_empty')),
        'must_fix': must_fix,
        'manual_actions': manual_actions,
    }
    write_json(out / 'readiness_for_feedback_triage.json', readiness_payload)
    payload = {
        'status': readiness,
        'report_path': '.zoo-agent/post_launch/post_publish_report.md',
        'readiness_path': '.zoo-agent/post_launch/readiness_for_feedback_triage.json',
        'readiness': readiness_payload,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--workspace', default='.')
    args = parser.parse_args(argv)
    payload = generate(project_root(args.workspace))
    return 0 if payload.get('status') == 'READY_FOR_POST_LAUNCH_FEEDBACK_TRIAGE' else 1


if __name__ == '__main__':
    raise SystemExit(main())
