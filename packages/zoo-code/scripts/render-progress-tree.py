#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8-sig"))


def latest_run_dir() -> Path | None:
    root = Path(".zoo-agent") / "runs"
    if not root.exists():
        return None
    dirs = [p for p in root.iterdir() if p.is_dir()]
    return sorted(dirs, key=lambda p: p.stat().st_mtime)[-1] if dirs else None


def progress_path(run_id: str | None, explicit: str | None) -> Path:
    if explicit:
        return Path(explicit)
    if run_id:
        return Path(".zoo-agent") / "runs" / run_id / "progress.json"
    latest = latest_run_dir()
    return (latest / "progress.json") if latest else Path(".zoo-agent") / "runs" / "run-unknown" / "progress.json"


def icon(status: str) -> str:
    mapping = {
        "active": "[active]",
        "executing": "[active]",
        "done": "[done]",
        "completed": "[done]",
        "blocked": "[blocked]",
        "needs_decomposition": "[split]",
        "needs_user_decision": "[decision]",
        "abandoned": "[abandoned]",
        "redo_needed": "[redo]",
        "retained": "[retained]",
        "planned": "[planned]",
    }
    return mapping.get(str(status).lower(), "[state]")


def render_node(node: dict, lines: list[str], depth: int = 0) -> None:
    indent = "  " * depth
    marker = "*" if node.get("is_active_path") else "-"
    lines.append(
        f"{indent}{marker} {icon(node.get('status', 'unknown'))} {node.get('title', node.get('branch_id'))} "
        f"`{node.get('branch_id')}` risk:{node.get('risk', 'unknown')} gate:{node.get('quality_gate', 'unknown')} evidence:{node.get('evidence', 'unknown')}"
    )
    for child in node.get("children", []):
        render_node(child, lines, depth + 1)


def main() -> int:
    parser = argparse.ArgumentParser(description="Render progress.json as lightweight markdown tree.")
    parser.add_argument("--run-id")
    parser.add_argument("--progress")
    parser.add_argument("--output")
    args = parser.parse_args()
    source = progress_path(args.run_id, args.progress)
    data = load_json(source, {})
    if not data:
        print(json.dumps({"status": "fail", "error": "progress_json_missing", "path": str(source)}, indent=2))
        return 2
    lines = [
        "# Agent Progress Tree",
        "",
        f"- run_id: `{data.get('run_id', 'unknown')}`",
        f"- current_state: `{data.get('current_state', 'unknown')}`",
        f"- current_branch: `{data.get('current_branch', 'unknown')}`",
        f"- done_percent: `{data.get('overall', {}).get('done_percent', 0)}`",
        "",
        "## Tree",
        "",
    ]
    for node in data.get("tree", []):
        render_node(node, lines)
    lines.extend(["", "## Done", ""])
    lines.extend([f"- {x}" for x in data.get("done", [])] or ["- none"])
    lines.extend(["", "## Pending", ""])
    lines.extend([f"- {x}" for x in data.get("pending", [])] or ["- none"])
    lines.extend(["", "## Risks / Unknowns", ""])
    lines.extend([f"- {x}" for x in data.get("risks", [])] or ["- none"])
    lines.extend(["", "## Suggested Redirect Commands", ""])
    lines.extend([f"- `{x}`" for x in data.get("suggested_redirect_commands", [])] or ["- none"])
    target = Path(args.output) if args.output else source.parent / "progress-tree.md"
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"status": "pass", "input": str(source), "output": str(target)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
