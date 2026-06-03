#!/usr/bin/env python3
from __future__ import annotations

import argparse
import fnmatch
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PASS_STATUSES = {"pass", "passed", "ok", "closed", "closed_or_deferred", "not_required", "not_applicable"}
FAIL_STATUSES = {"fail", "failed", "blocker", "blocked", "error"}
REQUIRED_ARTIFACTS = {
    "completion_evidence": ["completion-evidence.md", "completion_evidence.md", "completion-evidence.json", "completion_evidence.json"],
    "obligation_ledger": ["obligation-ledger.json", "obligation_ledger.json"],
    "diagnostics_report": ["diagnostics-report.json", "diagnostics_report.json"],
    "quality_gate": ["quality-gate.json", "quality_gate.json"],
    "review_report": ["review-report.json", "review_report.json"],
}


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


def normalize(path: str) -> str:
    return str(path).replace("\\", "/").strip().strip("/")


def pattern_match(path: str, pattern: str) -> bool:
    candidate = normalize(path)
    pat = normalize(pattern)
    if not pat:
        return False
    if fnmatch.fnmatch(candidate, pat):
        return True
    if pat.endswith("/**"):
        return candidate == pat[:-3] or candidate.startswith(pat[:-2])
    return candidate == pat or candidate.startswith(pat.rstrip("*").rstrip("/") + "/")


def any_match(path: str, patterns: list[str]) -> bool:
    return any(pattern_match(path, p) for p in patterns)


def run_dir(args: argparse.Namespace) -> Path:
    return Path(args.run_dir) if args.run_dir else Path(".zoo-agent") / "runs" / args.run_id


def branch_entry(data: dict, branch_id: str) -> dict:
    for item in data.get("branches", []) + data.get("locks", []):
        if item.get("branch_id") == branch_id:
            return item
    return {}


def merge_item(data: dict, branch_id: str) -> dict:
    for item in data.get("queue", []):
        if item.get("branch_id") == branch_id:
            return item
    return {}


def status_from_file(path: Path) -> str:
    if not path.exists() or path.suffix.lower() != ".json":
        return "unknown"
    data = load_json(path, {})
    for key in ["status", "gate_status", "review_status", "diagnostics_status", "verdict"]:
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip().lower()
    return "unknown"


def find_artifact(run_dir_path: Path, branch_id: str, artifact_type: str, explicit: str | None = None) -> Path | None:
    if explicit:
        path = Path(explicit)
        return path if path.exists() else path
    branch_dir = run_dir_path / "branches" / slug(branch_id)
    for name in REQUIRED_ARTIFACTS[artifact_type]:
        candidate = branch_dir / name
        if candidate.exists():
            return candidate
    for name in REQUIRED_ARTIFACTS[artifact_type]:
        candidate = run_dir_path / name
        if candidate.exists():
            return candidate
    return None


