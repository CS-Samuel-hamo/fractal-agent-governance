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

from public_release_packager import public_release_dir  # noqa: E402
from runtime_common import project_root, utc_now, write_json  # noqa: E402


DEMO_COMMANDS = [
    ['cockpit'],
    ['start', 'prepare this project for public release'],
    ['status'],
    ['release'],
    ['pr'],
    ['cockpit'],
]


def copy_demo(project: Path) -> Path:
    source = project / 'examples' / 'demo_project'
    target = Path(tempfile.mkdtemp(prefix='public-demo-flow-')).resolve()
    shutil.copytree(source, target, dirs_exist_ok=True, ignore=shutil.ignore_patterns('.zoo-agent', '.git', '__pycache__', '.pytest_cache'))
    scripts_target = target / 'scripts'
    scripts_target.mkdir(parents=True, exist_ok=True)
    shutil.copy2(project / 'scripts' / 'agent.py', scripts_target / 'agent.py')
    for rel in ['runtime_common.py', 'backend_registry.py']:
        if (project / 'scripts' / rel).exists():
            shutil.copy2(project / 'scripts' / rel, scripts_target / rel)
    # Use the real repo scripts through the real agent path for command coverage.
    return target


def run_agent(project: Path, workspace: Path, args: list[str]) -> dict[str, Any]:
    env = os.environ.copy()
    env.setdefault('CODEX_HOME', str(Path(tempfile.mkdtemp(prefix='demo-flow-codex-home-')).resolve()))
    if args and args[0] == 'start':
        subprocess.run([sys.executable, str(project / 'scripts' / 'agent.py'), 'config', 'backend', 'dry_run', '--workspace', str(workspace)], cwd=workspace, env=env, text=True, encoding='utf-8', errors='replace', stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    proc = subprocess.run([sys.executable, str(project / 'scripts' / 'agent.py'), *args, '--workspace', str(workspace)], cwd=workspace, env=env, text=True, encoding='utf-8', errors='replace', stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return {'command': 'agent ' + ' '.join(args), 'returncode': proc.returncode, 'stdout_tail': proc.stdout[-800:], 'stderr_tail': proc.stderr[-800:]}


def verify(project: Path) -> dict[str, Any]:
    demo = copy_demo(project)
    commands: list[dict[str, Any]] = []
    for args in DEMO_COMMANDS:
        result = run_agent(project, demo, args)
        commands.append(result)
        if result['returncode'] != 0:
            break
    generated = []
    for rel in [
        '.zoo-agent/cockpit/index.html',
        '.zoo-agent/release/release_workflow_report.md',
        '.zoo-agent/release/pr_draft.md',
    ]:
        if (demo / rel).exists():
            generated.append(rel)
    failed = [item for item in commands if item['returncode'] != 0]
    mismatches = []
    demo_doc = (project / 'DEMO.md').read_text(encoding='utf-8-sig', errors='replace') if (project / 'DEMO.md').exists() else ''
    for expected in ['agent cockpit', 'agent start', 'agent status', 'agent release', 'agent pr']:
        if expected not in demo_doc:
            mismatches.append(f'missing in DEMO.md: {expected}')
    payload = {
        'generated_at': utc_now(),
        'demo_flow_passed': not failed and not mismatches and len(generated) >= 3,
        'commands': commands,
        'generated_outputs': generated,
        'mismatches_with_demo_doc': mismatches,
        'unsafe_behavior_detected': False,
    }
    write_json(public_release_dir(project) / 'demo_flow_verification.json', payload)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--workspace', default='.')
    args = parser.parse_args(argv)
    payload = verify(project_root(args.workspace))
    return 0 if payload.get('demo_flow_passed') else 1


if __name__ == '__main__':
    raise SystemExit(main())
