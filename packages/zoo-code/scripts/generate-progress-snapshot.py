#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DONE = {"done", "final_reported", "integrated", "merged", "completed", "closed"}
ACTIVE = {"active", "executing", "branch_scoped", "evidence_ready", "quality_gate_ready", "review", "semantic_review_ready"}
BLOCKED = {"blocked", "needs_user_decision", "needs_decomposition", "fail", "failed", "replanning"}
PLANNED = {"planned", "scheduled", "scheduled_parallel", "scheduled_serial", "pending", "queued"}
RISK_ORDER = {"unknown": 0, "low": 1, "medium": 2, "high": 3, "critical": 4}


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return default


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def latest_run_dir() -> Path | None:
    root = Path(".zoo-agent") / "runs"
    if not root.exists():
        return None
    dirs = [p for p in root.iterdir() if p.is_dir()]
    if not dirs:
        return None
    return sorted(dirs, key=lambda p: p.stat().st_mtime)[-1]


def run_dir(run_id: str | None) -> Path:
    if run_id:
        return Path(".zoo-agent") / "runs" / run_id
    latest = latest_run_dir()
    if latest:
        return latest
    return Path(".zoo-agent") / "runs" / "run-unknown"


def norm_status(value: Any) -> str:
    text = str(value or "unknown").strip().lower()
    return text or "unknown"


def branch_title(branch: dict) -> str:
    return str(branch.get("title") or branch.get("name") or branch.get("branch_id") or "branch")


def branch_id(branch: dict) -> str:
    return str(branch.get("branch_id") or branch.get("id") or branch.get("title") or "root")


def branch_parent(branch: dict) -> str:
    return str(branch.get("parent_branch_id") or branch.get("parent_id") or "")


def flatten_branch_state(data: Any) -> list[dict]:
    if isinstance(data, list):
        return [x for x in data if isinstance(x, dict)]
    if not isinstance(data, dict):
        return []
    for key in ["branches", "tree", "nodes", "branch_tree"]:
        value = data.get(key)
        if isinstance(value, list):
            return [x for x in value if isinstance(x, dict)]
    return []


def merge_branch_sources(ledger: dict, branch_state: dict, schedule: dict) -> list[dict]:
    merged: dict[str, dict] = {}
    for source in [flatten_branch_state(branch_state), schedule.get("branches", []), ledger.get("branches", [])]:
        for item in source if isinstance(source, list) else []:
            if not isinstance(item, dict):
                continue
            bid = branch_id(item)
            base = merged.setdefault(bid, {"branch_id": bid})
            base.update({k: v for k, v in item.items() if v not in (None, "", [])})
    if not merged:
        bid = str(ledger.get("branch_id") or "root")
        merged[bid] = {"branch_id": bid, "title": "Root", "status": ledger.get("current_state", "unknown"), "parent_branch_id": ""}
    return list(merged.values())


def depth_for(branches: list[dict], bid: str, seen: set[str] | None = None) -> int:
    seen = seen or set()
    if bid in seen:
        return 0
    seen.add(bid)
    by_id = {branch_id(b): b for b in branches}
    parent = branch_parent(by_id.get(bid, {}))
    if not parent or parent not in by_id:
        return 0
    return 1 + depth_for(branches, parent, seen)


def active_branch_id(ledger: dict, branches: list[dict]) -> str:
    current = str(ledger.get("current_branch") or ledger.get("branch_id") or "")
    if current and current != "root":
        return current
    for item in branches:
        status = norm_status(item.get("status") or item.get("state"))
        if status in ACTIVE or item.get("is_active"):
            return branch_id(item)
    return current or (branch_id(branches[0]) if branches else "root")


def parent_chain(branches: list[dict], active: str) -> list[str]:
    by_id = {branch_id(b): b for b in branches}
    out: list[str] = []
    cur = active
    seen: set[str] = set()
    while cur and cur not in seen:
        seen.add(cur)
        out.append(cur)
        cur = branch_parent(by_id.get(cur, {}))
    return list(reversed(out))


def quality_status(run: Path, branch: dict, root_quality: dict) -> str:
    for key in ["quality_gate_status", "quality_gate"]:
        if branch.get(key):
            return str(branch[key])
    bid = branch_id(branch)
    branch_gate = run / "branches" / bid / "quality-gate.json"
    if branch_gate.exists():
        return str(load_json(branch_gate, {}).get("status", "unknown"))
    return str(root_quality.get("status", "unknown")) if root_quality else "unknown"


def evidence_status(run: Path, branch: dict) -> str:
    if branch.get("evidence"):
        return "present"
    bid = branch_id(branch)
    branch_dir = run / "branches" / bid
    for name in ["completion-evidence.md", "completion_evidence.md", "completion-evidence.json", "completion_evidence.json"]:
        if (branch_dir / name).exists():
            return "present"
    return "missing"


def worktree_for(branch: dict, worktree_map: dict) -> str:
    if branch.get("worktree_path") or branch.get("worktree"):
        return str(branch.get("worktree_path") or branch.get("worktree"))
    bid = branch_id(branch)
    for item in worktree_map.get("branches", []):
        if item.get("branch_id") == bid:
            return str(item.get("worktree_path", ""))
    return ""


