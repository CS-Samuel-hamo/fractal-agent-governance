#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from public_release_packager import VERSION, public_release_dir
from runtime_common import project_root, utc_now, write_json

TAG = f'v{VERSION}'


def run_git(project: Path, args: list[str]) -> tuple[int, str]:
    try:
        proc = subprocess.run(
            ['git', *args],
            cwd=project,
            text=True,
            encoding='utf-8',
            errors='replace',
            capture_output=True,
            timeout=8,
        )
        return proc.returncode, proc.stdout.strip()
    except Exception:
        return 1, ''


def preflight(project: Path) -> dict:
    status_code, status = run_git(project, ['status', '--porcelain'])
    commit_code, commit = run_git(project, ['rev-parse', 'HEAD'])
    tag_code, _ = run_git(project, ['rev-parse', '--verify', TAG])
    clean = status_code == 0 and not status
    release_draft_exists = (project / 'GITHUB_RELEASE_DRAFT.md').exists()
    ready = clean and commit_code == 0 and tag_code != 0 and release_draft_exists
    payload = {
        'generated_at': utc_now(),
        'tag': TAG,
        'tag_exists': tag_code == 0,
        'current_commit': commit if commit_code == 0 else '',
        'working_tree_clean': clean,
        'release_draft_exists': release_draft_exists,
        'ready_to_tag': ready,
        'suggested_commands': [
            f'git tag -a {TAG} -m "AI Project Operator {TAG}"',
            f'git push origin HEAD:refs/heads/release/{TAG}',
            f'git push origin {TAG}',
        ],
        'auto_tag_created': False,
    }
    write_json(public_release_dir(project) / 'release_tag_preflight.json', payload)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--workspace', default='.')
    args = parser.parse_args(argv)
    payload = preflight(project_root(args.workspace))
    return 0 if payload.get('release_draft_exists') else 1


if __name__ == '__main__':
    raise SystemExit(main())
