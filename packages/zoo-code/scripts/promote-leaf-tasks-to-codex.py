#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


EXEC_TYPES = {"code", "test", "config"}


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate Codex Task Packs from ready implementation queue items.")
    parser.add_argument("--workspace", default=".")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--queue", default="")
    parser.add_argument("--item-id", action="append", default=[])
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    workspace = Path(args.workspace).resolve()
    queue_path = Path(args.queue) if args.queue else workspace / ".zoo-agent" / "runs" / args.run_id / "implementation-queue.json"
    queue = json.loads(queue_path.read_text(encoding="utf-8"))
    wanted = set(args.item_id)
    script = Path(__file__).resolve().parent / "generate-codex-task-pack.py"
    generated: list[str] = []
    for item in queue.get("items", []):
        if wanted and item.get("item_id") not in wanted:
            continue
        if item.get("type") not in EXEC_TYPES:
            continue
        if item.get("status") != "ready_for_worker":
            continue
        if item.get("preferred_executor", "codex") != "codex":
            continue
        cmd = [
            sys.executable,
            str(script),
            "--run-id",
            args.run_id,
            "--task-id",
            item.get("task_id") or item.get("item_id"),
            "--branch-id",
            item.get("branch_id") or item.get("task_id") or item.get("item_id"),
            "--objective",
            item.get("title") or item.get("item_id"),
            "--implementation-item-id",
            item.get("item_id"),
        ]
        for path in item.get("allowed_files", []):
            cmd.extend(["--allowed-file", path])
        for path in item.get("denied_files", []):
            cmd.extend(["--denied-file", path])
        for test in item.get("test_commands", []):
            cmd.extend(["--test-command", test])
        for acceptance in item.get("acceptance_link", []):
            cmd.extend(["--acceptance", acceptance])
        if args.dry_run:
            print("[dry-run] " + " ".join(cmd))
            continue
        proc = subprocess.run(cmd, cwd=workspace, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if proc.returncode != 0:
            print(proc.stdout + proc.stderr, file=sys.stderr)
            return proc.returncode
        generated.append(proc.stdout.strip())
        item["status"] = "worker_running"
        item["codex_task_pack"] = proc.stdout.strip()
    if not args.dry_run:
        queue_path.write_text(json.dumps(queue, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"generated": generated}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
