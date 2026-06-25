#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from check_codex_worker_concurrency import build_contract, git_root, write_json


def main() -> int:
    parser = argparse.ArgumentParser(description='Detect whether a leaf task index is safe for parallel execution.')
    parser.add_argument('--workspace', required=True)
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--leaf-index', required=True)
    parser.add_argument('--max-workers', type=int, default=2)
    parser.add_argument('--allow-planned', action='store_true')
    parser.add_argument('--json-output', default='')
    args = parser.parse_args()

    repo_root = git_root(Path(args.workspace).resolve())
    report = build_contract(
        repo_root,
        args.run_id,
        Path(args.leaf_index).resolve(),
        max_workers=args.max_workers,
        allow_planned=args.allow_planned,
    )
    if args.json_output:
        write_json(Path(args.json_output).resolve(), report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report.get('status') == 'pass' else 20


if __name__ == '__main__':
    raise SystemExit(main())
