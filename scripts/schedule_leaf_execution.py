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

    parser = argparse.ArgumentParser(description='Create a dry-run/actual schedule for ready leaf tasks.')
    parser.add_argument('--workspace', default='.')
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--allow-parallel-actual', action='store_true')
    args = parser.parse_args()
    project = project_root(args.workspace)
    resource_map = load_json(project / '.zoo-agent' / 'project-resource-map.json')
    backend = load_backend_profile(project)
    actual = args.allow_parallel_actual
    schedule = detect_independence(load_leaf_contracts(project, args.run_id), resource_map, backend, actual=actual)
    schedule['run_id'] = args.run_id
    schedule['actual_parallel_allowed'] = (
        actual and str(backend.get('health_status')) == 'healthy' and not schedule.get('parallel_denials')
    )
    path = project / '.zoo-agent' / 'runs' / args.run_id / 'leaf-schedule.json'
    write_json(path, schedule)
    print(json.dumps({'status': 'ok', 'path': str(path), 'schedule': schedule}, ensure_ascii=True, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
