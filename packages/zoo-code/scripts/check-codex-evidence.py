#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Check collected Codex result evidence.")
    parser.add_argument("--result", required=True)
    args = parser.parse_args()
    result_path = Path(args.result)
    data = json.loads(result_path.read_text(encoding="utf-8"))
    failures = []
    if data.get("scope_guard", {}).get("status") != "pass":
        failures.append("scope_guard_not_pass")
    if not data.get("git_status_short"):
        failures.append("missing_git_status")
    if not data.get("progress_md"):
        failures.append("missing_progress_md")
    if data.get("blockers_md") and "blocked" in data.get("blockers_md", "").lower():
        failures.append("blockers_present")
    report = {"result": str(result_path), "pass": not failures, "failures": failures}
    print(json.dumps(report, indent=2))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
