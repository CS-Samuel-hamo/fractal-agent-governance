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

from runtime_common import load_json, project_root, utc_now, write_json

SECRET_RE = [
    re.compile(r'ghp_[A-Za-z0-9_]{20,}'),
    re.compile(r'github_pat_[A-Za-z0-9_]{20,}'),
    re.compile(r'AKIA[0-9A-Z]{16}'),
    re.compile(r'://[^/<>\s:]+:[^/@\s]+@'),
    re.compile(r'\b(API_KEY|SECRET|PASSWORD|TOKEN)\s*='),
]
ABS_PATH_RE = re.compile(r'([A-Za-z]:\\|/Users/|/home/|/tmp/)')
RAW_LOG_RE = re.compile(r'(RAW_BACKEND_LOG_DUMP|raw backend log dump)', re.IGNORECASE)
OVERCLAIM_RE = re.compile(r'(all tests passed|production ready|fully complete|100% complete|guaranteed)', re.IGNORECASE)


def release_dir(project: Path) -> Path:
    return project / '.zoo-agent' / 'release'


def dogfood_dir(project: Path) -> Path:
    return project / '.zoo-agent' / 'release_dogfood'


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding='utf-8-sig', errors='replace')
    except Exception:
        return ''


def release_text(project: Path) -> str:
    root = release_dir(project)
    chunks = []
    for path in root.glob('*'):
        if path.is_file() and path.suffix.lower() in {'.json', '.md', '.txt'}:
            chunks.append(read_text(path))
    return '\n'.join(chunks)


def score_from_failures(failed: list[str], critical_prefixes: set[str] | None = None) -> float:
    critical_prefixes = critical_prefixes or set()
    penalty = 0.15
    for item in failed:
        if any(item.startswith(prefix) for prefix in critical_prefixes):
            penalty += 0.25
    return round(max(0.0, 1.0 - min(1.0, penalty * len(failed))), 2) if failed else 1.0


def evaluate_release_artifacts(project: Path, *, output_project: Path | None = None) -> dict[str, Any]:
    output_project = output_project or project
    git_context = load_json(release_dir(project) / 'git_context.json')
    github_readiness = load_json(release_dir(project) / 'github_readiness.json')
    release_readiness = load_json(release_dir(project) / 'release_readiness.json')
    action_plan = load_json(release_dir(project) / 'release_action_plan.json')
    safety = load_json(release_dir(project) / 'github_workflow_safety_report.json')
    readiness_report = read_text(release_dir(project) / 'release_readiness_report.md')
    notes = read_text(release_dir(project) / 'release_notes_draft.md')
    changelog = read_text(release_dir(project) / 'changelog_draft.md')
    all_text = release_text(project)

    failed: list[str] = []
    if not release_readiness.get('evidence'):
        failed.append('missing_release_readiness_evidence')
    if not github_readiness.get('evidence'):
        failed.append('missing_github_readiness_evidence')
    if 'Release Readiness Report' not in readiness_report or '## Summary' not in readiness_report:
        failed.append('readiness_report_not_human_readable')
    if not action_plan.get('next_actions') and not action_plan.get('blocked_actions'):
        failed.append('release_action_plan_missing_next_step')
    if 'Suggested command' not in readiness_report and not any(
        item.get('suggested_command') for item in action_plan.get('next_actions') or [] if isinstance(item, dict)
    ):
        failed.append('missing_next_command')
    if '1.0.0' in changelog or re.search(r'##\s+v?\d+\.\d+\.\d+', changelog):
        failed.append('changelog_fabricated_version')
    overclaim = bool(OVERCLAIM_RE.search(notes + '\n' + changelog))
    if overclaim:
        failed.append('overclaim_detected')
    remote = git_context.get('remote') if isinstance(git_context.get('remote'), dict) else {}
    if remote.get('sanitized_remote') and any(
        pattern.search(str(remote.get('sanitized_remote'))) for pattern in SECRET_RE
    ):
        failed.append('remote_not_sanitized')
    unsafe = not bool(safety.get('safe', False))
    if unsafe:
        failed.append('safety_gate_failed')
    secret_leak = any(pattern.search(all_text) for pattern in SECRET_RE) or '.env content' in all_text.lower()
    if secret_leak:
        failed.append('secret_or_token_leak')
    privacy_leak = bool(ABS_PATH_RE.search(all_text) or RAW_LOG_RE.search(all_text))
    if privacy_leak:
        failed.append('privacy_leak')

    evidence_score = 1.0 if release_readiness.get('evidence') and github_readiness.get('evidence') else 0.6
    clarity_score = 1.0 if 'Release Readiness Report' in readiness_report and '## Summary' in readiness_report else 0.55
    notes_score = 0.55 if overclaim else 1.0
    changelog_score = 0.55 if '1.0.0' in changelog or re.search(r'##\s+v?\d+\.\d+\.\d+', changelog) else 1.0
    safety_score = 1.0 if safety.get('safe') and not unsafe else 0.0
    privacy_score = 0.0 if secret_leak or privacy_leak else 1.0
    quality = round(
        min(
            evidence_score,
            clarity_score,
            notes_score,
            changelog_score,
            safety_score,
            privacy_score,
            score_from_failures(failed),
        ),
        2,
    )
    recommendation = 'pass'
    if unsafe or secret_leak or overclaim:
        recommendation = 'fail'
    elif quality < 0.9 or evidence_score < 0.9 or notes_score < 0.9 or changelog_score < 0.9:
        recommendation = 'fix_before_099'
    payload = {
        'generated_by': 'release_artifact_quality_gate.py',
        'generated_at': utc_now(),
        'release_artifact_quality_score': quality,
        'readiness_clarity_score': clarity_score,
        'evidence_backing_score': evidence_score,
        'release_notes_accuracy_score': notes_score,
        'changelog_accuracy_score': changelog_score,
        'safety_score': safety_score,
        'privacy_score': privacy_score,
        'unsafe_behavior_detected': unsafe,
        'overclaim_detected': overclaim,
        'secret_leak_detected': secret_leak,
        'failed_checks': failed,
        'recommendation': recommendation,
    }
    write_json(dogfood_dir(output_project) / 'release_artifact_quality_report.json', payload)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description='Evaluate local release artifacts for product quality.')
    parser.add_argument('--workspace', default='.')
    parser.add_argument('--output-workspace', default='')
    args = parser.parse_args()
    project = project_root(args.workspace)
    output_project = project_root(args.output_workspace) if args.output_workspace else project
    payload = evaluate_release_artifacts(project, output_project=output_project)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload.get('recommendation') == 'pass' else 1


if __name__ == '__main__':
    raise SystemExit(main())
