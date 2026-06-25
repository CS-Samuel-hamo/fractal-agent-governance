#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from feedback_template_validator import validate
from public_docs_leakage_scanner import scan_texts
from public_launch_packager import FEEDBACK_TEMPLATES


def test_issue_templates_exist() -> None:
    for rel in FEEDBACK_TEMPLATES:
        assert (ROOT / rel).exists(), rel


def test_feedback_templates_collect_product_feedback() -> None:
    report = validate(ROOT)
    assert report['recommendation'] == 'pass', report
    assert report['feedback_template_score'] >= 0.9, report
    assert not report['privacy_warnings'], report
    combined = '\n'.join(
        (ROOT / rel).read_text(encoding='utf-8-sig', errors='replace')
        for rel in FEEDBACK_TEMPLATES
        if rel.endswith('.md')
    )
    for phrase in ['Project Map', 'Autopilot', 'Cockpit', 'release / PR']:
        assert phrase.lower() in combined.lower()


def test_feedback_templates_are_privacy_safe() -> None:
    texts = {
        rel: (ROOT / rel).read_text(encoding='utf-8-sig', errors='replace')
        for rel in FEEDBACK_TEMPLATES
        if rel.endswith('.md')
    }
    report = scan_texts(texts)
    assert report['safe'] is True, report


def main() -> None:
    test_issue_templates_exist()
    test_feedback_templates_collect_product_feedback()
    test_feedback_templates_are_privacy_safe()
    print('feedback template tests passed')


if __name__ == '__main__':
    main()
