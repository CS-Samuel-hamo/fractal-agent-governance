#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def queue_path(run_id: str, explicit: str | None) -> Path:
    return Path(explicit) if explicit else Path(".zoo-agent") / "runs" / run_id / "merge-queue.json"


def load(path: Path, run_id: str) -> dict:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8-sig"))
    return {"run_id": run_id, "queue": [], "rejected": [], "updated_at": now()}


def eligible(args: argparse.Namespace) -> tuple[bool, list[str]]:
    reasons = []
    if args.quality_gate_status != "pass":
        reasons.append("quality_gate_not_pass")
    if args.review_status != "pass":
        reasons.append("review_not_pass")
    if args.path_lock_status != "pass":
        reasons.append("path_lock_not_pass")
    if args.parent_aggregation_status not in {"pass", "not_required"}:
        reasons.append("parent_aggregation_not_pass")
    if args.risk_level in {"high", "critical"}:
        reasons.append("high_or_critical_risk")
    return not reasons, reasons


def load_branch_statuses(run_id: str) -> dict[str, str]:
    path = Path(".zoo-agent") / "runs" / run_id / "branch-state.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return {}
    return {item.get("branch_id"): str(item.get("status", "unknown")).lower() for item in data.get("branches", [])}


def prune_unsafe(data: dict, run_id: str) -> tuple[dict, list[dict]]:
    statuses = load_branch_statuses(run_id)
    unsafe = {"abandoned", "redo_needed", "paused"}
    kept = []
    moved = []
    for item in data.get("queue", []):
        bid = item.get("branch_id")
        status = statuses.get(bid)
        if status in unsafe:
            rejected = dict(item)
            rejected["branch_status"] = status
            rejected["reasons"] = ["branch_not_safe_for_merge_queue"]
            rejected["moved_at"] = now()
            moved.append(rejected)
        else:
            kept.append(item)
    data["queue"] = kept
    data.setdefault("rejected", []).extend(moved)
    data["updated_at"] = now()
    data["redirect_impact"] = "reorder_required" if moved else data.get("redirect_impact", "unchanged")
    return data, moved


def main() -> int:
    parser = argparse.ArgumentParser(description="Update merge queue; only gate/review/path-lock safe branches can enqueue.")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--branch-id")
    parser.add_argument("--action", choices=["enqueue", "list", "prune-unsafe"], default="enqueue")
    parser.add_argument("--queue")
    parser.add_argument("--quality-gate-status", default="unknown")
    parser.add_argument("--review-status", default="unknown")
    parser.add_argument("--path-lock-status", default="unknown")
    parser.add_argument("--parent-aggregation-status", default="not_required")
    parser.add_argument("--risk-level", choices=["low", "medium", "high", "critical", "unknown"], default="unknown")
    parser.add_argument("--output")
    args = parser.parse_args()
    path = queue_path(args.run_id, args.queue)
    data = load(path, args.run_id)
    if args.action == "prune-unsafe":
        data, moved = prune_unsafe(data, args.run_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        status = "pass"
    elif args.action == "enqueue":
        if not args.branch_id:
            print(json.dumps({"status": "fail", "error": "branch_id_required_for_enqueue"}, indent=2))
            return 2
        ok, reasons = eligible(args)
        entry = {
            "branch_id": args.branch_id,
            "quality_gate_status": args.quality_gate_status,
            "review_status": args.review_status,
            "path_lock_status": args.path_lock_status,
            "parent_aggregation_status": args.parent_aggregation_status,
            "risk_level": args.risk_level,
            "queued_at": now(),
        }
        if ok:
            data["queue"] = [x for x in data.get("queue", []) if x.get("branch_id") != args.branch_id]
            data["queue"].append(entry)
            status = "pass"
        else:
            entry["reasons"] = reasons
            data.setdefault("rejected", []).append(entry)
            status = "fail"
        data["updated_at"] = now()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    else:
        status = "pass"
    report = {"status": status, "path": str(path), "queue": data.get("queue", []), "rejected": data.get("rejected", [])}
    text = json.dumps(report, indent=2)
    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0 if status == "pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())
