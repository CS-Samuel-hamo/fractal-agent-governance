#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from big_task_common import detect_independence, load_backend_profile, load_leaf_contracts, project_root
from runtime_common import load_json, write_json


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description='Detect independence among leaf tasks.')
    parser.add_argument('--workspace', default='.')
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--actual', action='store_true')
    args = parser.parse_args()
    project = project_root(args.workspace)
    leaves = load_leaf_contracts(project, args.run_id)
    resource_map = load_json(project / '.zoo-agent' / 'project-resource-map.json')
    report = detect_independence(leaves, resource_map, load_backend_profile(project), actual=args.actual)
    report['run_id'] = args.run_id
    path = project / '.zoo-agent' / 'runs' / args.run_id / 'leaf-independence.json'
    write_json(path, report)
    print(json.dumps({'status': 'ok', 'path': str(path), 'report': report}, ensure_ascii=True, indent=2))
    return 0 if not report.get('parallel_denials') else 10


if __name__ == '__main__':
    raise SystemExit(main())
