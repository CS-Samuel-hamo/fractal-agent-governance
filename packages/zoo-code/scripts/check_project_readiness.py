#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Check project bootstrap readiness.")
    parser.add_argument("--project", required=True)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    readiness_path = Path(args.project).resolve() / ".zoo-agent" / "project-readiness.json"
    if not readiness_path.exists():
        print(f"missing readiness file: {readiness_path}", file=sys.stderr)
        return 2
    readiness = json.loads(readiness_path.read_text(encoding="utf-8"))
    if args.json:
        print(json.dumps(readiness, indent=2))
    else:
        print(f"safe_for_level_0_1_trial={readiness.get('safe_for_level_0_1_trial')}")
        for issue in readiness.get("blocking_issues", []):
            print(f"BLOCKING: {issue}")
        for warning in readiness.get("warnings", []):
            print(f"WARNING: {warning}")
        for action in readiness.get("next_actions", []):
            print(f"NEXT: {action}")
    return 0 if readiness.get("safe_for_level_0_1_trial") else 1


if __name__ == "__main__":
    raise SystemExit(main())
