#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from cockpit_renderer import render_cockpit
from runtime_common import project_root


def sync_cockpit(project: Path) -> dict:
    try:
        return render_cockpit(project)
    except Exception as exc:
        return {'status': 'failed', 'reason': str(exc), 'cockpit': '.zoo-agent/cockpit/index.html'}


def main() -> int:
    parser = argparse.ArgumentParser(description='Sync session state into the local Project Cockpit.')
    parser.add_argument('--workspace', default='.')
    args = parser.parse_args()
    project = project_root(args.workspace)
    payload = sync_cockpit(project)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload.get('status') != 'failed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
