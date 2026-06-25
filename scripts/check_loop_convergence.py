#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from runtime_common import initialize_loop, project_root, write_json


def main() -> int:
    parser = argparse.ArgumentParser(description='Explain loop convergence and loss-control status.')
    parser.add_argument('--workspace', default='.')
    parser.add_argument('--output', default='')
    args = parser.parse_args()
    project = project_root(args.workspace)
    state = initialize_loop(project, source='check_loop_convergence.py')
    verdict = state.get('status') or 'active'
    report = {
        'schema_version': '1.0',
        'generated_by': 'check_loop_convergence.py',
        'workspace': str(project),
        'verdict': verdict,
        'loop_state': state,
        'loss_controls': {
            'no_delivery_stop': int(state.get('no_delivery_count') or 0) >= 2,
            'backend_failure_dry_run_only': int(state.get('backend_failure_count') or 0) >= 2,
            'doc_only_implementation_pass': int(state.get('doc_only_count') or 0) >= 2,
            'local_optimization_follow_up': int(state.get('local_optimization_count') or 0) >= 2,
            'max_iterations_reached': int(state.get('iteration') or 0)
            >= int(state.get('max_iterations') or state.get('max_iteration') or 5),
        },
        'next_action': state.get('next_action', ''),
    }
    if args.output:
        write_json(Path(args.output).resolve(), report)
    print(json.dumps(report, ensure_ascii=True, indent=2))
    return 0 if verdict not in {'stopped', 'blocked', 'diverging'} else 10


if __name__ == '__main__':
    raise SystemExit(main())
