#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Score an executor benchmark run.")
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", default="")
    args = parser.parse_args()
    data = json.loads(Path(args.input).read_text(encoding="utf-8"))
    records = data.get("records", [])
    score = {
        "case_count": len(records),
        "scope_violations": sum((r.get("scope_violation_count") or 0) for r in records),
        "review_blockers": sum((r.get("review_blocker_count") or 0) for r in records),
        "manual_interventions": sum((r.get("manual_intervention_count") or 0) for r in records),
        "completed": sum(1 for r in records if r.get("final_status") == "complete"),
        "template_only": sum(1 for r in records if r.get("final_status") == "template_only"),
    }
    output = Path(args.output) if args.output else Path(args.input).with_suffix(".score.json")
    output.write_text(json.dumps(score, indent=2), encoding="utf-8")
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