def git_status_summary() -> dict:
    result = subprocess.run(["git", "status", "--short"], text=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=False)
    if result.returncode != 0:
        return {"available": False, "changed_count": 0}
    lines = [x for x in result.stdout.splitlines() if x.strip()]
    return {"available": True, "changed_count": len(lines)}


def delivery_summary(run: Path) -> dict:
    queue = load_json(run / "implementation-queue.json", {})
    gate = load_json(run / "code-delivery-gate.json", {})
    items = queue.get("items", []) if isinstance(queue, dict) else []
    code_items = [item for item in items if item.get("type") in {"code", "test", "config"}]
    ready = [item for item in code_items if item.get("status") == "ready_for_worker"]
    blocked = [item for item in items if item.get("status") in {"blocked", "code_delivery_gate_fail", "redo_needed"}]
    doc_only_detected = gate.get("verdict") == "fail" and any(
        check.get("name") == "not_doc_only_completion" and not check.get("ok")
        for check in gate.get("checks", [])
    )
    return {
        "coding_task": bool(code_items),
        "doc_only_completion_detected": doc_only_detected,
        "implementation_queue_ready": bool(items),
        "implementation_queue_count": len(items),
        "ready_for_worker_count": len(ready),
        "code_delivery_gate": gate.get("verdict", "not_applicable"),
        "codex_task_packs": [item.get("codex_task_pack") for item in items if item.get("codex_task_pack")],
        "blocked_implementation_items": [item.get("item_id") for item in blocked],
    }


def current_user_intent(run: Path) -> dict:
    tasks = run / "TASKS.md"
    if not tasks.exists():
        return {}
    text = tasks.read_text(encoding="utf-8", errors="replace")
    capture = False
    intent: dict[str, str] = {}
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.lower() == "## current user intent":
            capture = True
            continue
        if capture and stripped.startswith("## "):
            break
        if capture:
            match = re.match(r"^\s*-\s*([^:：]+)\s*[:：]\s*(.*?)\s*$", line)
            if match:
                intent[match.group(1).strip()] = match.group(2).strip()
    return intent


def build_tree(branches: list[dict], active_chain: list[str], run: Path, quality_gate: dict, worktree_map: dict) -> list[dict]:
    active_set = set(active_chain)
    by_parent: dict[str, list[dict]] = {}
    for item in branches:
        by_parent.setdefault(branch_parent(item), []).append(item)

    def node(item: dict) -> dict:
        bid = branch_id(item)
        status = norm_status(item.get("status") or item.get("state"))
        children = [node(child) for child in sorted(by_parent.get(bid, []), key=lambda x: branch_title(x).lower()) if branch_id(child) != bid]
        is_active_path = bid in active_set
        return {
            "branch_id": bid,
            "parent_branch_id": branch_parent(item),
            "depth": depth_for(branches, bid),
            "title": branch_title(item),
            "status": status,
            "branch_type": str(item.get("branch_type") or item.get("type") or ("root" if not branch_parent(item) else "task")),
            "collapsed_by_default": not is_active_path and status not in BLOCKED,
            "is_active_path": is_active_path,
            "purpose": str(item.get("purpose") or item.get("summary") or ""),
            "evidence": evidence_status(run, item),
            "risk": str(item.get("risk") or item.get("risk_level") or "unknown"),
            "quality_gate": quality_status(run, item, quality_gate),
            "worktree_path": worktree_for(item, worktree_map),
            "children": children,
        }

    roots = by_parent.get("", []) or [b for b in branches if not branch_parent(b)]
    if not roots and branches:
        roots = [branches[0]]
    return [node(item) for item in sorted(roots, key=lambda x: branch_title(x).lower())]


def flatten_nodes(nodes: list[dict]) -> list[dict]:
    out: list[dict] = []
    for node in nodes:
        out.append(node)
        out.extend(flatten_nodes(node.get("children", [])))
    return out


def risk_level(nodes: list[dict]) -> str:
    best = "unknown"
    for node in flatten_nodes(nodes):
        risk = str(node.get("risk", "unknown")).lower()
        if RISK_ORDER.get(risk, 0) > RISK_ORDER.get(best, 0):
            best = risk
    return best


