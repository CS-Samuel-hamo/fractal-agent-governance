#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path


def load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def main() -> int:
    parser = argparse.ArgumentParser(description="Check goal success criteria coverage.")
    parser.add_argument("--goal", required=True, help="Goal contract JSON path.")
    parser.add_argument("--evidence", action="append", default=[], help="Evidence markdown/json files.")
    parser.add_argument("--output")
    args = parser.parse_args()
    goal_path = Path(args.goal)
    goal = load_json(goal_path)
    criteria = goal.get("success_criteria", []) if isinstance(goal, dict) else []
    evidence_text = ""
    for item in args.evidence:
        path = Path(item)
        if path.exists():
            evidence_text += "\n" + path.read_text(encoding="utf-8", errors="replace").lower()
    coverage = []
    for criterion in criteria:
        text = str(criterion)
        status = "covered" if text.lower() in evidence_text else "unknown"
        coverage.append({"criterion": text, "status": status})
    covered = sum(1 for item in coverage if item["status"] == "covered")
    total = len(coverage)
    report = {
        "status": "pass" if total > 0 and covered == total else "fail",
        "goal_id": goal.get("goal_id", "unknown") if isinstance(goal, dict) else "unknown",
        "coverage_ratio": covered / total if total else 0,
        "coverage": coverage,
    }
    text = json.dumps(report, indent=2)
    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0 if report["status"] == "pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())
