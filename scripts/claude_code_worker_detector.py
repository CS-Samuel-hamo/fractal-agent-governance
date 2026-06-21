#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from runtime_common import project_root, utc_now, write_json  # noqa: E402
from worker_adapter_contract import worker_contract  # noqa: E402


COMMAND_CANDIDATES = ['claude', 'claude-code']


def safe_probe(command: str) -> dict[str, Any]:
    for flag in ['--version', '--help']:
        try:
            proc = subprocess.run(
                [command, flag],
                text=True,
                encoding='utf-8',
                errors='replace',
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=4,
            )
            text = (proc.stdout or proc.stderr).strip().splitlines()
            return {
                'returncode': proc.returncode,
                'probe': flag,
                'summary': text[0][:120] if text else '',
            }
        except subprocess.TimeoutExpired:
            return {'returncode': 124, 'probe': flag, 'summary': 'probe timed out'}
        except Exception as exc:
            return {'returncode': 1, 'probe': flag, 'summary': f'probe failed: {type(exc).__name__}'}
    return {'returncode': 1, 'probe': '', 'summary': 'not probed'}


def detect_claude_code_cli() -> dict[str, Any]:
    for candidate in COMMAND_CANDIDATES:
        if shutil.which(candidate):
            probe = safe_probe(candidate)
            return {
                'available': True,
                'status': 'degraded',
                'mode': 'preview_only',
                'command': candidate,
                'reason': 'Claude Code CLI detected; actual execution adapter is not enabled in this release.',
                'probe': probe,
                'supports_actual_execution': False,
            }
    return {
        'available': False,
        'status': 'unavailable',
        'mode': 'unavailable',
        'command': '',
        'reason': 'Claude Code CLI not detected.',
        'probe': {},
        'supports_actual_execution': False,
    }


def claude_contract(project: Path | None = None) -> dict[str, Any]:
    payload = worker_contract(
        'claude_worker_stub',
        supports_preview=True,
        supports_actual_execution=False,
        supports_repo_scan=False,
        requires_external_binary=True,
        requires_network=False,
        reads_secrets=False,
        modifies_files=False,
        can_run_commands=False,
        safe_default_mode='unavailable',
    )
    if project:
        write_json(project / '.zoo-agent' / 'workers' / 'claude_code_contract.json', payload)
    return payload


def claude_health(project: Path | None = None) -> dict[str, Any]:
    detection = detect_claude_code_cli()
    payload = {
        'schema_version': '1.0',
        'generated_by': 'claude_code_worker_detector.py',
        'generated_at': utc_now(),
        'worker_name': 'claude_worker_stub',
        **detection,
        'reads_secrets': False,
    }
    if project:
        write_json(project / '.zoo-agent' / 'workers' / 'claude_code_detection.json', payload)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description='Detect local Claude Code CLI availability without executing work.')
    parser.add_argument('--workspace', default='.')
    args = parser.parse_args()
    project = project_root(args.workspace)
    payload = claude_health(project)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
