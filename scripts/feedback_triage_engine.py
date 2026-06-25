#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from feedback_intake_schema import feedback_dir, load_items, write_schema
from runtime_common import project_root, utc_now, write_json

CATEGORY_BY_FLOW = {
    'install': 'install friction',
    'first_run': 'first-run confusion',
    'positioning': 'positioning confusion',
    'project_map': 'project map quality',
    'session': 'session reliability',
    'cockpit': 'cockpit clarity',
    'release': 'release/pr usefulness',
    'pr': 'release/pr usefulness',
    'worker': 'worker availability',
    'docs': 'docs gap',
}


def category_for(item: dict[str, Any]) -> str:
    text = f'{item.get("summary", "")} {item.get("raw_feedback_sanitized", "")}'.lower()
    if any(word in text for word in ['secret', 'token', 'privacy', 'unsafe', 'push', 'merge']):
        return 'privacy/safety concern'
    if any(word in text for word in ['codex wrapper', 'just use codex', 'why not just use codex']):
        return 'positioning confusion'
    if item.get('product_signal') == 'missing_capability':
        return 'feature request'
    if item.get('product_signal') == 'bug':
        return 'bug'
    return CATEGORY_BY_FLOW.get(str(item.get('flow') or 'unknown'), 'not now')


def triage(project: Path) -> dict[str, Any]:
    write_schema(project)
    items = load_items(project, create_sample=True)
    severity_counts = Counter(str(item.get('severity') or 'low') for item in items)
    categories: list[dict[str, Any]] = []
    cat_counts = Counter(category_for(item) for item in items)
    for category, count in sorted(cat_counts.items()):
        categories.append({'category': category, 'count': count})

    must_fix: list[str] = []
    patch: list[str] = []
    roadmap: list[str] = []
    later: list[str] = []
    privacy: list[str] = []
    for item in items:
        cat = category_for(item)
        fid = str(item.get('feedback_id') or '')
        sev = str(item.get('severity') or 'low')
        if cat == 'privacy/safety concern' or sev == 'critical':
            must_fix.append(fid)
            privacy.append(fid)
        elif cat in {
            'install friction',
            'first-run confusion',
            'positioning confusion',
            'session reliability',
            'cockpit clarity',
            'docs gap',
            'bug',
        }:
            patch.append(fid)
        elif cat in {
            'project map quality',
            'autopilot next_action quality',
            'worker availability',
            'release/pr usefulness',
            'feature request',
        }:
            roadmap.append(fid)
        else:
            later.append(fid)

    if must_fix:
        recommendation = 'ready_for_104_patch_plan'
    elif patch:
        recommendation = 'ready_for_104_patch_plan'
    elif items:
        recommendation = 'collect_more_feedback'
    else:
        recommendation = 'fix_feedback_pipeline'

    payload = {
        'generated_at': utc_now(),
        'triage_summary': {
            'total': len(items),
            'critical': severity_counts.get('critical', 0),
            'high': severity_counts.get('high', 0),
            'medium': severity_counts.get('medium', 0),
            'low': severity_counts.get('low', 0),
        },
        'categories': categories,
        'must_fix_now': must_fix,
        'patch_candidates': patch,
        'roadmap_candidates': roadmap,
        'wont_fix_or_later': later,
        'privacy_flags': privacy,
        'recommendation': recommendation,
    }
    write_json(feedback_dir(project) / 'feedback_triage_report.json', payload)
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--workspace', default='.')
    args = parser.parse_args(argv)
    payload = triage(project_root(args.workspace))
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload.get('recommendation') != 'fix_feedback_pipeline' else 1


if __name__ == '__main__':
    raise SystemExit(main())
