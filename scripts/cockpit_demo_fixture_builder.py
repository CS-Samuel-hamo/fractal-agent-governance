#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from runtime_common import project_root, utc_now, write_json

SCENARIOS = [
    'active_session',
    'paused_session',
    'needs_attention',
    'full_project_map',
    'checkpoint_available',
]


def rel(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def evidence(kind: str, path: str, summary: str, confidence: float = 0.8) -> dict[str, Any]:
    return {'kind': kind, 'path': path, 'summary': summary, 'confidence': confidence}


def build_fixture_artifacts(fixture: Path) -> list[Path]:
    generated: list[Path] = []
    fixture.mkdir(parents=True, exist_ok=True)
    (fixture / 'README.md').write_text(
        '# Synthetic Cockpit Demo\n\nThis fixture is synthetic and safe.\n', encoding='utf-8'
    )
    (fixture / 'docs').mkdir(exist_ok=True)
    (fixture / 'docs' / 'release.md').write_text('# Release Notes\n\nDraft readiness notes.\n', encoding='utf-8')
    (fixture / 'tests').mkdir(exist_ok=True)
    (fixture / 'tests' / 'test_smoke.py').write_text('def test_smoke():\n    assert True\n', encoding='utf-8')
    generated.extend([fixture / 'README.md', fixture / 'docs' / 'release.md', fixture / 'tests' / 'test_smoke.py'])

    readme_ev = [evidence('file', 'README.md', 'Synthetic README demonstrates project entry point.')]
    docs_ev = [evidence('file', 'docs/release.md', 'Synthetic release notes show readiness gap.')]
    tests_ev = [evidence('file', 'tests/test_smoke.py', 'Synthetic smoke test demonstrates verification surface.')]

    project_map = {
        'schema_version': '1.0',
        'generated_by': 'cockpit_demo_fixture_builder.py',
        'synthetic_demo': True,
        'project_name': 'Synthetic Project Operator Demo',
        'project_type': 'local cli project',
        'main_goal': 'Prepare this project for a confident local alpha release.',
        'modules': [
            {
                'module_id': 'module-readme',
                'name': 'Project entry',
                'purpose': 'Explain what the project is.',
                'key_files': ['README.md'],
                'status': 'mapped',
                'confidence': 0.86,
                'evidence': readme_ev,
            },
            {
                'module_id': 'module-docs',
                'name': 'Release docs',
                'purpose': 'Track readiness and examples.',
                'key_files': ['docs/release.md'],
                'status': 'working',
                'confidence': 0.78,
                'evidence': docs_ev,
            },
            {
                'module_id': 'module-tests',
                'name': 'Smoke tests',
                'purpose': 'Provide a quick confidence check.',
                'key_files': ['tests/test_smoke.py'],
                'status': 'complete',
                'confidence': 0.82,
                'evidence': tests_ev,
            },
        ],
        'capabilities': [
            {
                'capability_id': 'cap-missing',
                'name': 'Install walkthrough',
                'status': 'missing',
                'evidence': [],
                'related_modules': ['module-docs'],
            },
            {
                'capability_id': 'cap-partial',
                'name': 'Release notes',
                'status': 'partial',
                'evidence': docs_ev,
                'related_modules': ['module-docs'],
            },
            {
                'capability_id': 'cap-implemented',
                'name': 'Project overview',
                'status': 'implemented',
                'evidence': readme_ev,
                'related_modules': ['module-readme'],
            },
            {
                'capability_id': 'cap-verified',
                'name': 'Smoke test surface',
                'status': 'verified',
                'evidence': tests_ev,
                'related_modules': ['module-tests'],
            },
        ],
        'risks': [
            {
                'risk_id': 'risk-low-doc-gap',
                'description': 'Release guide could be clearer.',
                'severity': 'low',
                'affected_files': ['docs/release.md'],
                'evidence': docs_ev,
            },
            {
                'risk_id': 'risk-medium-test-gap',
                'description': 'Only smoke-level validation is represented.',
                'severity': 'medium',
                'affected_files': ['tests/test_smoke.py'],
                'evidence': tests_ev,
            },
            {
                'risk_id': 'risk-high-release-claim',
                'description': 'Release confidence should not be claimed without review.',
                'severity': 'high',
                'affected_files': ['README.md', 'docs/release.md'],
                'evidence': [*readme_ev, *docs_ev],
            },
        ],
        'next_actions': [
            {
                'action_id': 'action-readme-clarity',
                'title': 'Clarify README alpha status',
                'why_now': 'The entry point exists and can explain current project readiness.',
                'expected_impact': 'A new user understands the project faster.',
                'risk_level': 'low',
                'target_files': ['README.md'],
                'autopilot_eligible': True,
                'evidence': readme_ev,
            },
            {
                'action_id': 'action-release-guide',
                'title': 'Complete release guide outline',
                'why_now': 'The release guide exists but is only partial.',
                'expected_impact': 'Release readiness becomes easier to verify.',
                'risk_level': 'medium',
                'target_files': ['docs/release.md'],
                'autopilot_eligible': False,
                'evidence': docs_ev,
            },
            {
                'action_id': 'action-human-review',
                'title': 'Review high-confidence release claim',
                'why_now': 'High-confidence release claims need a human check.',
                'expected_impact': 'Avoids overclaiming readiness.',
                'risk_level': 'high',
                'target_files': ['README.md'],
                'autopilot_eligible': False,
                'evidence': [*readme_ev, *docs_ev],
            },
        ],
        'last_updated': utc_now(),
    }
    project_state = {
        'schema_version': '1.0',
        'generated_by': 'cockpit_demo_fixture_builder.py',
        'synthetic_demo': True,
        'project_name': project_map['project_name'],
        'main_goal': project_map['main_goal'],
        'status': 'needs_attention',
        'progress': '65%',
        'last_action': 'Complete release guide outline',
        'last_result': 'needs attention before release claim',
        'last_updated': utc_now(),
    }
    map_evidence = {
        'schema_version': '1.0',
        'generated_by': 'cockpit_demo_fixture_builder.py',
        'synthetic_demo': True,
        'evidence': [*readme_ev, *docs_ev, *tests_ev],
        'skipped_sensitive_paths': [],
    }
    session = {
        'schema_version': '1.0',
        'generated_by': 'cockpit_demo_fixture_builder.py',
        'synthetic_demo': True,
        'session_id': 'synthetic-session-active',
        'goal': project_map['main_goal'],
        'mode': 'standard',
        'status': 'doing',
        'current_action': 'Clarify README alpha status',
        'paused_demo_status': 'paused',
        'updated_at': utc_now(),
        'step_count': 2,
        'max_steps': 3,
    }
    progress = {
        'schema_version': '1.0',
        'generated_by': 'cockpit_demo_fixture_builder.py',
        'synthetic_demo': True,
        'status': 'needs_attention',
        'title': 'Complete release guide outline',
        'changed_files': ['docs/release.md'],
        'why': ['Selected from project map because release readiness is partial.'],
        'project_progress': ['Project is closer to alpha readiness, but release claim needs review.'],
        'undo': 'agent undo',
        'result': 'needs_attention',
    }
    action_history = {
        'schema_version': '1.0',
        'generated_by': 'cockpit_demo_fixture_builder.py',
        'synthetic_demo': True,
        'actions': [
            {
                'at': utc_now(),
                'action_id': 'action-readme-clarity',
                'title': 'Clarify README alpha status',
                'status': 'done',
                'result': 'COMPLETED',
                'changed_files': ['README.md'],
                'checkpoint_id': 'checkpoint-0001',
            },
            {
                'at': utc_now(),
                'action_id': 'action-paused-demo',
                'title': 'Pause before higher-impact release claim',
                'status': 'paused',
                'result': 'PAUSED_FOR_REVIEW',
                'changed_files': [],
            },
            {
                'at': utc_now(),
                'action_id': 'action-release-guide',
                'title': 'Complete release guide outline',
                'status': 'needs_attention',
                'result': 'REVIEW_REQUIRED',
                'changed_files': ['docs/release.md'],
                'checkpoint_id': 'checkpoint-0002',
            },
        ],
    }
    attention = {
        'schema_version': '1.0',
        'generated_by': 'cockpit_demo_fixture_builder.py',
        'synthetic_demo': True,
        'status': 'needs_attention',
        'reason': 'A higher-impact release claim needs user review before continuing.',
        'suggested_next_step': 'Review the release guide, then run agent continue.',
        'action': project_map['next_actions'][2],
    }
    checkpoints = {
        'schema_version': '1.0',
        'generated_by': 'cockpit_demo_fixture_builder.py',
        'synthetic_demo': True,
        'checkpoints': [
            {
                'checkpoint_id': 'checkpoint-0001',
                'created_at': utc_now(),
                'action_id': 'action-readme-clarity',
                'title': 'Clarify README alpha status',
                'git_head': 'synthetic',
                'git_branch': 'synthetic-demo',
                'status_short': [],
                'undo_available': True,
            },
            {
                'checkpoint_id': 'checkpoint-0002',
                'created_at': utc_now(),
                'action_id': 'action-release-guide',
                'title': 'Complete release guide outline',
                'git_head': 'synthetic',
                'git_branch': 'synthetic-demo',
                'status_short': ['M docs/release.md'],
                'undo_available': True,
            },
        ],
    }
    map_quality = {
        'schema_version': '1.0',
        'generated_by': 'cockpit_demo_fixture_builder.py',
        'map_quality_score': 0.92,
        'evidence_coverage': 0.89,
        'hallucination_risk': 'low',
        'vague_action_count': 0,
        'unsupported_module_count': 0,
        'unsupported_capability_count': 0,
        'recommendation': 'pass',
    }
    readiness_094 = {
        'schema_version': '1.0',
        'generated_by': 'cockpit_demo_fixture_builder.py',
        'final_recommendation': 'READY_FOR_094_COCKPIT',
    }
    files = {
        '.zoo-agent/map/project_map.json': project_map,
        '.zoo-agent/map/project_state.json': project_state,
        '.zoo-agent/map/map_evidence.json': map_evidence,
        '.zoo-agent/autopilot/session.json': session,
        '.zoo-agent/autopilot/progress.json': progress,
        '.zoo-agent/autopilot/action_history.json': action_history,
        '.zoo-agent/autopilot/attention_required.json': attention,
        '.zoo-agent/autopilot/checkpoints.json': checkpoints,
        '.zoo-agent/dogfood/map_quality_report.json': map_quality,
        '.zoo-agent/dogfood/readiness_for_094.json': readiness_094,
    }
    for relative, payload in files.items():
        path = fixture / relative
        write_json(path, payload)
        generated.append(path)
    return generated


def build_demo_fixture(project: Path) -> dict[str, Any]:
    dogfood_dir = project / '.zoo-agent' / 'cockpit_dogfood'
    fixture = dogfood_dir / 'demo_fixture'
    generated = build_fixture_artifacts(fixture)
    summary = {
        'schema_version': '1.0',
        'generated_by': 'cockpit_demo_fixture_builder.py',
        'generated_at': utc_now(),
        'fixture_path': '.zoo-agent/cockpit_dogfood/demo_fixture',
        'scenarios': SCENARIOS,
        'generated_artifacts': [rel(path, fixture) for path in generated],
        'safe_to_use': True,
        'synthetic_demo': True,
    }
    write_json(dogfood_dir / 'demo_fixture_summary.json', summary)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description='Build a synthetic Project Cockpit dogfood fixture.')
    parser.add_argument('--workspace', default='.')
    args = parser.parse_args()
    project = project_root(args.workspace)
    payload = build_demo_fixture(project)
    print(
        json.dumps(
            {
                'status': 'ok',
                'fixture_path': payload['fixture_path'],
                'summary': str(project / '.zoo-agent' / 'cockpit_dogfood' / 'demo_fixture_summary.json'),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
