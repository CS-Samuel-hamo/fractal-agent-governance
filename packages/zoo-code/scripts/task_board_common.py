#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ALLOWED_STATUSES = {
    "active", "planned", "blocked", "needs_review", "done", "retained",
    "abandoned", "redo_needed", "paused", "needs_user_decision",
}
ALIASES = {
    "retain": "retained",
    "redo": "redo_needed",
    "rework": "redo_needed",
    "abandon": "abandoned",
    "drop": "abandoned",
    "complete": "done",
    "completed": "done",
    "review": "needs_review",
}
DIRECT_ALLOWED_TRANSITIONS = {
    ("planned", "abandoned"),
    ("planned", "paused"),
    ("active", "paused"),
    ("active", "redo_needed"),
    ("active", "retained"),
    ("blocked", "needs_user_decision"),
    ("blocked", "redo_needed"),
    ("done", "retained"),
    ("needs_review", "redo_needed"),
    ("retained", "retained"),
    ("abandoned", "abandoned"),
    ("planned", "planned"),
    ("active", "active"),
    ("blocked", "blocked"),
    ("done", "done"),
    ("paused", "paused"),
    ("needs_user_decision", "needs_user_decision"),
}
CONFIRM_REQUIRED_TRANSITIONS = {
    ("done", "planned"),
    ("done", "active"),
    ("abandoned", "active"),
    ("retained", "active"),
}


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return default


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def latest_run_dir() -> Path | None:
    root = Path(".zoo-agent") / "runs"
    if not root.exists():
        return None
    dirs = [p for p in root.iterdir() if p.is_dir()]
    return sorted(dirs, key=lambda p: p.stat().st_mtime)[-1] if dirs else None


def resolve_run_dir(run_id: str | None = None, explicit: str | None = None) -> Path:
    if explicit:
        return Path(explicit)
    if run_id:
        return Path(".zoo-agent") / "runs" / run_id
    latest = latest_run_dir()
    return latest if latest else Path(".zoo-agent") / "runs" / "run-unknown"


def normalize_status(value: Any, default: str = "planned") -> str:
    text = str(value or default).strip().lower()
    text = ALIASES.get(text, text)
    return text if text in ALLOWED_STATUSES else text


def slug(value: str) -> str:
    out = []
    for ch in str(value).lower():
        if ch.isalnum():
            out.append(ch)
        elif ch in {"-", "_", ".", " "}:
            out.append("-")
    return re.sub(r"-+", "-", "".join(out)).strip("-") or "branch"


def clean_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(x).strip() for x in value if str(x).strip()]
    if isinstance(value, str):
        return [value.strip()] if value.strip() else []
    return [str(value)]


def branch_id(item: dict) -> str:
    return str(item.get("branch_id") or item.get("id") or item.get("title") or "root")


def parent_id(item: dict) -> str:
    return str(item.get("parent_branch_id") or item.get("parent_id") or "")


def title(item: dict) -> str:
    return str(item.get("title") or item.get("name") or branch_id(item))


def parse_key_values(lines: list[str]) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in lines:
        match = re.match(r"^\s*-\s*([^:：]+)\s*[:：]\s*(.*?)\s*$", line)
        if match:
            out[match.group(1).strip()] = match.group(2).strip()
    return out


def section_lines(text: str, section_name: str) -> list[str]:
    wanted = section_name.strip().lower()
    capture = False
    out: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("## "):
            capture = stripped[3:].strip().lower() == wanted
            continue
        if capture and stripped.startswith("#"):
            break
        if capture:
            out.append(line)
    return out


def parse_tasks_md(path: Path) -> dict:
    if not path.exists():
        return {"user_control": {}, "current_user_intent": {}, "tree_statuses": {}}
    text = path.read_text(encoding="utf-8", errors="replace")
    tree_statuses: dict[str, str] = {}
    for line in text.splitlines():
        match = re.match(r"^\s*-\s+\[([^\]]+)\]\s+(.+?)\s+->\s+tasks/([^\s]+\.md)\s*$", line)
        if match:
            tree_statuses[match.group(3)] = normalize_status(match.group(1))
    return {
        "user_control": parse_key_values(section_lines(text, "User Control")),
        "current_user_intent": parse_key_values(section_lines(text, "Current User Intent")),
        "tree_statuses": tree_statuses,
    }


def parse_meta(text: str) -> dict[str, str]:
    meta: dict[str, str] = {}
    for line in text.splitlines():
        match = re.match(r"^\s*-\s*([A-Za-z0-9_-]+)\s*:\s*(.*?)\s*$", line)
        if match:
            meta[match.group(1)] = match.group(2).strip()
    return meta


def parse_list_section(text: str, section_name: str) -> list[str]:
    values = []
    for line in section_lines(text, section_name):
        match = re.match(r"^\s*-\s+(.*?)\s*$", line)
        if match:
            value = match.group(1).strip()
            if value and value.lower() != "none":
                values.append(value)
    return values


def parse_task_docs(run: Path) -> dict[str, dict]:
    tasks_dir = run / "tasks"
    out: dict[str, dict] = {}
    if not tasks_dir.exists():
        return out
    for doc in sorted(tasks_dir.glob("*.md")):
        text = doc.read_text(encoding="utf-8", errors="replace")
        meta = parse_meta(text)
        heading = doc.stem
        for line in text.splitlines():
            if line.startswith("# "):
                heading = line[2:].strip()
                break
        bid = meta.get("branch_id") or doc.stem
        out[doc.name] = {
            "branch_id": bid,
            "parent_branch_id": meta.get("parent_branch_id", ""),
            "title": heading,
            "status": normalize_status(meta.get("status") or "planned"),
            "user_override": normalize_status(meta.get("user_override") or meta.get("status") or "planned"),
            "branch_type": meta.get("branch_type", "task"),
            "risk_level": meta.get("risk") or meta.get("risk_level") or "unknown",
            "quality_gate": meta.get("quality_gate", "unknown"),
            "evidence": meta.get("evidence", "pending"),
            "worktree_path": meta.get("worktree_path", ""),
            "owned_paths": parse_list_section(text, "Owned Paths"),
            "shared_paths": parse_list_section(text, "Shared Paths"),
            "provides": parse_list_section(text, "Provides"),
            "consumes": parse_list_section(text, "Consumes"),
            "acceptance_criteria": parse_list_section(text, "Acceptance Criteria"),
            "verification_plan": parse_list_section(text, "Verification Plan"),
            "task_doc": str(doc),
        }
    return out


def branch_state_map(branch_state: dict) -> dict[str, dict]:
    return {branch_id(item): item for item in branch_state.get("branches", []) if isinstance(item, dict)}


def task_board_map(task_board: dict) -> dict[str, dict]:
    return {branch_id(item): item for item in task_board.get("tasks", []) if isinstance(item, dict)}


def child_counts(branches: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in branches:
        parent = parent_id(item)
        if parent:
            counts[parent] = counts.get(parent, 0) + 1
    return counts


def has_evidence(item: dict) -> bool:
    for key in ["evidence", "completion_evidence", "evidence_path"]:
        value = item.get(key)
        if isinstance(value, str) and value.strip().lower() not in {"", "pending", "missing", "none", "unknown"}:
            return True
        if isinstance(value, list) and value:
            return True
    return False
