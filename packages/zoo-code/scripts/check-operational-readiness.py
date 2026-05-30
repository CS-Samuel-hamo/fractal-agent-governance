#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

REQUIRED = ["logging", "metrics", "tracing", "error handling", "retry", "runbook", "alerting", "rollback"]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", required=True)
    parser.add_argument("--output")
    args = parser.parse_args()
    text = Path(args.file).read_text(encoding="utf-8", errors="replace").lower() if Path(args.file).exists() else ""
    missing = [x for x in REQUIRED if x not in text]
    report = {"status": "pass" if not missing else "fail", "missing": missing}
    out = json.dumps(report, indent=2)
    if args.output:
        p = Path(args.output); p.parent.mkdir(parents=True, exist_ok=True); p.write_text(out + "\n", encoding="utf-8")
    print(out)
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
