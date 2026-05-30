#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence", required=True)
    parser.add_argument("--test-plan")
    parser.add_argument("--output")
    args = parser.parse_args()
    text = Path(args.evidence).read_text(encoding="utf-8", errors="replace").lower() if Path(args.evidence).exists() else ""
    if args.test_plan and Path(args.test_plan).exists():
        text += "\n" + Path(args.test_plan).read_text(encoding="utf-8", errors="replace").lower()
    issues = []
    for word in ["behavior", "regression", "edge", "command"]:
        if word not in text:
            issues.append({"severity": "major", "issue": f"test adequacy evidence missing {word}"})
    if "existence-only" in text or "exists only" in text:
        issues.append({"severity": "blocker", "issue": "existence-only tests do not satisfy behavior coverage"})
    status = "pass" if not any(i["severity"] == "blocker" for i in issues) else "fail"
    report = {"status": status, "issues": issues}
    out = json.dumps(report, indent=2)
    if args.output:
        p = Path(args.output); p.parent.mkdir(parents=True, exist_ok=True); p.write_text(out + "\n", encoding="utf-8")
    print(out)
    return 0 if status == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
