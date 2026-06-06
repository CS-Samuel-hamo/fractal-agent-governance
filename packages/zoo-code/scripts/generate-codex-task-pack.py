#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_DIR = ROOT / "templates" / "codex"


def render(text: str, mapping: dict[str, str]) -> str:
    for key, value in mapping.items():
        text = text.replace("{{" + key + "}}", value)
    return text


def yaml_list(items: list[str], indent: str = "      ") -> str:
    values = items or [""]
    return "\n".join(indent + "- " + json.dumps(str(item)) for item in values)


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate a bounded Codex CLI Task Pack.")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--task-id", default="")
    parser.add_argument("--branch-id", default="")
    parser.add_argument("--objective", default="")
    parser.add_argument("--implementation-item-id", default="")
    parser.add_argument("--implementation-queue", default="")
    parser.add_argument("--from-implementation-item", default="")
    parser.add_argument("--allowed-file", action="append", default=[])
    parser.add_argument("--denied-file", action="append", default=[])
    parser.add_argument("--acceptance", action="append", default=[])
    parser.add_argument("--test-command", action="append", default=[])
    parser.add_argument("--worktree", default="")
    parser.add_argument("--output", default="")
    args = parser.parse_args()

    queue_item = {}
    if args.implementation_queue and args.from_implementation_item:
        queue = json.loads(Path(args.implementation_queue).read_text(encoding="utf-8"))
        for item in queue.get("items", []):
            if item.get("item_id") == args.from_implementation_item:
                queue_item = item
                break
        if not queue_item:
            raise SystemExit(f"Missing implementation item: {args.from_implementation_item}")
        args.implementation_item_id = args.implementation_item_id or queue_item.get("item_id", "")
        args.task_id = args.task_id or queue_item.get("task_id") or queue_item.get("item_id")
        args.branch_id = args.branch_id or queue_item.get("branch_id", "")
        args.objective = args.objective or queue_item.get("title", "")
        args.allowed_file.extend(queue_item.get("allowed_files", []))
        args.denied_file.extend(queue_item.get("denied_files", []))
        args.acceptance.extend(queue_item.get("acceptance_link", []))
        args.test_command.extend(queue_item.get("test_commands", []))

    if not args.task_id:
        raise SystemExit("--task-id is required unless --implementation-queue/--from-implementation-item supplies one")
    if not args.objective:
        raise SystemExit("--objective is required unless --implementation-queue/--from-implementation-item supplies one")

    out = Path(args.output) if args.output else Path(".zoo-agent") / "runs" / args.run_id / "codex-tasks" / args.task_id
    out.mkdir(parents=True, exist_ok=True)

    allowed = list(args.allowed_file)
    allowed.append(f".zoo-agent/runs/{args.run_id}/**")
    denied = args.denied_file or [".env", ".env.*", "**/*.pem", "**/*.key", "secrets/**", "credentials/**"]
    acceptance = args.acceptance or ["Scope guard passes", "Relevant tests pass or blockers are documented"]
    tests = args.test_command or []
    branch_id = args.branch_id or args.task_id

    mapping = {
        "RUN_ID": args.run_id,
        "TASK_ID": args.task_id,
        "IMPLEMENTATION_ITEM_ID": args.implementation_item_id,
        "BRANCH_ID": branch_id,
        "OBJECTIVE": args.objective,
        "ALLOWED_FILES": yaml_list(allowed),
        "DENIED_FILES": yaml_list(denied),
        "ACCEPTANCE": yaml_list(acceptance),
        "TEST_COMMANDS": yaml_list(tests),
    }

    for name in ["AGENTS.md", "TASKS.yaml", "ACCEPTANCE.md", "CODEX_TASK_PROMPT.md", "PROGRESS.md", "BLOCKERS.md"]:
        source = TEMPLATE_DIR / name
        if not source.exists():
            raise SystemExit(f"Missing template: {source}")
        (out / name).write_text(render(source.read_text(encoding="utf-8"), mapping), encoding="utf-8")

    scope_source = ROOT / "scripts" / "check-codex-scope.py"
    if not scope_source.exists():
        raise SystemExit(f"Missing scope guard: {scope_source}")
    shutil.copy2(scope_source, out / "check_codex_scope.py")

    metadata = {
        "run_id": args.run_id,
        "task_id": args.task_id,
        "implementation_item_id": args.implementation_item_id,
        "branch_id": branch_id,
        "root_goal_link": queue_item.get("root_goal_link", ""),
        "executor": "codex_cli",
        "objective": args.objective,
        "allowed_files": allowed,
        "denied_files": denied,
        "acceptance": acceptance,
        "test_commands": tests,
        "worktree_path": args.worktree,
        "scope_guard_command": f"python check_codex_scope.py {args.task_id}",
        "created_at": dt.datetime.now(dt.timezone.utc).isoformat(),
    }
    (out / "task-metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
