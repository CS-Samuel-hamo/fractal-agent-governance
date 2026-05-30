#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id")
    parser.add_argument("--file")
    parser.add_argument("--output")
    args = parser.parse_args()
    path = Path(args.file) if args.file else Path(".zoo-agent") / "runs" / (args.run_id or "") / "risk-register.json"
    issues: list[dict] = []
    risks: list[dict] = []
    if not path.exists():
        issues.append({"severity": "blocker", "issue": f"missing risk register: {path}"})
    else:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        risks = data.get("risks", data if isinstance(data, list) else [])
        for r in risks:
            for f in ["risk_id", "branch_id", "type", "severity", "probability", "impact", "owner", "mitigation", "escalation_trigger", "status"]:
                if not r.get(f):
                    issues.append({"risk_id": r.get("risk_id", "unknown"), "severity": "major", "issue": f"missing {f}"})
            if str(r.get("severity", "")).lower() in {"high", "critical"} and r.get("status") not in {"approved", "mitigated", "closed"}:
                issues.append({"risk_id": r.get("risk_id", "unknown"), "severity": "blocker", "issue": "open high/critical risk blocks final integration"})
    report = {"status": "pass" if not any(i["severity"] == "blocker" for i in issues) else "fail", "risk_count": len(risks), "issues": issues, "path": str(path)}
    text = json.dumps(report, indent=2)
    if args.output:
        out = Path(args.output); out.parent.mkdir(parents=True, exist_ok=True); out.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
