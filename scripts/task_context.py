#!/usr/bin/env python3
"""Shared task context for multi-worker task decomposition.

When a big task is split into sub-tasks (leaves), each leaf gets a copy of
the shared context. Workers can read findings/decisions from previous leaves
and append their own.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from runtime_common import load_json, utc_now, write_json


def default_context(task_id: str, goal: str) -> dict[str, Any]:
    return {
        'schema_version': '1.0',
        'task_id': task_id,
        'goal': goal,
        'created_at': utc_now(),
        'findings': [],
        'decisions': [],
        'blockers': [],
        'changed_files': [],
        'leaf_status': {},
    }


def context_path(project: Path, task_id: str) -> Path:
    return project / '.zoo-agent' / 'tasks' / task_id / 'context.json'


def load_context(project: Path, task_id: str) -> dict[str, Any]:
    return load_json(context_path(project, task_id))


def save_context(project: Path, context: dict[str, Any]) -> None:
    path = context_path(project, context.get('task_id', 'unknown'))
    path.parent.mkdir(parents=True, exist_ok=True)
    write_json(path, context)


def add_finding(context: dict[str, Any], worker: str, finding: str, file: str = '') -> None:
    context.setdefault('findings', []).append(
        {
            'worker': worker,
            'finding': finding,
            'file': file or '',
            'at': utc_now(),
        }
    )


def add_decision(context: dict[str, Any], decision: str, made_by: str, rationale: str = '') -> None:
    context.setdefault('decisions', []).append(
        {
            'decision': decision,
            'made_by': made_by,
            'rationale': rationale,
            'at': utc_now(),
        }
    )


def add_blocker(context: dict[str, Any], blocker: str, raised_by: str) -> None:
    context.setdefault('blockers', []).append(
        {
            'blocker': blocker,
            'raised_by': raised_by,
            'at': utc_now(),
        }
    )


def summarize_for_worker(context: dict[str, Any]) -> str:
    """Build a concise summary of the task context for injection into a worker prompt."""
    parts = ['<task-context>']
    findings = context.get('findings', [])
    if findings:
        parts.append('<previous-findings>')
        for f in findings[-5:]:
            parts.append(f'  {f.get("worker")}: {f.get("finding")} (in {f.get("file") or "?"})')
        parts.append('</previous-findings>')
    decisions = context.get('decisions', [])
    if decisions:
        parts.append('<decisions>')
        for d in decisions[-3:]:
            parts.append(f'  {d.get("decision")} (by {d.get("made_by")})')
        parts.append('</decisions>')
    blockers = context.get('blockers', [])
    if blockers:
        parts.append('<blockers>')
        for b in blockers:
            parts.append(f'  BLOCKED: {b.get("blocker")}')
        parts.append('</blockers>')
    parts.append('</task-context>')
    return '\n'.join(parts)