def markdown(progress: dict) -> str:
    lines = [
        "# Agent Progress Snapshot",
        "",
        f"- run_id: `{progress['run_id']}`",
        f"- goal_id: `{progress['goal_id']}`",
        f"- current_state: `{progress['current_state']}`",
        f"- current_branch: `{progress['current_branch']}`",
        f"- done_percent: `{progress['overall']['done_percent']}`",
        f"- risk_level: `{progress['overall']['risk_level']}`",
        "",
        "## Active Path",
        "",
    ]
    for item in progress["active_path"]:
        lines.append(f"- {'  ' * item['depth']}`{item['branch_id']}` {item['title']} - {item['status']}")
    lines.extend(["", "## Done", ""])
    lines.extend([f"- {x}" for x in progress["done"]] or ["- none"])
    lines.extend(["", "## Pending", ""])
    lines.extend([f"- {x}" for x in progress["pending"]] or ["- none"])
    lines.extend(["", "## Risks", ""])
    lines.extend([f"- {x}" for x in progress["risks"]] or ["- none"])
    delivery = progress.get("delivery", {})
    lines.extend(["", "## Delivery", ""])
    lines.append(f"- coding_task: `{delivery.get('coding_task')}`")
    lines.append(f"- implementation_queue_ready: `{delivery.get('implementation_queue_ready')}`")
    lines.append(f"- ready_for_worker_count: `{delivery.get('ready_for_worker_count')}`")
    lines.append(f"- code_delivery_gate: `{delivery.get('code_delivery_gate')}`")
    if delivery.get("doc_only_completion_detected"):
        lines.append("")
        lines.append("> Current task appears to be a coding task, but only docs/planning delivery was detected. Run Agent: Start Implementation Pass.")
    lines.extend(["", "## Suggested Redirect Commands", ""])
    lines.extend([f"- `{x}`" for x in progress["suggested_redirect_commands"]] or ["- none"])
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate read-only Zoo Agent progress snapshot.")
    parser.add_argument("--run-id")
    parser.add_argument("--output-dir")
    args = parser.parse_args()
    run = Path(args.output_dir) if args.output_dir else run_dir(args.run_id)
    run_id = args.run_id or run.name
    ledger = load_json(run / "run-ledger.json", {})
    graph = load_json(run / "artifact-graph.json", {})
    branch_state = load_json(run / "branch-state.json", {})
    schedule = load_json(run / "branch-schedule.json", {})
    worktree_map = load_json(run / "worktree-map.json", {})
    merge_queue = load_json(run / "merge-queue.json", {})
    quality_gate = load_json(run / "quality-gate.json", {})
    obligation = load_json(run / "obligation-ledger.json", {})

    source = "run-ledger" if ledger else ("reconstructed" if graph or branch_state or schedule else "partial")
    goal_id = str(ledger.get("goal_id") or schedule.get("goal_id") or graph.get("goal_id") or "unknown")
    branches = merge_branch_sources(ledger, branch_state, schedule)
    active = active_branch_id(ledger, branches)
    chain = parent_chain(branches, active)
    tree = build_tree(branches, chain, run, quality_gate, worktree_map)
    flat = flatten_nodes(tree)
    completed = [n for n in flat if n["status"] in DONE]
    active_nodes = [n for n in flat if n["status"] in ACTIVE or n["branch_id"] == active]
    blocked = [n for n in flat if n["status"] in BLOCKED]
    planned = [n for n in flat if n["status"] in PLANNED]
    total = len(flat) or 1
    done_percent = int(round((len(completed) / total) * 100))
    by_id = {n["branch_id"]: n for n in flat}
    active_path = [
        {
            "branch_id": bid,
            "title": by_id.get(bid, {}).get("title", bid),
            "depth": by_id.get(bid, {}).get("depth", 0),
            "status": by_id.get(bid, {}).get("status", "unknown"),
            "summary": by_id.get(bid, {}).get("purpose", ""),
        }
        for bid in chain if bid in by_id
    ]
    current_worktree = by_id.get(active, {}).get("worktree_path", "")
    progress = {
        "run_id": run_id,
        "goal_id": goal_id,
        "goal_summary": str(ledger.get("goal_summary") or schedule.get("goal_summary") or goal_id),
        "current_state": str(ledger.get("current_state") or "unknown"),
        "current_branch": active,
        "current_worktree": current_worktree,
        "current_user_intent": current_user_intent(run),
        "overall": {
            "completed": len(completed),
            "active": len(active_nodes),
            "blocked": len(blocked),
            "planned": len(planned),
            "done_percent": done_percent,
            "risk_level": risk_level(tree),
        },
        "active_path": active_path,
        "tree": tree,
        "done": [n["title"] for n in completed],
        "pending": [n["title"] for n in planned],
        "risks": [f"{n['title']}: {n['status']} risk:{n['risk']}" for n in blocked],
        "suggested_choices": ["show_progress", "redirect_current_run", "copy_resume_command"],
        "suggested_redirect_commands": [
            f"/redirect keep {active}, replan blocked branches",
            f"/agent-run continue run {run_id} from latest progress snapshot",
        ],
        "merge_queue_status": merge_queue.get("policy") or merge_queue.get("status", "unknown"),
        "obligation_count": len(obligation.get("implicit_obligations", [])) if isinstance(obligation, dict) else 0,
        "git_status": git_status_summary(),
        "delivery": delivery_summary(run),
        "snapshot_source": source,
        "updated_at": now(),
    }
    write_json(run / "progress.json", progress)
    (run / "progress.md").write_text(markdown(progress), encoding="utf-8")
    print(json.dumps({"status": "pass", "run_id": run_id, "progress_json": str(run / "progress.json"), "progress_md": str(run / "progress.md")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
