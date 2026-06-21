#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from feedback_intake_schema import feedback_dir, load_items, write_schema  # noqa: E402
from feedback_triage_engine import category_for, triage  # noqa: E402
from runtime_common import project_root, utc_now, write_json  # noqa: E402


SEVERITY = {'critical': 100.0, 'high': 75.0, 'medium': 45.0, 'low': 20.0}
CATEGORY_BOOST = {
    'privacy/safety concern': 50,
    'install friction': 35,
    'first-run confusion': 35,
    'positioning confusion': 30,
    'session reliability': 25,
    'cockpit clarity': 22,
    'release/pr usefulness': 18,
    'project map quality': 18,
    'feature request': -10,
    'not now': -30,
}


def bucket(category: str, score: float, product_signal: str) -> str:
    if category == 'privacy/safety concern' or score >= 95:
        return 'patch'
    if category in {'install friction', 'first-run confusion', 'positioning confusion', 'session reliability', 'cockpit clarity', 'docs gap', 'bug'}:
        return 'patch'
    if product_signal == 'missing_capability' or category in {'feature request', 'project map quality', 'release/pr usefulness', 'worker availability'}:
        return 'roadmap'
    if category == 'not now':
        return 'later'
    return 'later'


def rank(project: Path) -> dict[str, Any]:
    write_schema(project)
    triage(project)
    items = load_items(project, create_sample=True)
    ranked: list[dict[str, Any]] = []
    for item in items:
        category = category_for(item)
        score = SEVERITY.get(str(item.get('severity') or 'low'), 20.0) + CATEGORY_BOOST.get(category, 0)
        score = max(0.0, min(100.0, score))
        recommended = bucket(category, score, str(item.get('product_signal') or 'unknown'))
        ranked.append(
            {
                'feedback_id': item.get('feedback_id'),
                'priority_score': round(score, 1),
                'recommended_bucket': recommended,
                'reason': f'{category}; severity={item.get("severity")}',
            }
        )
    ranked.sort(key=lambda row: row['priority_score'], reverse=True)
    payload = {
        'generated_at': utc_now(),
        'ranked_items': ranked,
        'top_patch_items': [item['feedback_id'] for item in ranked if item['recommended_bucket'] == 'patch'][:5],
        'top_roadmap_items': [item['feedback_id'] for item in ranked if item['recommended_bucket'] == 'roadmap'][:5],
    }
    write_json(feedback_dir(project) / 'feedback_priority_report.json', payload)
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--workspace', default='.')
    args = parser.parse_args(argv)
    payload = rank(project_root(args.workspace))
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
