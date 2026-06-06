#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
import subprocess
from pathlib import Path
from typing import Any


DOC_EXTS = {".md", ".mdx", ".rst", ".txt"}
CODE_EXTS = {".py", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".go", ".rs", ".java", ".cs", ".cpp", ".c", ".h"}
CONFIG_EXTS = {".json", ".yaml", ".yml", ".toml", ".ini", ".cfg"}


def read_json(path: Path, fallback: Any) -> Any:
    if not path.exists():
        return fallback
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return fallback


def git_changed(workspace: Path) -> list[str]:
    proc = subprocess.run(["git", "status", "--porcelain"], cwd=workspace, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if proc.returncode != 0:
        return []
    return [line[3:].strip() for line in proc.stdout.splitlines() if len(line) > 3 and line[3:].strip()]


def classify(paths: list[str]) -> dict[str, list[str]]:
    result = {"docs": [], "code": [], "config": [], "other": []}
    for path in paths:
        suffix = Path(path).suffix.lower()
        normalized = path.replace("\\", "/")
        if suffix in DOC_EXTS:
            result["docs"].append(path)
        elif suffix in CODE_EXTS or "/src/" in normalized or normalized.startswith("src/"):
            result["code"].append(path)
        elif suffix in CONFIG_EXTS:
            result["config"].append(path)
        else:
            result["other"].append(path)
    return result


def find_item(queue: dict[str, Any], task_id: str, item_id: str) -> dict[str, Any]:
    for item in queue.get("items", []):
        if item_id and item.get("item_id") == item_id:
            return item
        if task_id and item.get("task_id") == task_id:
            return item
    return {}


def main() -> int:
    parser = argparse.ArgumentParser(description="Run code delivery gate for coding branches.")
    parser.add_argument("--workspace", default=".")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--task-id", default="")
    parser.add_argument("--implementation-item-id", default="")
    parser.add_argument("--queue", default="")
    parser.add_argument("--changed-file", action="append", default=[])
    parser.add_argument("--no-code-reason", default="")
    parser.add_argument("--tests-status", default="unknown", choices=["pass", "fail", "unknown", "not_applicable"])
    parser.add_argument("--scope-status", default="unknown", choices=["pass", "fail", "unknown", "not_run"])
    args = parser.parse_args()
    workspace = Path(args.workspace).resolve()
    run_root = workspace / ".zoo-agent" / "runs" / args.run_id
    queue_path = Path(args.queue) if args.queue else run_root / "implementation-queue.json"
    queue = read_json(queue_path, {"items": []})
    item = find_item(queue, args.task_id, args.implementation_item_id)
    item_type = item.get("type", "code")
    changed = args.changed_file or git_changed(workspace)
    groups = classify(changed)
    checks = []
    def add(name: str, ok: bool, detail: str) -> None:
        checks.append({"name": name, "ok": ok, "detail": detail})

    coding = item_type in {"code", "test", "config"}
    has_impl = bool(groups["code"] or groups["config"])
    doc_only = bool(changed) and bool(groups["docs"]) and not has_impl
    task_pack = item.get("codex_task_pack") or (run_root / "codex-tasks" / (args.task_id or item.get("task_id", ""))).exists()
    result_path = run_root / "codex-results" / (args.task_id or item.get("task_id", "")) / "result.json"
    result = read_json(result_path, {})
    if result:
        scope = result.get("scope_guard", {}).get("status", args.scope_status)
    else:
        scope = args.scope_status

    add("implementation_queue_exists", queue_path.exists(), str(queue_path))
    add("implementation_item_exists", bool(item), args.implementation_item_id or args.task_id)
    if coding:
        add("has_code_test_or_config_diff", has_impl or bool(args.no_code_reason), "implementation diff or no-code reason required")
        add("not_doc_only_completion", not doc_only or bool(args.no_code_reason), "docs-only coding completion is forbidden")
        add("codex_task_pack_or_no_code_reason", bool(task_pack) or has_impl or bool(args.no_code_reason), "task pack/result/diff required")
    add("scope_guard", scope in {"pass", "unknown", "not_run"} and scope != "fail", scope)
    add("tests", args.tests_status in {"pass", "unknown", "not_applicable"}, args.tests_status)

    ok = all(check["ok"] for check in checks)
    payload = {
        "run_id": args.run_id,
        "task_id": args.task_id,
        "implementation_item_id": args.implementation_item_id or item.get("item_id", ""),
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "verdict": "pass" if ok else "fail",
        "changed_files": changed,
        "groups": groups,
        "checks": checks,
    }
    out_json = run_root / "code-delivery-gate.json"
    out_md = run_root / "code-delivery-gate.md"
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    lines = ["# Code Delivery Gate", "", f"- verdict: `{payload['verdict']}`", "", "## Checks", ""]
    for check in checks:
        lines.append(f"- {'PASS' if check['ok'] else 'FAIL'}: {check['name']} - {check['detail']}")
    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
