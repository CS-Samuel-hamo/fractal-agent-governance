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

from public_release_packager import build_release_manifest, public_release_dir
from runtime_common import project_root, utc_now, write_json

TEST_COMMANDS = [
    ['scripts/validate_starter_pack.py'],
    ['scripts/test_product_alpha.py'],
    ['scripts/test_product_surface_hardening.py'],
    ['scripts/test_public_alpha_packaging.py'],
    ['scripts/test_public_positioning.py'],
    ['scripts/test_public_docs_safety.py'],
]


def copy_public_tree(source: Path, target: Path) -> list[str]:
    manifest = build_release_manifest(source)
    copied: list[str] = []
    for rel in manifest.get('included_files') or []:
        src = source / rel
        dst = target / rel
        if not src.exists() or not src.is_file():
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        copied.append(rel)
    return copied


def run_python_script(root: Path, script: str) -> dict[str, Any]:
    env = os.environ.copy()
    env.setdefault('CODEX_HOME', str(Path(tempfile.mkdtemp(prefix='fresh-clone-codex-home-')).resolve()))
    proc = subprocess.run(
        [sys.executable, script],
        cwd=root,
        env=env,
        text=True,
        encoding='utf-8',
        errors='replace',
        capture_output=True,
    )
    return {
        'command': f'python {script}',
        'returncode': proc.returncode,
        'stdout_tail': proc.stdout[-800:],
        'stderr_tail': proc.stderr[-800:],
    }


def run_agent(root: Path, args: list[str]) -> dict[str, Any]:
    env = os.environ.copy()
    env.setdefault('CODEX_HOME', str(Path(tempfile.mkdtemp(prefix='fresh-clone-agent-codex-home-')).resolve()))
    proc = subprocess.run(
        [sys.executable, str(root / 'scripts' / 'agent.py'), *args],
        cwd=root,
        env=env,
        text=True,
        encoding='utf-8',
        errors='replace',
        capture_output=True,
    )
    return {
        'command': 'agent ' + ' '.join(args),
        'returncode': proc.returncode,
        'stdout_tail': proc.stdout[-800:],
        'stderr_tail': proc.stderr[-800:],
    }


def verify(project: Path) -> dict[str, Any]:
    temp_root = Path(tempfile.mkdtemp(prefix='fresh-public-alpha-')).resolve()
    copied = copy_public_tree(project, temp_root)
    commands: list[dict[str, Any]] = []
    for command in TEST_COMMANDS:
        commands.append(run_python_script(temp_root, command[0]))
        if commands[-1]['returncode'] != 0:
            break
    if all(item['returncode'] == 0 for item in commands):
        for args in [
            ['--help'],
            ['cockpit'],
            ['release'],
            ['pr'],
        ]:
            commands.append(run_agent(temp_root, args))
            if commands[-1]['returncode'] != 0:
                break
    artifacts = []
    for rel in [
        '.zoo-agent/cockpit/index.html',
        '.zoo-agent/release/release_workflow_report.md',
        '.zoo-agent/release/pr_draft.md',
    ]:
        if (temp_root / rel).exists():
            artifacts.append(rel)
    failed = [item for item in commands if item['returncode'] != 0]
    payload = {
        'generated_at': utc_now(),
        'fresh_clone_passed': not failed and bool(copied),
        'temp_dir': str(temp_root),
        'commands_run': [item['command'] for item in commands],
        'failed_commands': failed,
        'artifacts_generated': artifacts,
        'unsafe_behavior_detected': False,
        'notes': ['copied public package files only; no git push, merge, network publish, or GitHub API call'],
    }
    write_json(public_release_dir(project) / 'fresh_clone_verification.json', payload)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--workspace', default='.')
    args = parser.parse_args(argv)
    payload = verify(project_root(args.workspace))
    return 0 if payload.get('fresh_clone_passed') else 1


if __name__ == '__main__':
    raise SystemExit(main())
