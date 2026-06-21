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

from runtime_common import project_root, utc_now, write_json  # noqa: E402


RECOMMENDED_DEFAULT_BRANCH = 'release/v1.0.0-alpha.1'
POST_LAUNCH_DIR = Path('.zoo-agent') / 'post_launch'


def run_git(project: Path, args: list[str], timeout: int = 30) -> dict[str, Any]:
    try:
        proc = subprocess.run(['git', *args], cwd=project, text=True, encoding='utf-8', errors='replace', stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
        return {'ok': proc.returncode == 0, 'stdout': proc.stdout.strip(), 'stderr': proc.stderr.strip()}
    except Exception as exc:
        return {'ok': False, 'stdout': '', 'stderr': str(exc)}


def detect_default_branch(project: Path) -> tuple[str, bool]:
    symbolic = run_git(project, ['symbolic-ref', '--short', 'refs/remotes/origin/HEAD'], timeout=10)
    if symbolic.get('ok') and symbolic.get('stdout'):
        value = symbolic['stdout'].strip()
        return value.removeprefix('origin/'), True
    remote_show = run_git(project, ['remote', 'show', 'origin'], timeout=45)
    if remote_show.get('ok'):
        for line in remote_show.get('stdout', '').splitlines():
            if 'HEAD branch:' in line:
                return line.split(':', 1)[1].strip(), True
    return 'unknown', False


def advise(project: Path, *, recommended: str = RECOMMENDED_DEFAULT_BRANCH) -> dict[str, Any]:
    current, known = detect_default_branch(project)
    should_change = current != recommended
    payload = {
        'generated_at': utc_now(),
        'current_default_branch': current,
        'default_branch_known': known,
        'recommended_default_branch': recommended,
        'should_change_default_branch': should_change,
        'needs_manual_confirmation': not known,
        'manual_steps': [
            'Open the GitHub repository in a browser.',
            'Open Settings.',
            'Go to Branches.',
            f'Change Default branch to {recommended}.',
        ],
        'automated_change_performed': False,
    }
    write_json(project / POST_LAUNCH_DIR / 'default_branch_advice.json', payload)
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--workspace', default='.')
    args = parser.parse_args(argv)
    payload = advise(project_root(args.workspace))
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
