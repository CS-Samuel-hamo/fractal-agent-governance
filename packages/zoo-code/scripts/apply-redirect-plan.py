#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def latest_run_dir() -> Path | None:
    root = Path(".zoo-agent") / "runs"
    if not root.exists():
        return None
    dirs = [p for p in root.iterdir() if p.is_dir()]
    return sorted(dirs, key=lambda p: p.stat().st_mtime)[-1] if dirs else None


def run_dir(run_id: str | None) -> Path:
    if run_id:
        return Path(".zoo-agent") / "runs" / run_id
    latest = latest_run_dir()
    return latest if latest else Path(".zoo-agent") / "runs" / "run-unknown"


def lower(value: str) -> str:
    return value.lower()


def node_terms(node: dict) -> str:
    return " ".join(str(node.get(k, "")) for k in ["branch_id", "title", "branch_type", "purpose"]).lower()


def flatten(nodes: list[dict]) -> list[dict]:
    out: list[dict] = []
    for node in nodes:
        out.append(node)
        out.extend(flatten(node.get("children", [])))
    return out


def choose_status(node: dict, direction: str) -> str:
    text = node_terms(node)
    d = lower(direction)
    if any(word in d for word in ["abort", "archive", "stop all"]):
        return "abandoned"
    if any(word in d for word in ["abandon", "drop", "discard", "废弃", "放弃"]):
        if any(word in text for word in ["ui", "panel", "frontend"]):
            return "abandoned"
    if any(word in d for word in ["keep", "retain", "保留"]):
        if any(word in text for word in ["backend", "api", "domain"]):
            return "retained"
    if any(word in d for word in ["redo", "replan", "重做", "重新"]):
        if any(word in text for word in ["test", "tests", "qa"]):
            return "redo_needed"
    return str(node.get("status", "planned"))


def branch_state_from_progress(progress: dict, direction: str) -> dict:
    branches = []
    for node in flatten(progress.get("tree", [])):
        updated = dict(node)
        updated["status"] = choose_status(node, direction)
        branches.append(updated)
    return {
        "schema_version": "1.0",
        "run_id": progress.get("run_id", "unknown"),
        "goal_id": progress.get("goal_id", "unknown"),
        "updated_at": now(),
        "branches": branches,
    }


def update_worktrees(worktree_map: dict, branch_state: dict, direction: str) -> dict:
    status_by_id = {b.get("branch_id"): b.get("status") for b in branch_state.get("branches", [])}
    stop_parallel = any(word in lower(direction) for word in ["stop parallel", "no parallel", "停止并发", "不要并发"])
    for item in worktree_map.get("branches", []):
        bid = item.get("branch_id")
        state = status_by_id.get(bid)
        if state == "abandoned":
            item["status"] = "abandoned"
        elif state == "retained":
            item["status"] = "retained"
        elif stop_parallel:
            item["status"] = "paused"
        item["updated_at"] = now()
    worktree_map["updated_at"] = now()
    return worktree_map


def update_merge_queue(queue: dict, direction: str) -> dict:
    d = lower(direction)
    if any(word in d for word in ["stop parallel", "no parallel", "停止并发", "不要并发"]):
        queue["redirect_impact"] = "reorder_required"
    elif any(word in d for word in ["abort", "archive", "clear queue"]):
        queue["redirect_impact"] = "clear_required"
    else:
        queue["redirect_impact"] = "unchanged"
    queue["direct_merge_allowed"] = False
    queue["updated_at"] = now()
    return queue


def markdown(plan: dict) -> str:
    sections = [
        "# Redirect Plan",
        "",
        "## User New Direction",
        plan["user_new_direction"],
        "",
        "## Keep",
        "\n".join(f"- {x}" for x in plan["keep"]) or "- none",
        "",
        "## Drop / Abandon",
        "\n".join(f"- {x}" for x in plan["drop_abandon"]) or "- none",
        "",
        "## Redo / Replan",
        "\n".join(f"- {x}" for x in plan["redo_replan"]) or "- none",
        "",
        "## Reclassify",
        plan["reclassify"],
        "",
        "## Worktree / Merge Queue Impact",
        plan["worktree_merge_queue_impact"],
        "",
        "## New Next Steps",
        "\n".join(f"- {x}" for x in plan["new_next_steps"]),
        "",
        "## Resume Command",
        f"`{plan['resume_command']}`",
        "",
    ]
    return "\n".join(sections)


