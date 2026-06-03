#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SENSITIVE_FLAGS = {
    "security",
    "auth",
    "authorization",
    "payment",
    "pii",
    "privacy",
    "migration",
    "credentials",
    "production_config",
}
HIGH_RISK = {"high", "critical"}
STABLE_CONTRACTS = {"stable", "approved", "locked", "declared", "not_required"}
GPT_APPROVERS = {"agent-orchestrator", "agent-planner"}
HARD_UNSCHEDULABLE_BLOCKERS = {
    "branch_not_schedulable",
    "retained_no_execution_required",
    "redo_requires_replanning",
    "needs_decomposition",
    "dependency_on_unschedulable_branch",
    "parent_aggregation_node",
}
BRANCH_OUTPUTS = [
    "completion_evidence",
    "obligation_ledger",
    "diagnostics_report",
    "parent_aggregation_matrices",
]
SCHEDULER_ARTIFACT_TYPES = {
    "branch_schedule",
    "worktree_map",
    "path_locks",
    "merge_queue",
    "parent_aggregation_matrices",
    "parallel_metrics",
    "parallel_execution_report",
}


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_json(path: Path, default: Any) -> Any:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8-sig"))
    return default


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def normalize_path(value: str) -> str:
    return str(value).replace("\\", "/").strip().strip("/").rstrip("*")


def listify(value: Any) -> list:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def clean_list(value: Any) -> list[str]:
    return [str(x).replace("\\", "/").strip() for x in listify(value) if str(x).strip()]


def path_overlap(left: str, right: str) -> bool:
    a = normalize_path(left)
    b = normalize_path(right)
    return bool(a and b and (a == b or a.startswith(b + "/") or b.startswith(a + "/") or a.startswith(b) or b.startswith(a)))


def slug(value: str) -> str:
    out = []
    for ch in value.lower():
        if ch.isalnum():
            out.append(ch)
        elif ch in {"-", "_", "."}:
            out.append("-")
    return "".join(out).strip("-") or "branch"


def git_head() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--verify", "HEAD"],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=False,
        )
    except OSError:
        return "pending:zoo-code-checkpoint"
    if result.returncode != 0:
        return "pending:zoo-code-checkpoint"
    return "git-head:" + result.stdout.strip()


def load_branches(path: Path) -> list[dict]:
    data = load_json(path, {})
    if isinstance(data, list):
        branches = data
    elif isinstance(data, dict):
        branches = data.get("branches") or data.get("tasks") or data.get("branch_tree") or data.get("nodes") or []
    else:
        branches = []
    normalized = []
    for item in branches:
        if not isinstance(item, dict):
            continue
        branch = dict(item)
        branch["branch_id"] = str(branch.get("branch_id") or branch.get("id") or "")
        if not branch["branch_id"]:
            continue
        branch["parent_branch_id"] = str(branch.get("parent_branch_id") or branch.get("parent_id") or "root")
        branch["owned_paths"] = clean_list(branch.get("owned_paths"))
        branch["shared_paths"] = clean_list(branch.get("shared_paths"))
        branch["forbidden_paths"] = clean_list(branch.get("forbidden_paths"))
        branch["provides"] = clean_list(branch.get("provides"))
        branch["consumes"] = clean_list(branch.get("consumes"))
        branch["dependencies"] = clean_list(branch.get("dependencies") or branch.get("depends_on"))
        branch["acceptance_criteria"] = clean_list(branch.get("acceptance_criteria"))
        branch["verification_plan"] = clean_list(branch.get("verification_plan"))
        branch["risk_level"] = str(branch.get("risk_level", "unknown")).lower()
        branch["sensitive_flags"] = [str(x).lower() for x in clean_list(branch.get("sensitive_flags") or branch.get("risk_tags"))]
        branch["contracts_stable"] = branch.get("contracts_stable", None)
        branch["contract_status"] = str(branch.get("contract_status", "stable")).lower()
        if branch.get("status") in {"retained", "abandoned", "redo_needed", "paused"}:
            branch["status"] = str(branch.get("status")).lower()
        normalized.append(branch)
    return normalized


