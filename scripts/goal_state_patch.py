#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from goal_state_manager import build_state_patch  # noqa: E402
from runtime_common import project_root, write_json  # noqa: E402


def parse_change(raw: str) -> dict[str, Any]:
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SystemExit(f'Invalid --change JSON: {exc}') from exc
    if not isinstance(payload, dict):
        raise SystemExit('--change must be a JSON object')
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description='Create a goal-state patch without applying it.')
    parser.add_argument('--workspace', default='.')
    parser.add_argument('--source', required=True)
    parser.add_argument('--reason', required=True)
    parser.add_argument('--patch-id', default='')
    parser.add_argument('--change', action='append', default=[], help='JSON change object.')
    parser.add_argument('--output', default='')
    args = parser.parse_args()
    project = project_root(args.workspace)
    changes = [parse_change(item) for item in args.change]
    patch = build_state_patch(project, source=args.source, reason=args.reason, changes=changes, patch_id=args.patch_id)
    if args.output:
        write_json(Path(args.output).resolve(), patch)
    print(json.dumps(patch, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