def update_tasks_current_intent(base: Path, direction: str, plan: dict) -> None:
    tasks = base / "TASKS.md"
    if not tasks.exists():
        return
    text = tasks.read_text(encoding="utf-8", errors="replace")
    block = "\n".join([
        "## Current User Intent",
        f"- 当前最重要目标: {direction}",
        "- 明确不要做: do not continue stale plans, do not merge, do not delete worktrees",
        "- 当前优先级: apply redirect before resume",
        f"- 并发策略: {plan.get('worktree_merge_queue_impact', 'unchanged')}",
        f"- 允许保留的成果: {', '.join(plan.get('keep', [])) or 'none'}",
        f"- 必须废弃的方向: {', '.join(plan.get('drop_abandon', [])) or 'none'}",
        f"- 当前 governance intensity: {plan.get('reclassify', 'unchanged')}",
        "- 当前 redirect status: redirected",
        "",
    ])
    lines = text.splitlines()
    out: list[str] = []
    i = 0
    replaced = False
    while i < len(lines):
        if lines[i].strip().lower() == "## current user intent":
            out.extend(block.rstrip().splitlines())
            i += 1
            while i < len(lines) and not lines[i].startswith("## "):
                i += 1
            replaced = True
            continue
        out.append(lines[i])
        i += 1
    if not replaced:
        insert_at = 4 if len(out) > 4 else len(out)
        out[insert_at:insert_at] = ["", *block.rstrip().splitlines()]
    tasks.write_text("\n".join(out) + "\n", encoding="utf-8")


def run_progress_script(run_id: str) -> None:
    script = Path(__file__).with_name("generate-progress-snapshot.py")
    subprocess.run([sys.executable, str(script), "--run-id", run_id], check=False)


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply a non-coding redirect plan to Zoo Agent runtime artifacts.")
    parser.add_argument("--run-id")
    parser.add_argument("--direction", required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    base = run_dir(args.run_id)
    run_id = args.run_id or base.name
    progress_path = base / "progress.json"
    if not progress_path.exists():
        run_progress_script(run_id)
    progress = load_json(progress_path, {"run_id": run_id, "tree": []})
    ledger = load_json(base / "run-ledger.json", {"run_id": run_id, "goal_id": progress.get("goal_id", "unknown"), "transitions": []})
    branch_state = branch_state_from_progress(progress, args.direction)
    worktree_map = update_worktrees(load_json(base / "worktree-map.json", {"branches": []}), branch_state, args.direction)
    merge_queue = update_merge_queue(load_json(base / "merge-queue.json", {"queue": []}), args.direction)

    keep = [b["branch_id"] for b in branch_state.get("branches", []) if b.get("status") == "retained"]
    drop = [b["branch_id"] for b in branch_state.get("branches", []) if b.get("status") == "abandoned"]
    redo = [b["branch_id"] for b in branch_state.get("branches", []) if b.get("status") == "redo_needed"]
    if any(word in lower(args.direction) for word in ["level 1", "level1"]):
        reclassify = "Governance intensity changed toward Level 1 routine coding."
    else:
        reclassify = "No explicit governance intensity change detected."
    plan = {
        "schema_version": "1.0",
        "redirect_plan_id": f"redirect-{stamp()}",
        "run_id": run_id,
        "goal_id": progress.get("goal_id", ledger.get("goal_id", "unknown")),
        "created_by_mode": "agent-orchestrator",
        "model": "GPT-5.5",
        "created_at": now(),
        "user_new_direction": args.direction,
        "keep": keep,
        "drop_abandon": drop,
        "redo_replan": redo,
        "reclassify": reclassify,
        "worktree_merge_queue_impact": f"worktrees updated without deletion; merge_queue={merge_queue.get('redirect_impact', 'unchanged')}; no merge executed.",
        "new_next_steps": [
            "Review this redirect plan.",
            "Resume through /agent-run so the orchestrator can re-plan from current artifacts.",
            "Do not continue abandoned branches.",
        ],
        "resume_command": f"/agent-run continue run {run_id} using redirect-plan.json and latest progress snapshot",
    }
    ledger["current_state"] = "replanning"
    ledger["redirect_plan"] = "redirect-plan.json"
    ledger.setdefault("transitions", []).append({
        "at": now(),
        "from": progress.get("current_state", "unknown"),
        "to": "replanning",
        "run_id": run_id,
        "goal_id": plan["goal_id"],
        "branch_id": progress.get("current_branch", "root"),
        "created_by_mode": "agent-orchestrator",
        "owner_mode": "agent-orchestrator",
        "model": "GPT-5.5",
        "input_artifacts": ["progress.json"],
        "output_artifacts": ["redirect-plan.json", "redirect-plan.md"],
        "gate_status": "not_applicable",
        "decision": "user_redirect_requested",
    })
    event = {
        "event_type": "redirect",
        "run_id": run_id,
        "goal_id": plan["goal_id"],
        "created_at": now(),
        "direction": args.direction,
        "redirect_plan": "redirect-plan.json",
    }
    if args.dry_run:
        print(json.dumps({"status": "dry-run", "plan": plan}, indent=2))
        return 0
    write_json(base / "redirect-plan.json", plan)
    (base / "redirect-plan.md").write_text(markdown(plan), encoding="utf-8")
    update_tasks_current_intent(base, args.direction, plan)
    write_json(base / "branch-state.json", branch_state)
    write_json(base / "worktree-map.json", worktree_map)
    write_json(base / "merge-queue.json", merge_queue)
    write_json(base / "run-ledger.json", ledger)
    write_json(base / "events" / f"{plan['redirect_plan_id']}.json", event)
    run_progress_script(run_id)
    print(json.dumps({"status": "pass", "run_id": run_id, "redirect_plan": str(base / "redirect-plan.json"), "resume_command": plan["resume_command"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
