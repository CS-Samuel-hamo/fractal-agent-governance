#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path


VALID_TYPES = {"code", "test", "config", "docs", "research", "review", "blocked", "planning"}
VALID_STATUSES = {
    "planned", "ready_for_worker", "worker_running", "needs_scope_guard", "needs_tests",
    "needs_review", "done", "blocked", "deferred", "follow_up", "redo_needed",
    "code_delivery_gate_fail",
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate implementation queue schema and delivery obligations.")
    parser.add_argument("--queue", default="")
    parser.add_argument("--workspace", default=".")
    parser.add_argument("--run-id", default="")
    args = parser.parse_args()
    workspace = Path(args.workspace).resolve()
    queue = Path(args.queue) if args.queue else workspace / ".zoo-agent" / "runs" / args.run_id / "implementation-queue.json"
    errors: list[str] = []
    try:
        payload = json.loads(queue.read_text(encoding="utf-8"))
    except Exception as exc:
        errors.append(f"cannot read queue: {exc}")
        payload = {}
    items = payload.get("items", [])
    if not isinstance(items, list):
        errors.append("items must be a list")
        items = []
    for index, item in enumerate(items):
        prefix = f"items[{index}]"
        for key in ["item_id", "task_id", "title", "type", "status"]:
            if not item.get(key):
                errors.append(f"{prefix}.{key} is required")
        if item.get("type") not in VALID_TYPES:
            errors.append(f"{prefix}.type invalid: {item.get('type')}")
        if item.get("status") not in VALID_STATUSES:
            errors.append(f"{prefix}.status invalid: {item.get('status')}")
        if item.get("type") in {"code", "test", "config"}:
            if not item.get("expected_artifacts"):
                errors.append(f"{prefix}.expected_artifacts required for coding item")
            if item.get("status") == "ready_for_worker" and not item.get("allowed_files"):
                errors.append(f"{prefix}.allowed_files required for ready coding item")
            if not item.get("root_goal_link"):
                errors.append(f"{prefix}.root_goal_link required for active coding item")
        if item.get("status") == "blocked" and not item.get("blocking_reason"):
            errors.append(f"{prefix}.blocking_reason required for blocked item")
    if errors:
        print("[FAIL] implementation queue invalid")
        for error in errors:
            print(f"- {error}")
        return 1
    print("[OK] implementation queue valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
