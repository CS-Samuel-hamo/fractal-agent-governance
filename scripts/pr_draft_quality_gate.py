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

from runtime_common import load_json, project_root, utc_now, write_json  # noqa: E402


SECRET_RE = [
    re.compile(r'ghp_[A-Za-z0-9_]{20,}'),
    re.compile(r'github_pat_[A-Za-z0-9_]{20,}'),
    re.compile(r'://[^/<>\s:]+:[^/@\s]+@'),
    re.compile(r'\b(API_KEY|SECRET|PASSWORD|TOKEN)\s*='),
]
ABS_PATH_RE = re.compile(r'([A-Za-z]:\\|/Users/|/home/|/tmp/)')
PASS_CLAIM_RE = re.compile(r'(tests? passed|all checks passed|validated successfully)', re.IGNORECASE)


def release_dir(project: Path) -> Path:
    return project / '.zoo-agent' / 'release'


def dogfood_dir(project: Path) -> Path:
    return project / '.zoo-agent' / 'release_dogfood'


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding='utf-8-sig', errors='replace')
    except Exception:
        return ''


def heading_score(draft: str) -> float:
    headings = ['## Summary', '## What changed', '## Why', '## Evidence', '## Test plan', '## Risks', '## Rollback', '## Review focus', '## Not included']
    found = sum(1 for item in headings if item in draft)
    return round(found / len(headings), 2)


def evaluate_pr_draft(project: Path, *, output_project: Path | None = None) -> dict[str, Any]:
    output_project = output_project or project
    plan = load_json(release_dir(project) / 'pr_plan.json')
    git_context = load_json(release_dir(project) / 'git_context.json')
    safety = load_json(release_dir(project) / 'github_workflow_safety_report.json')
    draft = read_text(release_dir(project) / 'pr_draft.md')
    failed: list[str] = []
    changed = [str(item).replace('\\', '/') for item in plan.get('changed_areas') or []]
    git_changed = [str(item).replace('\\', '/') for item in git_context.get('changed_files') or []]

    if not plan.get('pr_title'):
        failed.append('missing_pr_title')
    if not plan.get('summary') or '## Summary' not in draft:
        failed.append('missing_summary')
    for heading in ['## What changed', '## Why', '## Evidence', '## Test plan', '## Risks', '## Rollback', '## Review focus', '## Not included']:
        if heading not in draft:
            failed.append(f'missing_{heading.lower().replace("## ", "").replace(" ", "_")}')
    fake_changed = any(item not in git_changed for item in changed)
    if fake_changed:
        failed.append('fake_changed_files')
    if not changed and 'Draft only; no code changes included yet.' not in draft:
        failed.append('missing_draft_only_notice')
    fabricated_tests = bool(PASS_CLAIM_RE.search(draft)) and 'Not run in this workflow' not in draft
    if fabricated_tests:
        failed.append('fabricated_test_result')
    if 'Not run in this workflow' not in draft:
        failed.append('missing_not_run_notice')
    secret_leak = any(pattern.search(draft) for pattern in SECRET_RE) or bool(ABS_PATH_RE.search(draft)) or 'RAW_BACKEND_LOG' in draft
    if secret_leak:
        failed.append('secret_or_path_leak')
    if not safety.get('safe', False):
        failed.append('safety_gate_failed')

    copy_score = heading_score(draft)
    test_score = 0.0 if fabricated_tests else (1.0 if 'Not run in this workflow' in draft else 0.75)
    risk_score = 1.0 if '## Risks' in draft and 'Risk level:' in draft else 0.6
    review_score = 1.0 if '## Review focus' in draft and (plan.get('review_focus') or []) else 0.7
    honesty_score = 1.0 if not fabricated_tests and not fake_changed and (changed or 'Draft only; no code changes included yet.' in draft) else 0.0
    privacy_score = 0.0 if secret_leak else 1.0
    quality = round(min(copy_score, test_score, risk_score, review_score, honesty_score, privacy_score), 2)
    recommendation = 'pass'
    if fabricated_tests or secret_leak or fake_changed:
        recommendation = 'fail'
    elif quality < 0.9 or copy_score < 0.85 or honesty_score < 1.0:
        recommendation = 'fix_before_099'
    payload = {
        'generated_by': 'pr_draft_quality_gate.py',
        'generated_at': utc_now(),
        'pr_draft_quality_score': quality,
        'copy_paste_readiness_score': copy_score,
        'test_plan_accuracy_score': test_score,
        'risk_clarity_score': risk_score,
        'review_focus_score': review_score,
        'draft_honesty_score': honesty_score,
        'fabrication_detected': fabricated_tests or fake_changed,
        'secret_leak_detected': secret_leak,
        'failed_checks': failed,
        'recommendation': recommendation,
    }
    write_json(dogfood_dir(output_project) / 'pr_draft_quality_report.json', payload)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description='Evaluate a local PR draft for copy-paste readiness.')
    parser.add_argument('--workspace', default='.')
    parser.add_argument('--output-workspace', default='')
    args = parser.parse_args()
    project = project_root(args.workspace)
    output_project = project_root(args.output_workspace) if args.output_workspace else project
    payload = evaluate_pr_draft(project, output_project=output_project)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload.get('recommendation') == 'pass' else 1


if __name__ == '__main__':
    raise SystemExit(main())
