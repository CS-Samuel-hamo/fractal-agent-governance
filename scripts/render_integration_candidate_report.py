#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from big_task_common import integration_candidate, project_root, write_integration_report


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description='Render integration candidate report.')
    parser.add_argument('--workspace', default='.')
    parser.add_argument('--run-id', required=True)
    args = parser.parse_args()
    project = project_root(args.workspace)
    report = integration_candidate(project, args.run_id, create=False)
    paths = write_integration_report(project, args.run_id, report)
    print(json.dumps({'status': 'ok', 'paths': paths, 'report': report}, ensure_ascii=True, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
