#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from big_task_common import build_leaf_contracts, decomposition_gate, generate_resource_map, load_backend_profile, load_big_task_contract, project_root, write_leaf_contracts, write_resource_map  # noqa: E402
from runtime_common import write_json  # noqa: E402


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description='Decompose a big task into leaf task contracts.')
    parser.add_argument('--workspace', default='.')
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--allow-leaf-actual', action='store_true')
    args = parser.parse_args()
    project = project_root(args.workspace)
    contract = load_big_task_contract(project, args.run_id)
    if not contract:
        print('Missing big-task-contract.json.', file=sys.stderr)
        return 2
    allowed, blockers = decomposition_gate(contract)
    if not allowed:
        report = {
            'status': 'blocked',
            'run_id': args.run_id,
            'decomposition_allowed': False,
            'blocking_reasons': blockers,
            'message': 'Big task decomposition requires an explicit goal and verifiable success criteria.',
        }
        write_json(project / '.zoo-agent' / 'runs' / args.run_id / 'decomposition-blocked.json', report)
        print(json.dumps(report, ensure_ascii=True, indent=2))
        return 10
    resource_map = generate_resource_map(project, str(contract.get('raw_input') or ''))
    resource_paths = write_resource_map(project, resource_map)
    leaves = build_leaf_contracts(project, contract, resource_map, allow_leaf_actual=args.allow_leaf_actual)
    backend = load_backend_profile(project)
    readiness = []
    from big_task_common import leaf_readiness  # imported late to keep this script thin

    for leaf in leaves:
        gate = leaf_readiness(leaf, backend)
        leaf['task_readiness'] = gate
        leaf['task_readiness_ref'] = f".zoo-agent/runs/{args.run_id}/leaf-tasks/{leaf['leaf_id']}-readiness.json"
        leaf['blocking_reasons'] = gate.get('blocking_reasons') or []
        readiness.append(gate)
    index = write_leaf_contracts(project, args.run_id, leaves)
    readiness_path = project / '.zoo-agent' / 'runs' / args.run_id / 'leaf-task-readiness.json'
    write_json(readiness_path, {'run_id': args.run_id, 'readiness': readiness})
    report = {'status': 'ok', 'leaf_index': index, 'resource_map': resource_paths, 'readiness_path': str(readiness_path)}
    print(json.dumps(report, ensure_ascii=True, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
