#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from cross_project_store import load_store, store_dir  # noqa: E402
from runtime_common import project_root  # noqa: E402


READY = 'CROSS_PROJECT_LEARNING_097_READY'
PARTIAL = 'PARTIALLY_READY'


def report_status(project: Path) -> str:
    patterns = load_store(project, 'pattern_library').get('patterns') or []
    templates = load_store(project, 'release_templates').get('templates') or []
    memory = load_store(project, 'worker_memory').get('worker_performance') or []
    failures = load_store(project, 'failure_taxonomy').get('failure_patterns') or []
    insights = load_store(project, 'learning_insights').get('insights') or []
    if patterns and templates and memory and failures and insights:
        return READY
    return PARTIAL


def build_report(project: Path) -> str:
    patterns = load_store(project, 'pattern_library').get('patterns') or []
    templates = load_store(project, 'release_templates').get('templates') or []
    memory = load_store(project, 'worker_memory').get('worker_performance') or []
    failures = load_store(project, 'failure_taxonomy').get('failure_patterns') or []
    insights = load_store(project, 'learning_insights').get('insights') or []
    feedback = json.loads((store_dir(project) / 'learning_feedback_applied.json').read_text(encoding='utf-8-sig')) if (store_dir(project) / 'learning_feedback_applied.json').exists() else {'applied': []}
    status = report_status(project)
    lines = [
        '# Cross-project Learning Report',
        '',
        '## Summary',
        f'- Final judgment: {status}',
        '- Store mode: local-first, repository-local artifacts.',
        '- Privacy: raw source, secrets, absolute paths, and raw backend logs are filtered before storage.',
        '',
        '## Pattern Library',
        f'- Patterns: {len(patterns)}',
        *[f"- {item.get('pattern_id')}: confidence {item.get('confidence')}" for item in patterns[:8]],
        '',
        '## Release Readiness Templates',
        f'- Templates: {len(templates)}',
        *[f"- {item.get('template_id')}: {item.get('goal')}" for item in templates[:6]],
        '',
        '## Worker Performance Memory',
        f'- Rows: {len(memory)}',
        '',
        '## Failure Taxonomy',
        f'- Failure patterns: {len(failures)}',
        '',
        '## Learning Insights',
        f'- Insights: {len(insights)}',
        *[f"- {item.get('message')} ({item.get('recommended_effect')})" for item in insights[:8]],
        '',
        '## Feedback Applied',
        f"- Advisory effects applied: {len(feedback.get('applied') or [])}",
        '- Learning only affects ranking, suggestions, worker preference, Cockpit display, and digest suggestions.',
        '- Learning does not bypass blocked zones, checkpoints, secret handling, push, merge, or delete protections.',
        '',
    ]
    path = store_dir(project) / 'cross_project_learning_report.md'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('\n'.join(lines), encoding='utf-8')
    return str(path)


def generate_report(project: Path) -> dict[str, Any]:
    path = build_report(project)
    return {'status': report_status(project), 'report': '.zoo-agent/learning/cross_project/cross_project_learning_report.md'}


def main() -> int:
    parser = argparse.ArgumentParser(description='Generate local cross-project learning report.')
    parser.add_argument('--workspace', default='.')
    args = parser.parse_args()
    project = project_root(args.workspace)
    payload = generate_report(project)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