def inferred_dependencies(branches: list[dict]) -> dict[str, set[str]]:
    providers: dict[str, set[str]] = {}
    for branch in branches:
        bid = branch["branch_id"]
        for provided in branch.get("provides", []):
            providers.setdefault(provided, set()).add(bid)
    deps: dict[str, set[str]] = {}
    for branch in branches:
        bid = branch["branch_id"]
        deps[bid] = set(branch.get("dependencies", []))
        for consumed in branch.get("consumes", []):
            deps[bid].update(x for x in providers.get(consumed, set()) if x != bid)
    return deps


def branch_blockers(branch: dict, approval_owner: str, deps: set[str]) -> list[str]:
    blockers: list[str] = []
    if approval_owner not in GPT_APPROVERS:
        blockers.append("parallel_group_not_gpt_approved")
    if not branch.get("owned_paths"):
        blockers.append("missing_owned_paths")
    if "shared_paths" not in branch:
        blockers.append("shared_paths_not_declared")
    if branch.get("contracts_stable") is False:
        blockers.append("provides_consumes_contract_unstable")
    if str(branch.get("contract_status", "stable")).lower() not in STABLE_CONTRACTS:
        blockers.append("provides_consumes_contract_unstable")
    if branch.get("risk_level") in HIGH_RISK:
        blockers.append("high_or_critical_risk")
    if SENSITIVE_FLAGS & set(branch.get("sensitive_flags", [])):
        blockers.append("sensitive_work")
    if not branch.get("acceptance_criteria"):
        blockers.append("missing_independent_acceptance_criteria")
    if not branch.get("verification_plan"):
        blockers.append("missing_independent_verification_plan")
    if branch.get("needs_decomposition") is True:
        blockers.append("needs_decomposition")
    if branch.get("status") in {"blocked", "aborted", "abandoned", "paused"}:
        blockers.append("branch_not_schedulable")
    if branch.get("status") == "retained":
        blockers.append("retained_no_execution_required")
    if branch.get("status") == "redo_needed":
        blockers.append("redo_requires_replanning")
    if branch.get("parallel_allowed") is False:
        blockers.append("parallel_explicitly_disabled")
    if branch.get("risk_level") == "unknown":
        blockers.append("unknown_risk")
    if not isinstance(deps, set):
        blockers.append("invalid_dependency_matrix")
    return blockers


def branch_conflict(left: dict, right: dict) -> list[dict]:
    issues: list[dict] = []
    for a in left.get("owned_paths", []):
        for b in right.get("owned_paths", []):
            if path_overlap(a, b):
                issues.append({
                    "type": "owned_path_overlap",
                    "left": left["branch_id"],
                    "right": right["branch_id"],
                    "path_a": a,
                    "path_b": b,
                })
    for a in left.get("owned_paths", []):
        for b in right.get("shared_paths", []):
            if path_overlap(a, b):
                issues.append({
                    "type": "owned_shared_overlap_requires_parent_approval",
                    "left": left["branch_id"],
                    "right": right["branch_id"],
                    "owned_path": a,
                    "shared_path": b,
                })
    for a in left.get("shared_paths", []):
        for b in right.get("owned_paths", []):
            if path_overlap(a, b):
                issues.append({
                    "type": "owned_shared_overlap_requires_parent_approval",
                    "left": right["branch_id"],
                    "right": left["branch_id"],
                    "owned_path": b,
                    "shared_path": a,
                })
    return issues


def can_share_group(branch: dict, group: list[dict], deps: dict[str, set[str]]) -> tuple[bool, list[dict]]:
    issues: list[dict] = []
    bid = branch["branch_id"]
    for other in group:
        oid = other["branch_id"]
        if oid in deps.get(bid, set()) or bid in deps.get(oid, set()):
            issues.append({"type": "depends_on_parallel_sibling", "left": bid, "right": oid})
        issues.extend(branch_conflict(branch, other))
    return not issues, issues


