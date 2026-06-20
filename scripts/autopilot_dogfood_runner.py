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

from map_quality_evaluator import evaluate_map  # noqa: E402
from project_map_builder import build_project_map, render_markdown  # noqa: E402
from project_map_schema import map_dir  # noqa: E402
from runtime_common import load_json, project_root, write_json  # noqa: E402


def run_agent(args: list[str], project: Path) -> dict[str, Any]:
    proc = subprocess.run([sys.executable, str(ROOT / 'scripts' / 'agent.py'), *args], cwd=project, text=True, encoding='utf-8', errors='replace', stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return {
        'args': args,
        'returncode': proc.returncode,
        'stdout': proc.stdout,
        'stderr_tail': proc.stderr[-2000:],
    }


def ensure_map(project: Path, goal: str) -> None:
    out_dir = map_dir(project)
    if not (out_dir / 'project_map.json').exists():
        project_map, state, evidence = build_project_map(project, main_goal=goal)
        write_json(out_dir / 'project_map.json', project_map)
        write_json(out_dir / 'project_state.json', state)
        write_json(out_dir / 'map_evidence.json', evidence)
        (out_dir / 'project_map.md').write_text(render_markdown(project_map), encoding='utf-8')


def outcome_from_result(result: str, execution_mode: str) -> str:
    if result == 'COMPLETED':
        return 'delivered'
    if result == 'DRY_RUN_COMPLETE' or execution_mode == 'preview':
        return 'no_delivery'
    if result in {'BLOCKED', 'NO_DELIVERY', 'PARTIAL'}:
        return 'blocked'
    return 'failed' if result else 'blocked'


def build_trace(project: Path, commands: list[dict[str, Any]]) -> dict[str, Any]:
    history = [item for item in (load_json(project / '.zoo-agent' / 'autopilot' / 'action_history.json').get('actions') or []) if isinstance(item, dict)]
    checkpoints = load_json(project / '.zoo-agent' / 'autopilot' / 'checkpoints.json').get('checkpoints') or []
    checkpoint_ids = {str(item.get('checkpoint_id') or '') for item in checkpoints if isinstance(item, dict)}
    project_map = load_json(project / '.zoo-agent' / 'map' / 'project_map.json')
    action_ids = {str(item.get('action_id') or '') for item in project_map.get('next_actions') or [] if isinstance(item, dict)}
    progress_exists = (project / '.zoo-agent' / 'autopilot' / 'progress.json').exists()
    attention = load_json(project / '.zoo-agent' / 'autopilot' / 'attention_required.json')
    runs: list[dict[str, Any]] = []
    for index, row in enumerate(history, start=1):
        action_id = str(row.get('action_id') or '')
        execution_mode = str(row.get('execution_mode') or 'preview')
        runs.append(
            {
                'step': index,
                'selected_action': row.get('title') or action_id,
                'selected_action_id': action_id,
                'source': 'project_map.next_actions' if action_id in action_ids else 'unknown',
                'execution_mode': execution_mode if execution_mode in {'auto', 'preview', 'needs_attention'} else ('auto' if execution_mode else 'preview'),
                'changed_files': row.get('changed_files') or [],
                'checkpoint_created': str(row.get('checkpoint_id') or '') in checkpoint_ids,
                'map_updated': bool(project_map.get('last_updated')),
                'progress_summary_created': progress_exists,
                'attention_required': bool(attention and attention.get('status') == 'needs_attention'),
                'outcome': outcome_from_result(str(row.get('result') or ''), execution_mode),
            }
        )
    return {
        'schema_version': '1.0',
        'generated_by': 'autopilot_dogfood_runner.py',
        'commands': commands,
        'runs': runs,
    }


def run_dogfood(project: Path, *, goal: str, mode: str, backend: str, max_steps: int, include_continue: bool) -> dict[str, Any]:
    ensure_map(project, goal)
    quality = evaluate_map(load_json(map_dir(project) / 'project_map.json'), load_json(map_dir(project) / 'map_evidence.json'))
    write_json(project / '.zoo-agent' / 'dogfood' / 'map_quality_report.json', quality)
    commands: list[dict[str, Any]] = []
    start_args = ['start', goal, '--workspace', str(project), '--mode', mode, '--max-steps', str(max_steps)]
    if backend:
        start_args.extend(['--backend', backend])
    commands.append(run_agent(start_args, project))
    commands.append(run_agent(['status', '--workspace', str(project), '--no-write'], project))
    if include_continue:
        continue_args = ['continue', '--workspace', str(project), '--mode', mode, '--max-steps', '1']
        if backend:
            continue_args.extend(['--backend', backend])
        commands.append(run_agent(continue_args, project))
    commands.append(run_agent(['stop', '--workspace', str(project)], project))
    commands.append(run_agent(['undo', '--workspace', str(project)], project))
    trace = build_trace(project, commands)
    write_json(project / '.zoo-agent' / 'dogfood' / 'autopilot_trace.json', trace)
    return trace


def main() -> int:
    parser = argparse.ArgumentParser(description='Run controlled Project Operator dogfood.')
    parser.add_argument('--workspace', default='.')
    parser.add_argument('--goal', default='prepare this project for GitHub release')
    parser.add_argument('--mode', choices=['preview', 'standard', 'autopilot'], default='preview')
    parser.add_argument('--backend', default='')
    parser.add_argument('--max-steps', type=int, default=1)
    parser.add_argument('--include-continue', action='store_true')
    args = parser.parse_args()
    project = project_root(args.workspace)
    trace = run_dogfood(project, goal=args.goal, mode=args.mode, backend=args.backend, max_steps=args.max_steps, include_continue=args.include_continue)
    print(json.dumps({'status': 'ok', 'autopilot_trace': str(project / '.zoo-agent' / 'dogfood' / 'autopilot_trace.json'), 'run_count': len(trace.get('runs') or [])}, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
