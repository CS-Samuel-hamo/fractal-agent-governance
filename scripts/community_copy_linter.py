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

from public_launch_packager import public_launch_dir  # noqa: E402
from public_positioning_linter import lint_texts  # noqa: E402
from runtime_common import project_root, utc_now, write_json  # noqa: E402


REQUIRED_SECTIONS = [
    'GitHub Repo Description',
    'Hacker News Style Post',
    'Reddit / LocalLLaMA / ClaudeAI / OpenAI Community Style Post',
    'X / LinkedIn Short Post',
    'One-paragraph Founder Note',
    'Feedback Request Post',
    'Short Demo Script',
]
BAD_PATTERNS = [
    re.compile(r'\bfull autonomy\b|\bfully autonomous\b', re.IGNORECASE),
    re.compile(r'\bcreates? remote github pr', re.IGNORECASE),
    re.compile(r'\bcloud sync\b(?! or telemetry)', re.IGNORECASE),
    re.compile(r'\bbetter (?:code|coding) than\b', re.IGNORECASE),
]


def lint(project: Path) -> dict[str, Any]:
    path = project / 'COMMUNITY_POSTS.md'
    text = path.read_text(encoding='utf-8-sig', errors='replace') if path.exists() else ''
    positioning = lint_texts({'COMMUNITY_POSTS.md': text})
    missing = [section for section in REQUIRED_SECTIONS if section not in text]
    bad_phrases = list(positioning.get('bad_phrases') or [])
    for pattern in BAD_PATTERNS:
        for match in pattern.finditer(text):
            prefix = text[max(0, match.start() - 80) : match.start()].lower()
            if 'not ' in prefix or 'no ' in prefix or 'does not ' in prefix:
                continue
            bad_phrases.append(match.group(0))
    section_score = (len(REQUIRED_SECTIONS) - len(missing)) / len(REQUIRED_SECTIONS)
    overclaim = bool(bad_phrases) or bool(positioning.get('overclaim_detected'))
    score = round(max(0.0, min(1.0, (float(positioning.get('operator_positioning_score') or 0) + section_score) / 2 - (0.2 if overclaim else 0))), 3)
    recommendation = 'pass'
    if score < 0.85 or overclaim or positioning.get('codex_wrapper_risk') != 'low':
        recommendation = 'fix_before_launch'
    if score < 0.6 or positioning.get('codex_wrapper_risk') == 'high':
        recommendation = 'fail'
    payload = {
        'generated_at': utc_now(),
        'community_copy_score': score,
        'positioning_score': positioning.get('operator_positioning_score') or 0.0,
        'overclaim_detected': overclaim,
        'codex_wrapper_risk': positioning.get('codex_wrapper_risk') or 'high',
        'bad_phrases': sorted(set(bad_phrases)),
        'missing_sections': missing,
        'recommended_rewrites': positioning.get('recommended_rewrites') or [],
        'recommendation': recommendation,
    }
    write_json(public_launch_dir(project) / 'community_copy_report.json', payload)
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--workspace', default='.')
    args = parser.parse_args(argv)
    payload = lint(project_root(args.workspace))
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload.get('recommendation') == 'pass' else 1


if __name__ == '__main__':
    raise SystemExit(main())
