#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from runtime_common import load_json, project_root


def dogfood_dir(project: Path) -> Path:
    return project / '.zoo-agent' / 'release_dogfood'


def generate_replay(project: Path) -> dict[str, str]:
    trace = load_json(dogfood_dir(project) / 'release_workflow_dogfood_trace.json')
    artifact_quality = load_json(dogfood_dir(project) / 'release_artifact_quality_report.json')
    pr_quality = load_json(dogfood_dir(project) / 'pr_draft_quality_report.json')
    runs = [item for item in trace.get('runs') or [] if isinstance(item, dict)]
    lines = [
        '# Release Workflow Replay',
        '',
        '## Goal',
        '- Validate whether the local release / PR workflow closes the AI Project Operator product loop.',
        '',
        '## Git context',
        '- Each scenario generated local Git context without network access.',
        '- Token-like remotes were sanitized before storage.',
        '',
        '## GitHub readiness',
        '- Readiness was checked from local Git state, Project Map, session artifacts, and learning templates.',
        '- Missing docs, tests, or Git context were recorded as blockers or next actions instead of being treated as success.',
        '',
        '## Scenario replay',
    ]
    for item in runs:
        lines.extend(
            [
                f'### {item.get("scenario")}',
                f'- Outcome: {item.get("outcome")}',
                f'- Commands: {", ".join(item.get("commands") or []) or "not available"}',
                f'- Safety gate passed: {item.get("safety_gate_passed")}',
                f'- Cockpit synced: {item.get("cockpit_synced")}',
                f'- Release blockers: {", ".join(item.get("blockers") or []) or "none"}',
                '',
            ]
        )
    lines.extend(
        [
            '## PR draft generation',
            '- PR draft content is generated from PR plan evidence, Git context, release readiness, and session/project artifacts.',
            '- When there is no actual diff, the draft explicitly says it is draft-only.',
            '- Test results are not fabricated; missing execution is marked as not run.',
            '',
            '## Release notes / changelog generation',
            '- Drafts are based on Project Map capabilities, release readiness, and session evidence.',
            '- Version numbers are not invented.',
            '- Missing evidence remains in Known limitations or Not included sections.',
            '',
            '## Cockpit release view',
            '- Cockpit shows Release / PR state, readiness, blockers, draft paths, and the suggested next command.',
            '',
            '## Quality gates',
            f'- Release artifact quality: {artifact_quality.get("recommendation")} ({artifact_quality.get("release_artifact_quality_score")})',
            f'- PR draft quality: {pr_quality.get("recommendation")} ({pr_quality.get("pr_draft_quality_score")})',
            '',
            '## Next command',
            '- `agent release` to refresh the local release workflow pack.',
            '- `agent pr` to refresh the local PR draft.',
            '- `agent cockpit` to inspect project release state.',
            '',
        ]
    )
    path = dogfood_dir(project) / 'release_workflow_replay.md'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('\n'.join(lines), encoding='utf-8')
    return {'status': 'ok', 'replay': '.zoo-agent/release_dogfood/release_workflow_replay.md'}


def main() -> int:
    parser = argparse.ArgumentParser(description='Replay local release workflow dogfood trace.')
    parser.add_argument('--workspace', default='.')
    args = parser.parse_args()
    project = project_root(args.workspace)
    payload = generate_replay(project)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
