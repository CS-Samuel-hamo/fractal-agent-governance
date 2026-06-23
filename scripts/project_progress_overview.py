#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from runtime_common import load_json, project_root, utc_now, write_json
from project_logic_rules_check import build_project_logic_rules_check, render_logic_rules_check
from seed_action_queue import progress_summary as seed_progress_summary


PHASE1_FILES = {
    'docs/usage_guide.md',
    'docs/prompt_templates.md',
    'docs/workflow_checklist.md',
    'docs/output_schema.md',
}

PHASE1_HARDENING_FILES = {
    'docs/review_rubric.md',
    'docs/literature_search_protocol.md',
    'docs/evidence_quality_standard.md',
    'docs/failure_modes.md',
}

STOP_REASON_LABELS = {
    'reviewable_batch_complete': 'reviewable batch complete',
    'queue_completed': 'planned batch complete',
    'step_completed': 'one safe step complete',
    'project_job_started': 'project job started',
    'needs_attention': 'needs attention',
    'safety_boundary': 'safety boundary',
    'unclear_target': 'unclear target',
    'unsafe_or_unsupported_target': 'unsafe or unsupported target',
    'active_job_requires_review': 'active job requires review',
    'one_off_task_complete': 'one-off task complete',
}

RESULT_LABELS = {
    'completed': 'Done',
    'complete': 'Done',
    'done': 'Done',
    'working': 'Working',
    'active': 'Working',
    'ready for starter action': 'Working',
    'preview recommended': 'Working',
    'blocked with reason': 'Needs attention',
    'needs_attention': 'Needs attention',
    'needs attention': 'Needs attention',
    'not applied': 'Not applied',
    'failed': 'Not applied',
}


def _exists(project: Path, rel: str) -> bool:
    return (project / rel).exists()


def _phase_status(done: int, total: int) -> str:
    if total and done >= total:
        return 'complete'
    if done:
        return 'in_progress'
    return 'not_started'


def _project_label(project: Path) -> str:
    if _exists(project, 'docs/research_workflow.md') or _exists(project, 'project_beginning_prompt.md'):
        return 'Reusable paper workflow toolkit'
    name = project.name.strip()
    return name or 'Current project'


def _blocked_state(stop_reason: str) -> str:
    if stop_reason in {'needs_attention', 'safety_boundary', 'unclear_target', 'unsafe_or_unsupported_target', 'active_job_requires_review'}:
        return 'yes'
    return 'no'


def _display_stop_reason(stop_reason: str) -> str:
    return STOP_REASON_LABELS.get(stop_reason or '', stop_reason or 'reviewable batch complete')


def normalize_result_status(status: str) -> str:
    key = str(status or '').strip().lower()
    return RESULT_LABELS.get(key, status if status in {'Done', 'Working', 'Needs attention', 'Not applied'} else 'Working')


def _phase_progress_line(overview: dict[str, Any]) -> str:
    parts = []
    for phase in overview.get('phases') or []:
        if isinstance(phase, dict):
            parts.append(f'{phase.get("phase")} {phase.get("progress")} {phase.get("status")}')
    return ', '.join(parts) if parts else 'not available'


def _phase_completion_note(overview: dict[str, Any]) -> str:
    current = str(overview.get('current_position') or '')
    if 'ready for trial use' in current:
        return 'This project is usable now for trial use.'
    lowered = current.lower()
    if lowered.startswith('phase 0 complete') or lowered.startswith('phase 1 complete') or lowered.startswith('phase 1 hardened'):
        return 'This phase is complete. The whole project may still have later phases.'
    return ''


def _what_changed_lines(changed: list[str], preview_path: str = '', no_change_reason: str = '') -> list[str]:
    if changed:
        lines = [f'- Files changed: {len(changed)}']
        lines.extend([f'  - {item}' for item in changed[:8]])
        if len(changed) > 8:
            lines.append(f'  - ... {len(changed) - 8} more')
        return lines
    if preview_path:
        return ['- Files changed: 0', f'- Preview artifact created: {preview_path}']
    return ['- Files changed: 0', f'- Reason: {no_change_reason or "no file changes were reported"}']


