#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from attention_router import mark_attention  # noqa: E402
from autopilot_mode_engine import max_steps_for_mode, normalize_mode, should_pause_after_result  # noqa: E402
from backend_registry import read_backend_selection  # noqa: E402
from checkpoint_manager import create_checkpoint  # noqa: E402
from map_task_selector import select_next_action  # noqa: E402
from progress_summary_generator import build_progress_summary, render_user_summary  # noqa: E402
from project_map_builder import build_project_map  # noqa: E402
from project_map_schema import map_dir  # noqa: E402
from project_map_updater import update_project_map  # noqa: E402
from runtime_common import load_json, project_root, set_active_goal, utc_now, write_json  # noqa: E402


def run_command(command: list[str], cwd: Path) -> dict[str, Any]:
    proc = subprocess.run(command, cwd=cwd, text=True, encoding='utf-8', errors='replace', stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return {
        'command': [str(item) for item in command],
        'returncode': proc.returncode,
        'stdout_tail': proc.stdout[-4000:],
        'stderr_tail': proc.stderr[-4000:],
    }


def session_path(project: Path) -> Path:
    return project / '.zoo-agent' / 'autopilot' / 'session.json'


def append_history(project: Path, row: dict[str, Any]) -> None:
    path = project / '.zoo-agent' / 'autopilot' / 'action_history.json'
    payload = load_json(path)
    rows = [item for item in payload.get('actions') or [] if isinstance(item, dict)]
    rows.append(row)
    write_json(path, {'schema_version': '1.0', 'generated_by': 'autopilot_session_engine.py', 'actions': rows})


def load_or_build_map(project: Path, goal: str) -> None:
    if not (map_dir(project) / 'project_map.json').exists():
        project_map, state, evidence = build_project_map(project, main_goal=goal)
        write_json(map_dir(project) / 'project_map.json', project_map)
        write_json(map_dir(project) / 'project_state.json', state)
        write_json(map_dir(project) / 'map_evidence.json', evidence)
        md = map_dir(project) / 'project_map.md'
        md.parent.mkdir(parents=True, exist_ok=True)
        from project_map_builder import render_markdown

        md.write_text(render_markdown(project_map), encoding='utf-8')


def pipeline_paths(project: Path, run_id: str) -> tuple[Path, Path, Path]:
    base = project / '.zoo-agent' / 'runs' / run_id / 'pipeline'
    return base / 'plan.json', base / 'execution_result.json', base / 'final_result.json'


def run_selected_action(project: Path, *, action: dict[str, Any], mode: str, backend: str, step: int) -> dict[str, Any]:
    run_id = f'autopilot-{time.strftime("%Y%m%d%H%M%S", time.gmtime())}-{step:02d}'
    command = [
        sys.executable,
        str(ROOT / 'scripts' / 'pipeline_loop.py'),
        str(action.get('title') or action.get('selected_action_id') or 'project map action'),
        '--workspace',
        str(project),
        '--run-id',
        run_id,
        '--max-iterations',
        '1',
        '--backend',
        backend,
        '--max-retries',
        '2',
    ]
    for target in action.get('target_files') or []:
        if target and '*' not in str(target) and not str(target).endswith('/'):
            command.extend(['--allowed-file', str(target)])
    if mode == 'preview' or action.get('execution_mode') == 'preview':
        command.append('--dry-run')
    else:
        command.append('--allow-actual')
    result = run_command(command, ROOT)
    plan_path, execution_path, final_path = pipeline_paths(project, run_id)
    final_result = load_json(final_path)
    execution = load_json(execution_path)
    return {
        'run_id': run_id,
        'command_result': result,
        'plan_path': str(plan_path),
        'execution_path': str(execution_path),
        'final_path': str(final_path),
        'final_result': final_result,
        'execution': execution,
    }


def write_session(project: Path, payload: dict[str, Any]) -> None:
    write_json(session_path(project), payload)


def start_session(project: Path, *, goal: str, mode: str, max_steps: int = 0, backend: str = '') -> dict[str, Any]:
    mode = normalize_mode(mode)
    steps = max_steps_for_mode(mode, max_steps)
    backend = backend or read_backend_selection(project)
    goal_payload = set_active_goal(project, goal, source='autopilot_session_engine.py')
    load_or_build_map(project, goal)
    session = {
        'schema_version': '1.0',
        'generated_by': 'autopilot_session_engine.py',
        'session_id': f'session-{time.strftime("%Y%m%d%H%M%S", time.gmtime())}',
        'goal': goal,
        'goal_id': goal_payload.get('goal_id', ''),
        'mode': mode,
        'status': 'doing',
        'started_at': utc_now(),
        'updated_at': utc_now(),
        'step_count': 0,
        'max_steps': steps,
        'backend': backend,
    }
    write_session(project, session)
    summaries: list[dict[str, Any]] = []
    for step in range(1, steps + 1):
        selected = select_next_action(project, mode=mode)
        if selected.get('execution_mode') == 'needs_attention':
            attention = mark_attention(project, reason=str(selected.get('reason') or 'selected action needs attention'), suggested_next_step='Review the selected action, then run agent continue.', action=selected)
            session.update({'status': 'needs_attention', 'updated_at': utc_now(), 'attention_reason': attention.get('reason'), 'step_count': step - 1})
            write_session(project, session)
            return {'session': session, 'summary': None, 'attention': attention}
        checkpoint = create_checkpoint(project, action_id=str(selected.get('selected_action_id') or ''), title=str(selected.get('title') or ''))
        result = run_selected_action(project, action=selected, mode=mode, backend=backend, step=step)
        update_project_map(project, run_id=result['run_id'], action=selected, execution_result=result['execution'], final_result=result['final_result'])
        summary = build_progress_summary(project, action=selected, execution=result['execution'], final_result=result['final_result'], mode=mode)
        append_history(
            project,
            {
                'at': utc_now(),
                'action_id': selected.get('selected_action_id', ''),
                'title': selected.get('title', ''),
                'target_files': selected.get('target_files') or [],
                'execution_mode': selected.get('execution_mode', ''),
                'changed_files': summary.get('changed_files') or [],
                'run_id': result['run_id'],
                'result': summary.get('result'),
                'status': summary.get('status'),
                'checkpoint_id': checkpoint.get('checkpoint_id'),
            },
        )
        summaries.append(summary)
        pause, reason = should_pause_after_result(result['final_result'], result['execution'])
        session.update({'step_count': step, 'updated_at': utc_now(), 'last_run_id': result['run_id'], 'last_result': summary.get('result')})
        if pause:
            attention = mark_attention(project, reason=reason, suggested_next_step='Review the result, then run agent continue when ready.', action=selected)
            session.update({'status': 'needs_attention', 'attention_reason': reason})
            write_session(project, session)
            return {'session': session, 'summary': summary, 'attention': attention}
        if mode != 'autopilot':
            break
    session.update({'status': 'done', 'updated_at': utc_now()})
    write_session(project, session)
    return {'session': session, 'summary': summaries[-1] if summaries else None, 'attention': None}


def stop_session(project: Path) -> dict[str, Any]:
    session = load_json(session_path(project))
    session.update({'status': 'stopped', 'updated_at': utc_now()})
    write_session(project, session)
    return session


def continue_session(project: Path, *, mode: str = '', max_steps: int = 0, backend: str = '') -> dict[str, Any]:
    existing = load_json(session_path(project))
    goal = str(existing.get('goal') or 'Continue current project goal')
    return start_session(project, goal=goal, mode=mode or str(existing.get('mode') or 'standard'), max_steps=max_steps or 1, backend=backend or str(existing.get('backend') or ''))


def main() -> int:
    parser = argparse.ArgumentParser(description='Run a map-backed autopilot session.')
    parser.add_argument('goal', nargs='*')
    parser.add_argument('--workspace', default='.')
    parser.add_argument('--mode', choices=['preview', 'standard', 'autopilot'], default='standard')
    parser.add_argument('--max-steps', type=int, default=0)
    parser.add_argument('--backend', default='')
    parser.add_argument('--stop', action='store_true')
    parser.add_argument('--continue-session', action='store_true')
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args()
    project = project_root(args.workspace)
    if args.stop:
        payload = {'session': stop_session(project), 'summary': None, 'attention': None}
    elif args.continue_session:
        payload = continue_session(project, mode=args.mode, max_steps=args.max_steps, backend=args.backend)
    else:
        goal = ' '.join(args.goal).strip()
        if not goal:
            raise SystemExit('Missing project goal.')
        payload = start_session(project, goal=goal, mode=args.mode, max_steps=args.max_steps, backend=args.backend)
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    elif payload.get('attention'):
        attention = payload['attention']
        print('Needs attention.\nReason:\n* ' + str(attention.get('reason')) + '\n\nSuggested next step:\n* ' + str(attention.get('suggested_next_step')))
    elif payload.get('summary'):
        print(render_user_summary(payload['summary']))
    else:
        print('Done.\nChanged:\n* No business files changed\n\nWhy:\n* Session updated.\n\nProject progress:\n* ' + str((payload.get('session') or {}).get('status')) + '\n\nUndo:\nagent undo')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
