#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from public_docs_leakage_scanner import scan_texts  # noqa: E402
from public_launch_packager import FEEDBACK_TEMPLATES, public_launch_dir  # noqa: E402
from runtime_common import project_root, utc_now, write_json  # noqa: E402


def run_agent(project: Path, args: list[str]) -> dict[str, Any]:
    env = os.environ.copy()
    env.setdefault('CODEX_HOME', str(Path(tempfile.mkdtemp(prefix='post-smoke-codex-home-')).resolve()))
    proc = subprocess.run([sys.executable, str(project / 'scripts' / 'agent.py'), *args], cwd=project, env=env, text=True, encoding='utf-8', errors='replace', stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return {'command': 'agent ' + ' '.join(args), 'returncode': proc.returncode}


def tracked_runtime_artifacts(project: Path) -> list[str]:
    proc = subprocess.run(['git', 'ls-files', '.zoo-agent'], cwd=project, text=True, encoding='utf-8', errors='replace', stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return [line.strip() for line in proc.stdout.splitlines() if line.strip()]


def smoke(project: Path) -> dict[str, Any]:
    failed: list[str] = []
    commands: list[dict[str, Any]] = []
    for rel in ['VERSION', 'README.md', 'QUICKSTART.md', 'examples/demo_project']:
        if not (project / rel).exists():
            failed.append(f'missing:{rel}')
    for rel in FEEDBACK_TEMPLATES:
        if not (project / rel).exists():
            failed.append(f'missing:{rel}')
    for args in [['--help'], ['cockpit'], ['release'], ['pr']]:
        result = run_agent(project, args)
        commands.append(result)
        if result['returncode'] != 0:
            failed.append(f"command_failed:{result['command']}")
    if tracked_runtime_artifacts(project):
        failed.append('tracked_runtime_artifacts')
    texts = {}
    for rel in ['README.md', 'QUICKSTART.md', 'FEEDBACK.md', 'COMMUNITY_POSTS.md', 'LAUNCH.md']:
        if (project / rel).exists():
            texts[rel] = (project / rel).read_text(encoding='utf-8-sig', errors='replace')
    safety = scan_texts(texts)
    if not safety.get('safe'):
        failed.extend(safety.get('failed_checks') or [])
    payload = {
        'generated_at': utc_now(),
        'post_publish_smoke_passed': not failed,
        'commands_run': [item['command'] for item in commands],
        'failed_checks': sorted(set(failed)),
        'safe': not failed,
    }
    write_json(public_launch_dir(project) / 'post_publish_smoke_report.json', payload)
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--workspace', default='.')
    args = parser.parse_args(argv)
    payload = smoke(project_root(args.workspace))
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload.get('post_publish_smoke_passed') else 1


if __name__ == '__main__':
    raise SystemExit(main())
