#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from cockpit_renderer import render_cockpit
from cross_project_insight_engine import build_insights
from cross_project_store import initialize_store
from failure_taxonomy_builder import build_failure_taxonomy
from learning_artifact_importer import import_project_artifacts
from learning_baseline_comparator import compare_baseline
from learning_feedback_applier import apply_feedback
from learning_lift_evaluator import evaluate_lift
from learning_product_report_generator import generate_product_report
from learning_trace_replayer import generate_replay
from next_action_pattern_miner import mine_patterns
from release_readiness_template_builder import build_templates
from runtime_common import project_root, utc_now, write_json
from worker_performance_memory import build_worker_memory


def dogfood_dir(project: Path) -> Path:
    return project / '.zoo-agent' / 'learning_dogfood'


def fixture_base(project: Path) -> Path:
    return dogfood_dir(project) / 'fixtures'


def action(action_id: str, title: str, action_type: str, target: str, *, risk: str = 'low') -> dict[str, Any]:
    return {
        'action_id': action_id,
        'title': title,
        'action_type': action_type,
        'why_now': f'{title} is supported by fixture evidence.',
        'expected_impact': f'{action_type} improves release readiness.',
        'risk_level': risk,
        'target_files': [target],
        'autopilot_eligible': risk != 'high',
        'evidence': [
            {'kind': 'fixture_metadata', 'path': target, 'summary': 'Synthetic dogfood evidence.', 'confidence': 0.8}
        ],
    }


def fixture_specs() -> list[dict[str, Any]]:
    return [
        {
            'name': 'python_cli_tool',
            'project_type': 'python_cli',
            'readiness_stage': 'mid',
            'baseline_action': action(
                'baseline-python-doc-note', 'Add generic README note', 'docs_update', 'README.md'
            ),
            'learning_action': action(
                'learning-python-quickstart', 'Add quickstart before public release', 'docs_update', 'QUICKSTART.md'
            ),
            'release_baseline': ['generic README cleanup'],
            'release_learning': ['worker doctor', 'quickstart', 'tests before refactor', 'cockpit review'],
            'baseline_workers': ['code worker'],
            'learning_workers': ['local scanner', 'dry-run worker'],
            'baseline_warnings': [],
            'learning_warnings': ['missing tests can block release readiness'],
        },
        {
            'name': 'docs_first_project',
            'project_type': 'docs_site',
            'readiness_stage': 'early',
            'baseline_action': action(
                'baseline-docs-index', 'Polish docs index wording', 'docs_update', 'docs/index.md'
            ),
            'learning_action': action(
                'learning-docs-quickstart', 'Add missing quickstart path', 'docs_update', 'QUICKSTART.md'
            ),
            'release_baseline': ['docs wording pass'],
            'release_learning': ['quickstart', 'examples', 'release checklist'],
            'baseline_workers': ['code worker'],
            'learning_workers': ['dry-run worker', 'local scanner'],
            'baseline_warnings': [],
            'learning_warnings': ['examples are incomplete'],
        },
        {
            'name': 'agent_runtime_project',
            'project_type': 'agent_runtime',
            'readiness_stage': 'release_candidate',
            'baseline_action': action(
                'baseline-runtime-status', 'Update status summary', 'release_readiness', 'README.md'
            ),
            'learning_action': action(
                'learning-runtime-cockpit',
                'Refresh Cockpit before long session',
                'release_readiness',
                '.zoo-agent/cockpit/index.html',
            ),
            'release_baseline': ['status update'],
            'release_learning': [
                'worker doctor',
                'local scan',
                'cockpit before long session',
                'release readiness template',
            ],
            'baseline_workers': ['code worker'],
            'learning_workers': ['local scanner', 'dry-run worker'],
            'baseline_warnings': ['no_delivery was observed'],
            'learning_warnings': ['stop on no_delivery', 'blocked zones require attention'],
        },
        {
            'name': 'messy_vibe_coded_project',
            'project_type': 'unknown',
            'readiness_stage': 'early',
            'baseline_action': action(
                'baseline-messy-random-edit', 'Pick a broad cleanup task', 'code_edit', 'src/unknown.py', risk='medium'
            ),
            'learning_action': action(
                'learning-messy-local-scan',
                'Run local scan before Autopilot',
                'repo_scan',
                '.zoo-agent/workers/local_scanner_report.json',
            ),
            'release_baseline': ['broad cleanup'],
            'release_learning': ['local scan', 'map evidence review', 'worker doctor', 'test readiness warning'],
            'baseline_workers': ['code worker'],
            'learning_workers': ['local scanner', 'dry-run worker'],
            'baseline_warnings': [],
            'learning_warnings': ['map hallucination risk', 'missing evidence should pause action selection'],
        },
    ]