def _next_items(
    overview: dict[str, Any],
    *,
    status: str,
    next_action: str = '',
    attention: str = '',
    one_off: bool = False,
) -> list[dict[str, str]]:
    result = normalize_result_status(status)
    if result == 'Needs attention':
        return [
            {
                'command': next_action or 'agent',
                'why': attention or 'the request needs review before more files are changed',
            },
            {'command': 'agent do "explain what changed"', 'why': 'understand the current state without changing the project goal'},
            {'command': 'agent undo', 'why': 'return to the latest recoverable state if the direction is wrong'},
        ]
    if one_off:
        return [
            {'command': next_action or 'agent', 'why': 'return to the main project overview after the independent task'},
            {'command': 'git diff', 'why': 'verify exactly what changed on disk'},
            {'command': 'agent cockpit', 'why': 'open the visual project overview'},
        ]
    choices = [str(item) for item in overview.get('choices') or [] if str(item).strip()]
    pending = bool(next_action and 'agent continue' in next_action)
    if pending:
        return [
            {'command': next_action, 'why': 'there is a concrete queued next action ready to run'},
            {'command': 'git diff', 'why': 'review the current batch before continuing'},
            {'command': 'agent cockpit', 'why': 'see the project map and remaining work'},
        ]
    if choices:
        command = choices[0]
    else:
        command = 'agent "<next project goal>"'
    if command == 'agent continue':
        command = 'agent "<next project goal>"'
    return [
        {'command': command, 'why': str(overview.get('suggested_next') or 'choose the next project goal in natural language')},
        {'command': 'git diff', 'why': 'verify exactly what changed on disk'},
        {'command': 'agent cockpit', 'why': 'open the visual project overview'},
    ]


def render_interaction_summary(
    project: Path,
    *,
    status: str,
    goal: str = '',
    changed_files: list[str] | None = None,
    why: str = '',
    next_action: str = '',
    attention: str = '',
    preview_path: str = '',
    stop_reason: str = '',
    one_off: bool = False,
) -> list[str]:
    changed = [str(item) for item in (changed_files or []) if str(item).strip()]
    overview = build_overview(project, last_changed=changed, stop_reason=stop_reason or ('needs_attention' if status == 'Needs attention' else 'reviewable_batch_complete'))
    result = normalize_result_status(status)
    completion_note = _phase_completion_note(overview)
    next_items = _next_items(overview, status=result, next_action=next_action, attention=attention, one_off=one_off)
    lines = [
        'Result:',
        f'- {result}',
        f'- {why or "The request was handled and the project state was updated."}',
    ]
    if one_off:
        lines.append('- Mode: one-off task; current project goal unchanged')
    lines.extend(
        [
            '',
            'Where you are:',
            f'- {overview.get("current_position")}',
            f'- Plan progress: {_phase_progress_line(overview)}',
            f'- Stopped because: {overview.get("stop_reason_display")}',
        ]
    )
    if completion_note:
        lines.append(f'- {completion_note}')
    lines.extend(
        [
            '',
            'What changed:',
            *_what_changed_lines(changed, preview_path=preview_path, no_change_reason=why),
            '',
            'How to check:',
            '- Run `git diff` to inspect file changes.',
            '- Run `agent cockpit` to open the visual project overview.',
            '',
            'Next:',
        ]
    )
    for index, item in enumerate(next_items[:3], start=1):
        prefix = 'Recommended: ' if index == 1 else ''
        lines.append(f'{index}. {prefix}{item.get("command")}')
        lines.append(f'   Why: {item.get("why")}')
    lines.extend(
        [
            '',
            'If this is not what you wanted:',
            '- Run `agent undo` to return to the latest recoverable state.',
            '- Run `agent do "explain what changed"` for an independent explanation.',
            '- Or give a new direction with `agent "<new goal>"`.',
            '',
            'Details:',
        ]
    )
    if goal:
        lines.append(f'- Current goal: {goal}')
    lines.extend(render_landing_proof(project, changed_files=changed, preview_path=preview_path, status=result))
    lines.extend(render_overview(project, last_changed=changed, stop_reason=stop_reason))
    return lines


