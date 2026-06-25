#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime
import json
from pathlib import Path
from typing import Any


def utc_now() -> str:
    return datetime.datetime.utcnow().isoformat() + 'Z'


def load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding='utf-8-sig'))
    except Exception:
        return {}


def read_text(path: Path, limit: int = 6000) -> str:
    try:
        text = path.read_text(encoding='utf-8-sig')
    except Exception:
        return ''
    return text[:limit]


def safe_name(value: str) -> str:
    return ''.join(ch if ch.isalnum() or ch in '._-' else '-' for ch in value).strip('-') or 'task'


def latest_goal(goals_dir: Path) -> dict[str, Any]:
    goals = []
    for path in sorted(goals_dir.glob('*.json')):
        data = load_json(path)
        if data:
            data['_path'] = str(path)
            goals.append(data)
    if not goals:
        return {}
    return sorted(goals, key=lambda item: item.get('updated_at') or item.get('created_at') or '', reverse=True)[0]


def resolve_active_goal(project: Path, run_id: str, goal_id: str = '') -> dict[str, Any]:
    if goal_id:
        path = project / '.zoo-agent' / 'goals' / f'{goal_id}.json'
        data = load_json(path)
        if data:
            data['_path'] = str(path)
        return data

    current_run = load_json(project / '.zoo-agent' / 'current-run.json')
    candidate_goal = current_run.get('goal_id') or current_run.get('active_goal_id')
    if candidate_goal:
        path = project / '.zoo-agent' / 'goals' / f'{candidate_goal}.json'
        data = load_json(path)
        if data:
            data['_path'] = str(path)
            return data

    run_ledger = load_json(project / '.zoo-agent' / 'runs' / run_id / 'run-ledger.json')
    candidate_goal = run_ledger.get('goal_id') or run_ledger.get('active_goal_id')
    if candidate_goal and candidate_goal != 'unknown':
        path = project / '.zoo-agent' / 'goals' / f'{candidate_goal}.json'
        data = load_json(path)
        if data:
            data['_path'] = str(path)
            return data

    return latest_goal(project / '.zoo-agent' / 'goals')


def compact_charter(project: Path) -> dict[str, Any]:
    path = project / '.zoo-agent' / 'project-charter.json'
    data = load_json(path)
    if data:
        data['_path'] = str(path)
        return data
    md_path = project / 'docs' / 'project-charter.md'
    md = read_text(md_path)
    if md:
        return {'_path': str(md_path), 'markdown_excerpt': md}
    return {}


def explicit_durable_update_requested(user_request: str) -> bool:
    text = user_request.lower()
    markers = [
        'update project charter',
        'modify project charter',
        'change project charter',
        'update long-term goal',
        'change long-term goal',
        'update root goal',
        'change root goal',
        '\u957f\u671f\u76ee\u6807',
        '\u9879\u76ee\u76ee\u6807',
        '\u6839\u76ee\u6807',
        '\u4fee\u6539\u9879\u76ee\u76ee\u6807',
        '\u66f4\u65b0\u9879\u76ee\u76ee\u6807',
        '\u4fee\u6539charter',
        '\u66f4\u65b0charter',
    ]
    return any(marker in text for marker in markers)


