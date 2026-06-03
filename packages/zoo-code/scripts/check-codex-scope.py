#!/usr/bin/env python3
from __future__ import annotations

import argparse
import fnmatch
import json
import re
import subprocess
import sys
from pathlib import Path

try:
    import yaml  # type: ignore
except Exception:
    yaml = None


def simple_yaml_tasks(text: str) -> dict:
    tasks = []
    current = None
    current_key = None
    for raw in text.splitlines():
        line = raw.rstrip()
        if not line.strip() or line.strip().startswith("#"):
            continue
        if re.match(r"\s*-\s+id:\s*", line):
            if current:
                tasks.append(current)
            current = {"id": line.split("id:", 1)[1].strip().strip("\"'")}
            current_key = None
            continue
        if current is None:
            continue
        key_match = re.match(r"\s{4}([A-Za-z0-9_]+):\s*(.*)$", line)
        if key_match:
            current_key = key_match.group(1)
            value = key_match.group(2).strip()
            current[current_key] = [] if value == "" else value.strip("\"'")
            continue
        item_match = re.match(r"\s{6}-\s*(.*)$", line)
        if item_match and current_key:
            current.setdefault(current_key, [])
            if not isinstance(current[current_key], list):
                current[current_key] = [current[current_key]]
            current[current_key].append(item_match.group(1).strip().strip("\"'"))
    if current:
        tasks.append(current)
    return {"tasks": tasks}


def load_tasks(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    if yaml:
        return yaml.safe_load(text)
    return simple_yaml_tasks(text)


def run_git(args: list[str]) -> str:
    proc = subprocess.run(["git", *args], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return proc.stdout


def changed_files() -> list[str]:
    names = set()
    for command in (["diff", "--name-only"], ["diff", "--cached", "--name-only"]):
        for line in run_git(command).splitlines():
            if line.strip():
                names.add(line.strip().replace("\\", "/"))
    for line in run_git(["status", "--porcelain", "--untracked-files=all"]).splitlines():
        if not line.strip() or len(line) < 4:
            continue
        path = line[3:].strip()
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        if path:
            names.add(path.replace("\\", "/"))
    return sorted(names)


def matches(path: str, patterns: list[str]) -> bool:
    normalized = path.replace("\\", "/")
    for raw in patterns or []:
        pattern = str(raw).replace("\\", "/")
        if not pattern:
            continue
        if fnmatch.fnmatch(normalized, pattern) or fnmatch.fnmatch("/" + normalized, pattern):
            return True
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Check Codex worker scope against TASKS.yaml.")
    parser.add_argument("task_id_pos", nargs="?")
    parser.add_argument("--task-id", dest="task_id_opt")
    parser.add_argument("--tasks", default="TASKS.yaml")
    parser.add_argument("--json-output")
    parser.add_argument("--ignore-file", action="append", default=[], help="Changed-file glob to ignore")
    args = parser.parse_args()
    task_id = args.task_id_opt or args.task_id_pos
    if not task_id:
        print("Task id is required.", file=sys.stderr)
        return 2

    tasks_doc = load_tasks(Path(args.tasks))
    tasks = tasks_doc.get("tasks", []) if isinstance(tasks_doc, dict) else []
    task = next((item for item in tasks if str(item.get("id")) == task_id), None)
    if not task:
        print(f"Task not found: {task_id}", file=sys.stderr)
        return 2

    allowed = task.get("allowed_files") or []
    denied = task.get("denied_files") or []
    default_ignore = [
        ".zoo-agent/runs/**",
        ".zoo-agent/evals/**",
        ".zoo-agent/metrics/**",
        ".zoo-agent/tmp/**",
        ".zoo-agent/**/codex-final-message.md",
        ".zoo-agent/**/codex-results/**",
        ".zoo-agent/**/codex-tasks/**",
        "__pycache__/**",
        "**/__pycache__/**",
        ".pytest_cache/**",
        "**/.pytest_cache/**",
        ".codex-tmp/**",
        "**/.codex-tmp/**",
        "*.pyc",
        "**/*.pyc",
    ]
    changed = [name for name in changed_files() if not matches(name, default_ignore + (args.ignore_file or []))]
    violations = []
    for name in changed:
        if matches(name, denied):
            violations.append({"file": name, "reason": "denied_files"})
        elif allowed and not matches(name, allowed):
            violations.append({"file": name, "reason": "outside_allowed_files"})

    report = {
        "task_id": task_id,
        "changed_files": changed,
        "allowed_files": allowed,
        "denied_files": denied,
        "violations": violations,
        "pass": not violations,
    }
    if args.json_output:
        output = Path(args.json_output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, indent=2), encoding="utf-8")

    if violations:
        print("Scope check FAILED.")
        for item in violations:
            print(f" - {item['file']}: {item['reason']}")
        return 1
    print("Scope check passed.")
    if changed:
        print("Changed files:")
        for name in changed:
            print(f" - {name}")
    else:
        print("No changed files detected.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