def schedule_layers(branches: list[dict], eligible: set[str], schedulable: set[str], deps: dict[str, set[str]]) -> tuple[list[dict], list[dict], dict[str, list[dict]]]:
    by_id = {b["branch_id"]: b for b in branches}
    remaining = set(schedulable)
    phases: list[dict] = []
    conflicts: dict[str, list[dict]] = {}
    phase_no = 1
    while remaining:
        ready = [bid for bid in sorted(remaining) if not (deps.get(bid, set()) & remaining)]
        if not ready:
            for bid in sorted(remaining):
                conflicts.setdefault(bid, []).append({"type": "dependency_cycle_or_unknown_dependency"})
            break
        ready_eligible = [by_id[bid] for bid in ready if bid in eligible]
        ready_serial = [by_id[bid] for bid in ready if bid not in eligible]
        groups: list[list[dict]] = []
        for branch in ready_eligible:
            placed = False
            for group in groups:
                ok, issues = can_share_group(branch, group, deps)
                if ok:
                    group.append(branch)
                    placed = True
                    break
                conflicts.setdefault(branch["branch_id"], []).extend(issues)
            if not placed:
                groups.append([branch])
        scheduled_ids: set[str] = set()
        for group in groups:
            if len(group) > 1:
                phase_id = f"phase-{phase_no:03d}"
                phases.append({
                    "phase_id": phase_id,
                    "execution_mode": "parallel",
                    "branch_ids": [b["branch_id"] for b in group],
                    "requires_parent_aggregation": True,
                })
                scheduled_ids.update(b["branch_id"] for b in group)
                phase_no += 1
            else:
                ready_serial.extend(group)
        for branch in ready_serial:
            if branch["branch_id"] in scheduled_ids:
                continue
            phase_id = f"phase-{phase_no:03d}"
            phases.append({
                "phase_id": phase_id,
                "execution_mode": "serial",
                "branch_ids": [branch["branch_id"]],
                "requires_parent_aggregation": branch["branch_id"] in eligible,
            })
            scheduled_ids.add(branch["branch_id"])
            phase_no += 1
        remaining -= scheduled_ids
    blocked = [{"branch_id": bid, "issues": items} for bid, items in sorted(conflicts.items()) if bid in remaining]
    return phases, blocked, conflicts


def worktree_path(root: Path, run_id: str, branch_id: str) -> str:
    return str(root / run_id / slug(branch_id))


def runtime_artifact(run_dir: Path, filename: str) -> str:
    return str(run_dir / filename)


def branch_artifact_ref(run_dir: Path, branch_id: str, artifact_type: str) -> str:
    return str(run_dir / "branches" / slug(branch_id) / f"{artifact_type}.json")


def build_parent_matrices(run_id: str, goal_id: str, branches: list[dict], deps: dict[str, set[str]], phases: list[dict]) -> dict:
    return {
        "schema_version": "1.0",
        "run_id": run_id,
        "goal_id": goal_id,
        "generated_at": now(),
        "objective_coverage_matrix": [
            {
                "branch_id": b["branch_id"],
                "acceptance_criteria": b.get("acceptance_criteria", []),
                "provides": b.get("provides", []),
                "status": "planned",
            }
            for b in branches
        ],
        "dependency_matrix": [
            {
                "branch_id": bid,
                "depends_on": sorted(values),
            }
            for bid, values in sorted(deps.items())
        ],
        "ownership_matrix": [
            {
                "branch_id": b["branch_id"],
                "owned_paths": b.get("owned_paths", []),
                "shared_paths": b.get("shared_paths", []),
                "forbidden_paths": b.get("forbidden_paths", []),
            }
            for b in branches
        ],
        "risk_matrix": [
            {
                "branch_id": b["branch_id"],
                "risk_level": b.get("risk_level", "unknown"),
                "sensitive_flags": b.get("sensitive_flags", []),
            }
            for b in branches
        ],
        "integration_matrix": [
            {
                "phase_id": p["phase_id"],
                "execution_mode": p["execution_mode"],
                "branch_ids": p["branch_ids"],
                "merge_queue_order": idx + 1,
            }
            for idx, p in enumerate(phases)
        ],
    }


