#!/usr/bin/env python3
from __future__ import annotations

import json
import tempfile
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from feedback_intake_schema import FEEDBACK_DIR, validate_item, write_schema  # noqa: E402
from feedback_signal_classifier import classify  # noqa: E402


def write_items(project: Path) -> None:
    out = project / FEEDBACK_DIR
    out.mkdir(parents=True, exist_ok=True)
    items = [
        {
            'feedback_id': 'f1',
            'date': '2026-06-21',
            'source': 'manual',
            'user_type': 'solo_dev',
            'project_type': 'python_cli',
            'flow': 'positioning',
            'summary': 'Is this just a Codex wrapper?',
            'raw_feedback_sanitized': 'Why not just use Codex directly?',
            'severity': 'medium',
            'product_signal': 'positioning',
            'privacy_checked': True,
            'contains_secret': False,
            'status': 'new',
        },
        {
            'feedback_id': 'f2',
            'date': '2026-06-21',
            'source': 'manual',
            'user_type': 'oss_maintainer',
            'project_type': 'library',
            'flow': 'project_map',
            'summary': 'Project Map helped me understand project state.',
            'raw_feedback_sanitized': 'The map is useful.',
            'severity': 'low',
            'product_signal': 'delight',
            'privacy_checked': True,
            'contains_secret': False,
            'status': 'new',
        },
    ]
    with (out / 'feedback_items.jsonl').open('w', encoding='utf-8') as handle:
        for item in items:
            handle.write(json.dumps(item) + '\n')


def test_classifier_detects_positioning_and_map_signals() -> None:
    project = Path(tempfile.mkdtemp(prefix='feedback-signals-'))
    write_items(project)
    payload = classify(project)
    types = {signal['type'] for signal in payload['signals']}
    assert 'positioning' in types
    assert 'map_quality' in types
    assert any('Codex wrapper' in risk for risk in payload['top_product_risks'])


def test_schema_sanitizes_secret_and_path() -> None:
    item, errors = validate_item(
        {
            'feedback_id': 'secret',
            'date': '2026-06-21',
            'source': 'manual',
            'user_type': 'solo_dev',
            'project_type': 'python_cli',
            'flow': 'first_run',
            'summary': 'token=gho_secret from C:\\Users\\someone\\repo',
            'raw_feedback_sanitized': 'github_pat_secret',
            'severity': 'high',
            'product_signal': 'friction',
            'privacy_checked': False,
            'contains_secret': False,
            'status': 'new',
        }
    )
    assert not errors
    assert '<redacted-secret>' in item['summary'] or '<redacted-secret>' in item['raw_feedback_sanitized']
    assert '<redacted-path>' in item['summary']
    assert item['privacy_checked'] is True


def test_schema_writes() -> None:
    project = Path(tempfile.mkdtemp(prefix='feedback-schema-'))
    payload = write_schema(project)
    assert payload['path'] == '.zoo-agent/feedback/feedback_items.jsonl'
    assert (project / FEEDBACK_DIR / 'feedback_intake_schema.json').exists()


def main() -> int:
    test_classifier_detects_positioning_and_map_signals()
    test_schema_sanitizes_secret_and_path()
    test_schema_writes()
    print('feedback signal classifier tests passed')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
