#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from cockpit_renderer import render_cockpit
from learning_feedback_applier import apply_feedback
from map_task_selector import select_next_action
from worker_router import route_worker


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')


def assert_true(value: bool, message: str) -> None:
    if not value:
        raise AssertionError(message)


def seed_project_map(project: Path) -> None:
    write_json(
        project / '.zoo-agent' / 'map' / 'project_map.json',
        {
            'project_name': 'feedback-fixture',
            'project_type': 'python_cli',
            'main_goal': 'prepare for public release',
            'modules': [
                {
                    'module_id': 'module-docs',
                    'name': 'Docs',
                    'status': 'mapped',
                    'confidence': 0.8,
                    'key_files': ['README.md'],
                    'evidence': [{'path': 'README.md'}],
                },
            ],
            'capabilities': [],
            'risks': [],
            'next_actions': [
                {
                    'action_id': 'action-tests',
                    'title': 'Add test readiness note',
                    'why_now': 'Tests are useful before refactor.',
                    'expected_impact': 'Improves release confidence.',
                    'risk_level': 'low',
                    'target_files': ['README.md'],
                    'autopilot_eligible': True,
                    'evidence': [{'path': 'README.md'}],
                },
                {
                    'action_id': 'action-docs',
                    'title': 'Add README release note',
                    'why_now': 'README exists and release docs are a common next step.',
                    'expected_impact': 'Improves first-run clarity.',
                    'risk_level': 'low',
                    'target_files': ['README.md'],
                    'autopilot_eligible': True,
                    'evidence': [{'path': 'README.md'}],
                },
            ],
            'last_updated': '2026-06-21T00:00:00Z',
        },
    )
    write_json(
        project / '.zoo-agent' / 'map' / 'project_state.json', {'project_name': 'feedback-fixture', 'status': 'mapped'}
    )


def seed_learning(project: Path) -> None:
    write_json(
        project / '.zoo-agent' / 'learning' / 'cross_project' / 'learning_insights.json',
        {
            'insights': [
                {
                    'insight_id': 'insight-docs',
                    'type': 'next_action_boost',
                    'applies_to': 'docs_update',
                    'message': 'README docs release readiness is a common successful next action.',
                    'evidence': [{'pattern_id': 'docs_cleanup_before_release'}],
                    'confidence': 0.9,
                    'recommended_effect': 'boost',
                },
                {
                    'insight_id': 'insight-claude',
                    'type': 'worker_preference',
                    'applies_to': 'code_edit',
                    'message': 'Prefer claude for this code edit if a verified adapter is available.',
                    'evidence': [{'source': 'synthetic'}],
                    'confidence': 0.95,
                    'recommended_effect': 'prefer_worker',
                },
                {
                    'insight_id': 'insight-unsafe',
                    'type': 'next_action_boost',
                    'applies_to': 'blocked_zone',
                    'message': 'unsafe effect should be rejected',
                    'evidence': [],
                    'confidence': 1.0,
                    'recommended_effect': 'execute_blocked_zone',
                },
            ]
        },
    )


def main() -> int:
    with tempfile.TemporaryDirectory(prefix='agent-learning-feedback-') as tmp:
        project = Path(tmp)
        (project / 'README.md').write_text('# Feedback Fixture\n', encoding='utf-8')
        seed_project_map(project)
        seed_learning(project)

        feedback = apply_feedback(project)
        assert_true(
            any(item.get('target') == 'map_task_selector' for item in feedback.get('applied') or []),
            'map selector feedback not applied',
        )
        assert_true(
            any(item.get('target') == 'worker_router' for item in feedback.get('applied') or []),
            'worker router feedback not applied',
        )
        assert_true(
            any(item.get('reason') == 'unsafe_effect_rejected' for item in feedback.get('skipped') or []),
            'unsafe effect was not rejected',
        )

        selected = select_next_action(project, mode='standard')
        assert_true(
            selected.get('selected_action_id') == 'action-docs', 'learning boost did not affect next action ranking'
        )
        assert_true(selected.get('learning_feedback_ref'), 'selector did not record learning feedback reference')

        blocked_decision = route_worker(
            project,
            task_profile={
                'task_id': 'blocked',
                'task_type': 'code_edit',
                'risk_level': 'high',
                'trust_zone': 'blocked',
                'requires_actual_execution': True,
                'target_files': ['secrets/config.env'],
                'preferred_worker_type': 'code',
            },
            execution_mode='auto',
        )
        assert_true(blocked_decision.get('execution_allowed') is False, 'learning bypassed blocked zone')
        assert_true(
            blocked_decision.get('execution_mode') == 'needs_attention', 'blocked zone did not require attention'
        )

        code_decision = route_worker(
            project,
            task_profile={
                'task_id': 'code',
                'task_type': 'code_edit',
                'risk_level': 'low',
                'trust_zone': 'trusted',
                'requires_actual_execution': True,
                'target_files': ['README.md'],
                'preferred_worker_type': 'code',
            },
            execution_mode='auto',
        )
        assert_true(
            code_decision.get('selected_provider') != 'claude',
            'unverified Claude stub was selected for actual execution',
        )
        assert_true(code_decision.get('learning_feedback_ref'), 'router did not record learning feedback reference')

        render_cockpit(project)
        cockpit = (project / '.zoo-agent' / 'cockpit' / 'index.html').read_text(encoding='utf-8')
        assert_true('Cross-project Learning' in cockpit, 'cockpit missing learning panel')
        assert_true('README docs release readiness' in cockpit, 'cockpit did not show product-level learning insight')
        assert_true('learning_insights.json' not in cockpit, 'cockpit leaked raw learning artifact path')

        help_text = subprocess.run(
            [sys.executable, str(ROOT / 'scripts' / 'agent.py'), '--help'],
            cwd=ROOT,
            text=True,
            encoding='utf-8',
            capture_output=True,
        ).stdout
        assert_true(
            'learning --build' not in help_text and 'learning --import' not in help_text,
            'ordinary help exposed learning commands',
        )

    print('learning feedback integration tests passed')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