def build_overview(project: Path, *, last_changed: list[str] | None = None, stop_reason: str = '') -> dict[str, Any]:
    seed = seed_progress_summary(project)
    logic_rules = build_project_logic_rules_check(project)
    phase0_total = int(seed.get('total_actions') or 0)
    phase0_done = int(seed.get('completed_actions') or 0)
    phase0_status = _phase_status(phase0_done, phase0_total) if phase0_total else 'not_started'
    phase1_done_files = sorted(rel for rel in PHASE1_FILES if _exists(project, rel))
    phase1_status = _phase_status(len(phase1_done_files), len(PHASE1_FILES))
    hardening_done_files = sorted(rel for rel in PHASE1_HARDENING_FILES if _exists(project, rel))
    hardening_status = _phase_status(len(hardening_done_files), len(PHASE1_HARDENING_FILES))
    if phase0_status != 'complete':
        current_position = seed.get('current_position') or 'Phase 0 in progress: reusable paper workflow scaffold.'
        if phase0_total:
            suggested_next = 'Complete the workflow scaffold first.'
            choices = ['agent continue', 'agent cockpit', 'agent undo']
        else:
            suggested_next = 'Give the operator a project goal or seed prompt so it can build the first plan.'
            choices = ['agent "<project goal>"', 'agent cockpit', 'agent do "explain this project"']
    elif phase1_status == 'not_started':
        current_position = 'Phase 0 complete. Phase 1 is ready: turn the workflow into a reusable toolkit.'
        suggested_next = 'Generate usage guide, prompt templates, workflow checklist, and output schema.'
        choices = [
            'agent "继续把当前论文生成流程整理成可复用工具包：生成 docs/usage_guide.md、docs/prompt_templates.md、docs/workflow_checklist.md 和 docs/output_schema.md"',
            'agent cockpit',
            'agent undo',
        ]
    elif phase1_status == 'complete':
        if hardening_status == 'complete':
            current_position = 'Phase 1 hardened: reusable paper workflow toolkit is ready for trial use.'
            suggested_next = 'Review the full toolkit, then run it on a concrete paper idea when ready.'
            choices = [
                'agent "用一个真实论文题目试跑当前论文生成流程，先生成研究问题、贡献假设和证据计划"',
                'agent cockpit',
                'git diff',
            ]
        else:
            current_position = 'Phase 1 complete: reusable paper workflow toolkit is ready for review.'
            suggested_next = 'Review the toolkit, then decide whether to harden quality standards or apply it to a concrete paper idea.'
            choices = [
                'agent "继续完善这套论文生成工具包：补充 docs/review_rubric.md、docs/literature_search_protocol.md、docs/evidence_quality_standard.md 和 docs/failure_modes.md"',
                'agent cockpit',
                'git diff',
            ]
    else:
        current_position = f'Phase 1 in progress: reusable toolkit files are {len(phase1_done_files)}/{len(PHASE1_FILES)} complete.'
        suggested_next = 'Finish the remaining toolkit files.'
        choices = ['agent "<describe the missing toolkit docs>"', 'agent cockpit', 'git diff']
    overview = {
        'schema_version': '1.0',
        'generated_by': 'project_progress_overview.py',
        'generated_at': utc_now(),
        'product_model': 'AI Project Operator',
        'operator_contract': 'Project Map-backed progress, safe batch execution, review-point reporting, Cockpit visibility, undo support.',
        'project': _project_label(project),
        'project_map_role': 'tracks project state, phases, evidence, next actions, and attention points',
        'current_position': current_position,
        'stop_reason': stop_reason or 'reviewable_batch_complete',
        'stop_reason_display': _display_stop_reason(stop_reason or 'reviewable_batch_complete'),
        'blocked': _blocked_state(stop_reason or 'reviewable_batch_complete'),
        'last_changed': last_changed or [],
        'logic_rules': logic_rules,
        'phases': [
            {
                'phase': 'Phase 0',
                'title': 'Reusable paper workflow scaffold',
                'status': phase0_status,
                'progress': f'{phase0_done}/{phase0_total}' if phase0_total else '0/0',
            },
            {
                'phase': 'Phase 1',
                'title': 'Reusable toolkit: usage guide, prompt templates, checklist, output schema',
                'status': phase1_status,
                'progress': f'{len(phase1_done_files)}/{len(PHASE1_FILES)}',
            },
            {
                'phase': 'Phase 1B',
                'title': 'Quality hardening: rubric, search protocol, evidence standard, failure modes',
                'status': hardening_status if phase1_status == 'complete' else 'later',
                'progress': f'{len(hardening_done_files)}/{len(PHASE1_HARDENING_FILES)}',
            },
            {
                'phase': 'Phase 2',
                'title': 'Apply the workflow to a concrete paper idea',
                'status': 'later',
                'progress': '0/1',
            },
        ],
        'suggested_next': suggested_next,
        'choices': choices,
    }
    write_json(project / '.zoo-agent' / 'jobs' / 'project_progress_overview.json', overview)
    return overview


