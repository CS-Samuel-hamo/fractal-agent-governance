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

from public_alpha_packager import PUBLIC_DOCS, public_alpha_dir
from runtime_common import project_root, utc_now, write_json

REQUIRED_SIGNALS = [
    'ai project operator',
    'give it a project. it keeps moving it forward.',
    'project-level autopilot',
    'project map',
    'cockpit',
    'release',
    'pr',
]

WRAPPER_RISK_PATTERNS = [
    re.compile(r'\bsafer\s+codex\s+wrapper\b', re.IGNORECASE),
    re.compile(r'\bcodex\s+wrapper\s+for\b', re.IGNORECASE),
    re.compile(r'\bis\s+(?:just\s+)?a\s+codex\s+wrapper\b', re.IGNORECASE),
    re.compile(r'\bclaude\s+code\s+replacement\b', re.IGNORECASE),
    re.compile(r'\bgeneric\s+ai\s+coding\s+cli\b', re.IGNORECASE),
]

OVERCLAIM_PATTERNS = [
    re.compile(r'\bfully\s+autonomous\b', re.IGNORECASE),
    re.compile(r'\bguaranteed\b', re.IGNORECASE),
    re.compile(r'\bautomatically\s+creates?\s+(?:remote\s+)?(?:pull\s+requests?|prs?)\b', re.IGNORECASE),
    re.compile(r'\bpushes?\s+to\s+github\s+automatically\b', re.IGNORECASE),
    re.compile(r'\breplaces?\s+human\s+review\b', re.IGNORECASE),
    re.compile(r'\bbetter\s+than\s+codex\b', re.IGNORECASE),
    re.compile(r'\bbetter\s+than\s+claude\b', re.IGNORECASE),
    re.compile(r'\bcloud\s+sync\s+is\s+enabled\b', re.IGNORECASE),
]


def read_public_docs(project: Path) -> dict[str, str]:
    docs: dict[str, str] = {}
    for rel in PUBLIC_DOCS:
        path = project / rel
        if path.exists():
            docs[rel] = path.read_text(encoding='utf-8-sig', errors='replace')
    return docs


def lint_texts(texts: dict[str, str]) -> dict[str, Any]:
    combined = '\n'.join(texts.values())
    lower = combined.lower()
    present = [signal for signal in REQUIRED_SIGNALS if signal in lower]
    missing = [signal for signal in REQUIRED_SIGNALS if signal not in lower]
    bad_phrases: list[str] = []
    for pattern in WRAPPER_RISK_PATTERNS:
        for match in pattern.finditer(combined):
            prefix = combined[max(0, match.start() - 160) : match.start()].lower()
            if any(marker in prefix for marker in ['not ', 'not a ', 'not an ', 'is not ', "isn't ", 'no ']):
                continue
            bad_phrases.append(match.group(0))
    overclaims: list[str] = []
    for pattern in OVERCLAIM_PATTERNS:
        for match in pattern.finditer(combined):
            prefix = combined[max(0, match.start() - 160) : match.start()].lower()
            if any(marker in prefix for marker in ['not ', 'does not ', 'do not ', 'no ', 'never ']):
                continue
            overclaims.append(match.group(0))

    operator_score = len(present) / len(REQUIRED_SIGNALS)
    positioning_score = max(0.0, min(1.0, operator_score - (0.15 * len(bad_phrases)) - (0.2 * len(overclaims))))
    codex_wrapper_risk = 'high' if bad_phrases else ('medium' if 'codex wrapper' not in lower else 'low')
    overclaim_detected = bool(overclaims)
    recommendation = 'pass'
    if positioning_score < 0.9 or operator_score < 0.9 or codex_wrapper_risk != 'low' or overclaim_detected:
        recommendation = 'fix_before_100'
    if positioning_score < 0.6 or codex_wrapper_risk == 'high':
        recommendation = 'fail'

    rewrites = []
    if missing:
        rewrites.append('Add the missing positioning signals: ' + ', '.join(missing))
    if bad_phrases:
        rewrites.append('Replace wrapper language with AI Project Operator language.')
    if overclaims:
        rewrites.append('Remove unsupported automation or superiority claims.')

    return {
        'generated_at': utc_now(),
        'positioning_score': round(positioning_score, 3),
        'codex_wrapper_risk': codex_wrapper_risk,
        'operator_positioning_score': round(operator_score, 3),
        'overclaim_detected': overclaim_detected,
        'bad_phrases': sorted(set([*bad_phrases, *overclaims])),
        'recommended_rewrites': rewrites,
        'recommendation': recommendation,
    }


def lint_project(project: Path) -> dict[str, Any]:
    report = lint_texts(read_public_docs(project))
    write_json(public_alpha_dir(project) / 'public_positioning_report.json', report)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--workspace', default='.')
    args = parser.parse_args(argv)
    project = project_root(args.workspace)
    report = lint_project(project)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report.get('recommendation') == 'pass' else 1


if __name__ == '__main__':
    raise SystemExit(main())
