#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from runtime_common import project_root, utc_now, write_json
from worker_registry import write_worker_registry


def health_report(project: Path) -> dict[str, Any]:
    registry = write_worker_registry(project)
    rows = []
    for worker in registry.get('workers') or []:
        rows.append(
            {
                'name': worker.get('name', ''),
                'worker_type': worker.get('worker_type', ''),
                'available': bool(worker.get('available')),
                'health': worker.get('health', 'unavailable'),
                'reliability_score': worker.get('reliability_score', 0.0),
            }
        )
    return {
        'schema_version': '1.0',
        'generated_by': 'worker_health_monitor.py',
        'generated_at': utc_now(),
        'workers': rows,
    }


def write_health_report(project: Path) -> dict[str, Any]:
    payload = health_report(project)
    write_json(project / '.zoo-agent' / 'workers' / 'worker_health.json', payload)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description='Write worker health summary.')
    parser.add_argument('--workspace', default='.')
    args = parser.parse_args()
    project = project_root(args.workspace)
    payload = write_health_report(project)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