def branch_status(branch_id: str, phases: list[dict], blockers: list[str], conflict_items: list[dict]) -> str:
    if blockers or conflict_items:
        if "needs_decomposition" in blockers or conflict_items:
            return "needs_decomposition"
        return "scheduled_serial"
    for phase in phases:
        if branch_id in phase["branch_ids"]:
            return "scheduled_parallel" if phase["execution_mode"] == "parallel" else "scheduled_serial"
    return "needs_decomposition"


def update_run_ledger(run_dir: Path, run_id: str, goal_id: str, branches: list[dict], phases: list[dict], worktree_entries: list[dict], blockers: dict[str, list[str]], conflicts: dict[str, list[dict]], artifacts: list[str], approval_owner: str, approval_model: str) -> dict:
    ledger_path = run_dir / "run-ledger.json"
    ts = now()
    ledger = load_json(ledger_path, {
        "schema_version": "2.0",
        "run_id": run_id,
        "goal_id": goal_id,
        "branch_id": "root",
        "created_by_mode": "agent-orchestrator",
        "model": approval_model,
        "created_at": ts,
        "current_state": "planned",
        "transitions": [],
    })
    wt_by_branch = {x["branch_id"]: x for x in worktree_entries}
    phase_by_branch = {bid: phase for phase in phases for bid in phase["branch_ids"]}
    branch_rows = []
    for branch in branches:
        bid = branch["branch_id"]
        phase = phase_by_branch.get(bid, {})
        status = branch_status(bid, phases, blockers.get(bid, []), conflicts.get(bid, []))
        branch_rows.append({
            "run_id": run_id,
            "goal_id": goal_id,
            "branch_id": bid,
            "parent_branch_id": branch.get("parent_branch_id", "root"),
            "state": status,
            "execution_mode": phase.get("execution_mode", "serial"),
            "phase_id": phase.get("phase_id", ""),
            "worktree_path": wt_by_branch.get(bid, {}).get("worktree_path", ""),
            "checkpoint_ref": wt_by_branch.get(bid, {}).get("checkpoint_refs", [""])[0],
            "rollback_available": bool(wt_by_branch.get(bid, {}).get("checkpoint_refs")),
            "parallel_blockers": blockers.get(bid, []),
            "parallel_conflicts": conflicts.get(bid, []),
            "required_output_artifacts": [
                {"type": typ, "path": branch_artifact_ref(run_dir, bid, typ), "status": "required_before_parent_aggregation"}
                for typ in BRANCH_OUTPUTS
            ],
            "quality_gate_status": "pending",
            "parent_aggregation_status": "pending",
            "merge_queue_status": "waiting_for_completion",
            "updated_at": ts,
        })
    ledger["run_id"] = run_id
    ledger["goal_id"] = goal_id
    ledger["current_state"] = ledger.get("current_state", "planned")
    ledger["updated_at"] = ts
    ledger["parallel_scheduling"] = {
        "status": "planned",
        "approval_owner": approval_owner,
        "approval_model": approval_model,
        "phases": phases,
        "direct_parallel_merge_allowed": False,
        "parent_aggregation_required": True,
    }
    ledger["branches"] = branch_rows
    ledger.setdefault("transitions", []).append({
        "at": ts,
        "from": ledger.get("current_state", "planned"),
        "to": "planned",
        "run_id": run_id,
        "goal_id": goal_id,
        "branch_id": "root",
        "created_by_mode": approval_owner,
        "owner_mode": approval_owner,
        "model": approval_model,
        "input_artifacts": [],
        "output_artifacts": artifacts,
        "gate_status": "pass" if phases else "blocked",
        "decision": "active_parallel_schedule_generated",
    })
    write_json(ledger_path, ledger)
    return ledger