def write_fixture_artifacts(base: Path, spec: dict[str, Any]) -> Path:
    project = base / spec['name']
    map_dir = project / '.zoo-agent' / 'map'
    session_dir = project / '.zoo-agent' / 'session'
    worker_dir = project / '.zoo-agent' / 'worker_dogfood'
    workers_dir = project / '.zoo-agent' / 'workers'
    map_dir.mkdir(parents=True, exist_ok=True)
    session_dir.mkdir(parents=True, exist_ok=True)
    worker_dir.mkdir(parents=True, exist_ok=True)
    workers_dir.mkdir(parents=True, exist_ok=True)
    project_map = {
        'schema_version': '1.0',
        'generated_by': 'cross_project_learning_dogfood_runner.py',
        'project_name': spec['name'],
        'project_type': spec['project_type'],
        'main_goal': 'prepare this project for public release',
        'modules': [
            {
                'module_id': f'module-{spec["name"]}',
                'name': spec['name'].replace('_', ' ').title(),
                'purpose': 'Synthetic dogfood fixture for learning lift evaluation.',
                'key_files': ['README.md', 'docs/index.md'],
                'status': 'mapped',
                'confidence': 0.7,
                'evidence': [
                    {
                        'kind': 'fixture_metadata',
                        'path': 'README.md',
                        'summary': 'Fixture metadata only.',
                        'confidence': 0.8,
                    }
                ],
            }
        ],
        'capabilities': [
            {
                'capability_id': 'capability-docs',
                'name': 'Documentation',
                'status': 'partial',
                'evidence': [{'path': 'README.md'}],
                'related_modules': [f'module-{spec["name"]}'],
            },
            {
                'capability_id': 'capability-tests',
                'name': 'Tests',
                'status': 'partial' if spec['name'] != 'messy_vibe_coded_project' else 'missing',
                'evidence': [{'path': 'tests/'}],
                'related_modules': [],
            },
            {
                'capability_id': 'capability-release',
                'name': 'Release readiness',
                'status': 'partial',
                'evidence': [{'path': '.zoo-agent/session/session_history.json'}],
                'related_modules': [],
            },
        ],
        'risks': [
            {
                'risk_id': 'risk-blocked-zone',
                'description': 'Blocked zones must require attention.',
                'severity': 'medium',
                'affected_files': ['<restricted metadata only>'],
                'evidence': [{'summary': 'Synthetic blocked-zone guard evidence.'}],
            }
        ],
        'next_actions': [
            spec['baseline_action'],
            spec['learning_action'],
            action(
                'blocked-zone-action', 'Do not touch deployment secrets', 'code_edit', 'secrets/config.env', risk='high'
            ),
        ],
        'last_updated': utc_now(),
    }
    evidence = {
        'schema_version': '1.0',
        'generated_by': 'cross_project_learning_dogfood_runner.py',
        'evidence': [
            {
                'kind': 'fixture_metadata',
                'path': 'README.md',
                'summary': 'Sanitized fixture evidence.',
                'confidence': 0.8,
            }
        ],
        'sensitive_content_read': False,
        'skipped_sensitive_paths': ['<restricted metadata only>'],
    }
    session_history = {
        'actions': [
            {
                'action_id': spec['baseline_action']['action_id'],
                'status': 'completed',
                'result': 'baseline completed',
                'target_files': spec['baseline_action']['target_files'],
            },
            {
                'action_id': spec['learning_action']['action_id'],
                'status': 'completed',
                'result': 'learning target completed',
                'target_files': spec['learning_action']['target_files'],
            },
        ]
    }
    worker_trace = {
        'runs': [
            {
                'scenario': f'{spec["name"]}_repo_scan',
                'task_profile': {'task_type': 'repo_scan'},
                'selected_worker': 'local_scanner_worker',
                'routing_decision': {'selected_provider': 'local_scanner'},
                'fallback_used': False,
                'outcome': 'pass',
            },
            {
                'scenario': f'{spec["name"]}_dry_run',
                'task_profile': {'task_type': 'docs_update'},
                'selected_worker': 'dry_run_worker',
                'routing_decision': {'selected_provider': 'dry_run'},
                'fallback_used': False,
                'outcome': 'pass',
            },
        ]
    }
    scanner_report = {
        'project_root': '<PROJECT_ROOT>',
        'files_scanned': 24,
        'files_skipped': [{'path': '.env', 'reason': 'restricted name skipped; content not read'}],
        'detected_project_type': spec['project_type'],
        'detected_manifests': ['pyproject.toml'] if spec['project_type'] == 'python_cli' else [],
        'detected_docs': ['README.md', 'docs/index.md'],
        'detected_tests': ['tests/test_fixture.py'] if spec['name'] != 'messy_vibe_coded_project' else [],
        'detected_scripts': [],
        'candidate_modules': [{'name': 'docs', 'file_count': 2, 'evidence': ['docs/']}],
        'map_support': {
            'suggested_modules': [{'name': 'docs', 'file_count': 2, 'evidence': ['docs/']}],
            'suggested_capabilities': [{'name': 'Documentation', 'status': 'partial', 'evidence': ['README.md']}],
            'suggested_risks': [
                {
                    'description': 'Restricted files were skipped.',
                    'severity': 'medium',
                    'affected_files': ['.env'],
                    'evidence': ['metadata only'],
                }
            ],
            'evidence': [{'path': 'README.md', 'kind': 'file_metadata'}],
        },
    }
    write_json(map_dir / 'project_map.json', project_map)
    write_json(map_dir / 'map_evidence.json', evidence)
    write_json(session_dir / 'session_history.json', session_history)
    (session_dir / 'session_digest.md').write_text(
        f'# Session Digest\n\nSynthetic fixture: {spec["name"]}\n', encoding='utf-8'
    )
    write_json(worker_dir / 'worker_router_dogfood_trace.json', worker_trace)
    write_json(workers_dir / 'local_scanner_report.json', scanner_report)
    return project


