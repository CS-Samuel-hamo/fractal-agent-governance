#!/usr/bin/env python3
"""Show differences between project map versions."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from project_map_schema import map_dir
from runtime_common import load_json, project_root


def load_version(out_dir: Path, version: int) -> dict[str, Any]:
    vpath = out_dir / 'history' / f'v{version}.json'
    return load_json(vpath) if vpath.exists() else {}


def current_version(out_dir: Path) -> int:
    return (load_json(out_dir / 'project_map.json') or {}).get('_version', 0)


def show_diff(project: Path, v1: int | None = None, v2: int | None = None) -> dict[str, Any]:
    out_dir = map_dir(project)
    curr = load_json(out_dir / 'project_map.json')
    v_curr = curr.get('_version', 0) if curr else 0

    if not (out_dir / 'history').exists():
        return {'status': 'no_history', 'current_version': v_curr}

    v1 = v1 if v1 is not None else max(1, v_curr - 1)
    v2 = v2 if v2 is not None else v_curr

    left = load_version(out_dir, v1)
    right = curr if v2 == v_curr else load_version(out_dir, v2)

    return {
        'status': 'ok',
        'from_version': v1,
        'to_version': v2,
        'changelog': (right if v2 == v_curr else right or curr).get('_changelog', []),
        'from_modules': len(left.get('modules', [])),
        'to_modules': len((right if v2 == v_curr else right or curr).get('modules', [])),
        'from_risks': len(left.get('risks', [])),
        'to_risks': len((right if v2 == v_curr else right or curr).get('risks', [])),
        'from_actions': len(left.get('next_actions', [])),
        'to_actions': len((right if v2 == v_curr else right or curr).get('next_actions', [])),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description='Show project map version diff.')
    parser.add_argument('--workspace', default='.')
    parser.add_argument('--v1', type=int, default=None, help='From version (default: current-1)')
    parser.add_argument('--v2', type=int, default=None, help='To version (default: current)')
    parser.add_argument('--list', action='store_true', help='List available versions')
    args = parser.parse_args()
    project = project_root(args.workspace)
    out_dir = map_dir(project)

    if args.list:
        history_dir = out_dir / 'history'
        if not history_dir.exists():
            print(json.dumps({'status': 'no_history'}, indent=2))
            return 0
        versions = sorted(int(p.stem[1:]) for p in history_dir.glob('v*.json') if p.stem[1:].isdigit())
        curr = current_version(out_dir)
        print(json.dumps({'available_versions': versions, 'current': curr}, indent=2))
        return 0

    result = show_diff(project, args.v1, args.v2)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
