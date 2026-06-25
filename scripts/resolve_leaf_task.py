#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from big_task_common import load_backend_profile, project_root
from leaf_convergence_controller import resolve_one_leaf
from leaf_resolution_policy import DEFAULT_MAX_REFINEMENTS
from runtime_common import load_json


def main() -> int:
    parser = argparse.ArgumentParser(description='Resolve one leaf task into execute/refine/merge/defer/collapse.')
    parser.add_argument('--workspace', default='.')
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--leaf-id', required=True)
    parser.add_argument('--leaf', default='')
    parser.add_argument('--max-refinements', type=int, default=DEFAULT_MAX_REFINEMENTS)
    args = parser.parse_args()
    project = project_root(args.workspace)
    leaf_path = (
        Path(args.leaf)
        if args.leaf
        else project / '.zoo-agent' / 'runs' / args.run_id / 'leaf-tasks' / f'{args.leaf_id}.json'
    )
    leaf = load_json(leaf_path)
    if not leaf:
        print('Missing leaf contract.', file=sys.stderr)
        return 2
    leaf['_path'] = str(leaf_path)
    result = resolve_one_leaf(
        project, args.run_id, leaf, backend=load_backend_profile(project), max_refinements=args.max_refinements
    )
    print(json.dumps({'status': result.get('status'), 'resolution': result}, ensure_ascii=True, indent=2))
    return 0 if result.get('status') != 'stuck' else 10


if __name__ == '__main__':
    raise SystemExit(main())