def update_artifact_graph(run_dir: Path, run_id: str, goal_id: str, branches: list[dict], deps: dict[str, set[str]], phases: list[dict], artifacts: list[str], approval_owner: str, approval_model: str) -> dict:
    graph_path = run_dir / "artifact-graph.json"
    ts = now()
    graph = load_json(graph_path, {
        "schema_version": "2.0",
        "run_id": run_id,
        "goal_id": goal_id,
        "branch_id": "root",
        "created_by_mode": approval_owner,
        "model": approval_model,
        "created_at": ts,
        "input_artifacts": [],
        "output_artifacts": [],
        "gate_status": "not_applicable",
        "artifacts": [],
        "edges": [],
    })
    graph["artifacts"] = [
        x for x in graph.get("artifacts", [])
        if not (isinstance(x, dict) and x.get("branch_id") == "root" and x.get("type") in SCHEDULER_ARTIFACT_TYPES)
    ]
    existing = {x.get("artifact_id") for x in graph.get("artifacts", []) if isinstance(x, dict)}
    for path in artifacts:
        typ = Path(path).stem.replace("-", "_")
        aid = f"{typ}:{path}"
        if aid in existing:
            continue
        graph.setdefault("artifacts", []).append({
            "artifact_id": aid,
            "type": typ,
            "path": path,
            "run_id": run_id,
            "goal_id": goal_id,
            "branch_id": "root",
            "created_by_mode": approval_owner,
            "model": approval_model,
            "created_at": ts,
            "input_artifacts": [],
            "output_artifacts": artifacts,
            "gate_status": "pass",
        })
        existing.add(aid)
    graph["branch_nodes"] = [
        {
            "run_id": run_id,
            "goal_id": goal_id,
            "branch_id": b["branch_id"],
            "parent_branch_id": b.get("parent_branch_id", "root"),
            "owned_paths": b.get("owned_paths", []),
            "shared_paths": b.get("shared_paths", []),
            "provides": b.get("provides", []),
            "consumes": b.get("consumes", []),
            "worktree_path": "",
            "planned_artifacts": [
                {
                    "run_id": run_id,
                    "goal_id": goal_id,
                    "branch_id": b["branch_id"],
                    "artifact_type": typ,
                    "path": branch_artifact_ref(run_dir, b["branch_id"], typ),
                    "status": "required",
                }
                for typ in BRANCH_OUTPUTS
            ],
        }
        for b in branches
    ]
    graph["branch_edges"] = [
        {"from": dep, "to": bid, "type": "branch_dependency", "created_at": ts}
        for bid, values in sorted(deps.items())
        for dep in sorted(values)
    ]
    graph["merge_queue_order"] = [
        {
            "order": idx + 1,
            "phase_id": phase["phase_id"],
            "execution_mode": phase["execution_mode"],
            "branch_ids": phase["branch_ids"],
            "parent_aggregation_required": phase.get("requires_parent_aggregation", True),
        }
        for idx, phase in enumerate(phases)
    ]
    graph["updated_at"] = ts
    write_json(graph_path, graph)
    return graph


def markdown_report(run_id: str, goal_id: str, phases: list[dict], blockers: dict[str, list[str]], conflicts: dict[str, list[dict]], queue: list[dict], metrics: dict) -> str:
    lines = [
        "# Parallel Branch Execution Report",
        "",
        f"- run_id: `{run_id}`",
        f"- goal_id: `{goal_id}`",
        f"- generated_at: `{now()}`",
        f"- direct_parallel_merge_allowed: `false`",
        f"- parent_aggregation_required: `true`",
        "",
        "## Schedule",
        "",
    ]
    for phase in phases:
        lines.append(f"- `{phase['phase_id']}` {phase['execution_mode']}: " + ", ".join(f"`{x}`" for x in phase["branch_ids"]))
    lines.extend(["", "## Serial Merge Queue", ""])
    for item in queue:
        lines.append(f"- {item['order']}. `{item['branch_id']}` after `{item['phase_id']}` ({item['status']})")
    lines.extend(["", "## Conflicts And Blockers", ""])
    if not any(blockers.values()) and not any(conflicts.values()):
        lines.append("- none")
    else:
        for bid, items in sorted(blockers.items()):
            if items:
                lines.append(f"- `{bid}` blockers: " + ", ".join(f"`{x}`" for x in items))
        for bid, items in sorted(conflicts.items()):
            if items:
                lines.append(f"- `{bid}` conflicts: " + ", ".join(f"`{x.get('type')}`" for x in items))
    lines.extend(["", "## Metrics", ""])
    for key in sorted(metrics):
        lines.append(f"- {key}: `{metrics[key]}`")
    lines.extend([
        "",
        "## Required Before Parent Aggregation",
        "",
        "- completion evidence",
        "- obligation ledger",
        "- diagnostics report",
        "- parent aggregation matrices",
        "- quality gate pass",
        "- merge queue entry",
    ])
    return "\n".join(lines) + "\n"


