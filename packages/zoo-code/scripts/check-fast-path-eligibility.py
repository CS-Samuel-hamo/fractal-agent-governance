#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

TRIGGERS = {
    "auth", "security", "payment", "pii", "migration", "schema", "public api",
    "shared type", "new dependency", "architecture", "production config",
    "release", "ops", "worktree", "parallel", "cross-module",
}


def parse_level(value: str) -> int:
    match = re.search(r"([0-4])", value)
    return int(match.group(1)) if match else 4


def main() -> int:
    parser = argparse.ArgumentParser(description="Check whether a task can use adaptive fast path.")
    parser.add_argument("--governance-level", required=True)
    parser.add_argument("--description", default="")
    parser.add_argument("--changed-file", action="append", default=[])
    parser.add_argument("--json-output")
    args = parser.parse_args()
    level = parse_level(args.governance_level)
    text = " ".join([args.description, *args.changed_file]).lower()
    hits = sorted(trigger for trigger in TRIGGERS if trigger in text)
    allowed = level in (0, 1) and not hits
    result = {
        "governance_level": f"Level {level}",
        "allowed_to_fast_path": allowed,
        "blocking_factors": hits if not allowed else [],
        "skip_full_fractal_governance": allowed,
    }
    if args.json_output:
        out = Path(args.json_output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0 if allowed else 1


if __name__ == "__main__":
    raise SystemExit(main())
