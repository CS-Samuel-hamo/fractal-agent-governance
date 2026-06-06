#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
from typing import Any


CODE_TYPES = {"code", "test", "config"}
DOC_TYPES = {"docs", "research", "planning", "review"}


def read_json(path: Path, fallback: Any) -> Any:
    if not path.exists():
        return fallback
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return fallback


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def latest_run(workspace: Path) -> str:
    runs = workspace / ".zoo-agent" / "runs"
    if not runs.exists():
        return "run-001"
    dirs = [p for p in runs.iterdir() if p.is_dir()]
    if not dirs:
        return "run-001"
    return max(dirs, key=lambda p: p.stat().st_mtime).name


def infer_type(text: str, explicit: str) -> str:
    if explicit:
        return explicit
    lower = text.lower()
    if any(token in lower for token in ["doc", "readme", "planning", "plan only", "docs-only"]):
        return "docs"
    if any(token in lower for token in ["test", "pytest", "coverage"]):
        return "test"
    if any(token in lower for token in ["config", "setting", "schema"]):
        return "config"
    return "code"


def build_item(args: argparse.Namespace, run_id: str) -> dict[str, Any]:
    item_type = infer_type(args.objective, args.type)
    ready = item_type in CODE_TYPES and not args.blocking_reason
    status = "ready_for_worker" if ready else "planned"
    if item_type in DOC_TYPES:
        status = "planned"
    if args.blocking_reason:
        status = "blocked"
    preferred = "codex" if item_type in CODE_TYPES and ready else "zoo-only"
    expected = list(args.expected_artifact)
    if item_type in CODE_TYPES and not expected:
        expected = ["code/test/config diff or precise blocker"]
    item_id = args.item_id or f"impl-{args.task_id or '001'}"
    task_id = args.task_id or item_id
    return {
        "item_id": item_id,
        "branch_id": args.branch_id or task_id,
        "task_id": task_id,
        "title": args.title or args.objective,
        "type": item_type,
        "status": status,
        "root_goal_link": args.root_goal_link or args.goal_id or "",
        "acceptance_link": list(args.acceptance_link),
        "obligation_link": list(args.obligation_link),
        "expected_artifacts": expected,
        "preferred_executor": preferred,
        "allowed_files": list(args.allowed_file),
        "denied_files": list(args.denied_file) or [".env", ".env.*", "secrets/**", "credentials/**", "**/*.pem", "**/*.key"],
        "test_commands": list(args.test_command),
        "blocking_reason": args.blocking_reason,
        "follow_up_reason": "",
    }


def summarize(items: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "code_items": sum(1 for item in items if item.get("type") == "code"),
        "test_items": sum(1 for item in items if item.get("type") == "test"),
        "docs_items": sum(1 for item in items if item.get("type") in DOC_TYPES),
        "blocked_items": sum(1 for item in items if item.get("status") == "blocked"),
        "ready_for_worker": sum(1 for item in items if item.get("status") == "ready_for_worker"),
    }


def render_md(queue: dict[str, Any]) -> str:
    lines = [
        "# Implementation Queue",
        "",
        f"- run_id: `{queue.get('run_id', '')}`",
        f"- goal_id: `{queue.get('goal_id', '')}`",
        f"- generated_at: `{queue.get('generated_at', '')}`",
        "",
        "## Items",
        "",
        "| Item | Type | Status | Executor | Expected Artifact | Root Goal Link |",
        "|---|---|---|---|---|---|",
    ]
    for item in queue.get("items", []):
        expected = ", ".join(item.get("expected_artifacts", []))
        lines.append(
            f"| `{item.get('item_id', '')}` | {item.get('type', '')} | {item.get('status', '')} | "
            f"{item.get('preferred_executor', '')} | {expected} | {item.get('root_goal_link', '')} |"
        )
    lines.extend(["", "## Summary", ""])
    for key, value in queue.get("summary", {}).items():
        lines.append(f"- {key}: `{value}`")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate implementation queue from current task intent.")
    parser.add_argument("--workspace", default=".")
    parser.add_argument("--run-id", default="")
    parser.add_argument("--goal-id", default="")
    parser.add_argument("--task-id", default="")
    parser.add_argument("--item-id", default="")
    parser.add_argument("--branch-id", default="")
    parser.add_argument("--title", default="")
    parser.add_argument("--objective", required=True)
    parser.add_argument("--type", choices=["code", "test", "config", "docs", "research", "planning", "review", "blocked"], default="")
    parser.add_argument("--root-goal-link", default="")
    parser.add_argument("--acceptance-link", action="append", default=[])
    parser.add_argument("--obligation-link", action="append", default=[])
    parser.add_argument("--expected-artifact", action="append", default=[])
    parser.add_argument("--allowed-file", action="append", default=[])
    parser.add_argument("--denied-file", action="append", default=[])
    parser.add_argument("--test-command", action="append", default=[])
    parser.add_argument("--blocking-reason", default="")
    args = parser.parse_args()

    workspace = Path(args.workspace).resolve()
    run_id = args.run_id or latest_run(workspace)
    run_root = workspace / ".zoo-agent" / "runs" / run_id
    queue_path = run_root / "implementation-queue.json"
    queue = read_json(queue_path, {"run_id": run_id, "goal_id": args.goal_id, "items": []})
    queue["run_id"] = run_id
    if args.goal_id:
        queue["goal_id"] = args.goal_id
    queue["generated_at"] = dt.datetime.now(dt.timezone.utc).isoformat()

    item = build_item(args, run_id)
    items = [existing for existing in queue.get("items", []) if existing.get("item_id") != item["item_id"]]
    items.append(item)
    queue["items"] = items
    queue["summary"] = summarize(items)
    write_json(queue_path, queue)
    (run_root / "implementation-queue.md").write_text(render_md(queue), encoding="utf-8")
    print(queue_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