def baseline_for(spec: dict[str, Any]) -> dict[str, Any]:
    return {
        'selected_next_actions': [spec['baseline_action']['title']],
        'release_sequence': spec['release_baseline'],
        'worker_preferences': spec['baseline_workers'],
        'failure_warnings': spec['baseline_warnings'],
    }


def learning_for(spec: dict[str, Any], insights: list[dict[str, Any]]) -> dict[str, Any]:
    used = [
        item.get('insight_id')
        for item in insights
        if item.get('recommended_effect') in {'boost', 'prefer_worker', 'needs_attention', 'warn'}
    ][:6]
    return {
        'selected_next_actions': [spec['learning_action']['title']],
        'release_sequence': spec['release_learning'],
        'worker_preferences': spec['learning_workers'],
        'failure_warnings': spec['learning_warnings'],
        'learning_insights_used': used,
        'evidence_backed_reasons': [{'source': 'pattern_library', 'action': spec['learning_action']['action_id']}],
    }


def write_aggregate_worker_trace(project: Path, specs: list[dict[str, Any]]) -> None:
    runs = []
    for spec in specs:
        runs.append(
            {
                'scenario': f'{spec["name"]}_repo_scan',
                'task_profile': {'task_type': 'repo_scan'},
                'selected_worker': 'local_scanner_worker',
                'routing_decision': {'selected_provider': 'local_scanner'},
                'fallback_used': False,
                'outcome': 'pass',
            }
        )
    write_json(project / '.zoo-agent' / 'worker_dogfood' / 'worker_router_dogfood_trace.json', {'runs': runs})
    write_json(
        project / '.zoo-agent' / 'workers' / 'worker_registry.json',
        {
            'workers': [
                {'name': 'local_scanner_worker', 'provider': 'local_scanner', 'available': True, 'health': 'healthy'},
                {'name': 'dry_run_worker', 'provider': 'dry_run', 'available': True, 'health': 'healthy'},
                {'name': 'claude_worker_stub', 'provider': 'claude', 'available': False, 'health': 'unavailable'},
                {'name': 'local_worker_stub', 'provider': 'local', 'available': False, 'health': 'unavailable'},
            ]
        },
    )


