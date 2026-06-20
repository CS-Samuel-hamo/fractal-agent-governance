#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from big_task_common import integration_candidate, project_root, write_integration_report  # noqa: E402


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description='Create or plan an integration worktree for a big task.')
    parser.add_argument('--workspace', default='.')
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--yes', action='store_true', help='Actually create the integration worktree.')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    project = project_root(args.workspace)
    report = integration_candidate(project, args.run_id, create=args.yes and not args.dry_run)
    paths = write_integration_report(project, args.run_id, report)
    print(json.dumps({'status': 'ok', 'paths': paths, 'report': report}, ensure_ascii=True, indent=2))
    return 0 if report.get('verdict') == 'INTEGRATION_CANDIDATE_READY' else 10


if __name__ == '__main__':
    raise SystemExit(main())