def append_metrics(path: Path, metrics: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(metrics, sort_keys=True) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate active parallel branch schedule and runtime artifacts.")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--goal-id", required=True)
    parser.add_argument("--branch-tree", required=True, help="JSON file containing branches.")
    parser.add_argument("--run-dir")
    parser.add_argument("--worktree-root", default=".zoo-agent/worktrees")
    parser.add_argument("--base-branch", default="HEAD")
    parser.add_argument("--approval-owner", default="agent-planner", choices=sorted(GPT_APPROVERS))
    parser.add_argument("--approval-model", default="GPT-5.5")
    parser.add_argument("--metrics-output", default=".zoo-agent/metrics/parallel-branch-metrics.jsonl")
    parser.add_argument("--no-append-metrics", action="store_true")
    args = parser.parse_args()

    run_id = args.run_id
    goal_id = args.goal_id
    run_dir = Path(args.run_dir) if args.run_dir else Path(".zoo-agent") / "runs" / run_id
    worktree_root = Path(args.worktree_root)
    branches = load_branches(Path(args.branch_tree))
    if not branches:
        print(json.dumps({"status": "fail", "error": "no_branches_found", "branch_tree": args.branch_tree}, indent=2))
        return 2

    deps = inferred_dependencies(branches)
    blockers = {b["branch_id"]: branch_blockers(b, args.approval_owner, deps.get(b["branch_id"], set())) for b in branches}
    status_by_branch = {b["branch_id"]: str(b.get("status", "")).lower() for b in branches}
    child_counts: dict[str, int] = {}
    for branch in branches:
        parent = str(branch.get("parent_branch_id", "") or "")
        if parent:
            child_counts[parent] = child_counts.get(parent, 0) + 1
    for branch in branches:
        bid = branch["branch_id"]
        if child_counts.get(bid):
            blockers.setdefault(bid, []).append("parent_aggregation_node")
            branch["aggregation_only"] = True
    blocked_statuses = {"abandoned", "redo_needed", "paused", "blocked", "aborted"}
    for branch in branches:
        bid = branch["branch_id"]
        unsafe_deps = sorted(dep for dep in deps.get(bid, set()) if status_by_branch.get(dep) in blocked_statuses)
        if unsafe_deps:
            blockers.setdefault(bid, []).append("dependency_on_unschedulable_branch")
            branch["blocked_dependencies"] = unsafe_deps
    eligible = {bid for bid, items in blockers.items() if not items}
    schedulable = {
        bid for bid, items in blockers.items()
        if not (set(items) & HARD_UNSCHEDULABLE_BLOCKERS)
    }
    phases, blocked, conflicts = schedule_layers(branches, eligible, schedulable, deps)
    for item in blocked:
        blockers.setdefault(item["branch_id"], []).append("needs_decomposition")

    head = git_head()
    worktree_entries = []
    phase_by_branch = {bid: phase for phase in phases for bid in phase["branch_ids"]}
    for branch in branches:
        bid = branch["branch_id"]
        checkpoint_ref = branch.get("checkpoint_ref") or f"{head}:{slug(bid)}"
        worktree_entries.append({
            "branch_id": bid,
            "git_branch": branch.get("git_branch") or f"zoo/{run_id}/{slug(bid)}",
            "worktree_path": branch.get("worktree_path") or worktree_path(worktree_root, run_id, bid),
            "base_branch": branch.get("base_branch") or args.base_branch,
            "status": "planned" if bid in schedulable else "not_scheduled",
            "owned_paths": branch.get("owned_paths", []),
            "shared_paths": branch.get("shared_paths", []),
            "checkpoint_refs": [checkpoint_ref],
            "merge_queue_item": f"mq-{slug(bid)}",
            "phase_id": phase_by_branch.get(bid, {}).get("phase_id", ""),
            "requires_checkpoint_before_execution": True,
            "updated_at": now(),
        })

    parallel_groups = []
    for phase in phases:
        if phase["execution_mode"] == "parallel":
            parallel_groups.append({
                "group_id": phase["phase_id"],
                "decision_owner": args.approval_owner,
                "decision_model": args.approval_model,
                "approval_status": "approved",
                "branches": phase["branch_ids"],
                "requires_worktree": True,
                "requires_checkpoint_before_execution": True,
                "risk_level": "low_or_medium",
                "status": "scheduled",
            })

    schedule_branches = []
    wt_by_branch = {x["branch_id"]: x for x in worktree_entries}
    for branch in branches:
        bid = branch["branch_id"]
        schedule_branches.append({
            "branch_id": bid,
            "parent_branch_id": branch.get("parent_branch_id", "root"),
            "owned_paths": branch.get("owned_paths", []),
            "shared_paths": branch.get("shared_paths", []),
            "forbidden_paths": branch.get("forbidden_paths", []),
            "provides": branch.get("provides", []),
            "consumes": branch.get("consumes", []),
            "dependencies": sorted(deps.get(bid, set())),
            "acceptance_criteria": branch.get("acceptance_criteria", []),
            "verification_plan": branch.get("verification_plan", []),
            "risk_level": branch.get("risk_level", "unknown"),
            "sensitive_flags": branch.get("sensitive_flags", []),
            "contracts_stable": branch.get("contracts_stable", True),
            "contract_status": branch.get("contract_status", "stable"),
            "worktree": wt_by_branch[bid]["worktree_path"],
            "quality_gate_status": "pending",
            "review_status": "pending",
            "parent_aggregation_status": "pending",
            "parallel_blockers": blockers.get(bid, []),
            "parallel_conflicts": conflicts.get(bid, []),
            "phase_id": phase_by_branch.get(bid, {}).get("phase_id", ""),
            "execution_mode": phase_by_branch.get(bid, {}).get("execution_mode", "not_scheduled"),
        })

    schedule = {
        "schema_version": "1.0",
        "run_id": run_id,
        "goal_id": goal_id,
        "generated_at": now(),
        "parallel_allowed_by": args.approval_owner,
        "parallel_approval_model": args.approval_model,
        "direct_parallel_merge_allowed": False,
        "requires_merge_queue": True,
        "requires_parent_aggregation": True,
        "phases": phases,
        "parallel_groups": parallel_groups,
        "branches": schedule_branches,
    }

    locks = {
        "schema_version": "1.0",
        "run_id": run_id,
        "goal_id": goal_id,
        "generated_at": now(),
        "lock_policy": "exclusive_owned_paths_shared_paths_require_parent_approval",
        "forbidden_paths": sorted({p for b in branches for p in b.get("forbidden_paths", [])}),
        "locks": [
            {
                "branch_id": b["branch_id"],
                "owned_paths": b.get("owned_paths", []),
                "shared_paths": b.get("shared_paths", []),
                "forbidden_paths": b.get("forbidden_paths", []),
                "lock_status": "planned",
                "path_lock_status": "pass" if not blockers.get(b["branch_id"]) and not conflicts.get(b["branch_id"]) else "pending_parent_review",
            }
            for b in branches
        ],
    }

    queue = []
    order = 1
    for phase in phases:
        for bid in phase["branch_ids"]:
            queue.append({
                "queue_item_id": f"mq-{slug(bid)}",
                "order": order,
                "branch_id": bid,
                "phase_id": phase["phase_id"],
                "execution_mode": phase["execution_mode"],
                "status": "waiting_for_completion",
                "required_before_enqueue": [
                    "completion_evidence",
                    "obligation_ledger_closed_or_deferred",
                    "diagnostics_report",
                    "quality_gate_pass",
                    "review_pass",
                    "path_lock_pass",
                    "parent_aggregation_ready",
                ],
                "direct_merge_allowed": False,
                "integrator": "agent-integrator",
            })
            order += 1
    rejected = [
        {
            "branch_id": branch["branch_id"],
            "status": str(branch.get("status", "unknown")),
            "parallel_blockers": blockers.get(branch["branch_id"], []),
            "direct_merge_allowed": False,
            "reason": "not_scheduled_by_task_board_or_replanning_gate",
        }
        for branch in branches
        if branch["branch_id"] not in phase_by_branch
    ]
    merge_queue = {
        "schema_version": "1.0",
        "run_id": run_id,
        "goal_id": goal_id,
        "updated_at": now(),
        "policy": "serial_merge_after_parent_aggregation",
        "direct_parallel_merge_allowed": False,
        "queue": queue,
        "rejected": rejected,
    }

    parent_matrices = build_parent_matrices(run_id, goal_id, branches, deps, phases)
    metrics = {
        "run_id": run_id,
        "goal_id": goal_id,
        "created_at": now(),
        "branch_count": len(branches),
        "parallel_eligible_count": len(eligible),
        "parallel_scheduled_count": sum(1 for phase in phases if phase["execution_mode"] == "parallel" for _ in phase["branch_ids"]),
        "parallel_group_count": len(parallel_groups),
        "serial_scheduled_count": sum(1 for phase in phases if phase["execution_mode"] == "serial" for _ in phase["branch_ids"]),
        "not_scheduled_count": len(branches) - sum(len(phase["branch_ids"]) for phase in phases),
        "needs_decomposition_count": sum(1 for items in blockers.values() if "needs_decomposition" in items),
        "conflict_count": sum(len(items) for items in conflicts.values()),
        "parallel_utilization_rate": round((sum(1 for phase in phases if phase["execution_mode"] == "parallel" for _ in phase["branch_ids"]) / len(branches)), 4),
        "parent_aggregation_required": True,
        "parent_aggregation_success_rate": "pending",
        "merge_queue_serialized": True,
    }

    run_dir.mkdir(parents=True, exist_ok=True)
    write_json(run_dir / "branch-schedule.json", schedule)
    write_json(run_dir / "worktree-map.json", {"schema_version": "1.0", "run_id": run_id, "goal_id": goal_id, "branches": worktree_entries, "updated_at": now()})
    write_json(run_dir / "path-locks.json", locks)
    write_json(run_dir / "merge-queue.json", merge_queue)
    write_json(run_dir / "parent-aggregation-matrices.json", parent_matrices)
    write_json(run_dir / "parallel-metrics.json", metrics)

    artifacts = [
        runtime_artifact(run_dir, "branch-schedule.json"),
        runtime_artifact(run_dir, "worktree-map.json"),
        runtime_artifact(run_dir, "path-locks.json"),
        runtime_artifact(run_dir, "merge-queue.json"),
        runtime_artifact(run_dir, "parent-aggregation-matrices.json"),
        runtime_artifact(run_dir, "parallel-metrics.json"),
        runtime_artifact(run_dir, "parallel-execution-report.md"),
    ]
    update_run_ledger(run_dir, run_id, goal_id, branches, phases, worktree_entries, blockers, conflicts, artifacts, args.approval_owner, args.approval_model)
    update_artifact_graph(run_dir, run_id, goal_id, branches, deps, phases, artifacts[:-1], args.approval_owner, args.approval_model)
    report = markdown_report(run_id, goal_id, phases, blockers, conflicts, queue, metrics)
    (run_dir / "parallel-execution-report.md").write_text(report, encoding="utf-8")
    update_artifact_graph(run_dir, run_id, goal_id, branches, deps, phases, artifacts, args.approval_owner, args.approval_model)
    if not args.no_append_metrics:
        append_metrics(Path(args.metrics_output), metrics)

    status = "pass" if phases else "fail"
    print(json.dumps({
        "status": status,
        "run_dir": str(run_dir),
        "parallel_groups": parallel_groups,
        "phases": phases,
        "metrics": metrics,
        "artifacts": artifacts,
    }, indent=2))
    return 0 if status == "pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())