def changed_files_from_git(worktree: str) -> tuple[list[str], list[str]]:
    if not worktree:
        return [], ["missing_worktree_path_for_diff"]
    path = Path(worktree)
    if not path.exists():
        return [], ["worktree_path_missing"]
    files: set[str] = set()
    issues: list[str] = []
    for args in [["diff", "--name-only"], ["diff", "--cached", "--name-only"]]:
        result = subprocess.run(
            ["git", "-C", str(path), *args],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        if result.returncode != 0:
            issues.append("git_diff_unavailable")
            continue
        files.update(normalize(x) for x in result.stdout.splitlines() if x.strip())
    return sorted(files), sorted(set(issues))


def artifact_status(name: str, path: Path | None, override: str | None = None) -> dict:
    if override:
        status = override.lower()
    elif path and path.exists():
        if name in {"completion_evidence", "obligation_ledger"}:
            status = status_from_file(path)
            status = "pass" if status == "unknown" else status
        else:
            status = status_from_file(path)
    else:
        status = "missing"
    ok = status in PASS_STATUSES
    return {
        "artifact_type": name,
        "path": str(path) if path else "",
        "status": status,
        "ok": ok,
    }


def add_graph_artifact(graph: dict, path: str, run_id: str, goal_id: str, branch_id: str, status: str) -> None:
    artifact_id = f"branch_reconciliation:{path}"
    graph.setdefault("artifacts", [])
    graph["artifacts"] = [
        item for item in graph["artifacts"]
        if not (isinstance(item, dict) and item.get("artifact_id") == artifact_id)
    ]
    graph["artifacts"].append({
        "artifact_id": artifact_id,
        "type": "branch_reconciliation",
        "path": path,
        "run_id": run_id,
        "goal_id": goal_id,
        "branch_id": branch_id,
        "created_by_mode": "agent-orchestrator",
        "model": "GPT-5.5",
        "created_at": now(),
        "input_artifacts": ["branch-schedule", "worktree-map", "path-locks", "merge-queue"],
        "output_artifacts": [path],
        "gate_status": status,
    })
    graph["updated_at"] = now()


def update_ledger(ledger: dict, branch_id: str, report_path: str, status: str, branch_state: str, issues: list[dict]) -> None:
    ts = now()
    for item in ledger.get("branches", []):
        if item.get("branch_id") == branch_id:
            item["state"] = branch_state
            item["completion_reconciliation_status"] = status
            item["completion_reconciliation_report"] = report_path
            item["completion_reconciliation_issues"] = issues
            item["updated_at"] = ts
    ledger.setdefault("transitions", []).append({
        "at": ts,
        "from": ledger.get("current_state", "planned"),
        "to": ledger.get("current_state", "planned"),
        "run_id": ledger.get("run_id", "unknown"),
        "goal_id": ledger.get("goal_id", "unknown"),
        "branch_id": branch_id,
        "created_by_mode": "agent-orchestrator",
        "owner_mode": "agent-orchestrator",
        "model": "GPT-5.5",
        "input_artifacts": ["branch-schedule", "worktree-map", "path-locks", "merge-queue"],
        "output_artifacts": [report_path],
        "gate_status": status,
        "decision": "branch_completion_reconciled",
    })
    ledger["updated_at"] = ts


def update_merge_queue(queue: dict, branch_id: str, status: str, reasons: list[dict]) -> None:
    found = False
    for item in queue.get("queue", []):
        if item.get("branch_id") == branch_id:
            found = True
            item["reconciliation_status"] = status
            item["status"] = "ready_for_parent_aggregation" if status == "pass" else "blocked_reconciliation_failed"
            item["reconciliation_issues"] = reasons
            item["updated_at"] = now()
    if not found and status != "pass":
        queue.setdefault("rejected", []).append({
            "branch_id": branch_id,
            "status": "blocked_reconciliation_failed",
            "reasons": reasons,
            "updated_at": now(),
        })
    queue["updated_at"] = now()


def main() -> int:
    parser = argparse.ArgumentParser(description="Reconcile completed branch output against schedule, path locks, artifacts, and merge queue.")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--branch-id", required=True)
    parser.add_argument("--run-dir")
    parser.add_argument("--changed-file", action="append", default=[])
    parser.add_argument("--diff-name-only", action="store_true", help="Read changed file names from branch worktree with git diff; does not read file contents.")
    parser.add_argument("--parent-shared-approval", action="store_true")
    parser.add_argument("--completion-evidence")
    parser.add_argument("--obligation-ledger")
    parser.add_argument("--diagnostics-report")
    parser.add_argument("--quality-gate")
    parser.add_argument("--review-report")
    parser.add_argument("--obligation-status")
    parser.add_argument("--diagnostics-status")
    parser.add_argument("--quality-gate-status")
    parser.add_argument("--review-status")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    base = run_dir(args)
    schedule = load_json(base / "branch-schedule.json", {})
    locks = load_json(base / "path-locks.json", {})
    worktrees = load_json(base / "worktree-map.json", {})
    merge_queue = load_json(base / "merge-queue.json", {"run_id": args.run_id, "queue": [], "rejected": []})
    ledger = load_json(base / "run-ledger.json", {"run_id": args.run_id, "goal_id": schedule.get("goal_id", "unknown"), "branches": [], "transitions": []})
    graph = load_json(base / "artifact-graph.json", {"run_id": args.run_id, "goal_id": schedule.get("goal_id", "unknown"), "artifacts": [], "edges": []})

    scheduled = branch_entry(schedule, args.branch_id)
    lock = branch_entry(locks, args.branch_id)
    wt = branch_entry(worktrees, args.branch_id)
    issues: list[dict] = []
    if not scheduled:
        issues.append({"severity": "blocker", "type": "branch_missing_from_schedule"})
    if not lock:
        issues.append({"severity": "blocker", "type": "branch_missing_path_lock"})
    if not wt:
        issues.append({"severity": "blocker", "type": "branch_missing_worktree_map"})

    changed = [normalize(x) for x in args.changed_file]
    diff_issues: list[str] = []
    if args.diff_name_only:
        diff_files, diff_issues = changed_files_from_git(wt.get("worktree_path", ""))
        changed = sorted(set(changed) | set(diff_files))
    for item in diff_issues:
        issues.append({"severity": "major", "type": item})

    owned = lock.get("owned_paths", scheduled.get("owned_paths", []))
    shared = lock.get("shared_paths", scheduled.get("shared_paths", []))
    forbidden = lock.get("forbidden_paths", scheduled.get("forbidden_paths", []))
    for file_name in changed:
        if any_match(file_name, forbidden):
            issues.append({"severity": "blocker", "type": "forbidden_path_changed", "file": file_name})
        elif any_match(file_name, owned):
            continue
        elif any_match(file_name, shared):
            if not args.parent_shared_approval:
                issues.append({"severity": "blocker", "type": "shared_path_changed_without_parent_approval", "file": file_name})
        else:
            issues.append({"severity": "blocker", "type": "unowned_path_changed", "file": file_name})

    artifact_paths = {
        "completion_evidence": find_artifact(base, args.branch_id, "completion_evidence", args.completion_evidence),
        "obligation_ledger": find_artifact(base, args.branch_id, "obligation_ledger", args.obligation_ledger),
        "diagnostics_report": find_artifact(base, args.branch_id, "diagnostics_report", args.diagnostics_report),
        "quality_gate": find_artifact(base, args.branch_id, "quality_gate", args.quality_gate),
        "review_report": find_artifact(base, args.branch_id, "review_report", args.review_report),
    }
    artifact_checks = [
        artifact_status("completion_evidence", artifact_paths["completion_evidence"]),
        artifact_status("obligation_ledger", artifact_paths["obligation_ledger"], args.obligation_status),
        artifact_status("diagnostics_report", artifact_paths["diagnostics_report"], args.diagnostics_status),
        artifact_status("quality_gate", artifact_paths["quality_gate"], args.quality_gate_status),
        artifact_status("review_report", artifact_paths["review_report"], args.review_status),
    ]
    for check in artifact_checks:
        if not check["ok"]:
            issues.append({"severity": "blocker", "type": f"{check['artifact_type']}_not_ready", "status": check["status"], "path": check["path"]})

    blockers = [x for x in issues if x.get("severity") == "blocker"]
    status = "pass" if not blockers else "fail"
    branch_state = "ready_for_parent_aggregation" if status == "pass" else "needs_decomposition"
    report_path = str(base / "branches" / slug(args.branch_id) / "branch-reconciliation.json")
    report = {
        "schema_version": "1.0",
        "run_id": args.run_id,
        "goal_id": schedule.get("goal_id", ledger.get("goal_id", "unknown")),
        "branch_id": args.branch_id,
        "created_by_mode": "agent-orchestrator",
        "model": "GPT-5.5",
        "created_at": now(),
        "status": status,
        "branch_state": branch_state,
        "changed_files": changed,
        "path_lock_check": {
            "owned_paths": owned,
            "shared_paths": shared,
            "forbidden_paths": forbidden,
            "parent_shared_approval": args.parent_shared_approval,
        },
        "artifact_checks": artifact_checks,
        "issues": issues,
        "next_action": "parent_aggregation" if status == "pass" else "rollback_or_redecompose",
    }

    if args.dry_run:
        print(json.dumps(report, indent=2))
        return 0 if status == "pass" else 2

    write_json(Path(report_path), report)
    update_ledger(ledger, args.branch_id, report_path, status, branch_state, issues)
    update_merge_queue(merge_queue, args.branch_id, status, issues)
    add_graph_artifact(graph, report_path, args.run_id, report["goal_id"], args.branch_id, status)
    write_json(base / "run-ledger.json", ledger)
    write_json(base / "merge-queue.json", merge_queue)
    write_json(base / "artifact-graph.json", graph)
    print(json.dumps({"status": status, "path": report_path, "branch_state": branch_state, "issues": issues}, indent=2))
    return 0 if status == "pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())
