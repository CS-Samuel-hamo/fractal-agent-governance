#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from cross_project_store import load_store, write_store  # noqa: E402
from runtime_common import load_json, project_root  # noqa: E402


def insight(insight_id: str, kind: str, applies_to: str, message: str, evidence: list[dict[str, Any]], confidence: float, effect: str) -> dict[str, Any]:
    if confidence < 0.5 and effect == 'boost':
        effect = 'warn'
    return {
        'insight_id': insight_id,
        'type': kind,
        'applies_to': applies_to,
        'message': message,
        'evidence': evidence[:8],
        'confidence': round(confidence, 3),
        'recommended_effect': effect,
    }


def build_insights(project: Path) -> dict[str, Any]:
    patterns = load_store(project, 'pattern_library').get('patterns') or []
    templates = load_store(project, 'release_templates').get('templates') or []
    worker_memory = load_store(project, 'worker_memory').get('worker_performance') or []
    failures = load_store(project, 'failure_taxonomy').get('failure_patterns') or []
    project_map = load_json(project / '.zoo-agent' / 'map' / 'project_map.json')
    insights = []
    for pattern in sorted(patterns, key=lambda item: item.get('confidence', 0), reverse=True)[:5]:
        effect = 'boost' if float(pattern.get('confidence') or 0) >= 0.5 and pattern.get('recommended_next_action_type') != 'failure_warning' else 'warn'
        insights.append(
            insight(
                f"insight-{pattern.get('pattern_id')}",
                'next_action_boost' if effect == 'boost' else 'next_action_warning',
                str(pattern.get('recommended_next_action_type') or ''),
                str(pattern.get('why_it_works') or pattern.get('situation') or ''),
                [item for item in pattern.get('evidence') or [] if isinstance(item, dict)],
                float(pattern.get('confidence') or 0.0),
                effect,
            )
        )
    template = next((item for item in templates if item.get('template_id') in {'agent_runtime_release', 'cli_tool_release'}), templates[0] if templates else {})
    if template:
        insights.append(
            insight(
                f"insight-template-{template.get('template_id')}",
                'readiness_template',
                str(template.get('goal') or 'release'),
                f"Use {template.get('template_id')} as a local readiness path.",
                [{'template_id': template.get('template_id')}],
                float(template.get('confidence') or 0.5),
                'warn' if float(template.get('confidence') or 0) < 0.5 else 'boost',
            )
        )
    preferred = next((item for item in worker_memory if item.get('recommended_use') == 'prefer' and item.get('worker_role') == 'local_scanner'), None)
    if preferred:
        insights.append(
            insight(
                'insight-worker-local-scanner',
                'worker_preference',
                str(preferred.get('task_type') or 'repo_scan'),
                'Prefer Local Scanner for metadata-backed project map support.',
                [item for item in preferred.get('evidence') or [] if isinstance(item, dict)],
                float(preferred.get('avg_confidence') or 0.6),
                'prefer_worker',
            )
        )
    blocker = next((item for item in failures if item.get('failure_type') == 'blocked_zone_attempt'), None)
    if blocker:
        insights.append(
            insight(
                'insight-failure-blocked-zone',
                'failure_warning',
                'blocked_zone',
                str(blocker.get('recommended_response') or 'Blocked zones require attention.'),
                [item for item in blocker.get('evidence') or [] if isinstance(item, dict)],
                0.8,
                'needs_attention',
            )
        )
    if project_map.get('next_actions') and not insights:
        insights.append(insight('insight-uncertain', 'next_action_warning', 'project', 'No strong cross-project pattern yet; continue collecting local session evidence.', [{'source': 'current_project_map'}], 0.3, 'warn'))
    return write_store(project, 'learning_insights', {'generated_by': 'cross_project_insight_engine.py', 'insights': insights})


def main() -> int:
    parser = argparse.ArgumentParser(description='Build advisory cross-project learning insights.')
    parser.add_argument('--workspace', default='.')
    args = parser.parse_args()
    project = project_root(args.workspace)
    payload = build_insights(project)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
