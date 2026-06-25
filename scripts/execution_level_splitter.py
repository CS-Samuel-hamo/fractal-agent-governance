#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def split_leaf_execution(leaf: dict[str, Any], *, reason: str = '') -> list[dict[str, Any]]:
    allowed = [str(item) for item in leaf.get('allowed_files') or []]
    if len(allowed) <= 1:
        clone = dict(leaf)
        clone['leaf_id'] = f'{leaf.get("leaf_id", "leaf")}-reduced'
        clone['objective'] = f'Reduced-scope execution for: {leaf.get("objective", "")}'
        clone['execution_split_reason'] = reason or 'reduce_scope_execution'
        return [clone]
    chunks: list[dict[str, Any]] = []
    for index, path in enumerate(allowed, start=1):
        clone = dict(leaf)
        clone['leaf_id'] = f'{leaf.get("leaf_id", "leaf")}-chunk-{index:02d}'
        clone['objective'] = f'{leaf.get("objective", "")} (only {path})'
        clone['allowed_files'] = [path]
        clone['execution_split_reason'] = reason or 'split_execution_by_allowed_file'
        chunks.append(clone)
    return chunks


def main() -> int:
    parser = argparse.ArgumentParser(description='Split an executor leaf into smaller executor-only chunks.')
    parser.add_argument('--leaf-json', required=True)
    parser.add_argument('--reason', default='')
    parser.add_argument('--output', default='')
    args = parser.parse_args()
    leaf = json.loads(Path(args.leaf_json).resolve().read_text(encoding='utf-8-sig'))
    payload = {'chunks': split_leaf_execution(leaf, reason=args.reason)}
    if args.output:
        path = Path(args.output).resolve()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
