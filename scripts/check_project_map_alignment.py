#!/usr/bin/env python3
"""Check whether the project map is aligned with the current filesystem.

This is now a thin wrapper around project_map_builder's inventory system.
The core inventory logic lives in project_map_builder.build_inventory().
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from project_map_builder import build_inventory, build_project_map
from project_map_schema import map_dir
from runtime_common import load_json, project_root, write_json


def check_alignment(project: Path) -> dict[str, Any]:
    """Compare current filesystem inventory with stored map inventory."""
    out_dir = map_dir(project)
    stored = load_json(out_dir / 'project_map.json') if (out_dir / 'project_map.json').exists() else {}
    stored_digest = (stored.get('inventory') or {}).get('filesystem_digest', '')
    current = build_inventory(project)
    current_digest = current.get('filesystem_digest', '')
    aligned = bool(stored_digest) and stored_digest == current_digest
    return {
        'aligned': aligned,
        'stored_digest': stored_digest,
        'current_digest': current_digest,
        'stored_file_count': (stored.get('inventory') or {}).get('inventory_file_count', 0),
        'current_file_count': current.get('inventory_file_count', 0),
        'source_roots': current.get('source_roots', []),
        'test_roots': current.get('test_roots', []),
        'manifests': current.get('manifests', []),
    }


def promote(project: Path, *, dry_run: bool = False) -> dict[str, Any]:
    """Rebuild the project map from current filesystem state."""
    if dry_run:
        return {'status': 'dry_run', 'message': 'would rebuild project map'}
    payload, state, evidence = build_project_map(project)
    out_dir = map_dir(project)
    write_json(out_dir / 'project_map.json', payload)
    write_json(out_dir / 'project_state.json', state)
    write_json(out_dir / 'map_evidence.json', evidence)
    return {'status': 'promoted', 'modules': len(payload.get('modules', []))}


def main() -> int:
    parser = argparse.ArgumentParser(description='Check whether the project map is aligned.')
    parser.add_argument('--workspace', default='.')
    parser.add_argument('--refresh', action='store_true', help='Rebuild map from filesystem.')
    parser.add_argument('--promote', action='store_true', help='Alias for --refresh.')
    parser.add_argument('--promote-if-missing', action='store_true', help='Rebuild only if map is missing.')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    project = project_root(args.workspace)
    out_dir = map_dir(project)
    map_exists = (out_dir / 'project_map.json').exists()

    if args.dry_run:
        report = check_alignment(project)
        report['dry_run'] = True
        report['would_promote'] = not report['aligned']
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0

    if args.refresh or args.promote or (args.promote_if_missing and not map_exists):
        result = promote(project, dry_run=False)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    if not map_exists:
        print(
            json.dumps(
                {'status': 'no_map', 'message': 'project map not found; run with --refresh'},
                ensure_ascii=False,
                indent=2,
            )
        )
        return 10

    report = check_alignment(project)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report.get('aligned') else 10


if __name__ == '__main__':
    raise SystemExit(main())
