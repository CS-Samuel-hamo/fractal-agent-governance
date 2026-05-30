#!/usr/bin/env python3
from __future__ import annotations
import argparse, datetime as dt, re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def slugify(s: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9\u4e00-\u9fff]+", "-", s).strip("-").lower()
    return s[:80] or "task"

parser = argparse.ArgumentParser(description="Create task and branch-state files for the Zoo Code agent governance workflow.")
parser.add_argument("title")
parser.add_argument("--parent", default="root")
parser.add_argument("--area", default="general")
args = parser.parse_args()
now = dt.datetime.now().strftime("%Y%m%d-%H%M")
task_id = f"task-{now}-{slugify(args.title)}"
branch_id = f"branch-{args.area}-{now}"

task_path = ROOT / "docs" / "agent-governance" / "tasks" / f"{task_id}.md"
branch_path = ROOT / "docs" / "agent-governance" / "branch-state" / f"{branch_id}.md"

task_path.parent.mkdir(parents=True, exist_ok=True)
branch_path.parent.mkdir(parents=True, exist_ok=True)

task_path.write_text(f"""# Task Spec / Implementation Contract\n\n- task_id: {task_id}\n- branch_id: {branch_id}\n- parent_branch_id: {args.parent}\n- owner_mode: agent-executor\n- reviewer_mode: agent-reviewer\n- status: draft\n\n## Objective\n{args.title}\n\n## Non-goals\n\n## Affected Surfaces\n\n## Acceptance Criteria\n1.\n2.\n3.\n\n## Verification Plan\n\n## Rollback Plan\n""", encoding="utf-8")

branch_path.write_text(f"""# Branch State: {branch_id}\n\n- branch_id: {branch_id}\n- parent_branch_id: {args.parent}\n- task_id: {task_id}\n- status: draft\n\n## Objective\n{args.title}\n\n## Scope Boundary\n\n## Recursion Exit Condition\n\n## Child Branches\n\n## Evidence Log\n\n## Risks\n\n## Parent Summary\n""", encoding="utf-8")

print(task_path.relative_to(ROOT))
print(branch_path.relative_to(ROOT))
