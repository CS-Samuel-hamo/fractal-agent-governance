#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path


ACTIVE_STATUSES = {"planned", "ready_for_worker", "worker_running", "needs_scope_guard", "needs_tests", "needs_review", "done"}


def main() -> int:
    parser = argparse.ArgumentParser(description="Check active implementation items have root-goal alignment.")
    parser.add_argument("--queue", required=True)
    args = parser.parse_args()
    queue = json.loads(Path(args.queue).read_text(encoding="utf-8"))
    failures = []
    for item in queue.get("items", []):
        if item.get("status") in ACTIVE_STATUSES and item.get("type") in {"code", "test", "config"}:
            if not item.get("root_goal_link"):
                failures.append(f"{item.get('item_id')}: missing root_goal_link")
            if not item.get("expected_artifacts"):
                failures.append(f"{item.get('item_id')}: missing expected_artifacts")
    if failures:
        print("[FAIL] root goal alignment")
        for failure in failures:
            print(f"- {failure}")
        return 1
    print("[OK] root goal alignment")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
