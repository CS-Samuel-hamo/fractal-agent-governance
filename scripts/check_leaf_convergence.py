#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from leaf_convergence_controller import run_leaf_convergence
from runtime_common import load_json, project_root, write_json


def main() -> int:
    parser = argparse.ArgumentParser(description='Check that all leaf tasks have a final convergence resolution.')
    parser.add_argument('--workspace', default='.')
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--refresh', action='store_true', help='Run the convergence controller before checking.')
    args = parser.parse_args()
    project = project_root(args.workspace)
    path = project / '.zoo-agent' / 'runs' / args.run_id / 'leaf-convergence-report.json'
    report = run_leaf_convergence(project, args.run_id) if args.refresh or not path.exists() else load_json(path)
    unresolved = [item for item in report.get('resolutions') or [] if item.get('status') == 'stuck']
    check = {
        'schema_version': '1.0',
        'generated_by': 'check_leaf_convergence.py',
        'run_id': args.run_id,
        'status': 'pass' if not unresolved else 'convergence_failure',
        'leaf_count': report.get('leaf_count', 0),
        'unresolved_leaf_ids': [item.get('leaf_id') for item in unresolved],
        'resolution_rate': 0.0,
    }
    leaf_count = max(int(report.get('leaf_count') or 0), 1)
    check['resolution_rate'] = round((leaf_count - len(unresolved)) / leaf_count, 4)
    out = project / '.zoo-agent' / 'runs' / args.run_id / 'leaf-convergence-check.json'
    write_json(out, check)
    print(json.dumps({'status': check['status'], 'path': str(out), 'check': check}, ensure_ascii=True, indent=2))
    return 0 if check['status'] == 'pass' else 10


if __name__ == '__main__':
    raise SystemExit(main())
