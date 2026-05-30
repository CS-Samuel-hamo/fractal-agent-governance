#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

REQUIRED = ["skill", "mode", "model", "trigger_reason", "artifacts", "outcome", "reviewer_notes", "follow_up"]
OUTCOMES = {"useful", "partial", "irrelevant", "harmful", "unknown"}


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate skill invocation telemetry.")
    parser.add_argument("--run-id")
    parser.add_argument("--file")
    parser.add_argument("--output")
    args = parser.parse_args()
    path = Path(args.file) if args.file else Path(".zoo-agent") / "runs" / (args.run_id or "") / "skill-invocations.json"
    issues = []
    rows = []
    if not path.exists():
        issues.append({"severity": "blocker", "issue": f"missing {path}"})
    else:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        rows = data.get("invocations", data if isinstance(data, list) else [])
        for i, row in enumerate(rows):
            for field in REQUIRED:
                if field not in row:
                    issues.append({"index": i, "severity": "blocker", "issue": f"missing {field}"})
            if row.get("outcome") not in OUTCOMES:
                issues.append({"index": i, "severity": "blocker", "issue": "invalid outcome"})
    by_skill: dict[str, list[str]] = {}
    for row in rows:
        by_skill.setdefault(row.get("skill", "unknown"), []).append(row.get("outcome", "unknown"))
    deprecation_candidates = [skill for skill, outcomes in by_skill.items() if len(outcomes) >= 5 and outcomes[-5:] == ["irrelevant"] * 5]
    report = {"status": "pass" if not issues else "fail", "invocation_count": len(rows), "deprecation_candidates": deprecation_candidates, "issues": issues}
    text = json.dumps(report, indent=2)
    if args.output:
        out = Path(args.output); out.parent.mkdir(parents=True, exist_ok=True); out.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
