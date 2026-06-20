#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from goal_state_manager import render_state_diff  # noqa: E402
from runtime_common import load_json, write_json  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description='Render a human-readable goal-state diff.')
    parser.add_argument('--before', required=True)
    parser.add_argument('--after', required=True)
    parser.add_argument('--patch', default='')
    parser.add_argument('--output', default='')
    args = parser.parse_args()
    before = load_json(Path(args.before).resolve())
    after = load_json(Path(args.after).resolve())
    patch = load_json(Path(args.patch).resolve()) if args.patch else {}
    diff = render_state_diff(before, after, patch)
    if args.output:
        out = Path(args.output).resolve()
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(diff, encoding='utf-8')
    else:
        print(diff)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
