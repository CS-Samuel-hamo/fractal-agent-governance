#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path


DOC_EXTS = {".md", ".mdx", ".rst", ".txt"}
CODE_EXTS = {".py", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".go", ".rs", ".java", ".cs", ".cpp", ".c", ".h"}
CONFIG_EXTS = {".json", ".yaml", ".yml", ".toml", ".ini", ".cfg"}


def git_changed(workspace: Path) -> list[str]:
    proc = subprocess.run(["git", "status", "--porcelain"], cwd=workspace, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if proc.returncode != 0:
        return []
    return [line[3:].strip() for line in proc.stdout.splitlines() if len(line) > 3 and line[3:].strip()]


def classify(paths: list[str]) -> dict[str, list[str]]:
    result = {"docs": [], "code": [], "config": [], "other": []}
    for path in paths:
        suffix = Path(path).suffix.lower()
        if suffix in DOC_EXTS:
            result["docs"].append(path)
        elif suffix in CODE_EXTS or "/src/" in path.replace("\\", "/") or path.startswith("src/"):
            result["code"].append(path)
        elif suffix in CONFIG_EXTS:
            result["config"].append(path)
        else:
            result["other"].append(path)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Fail coding tasks that only completed docs/planning.")
    parser.add_argument("--workspace", default=".")
    parser.add_argument("--task-type", default="code", choices=["code", "test", "config", "docs", "research", "planning", "review", "blocked"])
    parser.add_argument("--changed-file", action="append", default=[])
    parser.add_argument("--no-code-reason", default="")
    parser.add_argument("--json-output", default="")
    args = parser.parse_args()
    workspace = Path(args.workspace).resolve()
    changed = args.changed_file or git_changed(workspace)
    groups = classify(changed)
    coding = args.task_type in {"code", "test", "config"}
    doc_only = bool(changed) and bool(groups["docs"]) and not groups["code"] and not groups["config"]
    ok = True
    reason = "not_applicable"
    if coding and doc_only and not args.no_code_reason:
        ok = False
        reason = "DOC_ONLY_NOT_ACCEPTED"
    elif coding and not changed and not args.no_code_reason:
        ok = False
        reason = "NO_DELIVERY_EVIDENCE"
    else:
        reason = "PASS"
    payload = {"ok": ok, "reason": reason, "task_type": args.task_type, "changed_files": changed, "groups": groups}
    if args.json_output:
        out = Path(args.json_output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
