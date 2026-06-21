#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from branch_hygiene_audit import audit as branch_audit  # noqa: E402
from default_branch_advisor import RECOMMENDED_DEFAULT_BRANCH, advise  # noqa: E402
from post_publish_remote_verifier import EXPECTED_TAG, verify  # noqa: E402
from publishing_command_linter import lint_project  # noqa: E402
from runtime_common import project_root, utc_now  # noqa: E402


POST_LAUNCH_DIR = Path('.zoo-agent') / 'post_launch'


def build_markdown(remote: dict[str, Any], branch: dict[str, Any], lint: dict[str, Any], default: dict[str, Any]) -> str:
    lines = [
        '# Post Launch Status',
        '',
        f'Generated: {utc_now()}',
        '',
        '## Published Alpha',
        '',
        f'- Version: `{EXPECTED_TAG}`',
        f'- Release branch: `{RECOMMENDED_DEFAULT_BRANCH}`',
        f'- Tag: `{EXPECTED_TAG}`',
        '- Release branch URL: https://github.com/CS-Samuel-hamo/fractal-agent-governance/tree/release/v1.0.0-alpha.1',
        '- Tag URL: https://github.com/CS-Samuel-hamo/fractal-agent-governance/releases/tag/v1.0.0-alpha.1',
        '',
        '## Verification',
        '',
        f"- Remote branch exists: {remote.get('remote_branch_exists')}",
        f"- Remote tag exists: {remote.get('remote_tag_exists')}",
        f"- Local tree: `{remote.get('local_tree') or 'unknown'}`",
        f"- Remote tree: `{remote.get('remote_tree') or 'unknown'}`",
        f"- Tree equality: {remote.get('tree_equal')}",
        f"- File diff empty: {remote.get('local_remote_diff_empty')}",
        f"- Commit SHA differs but tree is equal: {remote.get('commit_sha_differs_but_tree_equal')}",
        '',
        '## Publish Method',
        '',
        '- Git HTTPS push was reset while uploading pack data.',
        '- The release branch and tag were completed with a GitHub Git Data API fallback after manual verification.',
        '- Commit SHAs can differ between local and remote because the fallback reconstructed equivalent commit objects.',
        '- Content verification is based on tree equality, empty file diff, release branch contents, and tag target.',
        '- A GitHub Release object was not created by the toolchain.',
        '',
        '## Branch Caveats',
        '',
        '- There is no `main` branch assumption for publishing.',
        '- Local `master` and remote `origin/master` are not treated as safely pushable.',
        f"- Current default branch: `{default.get('current_default_branch')}`",
        f"- Recommended default branch: `{RECOMMENDED_DEFAULT_BRANCH}`",
        '- Default branch changes must be done manually in GitHub Settings -> Branches.',
        '',
        '## What Was Not Done',
        '',
        '- No force push.',
        '- No merge.',
        '- No remote PR creation.',
        '- No automatic default branch change.',
        '- No remote GitHub Release object creation.',
        '',
        '## Publishing Command Hygiene',
        '',
        f"- Hardcoded main-branch push command detected: {lint.get('hardcoded_main_push_detected')}",
        f"- Force push command detected: {lint.get('force_push_detected')}",
        f"- Unsafe GitHub write command detected: {lint.get('unsafe_github_write_detected')}",
        '',
        '## Next Operational Steps',
        '',
        '- Run post-publish smoke checks.',
        '- Collect first-user feedback through issue templates.',
        '- Triage first launch issues before product iteration.',
        '- Manually change the GitHub default branch if the maintainer wants the 1.0 alpha branch as the repo homepage.',
        '',
        '## Recommendation',
        '',
        'Proceed to post-launch feedback triage after the manual default branch decision is made.',
        '',
    ]
    if branch.get('recommendation') == 'fix_docs':
        lines[-2] = 'Fix branch-aware publishing docs before feedback triage.'
    return '\n'.join(lines)


def generate(project: Path) -> dict[str, Any]:
    remote = verify(project)
    branch = branch_audit(project)
    lint = lint_project(project)
    default = advise(project)
    text = build_markdown(remote, branch, lint, default)
    (project / 'POST_LAUNCH_STATUS.md').write_text(text, encoding='utf-8')
    out = project / POST_LAUNCH_DIR
    out.mkdir(parents=True, exist_ok=True)
    (out / 'post_launch_status_report.md').write_text(text, encoding='utf-8')
    payload = {
        'generated_at': utc_now(),
        'post_launch_status_path': 'POST_LAUNCH_STATUS.md',
        'artifact_path': '.zoo-agent/post_launch/post_launch_status_report.md',
        'remote_verification_passed': remote.get('remote_verification_passed'),
        'branch_hygiene_recommendation': branch.get('recommendation'),
        'publishing_command_lint_passed': lint.get('publishing_command_lint_passed'),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--workspace', default='.')
    args = parser.parse_args(argv)
    payload = generate(project_root(args.workspace))
    return 0 if payload.get('publishing_command_lint_passed') else 1


if __name__ == '__main__':
    raise SystemExit(main())
