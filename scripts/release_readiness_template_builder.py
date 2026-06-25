#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from cross_project_store import load_store, write_store
from runtime_common import project_root


def step(number: int, action_type: str, reason: str, evidence: list[str]) -> dict[str, Any]:
    return {'step': number, 'action_type': action_type, 'reason': reason, 'required_evidence': evidence}


def build_templates(project: Path) -> dict[str, Any]:
    patterns = load_store(project, 'pattern_library').get('patterns') or []
    evidence = [item.get('pattern_id') for item in patterns[:8] if item.get('pattern_id')]
    templates = [
        {
            'template_id': 'cli_tool_release',
            'project_type': 'python_cli',
            'goal': 'cli_tool_release',
            'recommended_sequence': [
                step(1, 'repo_scan', 'Build evidence before selecting release tasks.', ['local_scanner_report']),
                step(
                    2,
                    'docs_update',
                    'README and quickstart should be clear before public release.',
                    ['README', 'QUICKSTART'],
                ),
                step(3, 'test_update', 'Smoke tests should pass before release claims.', ['tests']),
                step(
                    4,
                    'worker_doctor',
                    'Confirm local worker capability before real execution.',
                    ['worker_doctor_report'],
                ),
                step(5, 'cockpit', 'Generate a readable project state view.', ['cockpit']),
            ],
            'must_have': ['README', 'install instructions', 'quickstart', 'tests or smoke validation'],
            'nice_to_have': ['examples', 'cockpit report', 'worker readiness'],
            'common_blockers': ['missing tests', 'unclear install path', 'worker unavailable'],
            'confidence': 0.72 if evidence else 0.55,
            'evidence': evidence,
        },
        {
            'template_id': 'python_library_release',
            'project_type': 'python_library',
            'goal': 'library_release',
            'recommended_sequence': [
                step(1, 'repo_scan', 'Identify package metadata and tests.', ['pyproject', 'tests']),
                step(2, 'test_update', 'Validate public API before packaging.', ['tests']),
                step(3, 'docs_update', 'Document library usage and compatibility.', ['docs']),
            ],
            'must_have': ['package metadata', 'tests', 'usage docs'],
            'nice_to_have': ['examples', 'changelog'],
            'common_blockers': ['missing version metadata', 'test failure'],
            'confidence': 0.62,
            'evidence': evidence[:4],
        },
        {
            'template_id': 'docs_first_release',
            'project_type': 'docs_site',
            'goal': 'public_release',
            'recommended_sequence': [
                step(1, 'docs_update', 'Clarify user-facing entry point.', ['README or docs index']),
                step(2, 'repo_scan', 'Check docs structure and missing pages.', ['local_scanner_report']),
            ],
            'must_have': ['entry page', 'quickstart'],
            'nice_to_have': ['examples', 'screenshots'],
            'common_blockers': ['missing navigation', 'stale examples'],
            'confidence': 0.58,
            'evidence': evidence[:3],
        },
        {
            'template_id': 'agent_runtime_release',
            'project_type': 'agent_runtime',
            'goal': 'github_alpha',
            'recommended_sequence': [
                step(1, 'worker_doctor', 'Confirm local execution capability.', ['worker_doctor_report']),
                step(2, 'repo_scan', 'Refresh Project Map evidence.', ['local_scanner_report']),
                step(3, 'docs_update', 'Keep product surface user-first.', ['README', 'QUICKSTART']),
                step(4, 'test_update', 'Run product and safety gates.', ['test reports']),
                step(5, 'cockpit', 'Generate Project Cockpit before handoff.', ['cockpit']),
            ],
            'must_have': ['safe CLI UX', 'local scanner', 'worker fallback', 'product docs'],
            'nice_to_have': ['dogfood report', 'cockpit'],
            'common_blockers': ['backend unavailable', 'internal leakage', 'missing readiness evidence'],
            'confidence': 0.78 if evidence else 0.6,
            'evidence': evidence,
        },
    ]
    return write_store(
        project, 'release_templates', {'generated_by': 'release_readiness_template_builder.py', 'templates': templates}
    )


def main() -> int:
    parser = argparse.ArgumentParser(description='Build local release readiness templates.')
    parser.add_argument('--workspace', default='.')
    args = parser.parse_args()
    project = project_root(args.workspace)
    payload = build_templates(project)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