def build_context(
    project: Path,
    run_id: str,
    task_id: str,
    user_request: str,
    goal_id: str = '',
    allow_durable_state_update: bool = False,
) -> dict[str, Any]:
    charter = compact_charter(project)
    goal = resolve_active_goal(project, run_id, goal_id)
    current_run = load_json(project / '.zoo-agent' / 'current-run.json')
    project_tasks = read_text(project / '.zoo-agent' / 'TASKS.md', limit=3000)
    run_tasks = read_text(project / '.zoo-agent' / 'runs' / run_id / 'TASKS.md', limit=3000)
    project_readiness = load_json(project / '.zoo-agent' / 'project-readiness.json')
    architecture_compatibility = load_json(project / '.zoo-agent' / 'architecture-compatibility-report.json')
    source_of_truth_resolver = load_json(project / '.zoo-agent' / 'bootstrap' / 'source-of-truth-resolver.json')
    local_rules_summary = read_text(project / '.zoo-agent' / 'local-rules-summary.md', limit=3000)
    explicit_update = explicit_durable_update_requested(user_request)
    durable_writes_allowed = bool(allow_durable_state_update and explicit_update)

    return {
        'schema_version': '1.0',
        'generated_by': 'build_task_context.py',
        'generated_at': utc_now(),
        'run_id': run_id,
        'task_id': task_id,
        'current_user_request': user_request,
        'current_task_objective': user_request,
        'short_task_objective': user_request,
        'interpretation_policy': {
            'default_interpretation': 'current_user_request_is_current_task',
            'do_not_classify_request_as_short_or_long': True,
            'do_not_rewrite_project_goal_from_request': True,
            'use_durable_context_as_background': True,
            'if_request_conflicts_with_charter_or_goal': 'record_escalation_or_ask_user_before_execution',
        },
        'write_policy': {
            'project_charter': 'read_only' if not durable_writes_allowed else 'explicit_update_allowed',
            'goal_contract': 'read_only' if not durable_writes_allowed else 'explicit_update_allowed',
            'project_profile': 'read_only',
            'project_map': 'read_only',
            'task_board': 'may_append_or_propose',
            'runtime_artifacts': 'may_write',
            'durable_update_requested': explicit_update,
            'durable_update_authorized': durable_writes_allowed,
        },
        'durable_project_context': {
            'project_charter': charter,
            'project_profile_path': str(project / '.zoo-agent' / 'project-profile.json'),
            'project_map_path': str(project / '.zoo-agent' / 'project-map.json'),
            'architecture_boundaries_path': str(project / '.zoo-agent' / 'architecture-boundaries.json'),
            'project_readiness': project_readiness,
            'architecture_compatibility': architecture_compatibility,
            'source_of_truth_resolver': source_of_truth_resolver,
            'local_rules_summary_excerpt': local_rules_summary,
        },
        'active_goal_context': {
            'goal': goal,
            'requested_goal_id': goal_id or '',
            'current_run': current_run,
        },
        'task_board_context': {
            'project_tasks_md_excerpt': project_tasks,
            'run_tasks_md_excerpt': run_tasks,
        },
        'worker_guidance': [
            'Treat current_user_request as the task for this run.',
            'Use project charter and active goal only as read-only background unless write_policy explicitly allows durable updates.',
            'Do not replace root_goal, project mission, or project charter with the current task wording.',
            'Check project_readiness and architecture_compatibility before claiming worker readiness, merge readiness, or current architecture facts.',
            'Use source_of_truth_resolver when .zoo-agent, docs, retired frameworks, or local rules disagree.',
            'When proposing cleanup/review work, express it as leaf tasks aligned to the active goal.',
        ],
    }


