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

from default_branch_advisor import RECOMMENDED_DEFAULT_BRANCH, advise
from publishing_command_linter import lint_project
from runtime_common import project_root, utc_now, write_json

EXPECTED_TAG = 'v1.0.0-alpha.1'
POST_LAUNCH_DIR = Path('.zoo-agent') / 'post_launch'


def run_git(project: Path, args: list[str], timeout: int = 30) -> dict[str, Any]:
    try:
        proc = subprocess.run(
            ['git', *args],
            cwd=project,
            text=True,
            encoding='utf-8',
            errors='replace',
            capture_output=True,
            timeout=timeout,
        )
        return {
            'ok': proc.returncode == 0,
            'stdout': proc.stdout.strip(),
            'stderr': proc.stderr.strip(),
            'returncode': proc.returncode,
        }
    except Exception as exc:
        return {'ok': False, 'stdout': '', 'stderr': str(exc), 'returncode': 1}


def branch_exists(project: Path, name: str) -> bool:
    local = run_git(project, ['show-ref', '--verify', f'refs/heads/{name}'], timeout=10)
    remote = run_git(project, ['show-ref', '--verify', f'refs/remotes/origin/{name}'], timeout=10)
    if local.get('ok') or remote.get('ok'):
        return True
    ls_remote = run_git(project, ['ls-remote', '--heads', 'origin', name], timeout=45)
    return bool(ls_remote.get('ok') and ls_remote.get('stdout'))


def tag_exists(project: Path, tag: str) -> bool:
    local = run_git(project, ['show-ref', '--verify', f'refs/tags/{tag}'], timeout=10)
    if local.get('ok'):
        return True
    remote = run_git(project, ['ls-remote', '--tags', 'origin', tag], timeout=45)
    return bool(remote.get('ok') and remote.get('stdout'))


def fast_forward_safe(project: Path) -> bool:
    has_local = run_git(project, ['show-ref', '--verify', 'refs/heads/master'], timeout=10).get('ok')
    has_remote = run_git(project, ['show-ref', '--verify', 'refs/remotes/origin/master'], timeout=10).get('ok')
    if not (has_local and has_remote):
        return False
    return bool(run_git(project, ['merge-base', '--is-ancestor', 'origin/master', 'master'], timeout=10).get('ok'))


def audit(
    project: Path, *, release_branch: str = RECOMMENDED_DEFAULT_BRANCH, expected_tag: str = EXPECTED_TAG
) -> dict[str, Any]:
    current = run_git(project, ['branch', '--show-current'], timeout=10).get('stdout') or 'unknown'
    main = branch_exists(project, 'main')
    master = branch_exists(project, 'master')
    release = branch_exists(project, release_branch)
    tag = tag_exists(project, expected_tag)
    default = advise(project, recommended=release_branch)
    lint = lint_project(project)
    ff_safe = fast_forward_safe(project)
    force_push_risk = 'high' if master and not ff_safe else 'low'

    score = 1.0
    if lint.get('hardcoded_main_push_detected'):
        score -= 0.35
    if force_push_risk == 'high':
        score -= 0.15
    if not release:
        score -= 0.25
    if not tag:
        score -= 0.15
    if default.get('should_change_default_branch'):
        score -= 0.05
    score = round(max(score, 0.0), 3)

    if (
        lint.get('hardcoded_main_push_detected')
        or lint.get('force_push_detected')
        or lint.get('unsafe_github_write_detected')
    ):
        recommendation = 'fix_docs'
    elif not release or not tag:
        recommendation = 'fail'
    elif default.get('should_change_default_branch'):
        recommendation = 'manual_action_needed'
    else:
        recommendation = 'pass'

    payload = {
        'generated_at': utc_now(),
        'branch_hygiene_score': score,
        'current_branch': current,
        'main_exists': main,
        'master_exists': master,
        'release_branch_exists': release,
        'tag_exists': tag,
        'default_branch_known': bool(default.get('default_branch_known')),
        'default_branch': default.get('current_default_branch') or 'unknown',
        'master_fast_forward_safe': ff_safe,
        'force_push_risk': force_push_risk,
        'hardcoded_main_detected': bool(lint.get('hardcoded_main_push_detected')),
        'manual_default_branch_change_recommended': bool(default.get('should_change_default_branch')),
        'recommended_default_branch': release_branch,
        'recommendation': recommendation,
    }
    write_json(project / POST_LAUNCH_DIR / 'branch_hygiene_report.json', payload)
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--workspace', default='.')
    args = parser.parse_args(argv)
    payload = audit(project_root(args.workspace))
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload.get('recommendation') in {'pass', 'manual_action_needed'} else 1


if __name__ == '__main__':
    raise SystemExit(main())
