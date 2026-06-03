#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


def level_number(value: str) -> int:
    match = re.search(r"([0-4])", value)
    if not match:
        raise ValueError(f"Cannot parse governance level: {value}")
    return int(match.group(1))


def select(run_id: str, task_id: str, governance_level: str) -> dict:
    level = level_number(governance_level)
    if level == 0:
        executor = "codex_cli"
        reason = "Level 0 fast path; Codex CLI is optional and bounded by scope guard."
        task_pack = False
        fast = True
        gpt = False
        human = False
    elif level == 1:
        executor = "codex_cli"
        reason = "Level 1 routine coding; Codex CLI preferred for bounded implementation."
        task_pack = True
        fast = True
        gpt = False
        human = False
    elif level == 2:
        executor = "codex_cli"
        reason = "Level 2 multi-surface work; require GPT plan approval before bounded Codex execution."
        task_pack = True
        fast = False
        gpt = True
        human = False
    elif level == 3:
        executor = "zoo_only"
        reason = "Level 3 requires Zoo fractal decomposition, then Codex leaf workers from bounded Task Packs."
        task_pack = True
        fast = False
        gpt = True
        human = False
    else:
        executor = "human"
        reason = "Level 4 requires GPT final planner and human gate; Codex may only run explicit bounded subtasks."
        task_pack = True
        fast = False
        gpt = True
        human = True
    return {
        "run_id": run_id,
        "task_id": task_id,
        "governance_level": f"Level {level}",
        "recommended_executor": executor,
        "reason": reason,
        "requires_task_pack": task_pack,
        "requires_gpt_approval": gpt,
        "requires_human_gate": human,
        "allowed_to_fast_path": fast,
        "blocking_factors": [],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Select executor for a Zoo task.")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--task-id", required=True)
    parser.add_argument("--governance-level", required=True)
    parser.add_argument("--output")
    parser.add_argument("--format", choices=["human", "json"], default="human")
    args = parser.parse_args()
    result = select(args.run_id, args.task_id, args.governance_level)
    output = Path(args.output) if args.output else Path(".zoo-agent") / "runs" / args.run_id / "executor-selection.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    if args.format == "json":
        print(json.dumps(result, indent=2))
    else:
        print(f"{result['recommended_executor']}: {result['reason']}")
        print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