def render_markdown(context: dict[str, Any]) -> str:
    charter = context.get('durable_project_context', {}).get('project_charter') or {}
    durable = context.get('durable_project_context', {}) or {}
    goal = context.get('active_goal_context', {}).get('goal') or {}
    readiness = durable.get('project_readiness') or {}
    compatibility = durable.get('architecture_compatibility') or {}
    resolver = durable.get('source_of_truth_resolver') or {}
    lines = [
        f'# Task Context: {context.get("task_id")}',
        '',
        '## Current User Request',
        '',
        context.get('current_user_request') or 'unknown',
        '',
        '## Interpretation Policy',
        '',
        f'- Default: {context.get("interpretation_policy", {}).get("default_interpretation")}',
        '- Do not classify this request as short-term or long-term before acting.',
        '- Durable project and goal state are read-only unless explicitly authorized.',
        '- Do not rewrite project mission/root goal from the current request.',
        '',
        '## Project Charter Context',
        '',
        f'- path: {charter.get("_path", "missing")}',
        f'- mission: {charter.get("mission", "unknown")}',
        f'- product_goals: {json.dumps(charter.get("product_goals", ["unknown"]), ensure_ascii=False)}',
        f'- technical_goals: {json.dumps(charter.get("technical_goals", ["unknown"]), ensure_ascii=False)}',
        f'- non_goals: {json.dumps(charter.get("non_goals", ["unknown"]), ensure_ascii=False)}',
        '',
    ]
    if charter.get('markdown_excerpt'):
        lines += [
            '### Charter Markdown Excerpt',
            '',
            charter.get('markdown_excerpt', ''),
            '',
        ]
    lines += [
        '## Architecture Runtime Context',
        '',
        f'- project_readiness: {readiness.get("safe_for_level_0_1_trial", "unknown")}',
        f'- codex_cli_ready: {readiness.get("codex_cli_ready", "unknown")}',
        f'- architecture_compatibility_status: {compatibility.get("status", "unknown")}',
        f'- architecture_compatibility_issues: {len(compatibility.get("issues") or []) if isinstance(compatibility.get("issues"), list) else "unknown"}',
        f'- source_of_truth_resolver: {resolver.get("schema_version", "missing")}',
        '',
        '## Active Goal Context',
        '',
        f'- path: {goal.get("_path", "missing")}',
        f'- goal_id: {goal.get("goal_id", "unknown")}',
        f'- root_goal: {goal.get("root_goal", "unknown")}',
        f'- success_criteria: {json.dumps(goal.get("success_criteria", ["unknown"]), ensure_ascii=False)}',
        f'- constraints: {json.dumps(goal.get("constraints", ["unknown"]), ensure_ascii=False)}',
        '',
        '## Write Policy',
        '',
    ]
    for key, value in (context.get('write_policy') or {}).items():
        lines.append(f'- {key}: {value}')
    lines.append('')
    return '\n'.join(lines)


def write_context(project: Path, run_id: str, task_id: str, context: dict[str, Any]) -> dict[str, str]:
    out_dir = project / '.zoo-agent' / 'runs' / run_id / 'task-contexts'
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / f'{safe_name(task_id)}.json'
    md_path = out_dir / f'{safe_name(task_id)}.md'
    json_path.write_text(json.dumps(context, ensure_ascii=False, indent=2), encoding='utf-8')
    md_path.write_text(render_markdown(context), encoding='utf-8')
    latest_json = project / '.zoo-agent' / 'runs' / run_id / 'task-context.json'
    latest_md = project / '.zoo-agent' / 'runs' / run_id / 'task-context.md'
    latest_json.write_text(json.dumps(context, ensure_ascii=False, indent=2), encoding='utf-8')
    latest_md.write_text(render_markdown(context), encoding='utf-8')
    return {
        'json': str(json_path),
        'markdown': str(md_path),
        'latest_json': str(latest_json),
        'latest_markdown': str(latest_md),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description='Build a read-only durable context envelope for a current task request.')
    ap.add_argument('--run-id', required=True)
    ap.add_argument('--task-id', required=True)
    ap.add_argument('--workspace', default='.')
    ap.add_argument('--user-request', required=True)
    ap.add_argument('--goal-id', default='')
    ap.add_argument('--allow-durable-state-update', action='store_true')
    ap.add_argument('--output', default='')
    args = ap.parse_args()

    project = Path(args.workspace).resolve()
    context = build_context(
        project, args.run_id, args.task_id, args.user_request, args.goal_id, args.allow_durable_state_update
    )
    paths = write_context(project, args.run_id, args.task_id, context)
    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(context, ensure_ascii=False, indent=2), encoding='utf-8')
        paths['output'] = str(out)
    print(
        json.dumps(
            {'status': 'ok', 'paths': paths, 'write_policy': context['write_policy']}, ensure_ascii=False, indent=2
        )
    )
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
