#!/usr/bin/env python3
from __future__ import annotations
import argparse, json
from pathlib import Path

def ok_event(p: Path) -> bool:
    if not p.exists(): return False
    text = p.read_text(encoding="utf-8", errors="replace").lower()
    return all(x in text for x in ["event_id", "failure_type", "regression_prompt", "expected_behavior_change", "rollback_plan"])

def main() -> int:
    ap = argparse.ArgumentParser(); ap.add_argument("--files", nargs="*", default=[]); ap.add_argument("--event")
    a = ap.parse_args(); gov = [f for f in a.files if ".roo/rules" in f.replace("\\", "/") or ".roo/skills" in f.replace("\\", "/")]
    if not gov: print(json.dumps({"status": "pass", "governance_changes": []}, indent=2)); return 0
    if not a.event or not ok_event(Path(a.event)):
        print(json.dumps({"status": "fail", "governance_changes": gov, "error": "missing_event_backed_governance_metadata"}, indent=2)); return 2
    print(json.dumps({"status": "pass", "governance_changes": gov, "event": a.event}, indent=2)); return 0
if __name__ == "__main__": raise SystemExit(main())
