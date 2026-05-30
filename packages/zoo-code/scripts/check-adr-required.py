#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

TRIGGERS = ["public api", "migration", "database schema", "auth", "security boundary", "external dependency", "shared type", "shared utility", "processor data-source", "proc/processor", "dependency direction", "architecture_unknown", "conflicting existing patterns"]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input")
    parser.add_argument("--decision-dir", default="docs/agent-governance/decisions")
    parser.add_argument("--output")
    args = parser.parse_args()
    text = Path(args.input).read_text(encoding="utf-8", errors="replace").lower() if args.input and Path(args.input).exists() else ""
    found = [t for t in TRIGGERS if t in text]
    decision_dir = Path(args.decision_dir)
    adr_exists = decision_dir.exists() and any(decision_dir.glob("*.md"))
    status = "pass" if not found or adr_exists else "fail"
    report = {"status": status, "adr_required": bool(found), "triggers": found, "adr_exists": adr_exists}
    out = json.dumps(report, indent=2)
    if args.output:
        p = Path(args.output); p.parent.mkdir(parents=True, exist_ok=True); p.write_text(out + "\n", encoding="utf-8")
    print(out)
    return 0 if status == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
