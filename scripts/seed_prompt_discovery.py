#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path
from typing import Any

from runtime_common import project_root, utc_now, write_json


SEED_BOOTSTRAP_ENV = 'AGENT_ENABLE_INTENT_FIRST_BOOTSTRAP'
MAX_SEED_BYTES = 128 * 1024
SEED_PRIORITY = [
    'project_beginning_prompt.md',
    'project_prompt.md',
    'goal.md',
    'brief.md',
    'spec.md',
    'requirements.md',
    'prompt.md',
    'plan.md',
]
ALLOWED_SUFFIXES = {'.md', '.txt'}
DENIED_NAME_TERMS = {'secret', 'key', 'token', 'password', 'credential', 'private', 'cert'}
DENIED_DIRS = {'.git', 'node_modules', 'dist', 'build', 'cache', '.cache'}


def intent_first_bootstrap_enabled() -> bool:
    return os.environ.get(SEED_BOOTSTRAP_ENV, 'true').strip().lower() not in {'0', 'false', 'no', 'off'}


def _rel(project: Path, path: Path) -> str:
    return path.relative_to(project).as_posix()


def _safe_text_excerpt(path: Path, *, limit: int = 360) -> str:
    try:
        text = path.read_text(encoding='utf-8', errors='replace')
    except Exception:
        return ''
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return ' '.join(lines[:12])[:limit]


def _goal_path_candidates(goal: str) -> list[str]:
    candidates: list[str] = []
    quoted = re.findall(r'["\']([^"\']+\.(?:md|txt))["\']', goal, flags=re.IGNORECASE)
    tokens = re.findall(r'[\w./\\-]+\.(?:md|txt)', goal, flags=re.IGNORECASE)
    for value in [*quoted, *tokens]:
        value = value.strip().strip('\'"')
        if value and value not in candidates:
            candidates.append(value.replace('\\', '/'))
    return candidates


def _safe_seed_path(project: Path, path: Path) -> tuple[bool, str]:
    try:
        resolved = path.resolve()
        resolved.relative_to(project.resolve())
    except Exception:
        return False, 'outside_project'
    if path.is_symlink():
        return False, 'symlink_not_allowed'
    if not path.exists() or not path.is_file():
        return False, 'not_a_file'
    rel = _rel(project, resolved)
    parts = rel.split('/')
    if len(parts) > 2 or (len(parts) == 2 and parts[0] != 'docs'):
        return False, 'outside_seed_discovery_scope'
    if any(part.startswith('.') for part in parts[:-1]):
        return False, 'hidden_directory_not_allowed'
    if any(part in DENIED_DIRS for part in parts[:-1]):
        return False, 'denied_directory'
    lowered_name = path.name.lower()
    if path.suffix.lower() not in ALLOWED_SUFFIXES:
        return False, 'unsupported_extension'
    if any(term in lowered_name for term in DENIED_NAME_TERMS):
        return False, 'secret_like_name'
    if path.stat().st_size > MAX_SEED_BYTES:
        return False, 'seed_file_too_large'
    return True, 'ok'


def _seed_candidate_paths(project: Path, goal: str) -> list[tuple[Path, bool]]:
    rows: list[tuple[Path, bool]] = []
    seen: set[str] = set()
    for explicit in _goal_path_candidates(goal):
        path = (project / explicit).resolve()
        key = str(path).lower()
        if key not in seen:
            rows.append((path, True))
            seen.add(key)
    for name in SEED_PRIORITY:
        for base in [project, project / 'docs']:
            path = (base / name).resolve()
            key = str(path).lower()
            if key not in seen:
                rows.append((path, False))
                seen.add(key)
    return rows


def is_research_seed(summary: str, goal: str = '') -> bool:
    surface = f'{summary} {goal}'.lower()
    signals = [
        'paper',
        'research',
        'citation',
        'literature',
        'evidence',
        'experiment',
        'empirical',
        'economics',
        'reinforcement learning',
        'agent architecture',
        'reviewer',
    ]
    return any(signal in surface for signal in signals)


def discover_seed_prompt(project: Path, *, goal: str = '') -> dict[str, Any]:
    if not intent_first_bootstrap_enabled():
        return {
            'schema_version': '1.0',
            'generated_by': 'seed_prompt_discovery.py',
            'generated_at': utc_now(),
            'enabled': False,
            'selected': None,
            'candidates': [],
            'rejections': [],
        }
    rejections: list[dict[str, str]] = []
    candidates: list[dict[str, Any]] = []
    for path, explicit in _seed_candidate_paths(project, goal):
        ok, reason = _safe_seed_path(project, path)
        rel = ''
        try:
            rel = _rel(project, path.resolve())
        except Exception:
            rel = path.name
        if not ok:
            if path.exists() or explicit:
                rejections.append({'path': rel.replace('\\', '/'), 'reason': reason})
            continue
        summary = _safe_text_excerpt(path)
        row = {
            'path': rel.replace('\\', '/'),
            'size_bytes': path.stat().st_size,
            'explicit': explicit,
            'summary': summary or 'Seed prompt exists.',
            'research_seed': is_research_seed(summary, goal),
        }
        candidates.append(row)
        return {
            'schema_version': '1.0',
            'generated_by': 'seed_prompt_discovery.py',
            'generated_at': utc_now(),
            'enabled': True,
            'selected': row,
            'candidates': candidates,
            'rejections': rejections,
        }
    return {
        'schema_version': '1.0',
        'generated_by': 'seed_prompt_discovery.py',
        'generated_at': utc_now(),
        'enabled': True,
        'selected': None,
        'candidates': candidates,
        'rejections': rejections,
    }


def seed_evidence_item(seed: dict[str, Any]) -> dict[str, Any]:
    return {
        'kind': 'seed_prompt',
        'evidence_type': 'seed_prompt',
        'path': str(seed.get('path') or '').replace('\\', '/'),
        'summary': str(seed.get('summary') or 'Seed prompt exists.'),
        'confidence': 0.82,
        'trust_level': 'user_intent_evidence',
        'safety_checked': True,
        'size_bytes': int(seed.get('size_bytes') or 0),
        'explicit': bool(seed.get('explicit')),
        'research_seed': bool(seed.get('research_seed')),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description='Discover safe seed prompts for intent-first bootstrap.')
    parser.add_argument('--workspace', default='.')
    parser.add_argument('--goal', default='')
    parser.add_argument('--output', default='')
    args = parser.parse_args()
    project = project_root(args.workspace)
    payload = discover_seed_prompt(project, goal=args.goal)
    if args.output:
        write_json(Path(args.output).resolve(), payload)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
