#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

OPTIONS = ["continue", "re_scope", "research_spike", "redesign", "de_scope", "human_decision", "abort_archive"]


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate fallback ladder report.")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--branch-id", default="unknown")
    parser.add_argument("--option", required=True, choices=OPTIONS)
    parser.add_argument("--reason", required=True)
    parser.add_argument("--next-action", default="unknown")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    report_id = f"fallback-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{args.option}"
    data = {
        "fallback_report_id": report_id,
        "run_id": args.run_id,
        "branch_id": args.branch_id,
        "option": args.option,
        "reason": args.reason,
        "next_action": args.next_action,
        "allowed_options": OPTIONS,
        "decision_required": args.option in {"re_scope", "redesign", "de_scope", "human_decision", "abort_archive"},
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    out = Path(".zoo-agent") / "fallback" / f"{report_id}.json"
    text = json.dumps(data, indent=2)
    if args.dry_run:
        print(text)
        return 0
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text + "\n", encoding="utf-8")
    print(json.dumps({"status": "ok", "path": str(out), "fallback_report_id": report_id}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
