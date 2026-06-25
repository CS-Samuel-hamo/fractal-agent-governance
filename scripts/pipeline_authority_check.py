#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from runtime_common import project_root, utc_now, write_json

LEGACY_COMMANDS = ['plan-big', 'decompose', 'aggregate', 'goal-loop', 'global-loop', 'integration-check']


def read(path: Path) -> str:
    return path.read_text(encoding='utf-8', errors='replace')


def command_output(command: list[str]) -> tuple[int, str]:
    proc = subprocess.run(
        command,
        cwd=ROOT,
        text=True,
        encoding='utf-8',
        errors='replace',
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    return proc.returncode, proc.stdout


def build_report(workspace: Path | None = None) -> dict[str, Any]:
    agent_py = read(ROOT / 'scripts' / 'agent.py')
    route_task_py = read(ROOT / 'scripts' / 'route_task.py')
    conflicts: list[dict[str, Any]] = []
    blocking_paths: list[str] = []

    version_pipeline = (
        'three-stage-pipeline-runtime' in agent_py
        or 'runtime-engine-productization' in agent_py
        or 'semantic-decoupling-runtime-engine' in agent_py
        or 'cli-product-alpha' in agent_py
        or 'product-surface-hardening-alpha' in agent_py
        or 'external-user-release-simulation-alpha' in agent_py
    )
    pipeline_command = "'pipeline'" in agent_py and 'pipeline_parser' in agent_py
    run_defaults_pipeline = (
        'def run(args)' in agent_py and 'return pipeline(' in agent_py and 'legacy_runtime' in agent_py
    )
    route_defaults_pipeline = (
        'def delegate_to_pipeline' in route_task_py and 'if not args.legacy_runtime:' in route_task_py
    )
    legacy_flag_present = '--legacy-runtime' in agent_py and '--legacy-runtime' in route_task_py

    if not version_pipeline:
        conflicts.append(
            {'type': 'version', 'message': 'agent version does not advertise pipeline/runtime engine authority'}
        )
    if not pipeline_command:
        conflicts.append({'type': 'entrypoint', 'message': 'agent pipeline command is missing'})
        blocking_paths.append('agent pipeline')
    if not run_defaults_pipeline:
        conflicts.append({'type': 'routing', 'message': 'agent run does not default to pipeline'})
        blocking_paths.append('agent run')
    if not route_defaults_pipeline:
        conflicts.append({'type': 'routing', 'message': 'route_task.py does not default to pipeline'})
        blocking_paths.append('scripts/route_task.py')
    if not legacy_flag_present:
        conflicts.append({'type': 'compatibility', 'message': 'legacy runtime flag is missing'})

    help_code, _help_text = command_output([sys.executable, str(ROOT / 'scripts' / 'agent.py'), '--help'])
    if help_code != 0:
        conflicts.append({'type': 'cli', 'message': 'agent --help failed'})
    legacy_help_conflicts = []
    for command in LEGACY_COMMANDS:
        if f"sub.add_parser('{command}'" not in agent_py:
            legacy_help_conflicts.append(command)
            continue
        parser_index = agent_py.find(f"sub.add_parser('{command}'")
        window = agent_py[parser_index : parser_index + 260].lower()
        if 'compatibility/debug' not in window and 'argparse.suppress' not in window:
            legacy_help_conflicts.append(command)
    if legacy_help_conflicts:
        conflicts.append(
            {
                'type': 'legacy_mode_label',
                'message': 'legacy commands are not clearly marked compatibility/debug',
                'commands': legacy_help_conflicts,
            }
        )

    authority = 'pipeline'
    if conflicts:
        authority = 'mixed' if pipeline_command else 'legacy'

    return {
        'schema_version': '1.0',
        'generated_by': 'pipeline_authority_check.py',
        'generated_at': utc_now(),
        'workspace': str(workspace) if workspace else '',
        'authority': authority,
        'production_execution_entry': 'agent pipeline',
        'agent_run_default': 'pipeline' if run_defaults_pipeline else 'legacy_or_mixed',
        'route_task_default': 'pipeline' if route_defaults_pipeline else 'legacy_or_mixed',
        'legacy_runtime_mode': 'compatibility_debug_only' if legacy_flag_present else 'unknown',
        'legacy_commands': LEGACY_COMMANDS,
        'conflicts': conflicts,
        'blocking_paths': sorted(set(blocking_paths)),
        'checks': {
            'version_pipeline': version_pipeline,
            'pipeline_command': pipeline_command,
            'run_defaults_pipeline': run_defaults_pipeline,
            'route_defaults_pipeline': route_defaults_pipeline,
            'legacy_flag_present': legacy_flag_present,
            'agent_help_ok': help_code == 0,
            'legacy_commands_labeled_debug': not legacy_help_conflicts,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description='Validate that the three-stage pipeline owns production execution authority.'
    )
    parser.add_argument('--workspace', default='')
    parser.add_argument('--json-output', default='')
    args = parser.parse_args()
    workspace = project_root(args.workspace) if args.workspace else None
    report = build_report(workspace)
    if args.json_output:
        write_json(Path(args.json_output).resolve(), report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report['authority'] == 'pipeline' else 10


if __name__ == '__main__':
    raise SystemExit(main())
