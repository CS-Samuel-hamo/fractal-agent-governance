#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def present(value: object) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return value.strip().lower() not in {"", "unknown", "tbd", "todo", "none"}
    if isinstance(value, list):
        return bool(value)
    return True


def evaluate(data: dict) -> dict:
    issues: list[dict] = []
    counts = {"required": 0, "open_required": 0, "closed_required": 0, "deferred": 0, "escalated": 0, "not_applicable": 0}
    for item in data.get("implicit_obligations", []):
        oid = item.get("obligation_id", "unknown")
        status = item.get("status", "required")
        if status == "required":
            counts["required"] += 1
            if present(item.get("verification")) and present(item.get("evidence")):
                counts["closed_required"] += 1
            else:
                counts["open_required"] += 1
                issues.append({"obligation_id": oid, "severity": "blocker", "issue": "required obligation lacks verification or evidence"})
        elif status == "required_but_blocked":
            counts["required"] += 1
            counts["open_required"] += 1
            issues.append({"obligation_id": oid, "severity": "blocker", "issue": "required obligation is blocked"})
        elif status == "deferred":
            counts["deferred"] += 1
            if not present(item.get("owner_mode")) or not present(item.get("why_required")):
                issues.append({"obligation_id": oid, "severity": "major", "issue": "deferred obligation lacks owner or reason"})
        elif status == "escalated":
            counts["escalated"] += 1
            if not (present(item.get("escalation_id")) or item.get("escalation_required") is True):
                issues.append({"obligation_id": oid, "severity": "major", "issue": "escalated obligation lacks escalation marker"})
        elif status == "not_applicable":
            counts["not_applicable"] += 1
            if not present(item.get("evidence")):
                issues.append({"obligation_id": oid, "severity": "major", "issue": "not_applicable obligation lacks evidence"})
    for item in data.get("deferred_items", []):
        counts["deferred"] += 1
        if not present(item.get("owner")) or not present(item.get("reason")):
            issues.append({"item": item.get("item", "unknown"), "severity": "major", "issue": "deferred item lacks owner or reason"})
    for item in data.get("not_applicable_decisions", []):
        counts["not_applicable"] += 1
        if not present(item.get("evidence")) or not present(item.get("reason")):
            issues.append({"category": item.get("category", "unknown"), "severity": "major", "issue": "not_applicable decision lacks reason or evidence"})
    if not present(data.get("discovery_method")):
        issues.append({"severity": "major", "issue": "obligation ledger missing discovery_method"})
    status = "pass" if not any(i["severity"] == "blocker" for i in issues) and counts["open_required"] == 0 else "fail"
    return {"status": status, "counts": counts, "issues": issues}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--file")
    parser.add_argument("--run-id")
    parser.add_argument("--output")
    args = parser.parse_args()
    path = Path(args.file) if args.file else Path(".zoo-agent") / "runs" / (args.run_id or "") / "obligation-ledger.json"
    if not path.exists():
        report = {"status": "fail", "issues": [{"severity": "blocker", "issue": f"missing obligation ledger: {path}"}], "counts": {}}
    else:
        report = evaluate(load(path))
        report["path"] = str(path)
    text = json.dumps(report, indent=2)
    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
