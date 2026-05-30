#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", required=True)
    parser.add_argument("--obligation-ledger")
    parser.add_argument("--output")
    args = parser.parse_args()
    text = read(Path(args.plan)).lower()
    issues: list[dict] = []
    if not text:
        issues.append({"severity": "blocker", "issue": "missing test plan"})
    for word in ["unit", "integration", "smoke", "obligation"]:
        if word not in text:
            issues.append({"severity": "major", "issue": f"test plan does not mention {word}"})
    if args.obligation_ledger and Path(args.obligation_ledger).exists():
        data = json.loads(Path(args.obligation_ledger).read_text(encoding="utf-8-sig"))
        required = [o["obligation_id"] for o in data.get("implicit_obligations", []) if o.get("status") == "required" and o.get("category") == "verification"]
        for oid in required:
            if oid.lower() not in text:
                issues.append({"severity": "blocker", "issue": f"verification obligation not mapped: {oid}"})
    status = "pass" if not any(i["severity"] == "blocker" for i in issues) else "fail"
    report = {"status": status, "issues": issues}
    out = json.dumps(report, indent=2)
    if args.output:
        p = Path(args.output); p.parent.mkdir(parents=True, exist_ok=True); p.write_text(out + "\n", encoding="utf-8")
    print(out)
    return 0 if status == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
