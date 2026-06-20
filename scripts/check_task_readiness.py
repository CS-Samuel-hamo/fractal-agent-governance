#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from big_task_common import leaf_readiness, load_backend_profile, project_root  # noqa: E402
from leaf_convergence_controller import resolve_one_leaf  # noqa: E402
from runtime_common import load_json, write_json  # noqa: E402


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description='Run the leaf Task Readiness Gate.')
    parser.add_argument('--workspace', default='.')
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--leaf-id', required=True)
    parser.add_argument('--leaf', default='')
    args = parser.parse_args()
    project = project_root(args.workspace)
    leaf_path = Path(args.leaf) if args.leaf else project / '.zoo-agent' / 'runs' / args.run_id / 'leaf-tasks' / f'{args.leaf_id}.json'
    leaf = load_json(leaf_path)
    if not leaf:
        print('Missing leaf contract.', file=sys.stderr)
        return 2
    backend = load_backend_profile(project)
    leaf['_path'] = str(leaf_path)
    gate = leaf_readiness(leaf, backend)
    resolution = resolve_one_leaf(project, args.run_id, leaf, backend=backend)
    out = project / '.zoo-agent' / 'runs' / args.run_id / 'leaf-tasks' / f'{args.leaf_id}-readiness.json'
    write_json(out, {'readiness': gate, 'resolution': resolution})
    status = 'ok' if resolution.get('status') != 'stuck' else 'convergence_failure'
    print(json.dumps({'status': status, 'path': str(out), 'readiness': gate, 'resolution': resolution}, ensure_ascii=True, indent=2))
    return 0 if status == 'ok' else 10


if __name__ == '__main__':
    raise SystemExit(main())
