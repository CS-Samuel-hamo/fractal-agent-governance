#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

REQUIRED = ["exception_id", "approver", "scope", "reason", "accepted_risk", "rollback_plan", "monitoring_plan", "expiry"]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", required=True)
    parser.add_argument("--output")
    args = parser.parse_args()
    data = json.loads(Path(args.file).read_text(encoding="utf-8-sig"))
    issues = [{"severity": "blocker", "issue": f"missing {f}"} for f in REQUIRED if not data.get(f)]
    if data.get("approved_by_model", "").lower().startswith("deepseek"):
        issues.append({"severity": "blocker", "issue": "DeepSeek cannot accept human exception"})
    status = "pass" if not issues else "fail"
    report = {"status": status, "issues": issues}
    out = json.dumps(report, indent=2)
    if args.output:
        p = Path(args.output); p.parent.mkdir(parents=True, exist_ok=True); p.write_text(out + "\n", encoding="utf-8")
    print(out)
    return 0 if status == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
