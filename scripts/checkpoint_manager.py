#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any

from runtime_common import load_json, project_root, utc_now, write_json


def git_value(project: Path, command: list[str]) -> str:
    proc = subprocess.run(command, cwd=project, text=True, encoding='utf-8', errors='replace', stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return proc.stdout.strip() if proc.returncode == 0 else ''


def create_checkpoint(project: Path, *, action_id: str, title: str) -> dict[str, Any]:
    path = project / '.zoo-agent' / 'autopilot' / 'checkpoints.json'
    payload = load_json(path)
    checkpoints = [item for item in payload.get('checkpoints') or [] if isinstance(item, dict)]
    checkpoint = {
        'checkpoint_id': f'checkpoint-{len(checkpoints) + 1:04d}',
        'created_at': utc_now(),
        'action_id': action_id,
        'title': title,
        'git_head': git_value(project, ['git', 'rev-parse', 'HEAD']),
        'git_branch': git_value(project, ['git', 'branch', '--show-current']),
        'status_short': git_value(project, ['git', 'status', '--short']).splitlines(),
        'undo_available': True,
    }
    checkpoints.append(checkpoint)
    write_json(path, {'schema_version': '1.0', 'generated_by': 'checkpoint_manager.py', 'checkpoints': checkpoints})
    return checkpoint


def main() -> int:
    parser = argparse.ArgumentParser(description='Create an autopilot checkpoint.')
    parser.add_argument('--workspace', default='.')
    parser.add_argument('--action-id', default='')
    parser.add_argument('--title', default='')
    args = parser.parse_args()
    project = project_root(args.workspace)
    payload = create_checkpoint(project, action_id=args.action_id, title=args.title)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
