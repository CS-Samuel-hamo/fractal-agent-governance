#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from public_launch_packager import FEEDBACK_TEMPLATES, public_launch_dir  # noqa: E402
from runtime_common import project_root, utc_now, write_json  # noqa: E402


REQUIRED_SIGNALS = {
    'environment': ['environment', 'os'],
    'install_path': ['install path', 'repo location'],
    'command_used': ['command used', 'commands tried', 'commands used'],
    'expected_behavior': ['expected behavior'],
    'actual_behavior': ['actual behavior'],
    'privacy_removed': ['secrets', 'raw logs', '.env', 'local absolute paths'],
    'zoo_agent_artifacts': ['.zoo-agent'],
    'project_type': ['project type'],
    'project_map': ['project map'],
    'autopilot': ['autopilot'],
    'cockpit': ['cockpit'],
    'release_pr': ['release / pr', 'release/pr'],
}
HIGH_PRIVACY_PATTERNS = [
    re.compile(r'\b(API_KEY|TOKEN|PASSWORD|SECRET)\s*=', re.IGNORECASE),
    re.compile(r'\bghp_[A-Za-z0-9_]{12,}\b'),
    re.compile(r'\b[A-Za-z]:\\[^\s`]+'),
]


def template_texts(project: Path) -> dict[str, str]:
    return {
        rel: (project / rel).read_text(encoding='utf-8-sig', errors='replace')
        for rel in FEEDBACK_TEMPLATES
        if (project / rel).exists() and rel.endswith('.md')
    }


def validate(project: Path) -> dict[str, Any]:
    texts = template_texts(project)
    missing_templates = [rel for rel in FEEDBACK_TEMPLATES if not (project / rel).exists()]
    privacy_warnings: list[dict[str, str]] = []
    total = 0
    passed = 0
    missing_signals: dict[str, list[str]] = {}
    for rel, text in texts.items():
        lower = text.lower()
        missing = []
        for signal, options in REQUIRED_SIGNALS.items():
            total += 1
            if any(option in lower for option in options):
                passed += 1
            else:
                missing.append(signal)
        if missing:
            missing_signals[rel] = missing
        for pattern in HIGH_PRIVACY_PATTERNS:
            if pattern.search(text):
                privacy_warnings.append({'template': rel, 'severity': 'high', 'reason': 'secret_or_absolute_path_marker'})
    score = round(passed / total, 3) if total else 0.0
    recommendation = 'pass'
    if score < 0.9 or any(item['severity'] == 'high' for item in privacy_warnings) or missing_templates:
        recommendation = 'fix_before_launch'
    if score < 0.6 or any(item['severity'] == 'high' for item in privacy_warnings):
        recommendation = 'fail'
    payload = {
        'generated_at': utc_now(),
        'feedback_template_score': score,
        'templates_found': sorted(texts),
        'missing_templates': missing_templates,
        'missing_signals': missing_signals,
        'privacy_warnings': privacy_warnings,
        'recommendation': recommendation,
    }
    write_json(public_launch_dir(project) / 'feedback_template_report.json', payload)
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--workspace', default='.')
    args = parser.parse_args(argv)
    payload = validate(project_root(args.workspace))
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload.get('recommendation') == 'pass' else 1


if __name__ == '__main__':
    raise SystemExit(main())
