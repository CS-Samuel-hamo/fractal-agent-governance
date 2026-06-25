#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from runtime_common import load_json, project_root


def release_dir(project: Path) -> Path:
    return project / '.zoo-agent' / 'release'


def rows(values: list[Any], empty: str) -> list[str]:
    result = [f'- {value}' for value in values if str(value or '').strip()]
    return result if result else [f'- {empty}']


def build_release_notes(project: Path) -> dict[str, str]:
    project_map = load_json(project / '.zoo-agent' / 'map' / 'project_map.json')
    readiness = load_json(release_dir(project) / 'release_readiness.json')
    session_history = load_json(project / '.zoo-agent' / 'session' / 'session_history.json')
    capabilities = [
        f'{item.get("name") or item.get("capability_id")}: {item.get("status")}'
        for item in project_map.get('capabilities') or []
        if isinstance(item, dict) and item.get('status') in {'implemented', 'verified'}
    ][:10]
    partial = [
        f'{item.get("name") or item.get("capability_id")}: {item.get("status")}'
        for item in project_map.get('capabilities') or []
        if isinstance(item, dict) and item.get('status') in {'partial', 'missing'}
    ][:10]
    lines = [
        '# Release Notes Draft',
        '',
        '## Overview',
        f'- Project: {project_map.get("project_name") or project.name}',
        f'- Release stage: {readiness.get("stage") or "unknown"}',
        '- This is a local draft. It does not create a public release.',
        '',
        '## Added',
        *rows(capabilities, 'No implemented capability claims were found in the Project Map.'),
        '',
        '## Changed',
        *rows([f'Release readiness stage: {readiness.get("stage")}'], 'No release-stage change detected.'),
        '',
        '## Fixed',
        *rows([], 'No specific fixes are claimed by this workflow.'),
        '',
        '## Known limitations',
        *rows(readiness.get('must_fix') or partial, 'No known limitation recorded in release readiness.'),
        '',
        '## Not included',
        '- No remote release was created.',
        '- No remote PR was created.',
        f'- Session entries considered: {len(session_history.get("history") or session_history.get("steps") or [])}',
        '',
    ]
    path = release_dir(project) / 'release_notes_draft.md'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('\n'.join(lines), encoding='utf-8')
    return {'status': 'ok', 'release_notes': '.zoo-agent/release/release_notes_draft.md'}


def main() -> int:
    parser = argparse.ArgumentParser(description='Generate local release notes draft.')
    parser.add_argument('--workspace', default='.')
    args = parser.parse_args()
    project = project_root(args.workspace)
    payload = build_release_notes(project)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
