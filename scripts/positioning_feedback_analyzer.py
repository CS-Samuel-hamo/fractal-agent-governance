#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from feedback_intake_schema import feedback_dir, load_items, write_schema
from runtime_common import project_root, utc_now, write_json


def analyze(project: Path) -> dict[str, Any]:
    write_schema(project)
    items = load_items(project, create_sample=True)
    confusing: list[str] = []
    for item in items:
        text = f'{item.get("summary", "")} {item.get("raw_feedback_sanitized", "")}'.lower()
        if any(
            marker in text for marker in ['codex wrapper', 'just use codex', 'why not just use codex', 'github bot']
        ):
            confusing.append(str(item.get('feedback_id')))
    total = max(len(items), 1)
    confusion_rate = round(len(confusing) / total, 3)
    risk = 'high' if confusion_rate >= 0.35 else 'medium' if confusion_rate >= 0.15 else 'low'
    changes = []
    if confusing:
        changes.extend(
            [
                'Add a sharper README line: Codex and Claude are workers, not the product.',
                'Keep FAQ answer for "Why not just use Codex?" prominent.',
                'Use community copy that leads with Project Map + Session + Cockpit.',
            ]
        )
    payload = {
        'generated_at': utc_now(),
        'operator_positioning_understood': risk != 'high',
        'codex_wrapper_confusion_rate': confusion_rate,
        'top_confusing_phrases': ['Why not just use Codex?'] if confusing else [],
        'recommended_doc_changes': changes,
        'positioning_risk': risk,
    }
    write_json(feedback_dir(project) / 'positioning_feedback_report.json', payload)
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--workspace', default='.')
    args = parser.parse_args(argv)
    payload = analyze(project_root(args.workspace))
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
