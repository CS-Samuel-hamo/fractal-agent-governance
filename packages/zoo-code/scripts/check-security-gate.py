#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

SENSITIVE = ["auth", "authorization", "payment", "pii", "credential", "production config", "migration", "destructive", "external network"]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--obligation-ledger")
    parser.add_argument("--security-report")
    parser.add_argument("--output")
    args = parser.parse_args()
    text = ""
    if args.obligation_ledger and Path(args.obligation_ledger).exists():
        text += Path(args.obligation_ledger).read_text(encoding="utf-8", errors="replace").lower()
    triggered = [s for s in SENSITIVE if s in text]
    report_ok = args.security_report and Path(args.security_report).exists() and "pass" in Path(args.security_report).read_text(encoding="utf-8", errors="replace").lower()
    status = "pass" if not triggered or report_ok else "fail"
    report = {"status": status, "triggered": triggered, "security_report": args.security_report or None}
    out = json.dumps(report, indent=2)
    if args.output:
        p = Path(args.output); p.parent.mkdir(parents=True, exist_ok=True); p.write_text(out + "\n", encoding="utf-8")
    print(out)
    return 0 if status == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
