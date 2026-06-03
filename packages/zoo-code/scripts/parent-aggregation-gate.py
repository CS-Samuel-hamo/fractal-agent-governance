#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


READY_BRANCH_STATES = {"ready_for_parent_aggregation", "parent_aggregated", "queued", "merged"}


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def slug(value: str) -> str:
    out = []
    for ch in value.lower():
        if ch.isalnum():
            out.append(ch)
        elif ch in {"-", "_", "."}:
            out.append("-")
    return "".join(out).strip("-") or "branch"


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def run_dir(args: argparse.Namespace) -> Path:
    return Path(args.run_dir) if args.run_dir else Path(".zoo-agent") / "runs" / args.run_id


def branch_ids(schedule: dict, merge_queue: dict, explicit: list[str]) -> list[str]:
    if explicit:
        return explicit
    ids = [item.get("branch_id") for item in merge_queue.get("queue", []) if item.get("branch_id")]
    if ids:
        return ids
    return [item.get("branch_id") for item in schedule.get("branches", []) if item.get("branch_id")]


def branch_from_ledger(ledger: dict, branch_id: str) -> dict:
    for item in ledger.get("branches", []):
        if item.get("branch_id") == branch_id:
            return item
    return {}


def branch_from_schedule(schedule: dict, branch_id: str) -> dict:
    for item in schedule.get("branches", []):
        if item.get("branch_id") == branch_id:
            return item
    return {}


def queue_item(merge_queue: dict, branch_id: str) -> dict:
    for item in merge_queue.get("queue", []):
        if item.get("branch_id") == branch_id:
            return item
    return {}


def reconciliation_path(base: Path, branch_id: str) -> Path:
    return base / "branches" / slug(branch_id) / "branch-reconciliation.json"


def artifact_exists(path_value: str) -> bool:
    return bool(path_value) and Path(path_value).exists()


def evaluate_branch(base: Path, branch_id: str, schedule: dict, ledger: dict, merge_queue: dict) -> dict:
    issues: list[dict] = []
    scheduled = branch_from_schedule(schedule, branch_id)
    branch_state = branch_from_ledger(ledger, branch_id)
    queued = queue_item(merge_queue, branch_id)
    reconciliation = load_json(reconciliation_path(base, branch_id), {})

    if not scheduled:
        issues.append({"severity": "blocker", "type": "missing_schedule_branch"})
    if not branch_state:
        issues.append({"severity": "blocker", "type": "missing_run_ledger_branch"})
    if not queued:
        issues.append({"severity": "blocker", "type": "missing_merge_queue_item"})
    if branch_state and branch_state.get("state") not in READY_BRANCH_STATES:
        issues.append({"severity": "blocker", "type": "branch_not_ready_for_parent_aggregation", "state": branch_state.get("state")})
    if not reconciliation:
        issues.append({"severity": "blocker", "type": "missing_branch_reconciliation"})
    elif reconciliation.get("status") != "pass":
        issues.append({"severity": "blocker", "type": "branch_reconciliation_failed", "status": reconciliation.get("status")})
    if queued and queued.get("status") not in {"ready_for_parent_aggregation", "ready_for_serial_merge", "waiting_for_completion"}:
        issues.append({"severity": "blocker", "type": "merge_queue_item_not_ready", "status": queued.get("status")})

    for artifact in branch_state.get("required_output_artifacts", []) if branch_state else []:
        path = artifact.get("path", "")
        artifact_type = artifact.get("type", "artifact")
        if not artifact_exists(path):
            issues.append({"severity": "blocker", "type": "missing_required_branch_artifact", "artifact_type": artifact_type, "path": path})

    open_blockers = [x for x in issues if x.get("severity") == "blocker"]
    return {
        "branch_id": branch_id,
        "status": "pass" if not open_blockers else "fail",
        "execution_mode": scheduled.get("execution_mode", "unknown"),
        "phase_id": scheduled.get("phase_id", ""),
        "issues": issues,
        "recommended_action": "ready_for_serial_merge" if not open_blockers else "rollback_or_redecompose",
    }


def add_graph_artifact(graph: dict, path: str, run_id: str, goal_id: str, status: str) -> None:
    artifact_id = f"parent_aggregation:{path}"
    graph.setdefault("artifacts", [])
    graph["artifacts"] = [
        item for item in graph["artifacts"]
        if not (isinstance(item, dict) and item.get("artifact_id") == artifact_id)
    ]
    graph["artifacts"].append({
        "artifact_id": artifact_id,
        "type": "parent_aggregation",
        "path": path,
        "run_id": run_id,
        "goal_id": goal_id,
        "branch_id": "root",
        "created_by_mode": "agent-planner",
        "model": "GPT-5.5",
        "created_at": now(),
        "input_artifacts": ["branch-reconciliation", "parent-aggregation-matrices", "merge-queue"],
        "output_artifacts": [path],
        "gate_status": status,
    })
    graph["updated_at"] = now()


