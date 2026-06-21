#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from public_launch_packager import public_launch_dir  # noqa: E402
from runtime_common import project_root, utc_now, write_json  # noqa: E402


COMMANDS = [
    ['--help'],
    ['prepare this project for public release'],
    [],
    ['cockpit'],
    ['release'],
    ['pr'],
]


def make_demo_workspace(project: Path) -> Path:
    source = project / 'examples' / 'demo_project'
    target = Path(tempfile.mkdtemp(prefix='first-user-flow-')).resolve()
    shutil.copytree(source, target, dirs_exist_ok=True, ignore=shutil.ignore_patterns('.zoo-agent', '.git', '__pycache__'))
    return target


def run_agent(project: Path, workspace: Path, args: list[str]) -> dict[str, Any]:
    env = os.environ.copy()
    env.setdefault('CODEX_HOME', str(Path(tempfile.mkdtemp(prefix='first-user-codex-home-')).resolve()))
    if args and args[0] == 'prepare this project for public release':
        subprocess.run([sys.executable, str(project / 'scripts' / 'agent.py'), 'config', 'backend', 'dry_run', '--workspace', str(workspace)], cwd=workspace, env=env, text=True, encoding='utf-8', errors='replace', stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if args == ['--help']:
        command = [sys.executable, str(project / 'scripts' / 'agent.py'), '--help']
    elif not args:
        command = [sys.executable, str(project / 'scripts' / 'agent.py')]
    else:
        command = [sys.executable, str(project / 'scripts' / 'agent.py'), *args, '--workspace', str(workspace)]
    proc = subprocess.run(command, cwd=workspace, env=env, text=True, encoding='utf-8', errors='replace', stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    label = 'agent' if not args else 'agent ' + ' '.join(args)
    return {'command': label, 'returncode': proc.returncode, 'stdout_tail': proc.stdout[-800:], 'stderr_tail': proc.stderr[-800:]}


def validate(project: Path) -> dict[str, Any]:
    docs = ['README.md', 'QUICKSTART.md', 'FEEDBACK.md', 'DEMO.md']
    docs_verified = [doc for doc in docs if (project / doc).exists()]
    missing_instructions = []
    for doc in docs:
        if doc not in docs_verified:
            missing_instructions.append(doc)
    readme = (project / 'README.md').read_text(encoding='utf-8-sig', errors='replace') if (project / 'README.md').exists() else ''
    quickstart = (project / 'QUICKSTART.md').read_text(encoding='utf-8-sig', errors='replace') if (project / 'QUICKSTART.md').exists() else ''
    for phrase in ['AI Project Operator', 'agent "<goal>"', 'agent cockpit', 'agent release', 'agent pr']:
        if phrase not in readme and phrase not in quickstart:
            missing_instructions.append(phrase)
    workspace = make_demo_workspace(project)
    commands = []
    friction = []
    for args in COMMANDS:
        result = run_agent(project, workspace, args)
        commands.append(result)
        if result['returncode'] != 0:
            friction.append(f"{result['command']} failed")
            break
    if not (workspace / '.zoo-agent' / 'cockpit' / 'index.html').exists():
        friction.append('cockpit_not_generated')
    if not (project / 'FEEDBACK.md').exists() or not (project / '.github' / 'ISSUE_TEMPLATE').exists():
        friction.append('feedback_entry_missing')
    command_score = sum(1 for item in commands if item['returncode'] == 0) / len(COMMANDS)
    doc_score = len(docs_verified) / len(docs)
    score = round(max(0.0, min(1.0, (command_score + doc_score) / 2 - (0.1 * len(missing_instructions)))), 3)
    recommendation = 'pass' if score >= 0.9 and not friction and not missing_instructions else 'fix_before_launch'
    if score < 0.6:
        recommendation = 'fail'
    payload = {
        'generated_at': utc_now(),
        'first_user_flow_score': score,
        'commands_verified': [item['command'] for item in commands if item['returncode'] == 0],
        'docs_verified': docs_verified,
        'friction_points': friction,
        'missing_instructions': sorted(set(missing_instructions)),
        'recommendation': recommendation,
    }
    write_json(public_launch_dir(project) / 'first_user_flow_report.json', payload)
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--workspace', default='.')
    args = parser.parse_args(argv)
    payload = validate(project_root(args.workspace))
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload.get('recommendation') == 'pass' else 1


if __name__ == '__main__':
    raise SystemExit(main())
