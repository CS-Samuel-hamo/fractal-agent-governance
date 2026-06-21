#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from runtime_common import load_json, project_root, utc_now, write_json  # noqa: E402


STORE_FILES = {
    'project_index': 'project_index.json',
    'pattern_library': 'pattern_library.json',
    'worker_memory': 'worker_memory.json',
    'failure_taxonomy': 'failure_taxonomy.json',
    'release_templates': 'release_templates.json',
    'learning_insights': 'learning_insights.json',
}


def store_dir(project: Path) -> Path:
    return project / '.zoo-agent' / 'learning' / 'cross_project'


def store_path(project: Path, name: str) -> Path:
    return store_dir(project) / STORE_FILES[name]


def default_payload(name: str) -> dict[str, Any]:
    if name == 'project_index':
        return {'schema_version': '1.0', 'generated_by': 'cross_project_store.py', 'projects': []}
    if name == 'pattern_library':
        return {'schema_version': '1.0', 'generated_by': 'next_action_pattern_miner.py', 'patterns': []}
    if name == 'worker_memory':
        return {'schema_version': '1.0', 'generated_by': 'worker_performance_memory.py', 'worker_performance': []}
    if name == 'failure_taxonomy':
        return {'schema_version': '1.0', 'generated_by': 'failure_taxonomy_builder.py', 'failure_patterns': []}
    if name == 'release_templates':
        return {'schema_version': '1.0', 'generated_by': 'release_readiness_template_builder.py', 'templates': []}
    if name == 'learning_insights':
        return {'schema_version': '1.0', 'generated_by': 'cross_project_insight_engine.py', 'insights': []}
    return {'schema_version': '1.0', 'generated_by': 'cross_project_store.py'}


def initialize_store(project: Path) -> dict[str, Any]:
    base = store_dir(project)
    base.mkdir(parents=True, exist_ok=True)
    created = []
    for name, filename in STORE_FILES.items():
        path = base / filename
        if not path.exists():
            write_json(path, {**default_payload(name), 'generated_at': utc_now()})
            created.append(filename)
    return {'schema_version': '1.0', 'generated_by': 'cross_project_store.py', 'store': '.zoo-agent/learning/cross_project', 'created': created}


def load_store(project: Path, name: str) -> dict[str, Any]:
    initialize_store(project)
    return load_json(store_path(project, name))


def write_store(project: Path, name: str, payload: dict[str, Any]) -> dict[str, Any]:
    initialize_store(project)
    payload = {'schema_version': '1.0', **payload, 'updated_at': utc_now()}
    write_json(store_path(project, name), payload)
    return payload


def append_project_index(project: Path, row: dict[str, Any]) -> dict[str, Any]:
    payload = load_store(project, 'project_index')
    rows = [item for item in payload.get('projects') or [] if isinstance(item, dict)]
    project_id = str(row.get('project_id') or '')
    rows = [item for item in rows if item.get('project_id') != project_id]
    rows.append(row)
    return write_store(project, 'project_index', {'generated_by': 'cross_project_store.py', 'projects': rows})


def main() -> int:
    parser = argparse.ArgumentParser(description='Initialize local cross-project learning store.')
    parser.add_argument('--workspace', default='.')
    args = parser.parse_args()
    project = project_root(args.workspace)
    payload = initialize_store(project)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