def render_overview(project: Path, *, last_changed: list[str] | None = None, stop_reason: str = '') -> list[str]:
    overview = build_overview(project, last_changed=last_changed, stop_reason=stop_reason)
    lines = [
        'Overview:',
        f'- Product model: {overview.get("product_model")} ({overview.get("operator_contract")})',
        f'- Project: {overview.get("project")}',
        f'- Project Map: {overview.get("project_map_role")}',
        f'- Current position: {overview.get("current_position")}',
        f'- Stopped because: {overview.get("stop_reason_display")}',
        f'- Blocked: {overview.get("blocked")}',
        f'- Recommended next move: {overview.get("suggested_next")}',
    ]
    for phase in overview.get('phases') or []:
        if isinstance(phase, dict):
            lines.append(f'- {phase.get("phase")}: {phase.get("title")} [{phase.get("status")}, {phase.get("progress")}]')
    choices = [str(item) for item in overview.get('choices') or [] if str(item).strip()]
    if choices:
        lines.extend(['', 'Choices:'])
        lines.extend([f'- {item}' for item in choices[:3]])
    lines.extend(render_logic_rules_check(project))
    return lines


def render_landing_proof(project: Path, *, changed_files: list[str] | None = None, preview_path: str = '', status: str = '') -> list[str]:
    changed = [str(item) for item in (changed_files or []) if str(item).strip()]
    lines = ['Landing proof:']
    if changed:
        lines.append(f'- Files changed: {len(changed)}')
        lines.extend([f'  - {item}' for item in changed[:8]])
        if len(changed) > 8:
            lines.append(f'  - ... {len(changed) - 8} more')
    else:
        lines.append('- Files changed: none reported')
    if preview_path:
        lines.append(f'- Preview artifact: {preview_path}')
    overview_path = project / '.zoo-agent' / 'jobs' / 'project_progress_overview.json'
    cockpit_path = project / '.zoo-agent' / 'cockpit' / 'index.html'
    lines.append(f'- Project overview: {"updated" if overview_path.exists() else "not generated yet"}')
    lines.append(f'- Cockpit: {".zoo-agent/cockpit/index.html" if cockpit_path.exists() else "run agent cockpit"}')
    if status:
        lines.append(f'- Result state: {status}')
    lines.append('- Verify locally: git diff')
    return lines


def main() -> int:
    parser = argparse.ArgumentParser(description='Render project progress overview.')
    parser.add_argument('--workspace', default='.')
    args = parser.parse_args()
    project = project_root(args.workspace)
    overview = build_overview(project)
    print(json.dumps(overview, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