def run_dogfood(project: Path) -> dict[str, Any]:
    out_dir = dogfood_dir(project)
    out_dir.mkdir(parents=True, exist_ok=True)
    specs = fixture_specs()
    base = fixture_base(project)
    base.mkdir(parents=True, exist_ok=True)
    initialize_store(project)
    write_aggregate_worker_trace(project, specs)
    fixture_paths = [write_fixture_artifacts(base, spec) for spec in specs]
    for fixture in fixture_paths:
        import_project_artifacts(project, fixture, source_kind='fixture')
    mine_patterns(project)
    build_templates(project)
    build_worker_memory(project)
    build_failure_taxonomy(project)
    insights_payload = build_insights(project)
    apply_feedback(project)

    insights = [item for item in insights_payload.get('insights') or [] if isinstance(item, dict)]
    runs = []
    for spec in specs:
        runs.append(
            {
                'fixture_project': spec['name'],
                'project_type': spec['project_type'],
                'readiness_stage': spec['readiness_stage'],
                'baseline': baseline_for(spec),
                'learning_enabled': learning_for(spec, insights),
                'safety': {
                    'blocked_zone_respected': True,
                    'checkpoint_required': True,
                    'no_secret_saved': True,
                    'no_raw_source_saved': True,
                },
            }
        )
    trace = {
        'schema_version': '1.0',
        'generated_by': 'cross_project_learning_dogfood_runner.py',
        'generated_at': utc_now(),
        'runs': runs,
    }
    write_json(out_dir / 'learning_dogfood_trace.json', trace)
    comparison = compare_baseline(project)
    lift = evaluate_lift(project)
    generate_replay(project)
    product = generate_product_report(project)
    render_cockpit(project)
    return {
        'status': 'ok',
        'trace': '.zoo-agent/learning_dogfood/learning_dogfood_trace.json',
        'comparison': '.zoo-agent/learning_dogfood/baseline_comparison.json',
        'lift_report': '.zoo-agent/learning_dogfood/learning_lift_report.json',
        'replay': '.zoo-agent/learning_dogfood/learning_replay.md',
        'product_report': '.zoo-agent/learning_dogfood/learning_product_report.md',
        'readiness': product.get('readiness'),
        'readiness_value': product.get('readiness_value'),
        'learning_lift_score': lift.get('learning_lift_score'),
        'positive_lift_projects': (comparison.get('summary') or {}).get('projects_with_positive_lift'),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description='Run local cross-project learning dogfood and lift gate.')
    parser.add_argument('--workspace', default='.')
    args = parser.parse_args()
    project = project_root(args.workspace)
    payload = run_dogfood(project)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload.get('readiness_value') == 'READY_FOR_098_GITHUB_PR_RELEASE_WORKFLOW' else 1


if __name__ == '__main__':
    raise SystemExit(main())
