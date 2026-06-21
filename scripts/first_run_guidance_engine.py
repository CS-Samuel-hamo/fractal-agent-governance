#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any

from runtime_common import project_root, utc_now, write_json


COMMAND_UX_DIR = Path('.zoo-agent') / 'command_ux'


def _is_git_repo(project: Path) -> bool:
    proc = subprocess.run(
        ['git', 'rev-parse', '--show-toplevel'],
        cwd=project,
        text=True,
        encoding='utf-8',
        errors='replace',
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return proc.returncode == 0


def inspect_first_run(project: Path) -> dict[str, Any]:
    zoo = project / '.zoo-agent'
    state = {
        'generated_at': utc_now(),
        'has_zoo_agent': zoo.exists(),
        'has_project_map': (zoo / 'map' / 'project_map.json').exists(),
        'has_session': (zoo / 'session' / 'session_state.json').exists(),
        'has_job': (zoo / 'jobs' / 'current_job.json').exists(),
        'is_git_repo': _is_git_repo(project),
        'has_cockpit': (zoo / 'cockpit' / 'index.html').exists(),
        'has_release_pack': (zoo / 'release' / 'release_workflow_report.md').exists(),
        'recommended_first_command': 'agent "map this project and suggest the next action"',
        'optional_commands': ['agent', 'agent cockpit', 'agent continue'],
        'safety_note': 'Runs locally by default. It does not push, merge, deploy, or create remote PRs.',
    }
    write_json(project / COMMAND_UX_DIR / 'first_run_guidance_report.json', state)
    return state


def render_guidance(project: Path) -> str:
    state = inspect_first_run(project)
    lines = [
        'AI Project Operator',
        '',
        'No active project job yet.',
        '',
        'Recommended:',
        f'{state["recommended_first_command"]}',
        '',
        'Then check progress with:',
        'agent',
        '',
        'Useful next commands:',
        'agent cockpit',
        'agent continue',
        '',
        'Local-first safety:',
        '- no automatic push',
        '- no automatic merge',
        '- no remote PR creation',
    ]
    if not state['is_git_repo']:
        lines.extend(['', 'Note:', 'This directory is not a Git repo yet. The operator can still inspect local files, but Git/release context will be limited.'])
    return '\n'.join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description='Render first-run project job guidance.')
    parser.add_argument('--workspace', default='.')
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args()
    project = project_root(args.workspace)
    if args.json:
        print(json.dumps(inspect_first_run(project), ensure_ascii=False, indent=2))
    else:
        print(render_guidance(project))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