def update_ledger(ledger: dict, results: list[dict], path: str, status: str) -> None:
    ts = now()
    result_by_id = {item["branch_id"]: item for item in results}
    for branch in ledger.get("branches", []):
        bid = branch.get("branch_id")
        if bid in result_by_id:
            branch["parent_aggregation_status"] = result_by_id[bid]["status"]
            if result_by_id[bid]["status"] == "pass":
                branch["state"] = "parent_aggregated"
            else:
                branch["state"] = "needs_decomposition"
            branch["parent_aggregation_report"] = path
            branch["updated_at"] = ts
    ledger.setdefault("transitions", []).append({
        "at": ts,
        "from": ledger.get("current_state", "planned"),
        "to": "parent_aggregated" if status == "pass" else ledger.get("current_state", "planned"),
        "run_id": ledger.get("run_id", "unknown"),
        "goal_id": ledger.get("goal_id", "unknown"),
        "branch_id": "root",
        "created_by_mode": "agent-planner",
        "owner_mode": "agent-planner",
        "model": "GPT-5.5",
        "input_artifacts": ["branch-reconciliation", "merge-queue"],
        "output_artifacts": [path],
        "gate_status": status,
        "decision": "parent_aggregation_gate",
    })
    if status == "pass":
        ledger["current_state"] = "parent_aggregated"
    ledger["updated_at"] = ts


def update_merge_queue(merge_queue: dict, results: list[dict]) -> None:
    result_by_id = {item["branch_id"]: item for item in results}
    for item in merge_queue.get("queue", []):
        bid = item.get("branch_id")
        if bid not in result_by_id:
            continue
        result = result_by_id[bid]
        item["parent_aggregation_status"] = result["status"]
        item["status"] = "ready_for_serial_merge" if result["status"] == "pass" else "blocked_parent_aggregation_failed"
        item["parent_aggregation_issues"] = result["issues"]
        item["updated_at"] = now()
    merge_queue["updated_at"] = now()


def main() -> int:
    parser = argparse.ArgumentParser(description="Gate parent aggregation before any parallel branch can enter final integration.")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--run-dir")
    parser.add_argument("--branch-id", action="append", default=[])
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    base = run_dir(args)
    schedule = load_json(base / "branch-schedule.json", {})
    merge_queue = load_json(base / "merge-queue.json", {"queue": []})
    ledger = load_json(base / "run-ledger.json", {"run_id": args.run_id, "branches": [], "transitions": []})
    graph = load_json(base / "artifact-graph.json", {"run_id": args.run_id, "artifacts": [], "edges": []})
    goal_id = schedule.get("goal_id", ledger.get("goal_id", "unknown"))
    matrices_path = base / "parent-aggregation-matrices.json"

    ids = branch_ids(schedule, merge_queue, args.branch_id)
    results = [evaluate_branch(base, bid, schedule, ledger, merge_queue) for bid in ids]
    issues = [issue for result in results for issue in result["issues"] if issue.get("severity") == "blocker"]
    if not matrices_path.exists():
        issues.append({"severity": "blocker", "type": "missing_parent_aggregation_matrices", "path": str(matrices_path)})
    aggregation_diagnostics = load_json(base / "aggregation-diagnostics-report.json", {})
    if aggregation_diagnostics:
        if aggregation_diagnostics.get("status") == "fail":
            issues.append({"severity": "blocker", "type": "aggregation_diagnostics_failed"})
        for diagnostic in aggregation_diagnostics.get("new_errors", []) + aggregation_diagnostics.get("diagnostics", []):
            if isinstance(diagnostic, dict) and str(diagnostic.get("severity", diagnostic.get("level", ""))).lower() == "error":
                issues.append({"severity": "blocker", "type": "aggregation_error_diagnostic", "diagnostic": diagnostic})
            elif isinstance(diagnostic, str) and diagnostic.strip():
                issues.append({"severity": "blocker", "type": "aggregation_error_diagnostic", "diagnostic": diagnostic})
    elif merge_queue.get("queue"):
        issues.append({"severity": "blocker", "type": "missing_aggregation_diagnostics_report", "path": str(base / "aggregation-diagnostics-report.json")})
    status = "pass" if not issues and results else "fail"
    report_path = str(base / "parent-aggregation.json")
    report = {
        "schema_version": "1.0",
        "run_id": args.run_id,
        "goal_id": goal_id,
        "branch_id": "root",
        "created_by_mode": "agent-planner",
        "model": "GPT-5.5",
        "created_at": now(),
        "status": status,
        "parent_aggregation_matrices": str(matrices_path),
        "aggregation_diagnostics": str(base / "aggregation-diagnostics-report.json"),
        "branch_results": results,
        "issues": issues,
        "final_integration_allowed": status == "pass",
        "next_action": "serial_merge_queue" if status == "pass" else "rollback_or_redecompose",
    }

    if args.dry_run:
        print(json.dumps(report, indent=2))
        return 0 if status == "pass" else 2

    write_json(Path(report_path), report)
    update_ledger(ledger, results, report_path, status)
    update_merge_queue(merge_queue, results)
    add_graph_artifact(graph, report_path, args.run_id, goal_id, status)
    write_json(base / "run-ledger.json", ledger)
    write_json(base / "merge-queue.json", merge_queue)
    write_json(base / "artifact-graph.json", graph)
    print(json.dumps({"status": status, "path": report_path, "final_integration_allowed": status == "pass", "issues": issues}, indent=2))
    return 0 if status == "pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())
