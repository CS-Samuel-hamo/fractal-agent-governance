#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from big_task_common import leaf_readiness, load_backend_profile, load_leaf_contracts, project_root
from leaf_convergence_controller import run_leaf_convergence
from runtime_common import write_json


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description='Validate all leaf task contracts for a run.')
    parser.add_argument('--workspace', default='.')
    parser.add_argument('--run-id', required=True)
    args = parser.parse_args()
    project = project_root(args.workspace)
    backend = load_backend_profile(project)
    leaves = load_leaf_contracts(project, args.run_id)
    readiness = [leaf_readiness(leaf, backend) for leaf in leaves]
    blocked = [item for item in readiness if str(item.get('verdict')).startswith('BLOCKED')]
    convergence = run_leaf_convergence(project, args.run_id)
    unresolved = [item for item in convergence.get('resolutions') or [] if item.get('status') == 'stuck']
    report = {
        'run_id': args.run_id,
        'leaf_count': len(leaves),
        'readiness': readiness,
        'blocked_count': len(blocked),
        'leaf_convergence_status': convergence.get('status'),
        'leaf_resolutions': convergence.get('resolutions') or [],
        'unresolved_leaf_count': len(unresolved),
        'status': 'convergence_failure'
        if unresolved
        else ('resolved_with_non_execution' if blocked else 'ready_for_dry_run_or_review'),
    }
    path = project / '.zoo-agent' / 'runs' / args.run_id / 'leaf-contract-check.json'
    write_json(path, report)
    print(json.dumps({'status': report['status'], 'path': str(path), 'report': report}, ensure_ascii=True, indent=2))
    return 0 if not unresolved else 10


if __name__ == '__main__':
    raise SystemExit(main())
