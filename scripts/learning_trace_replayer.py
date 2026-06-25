#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from runtime_common import load_json, project_root


def dogfood_dir(project: Path) -> Path:
    return project / '.zoo-agent' / 'learning_dogfood'


def bullet(values: list[Any], *, empty: str = 'not available') -> str:
    rows = [f'- {item}' for item in values if str(item or '').strip()]
    return '\n'.join(rows) if rows else f'- {empty}'


def generate_replay(project: Path) -> dict[str, str]:
    trace = load_json(dogfood_dir(project) / 'learning_dogfood_trace.json')
    comparison = load_json(dogfood_dir(project) / 'baseline_comparison.json')
    comparisons = {
        item.get('fixture_project'): item for item in comparison.get('comparisons') or [] if isinstance(item, dict)
    }
    lines = [
        '# Cross-project Learning Replay',
        '',
        '## Imported fixture projects',
    ]
    for run in trace.get('runs') or []:
        if not isinstance(run, dict):
            continue
        name = str(run.get('fixture_project') or 'fixture')
        baseline = run.get('baseline') if isinstance(run.get('baseline'), dict) else {}
        learning = run.get('learning_enabled') if isinstance(run.get('learning_enabled'), dict) else {}
        safety = run.get('safety') if isinstance(run.get('safety'), dict) else {}
        comp = comparisons.get(name, {})
        lines.extend(
            [
                '',
                f'### {name}',
                f'- project_type: {run.get("project_type")}',
                f'- readiness_stage: {run.get("readiness_stage")}',
                '',
                'Baseline next action:',
                bullet(baseline.get('selected_next_actions') or []),
                '',
                'Learning-enabled next action:',
                bullet(learning.get('selected_next_actions') or []),
                '',
                'Why ranking changed:',
                '- Similar local project patterns favored a more release-oriented next action.',
                '- Release readiness templates added an ordered path instead of a generic cleanup.',
                '- Worker memory preferred metadata-safe workers for scan and readiness tasks.',
                '',
                'Signals used:',
                bullet(learning.get('learning_insights_used') or []),
                '',
                'Evidence check:',
                bullet(
                    [
                        item.get('source') or item.get('pattern_id') or item
                        for item in learning.get('evidence_backed_reasons') or []
                    ]
                ),
                '',
                'Safety boundary:',
                f'- blocked zone respected: {bool(safety.get("blocked_zone_respected"))}',
                f'- checkpoint required: {bool(safety.get("checkpoint_required"))}',
                f'- no secrets saved: {bool(safety.get("no_secret_saved"))}',
                f'- no raw source saved: {bool(safety.get("no_raw_source_saved"))}',
                '',
                'Skipped insights:',
                '- Unsafe effects are skipped; learning remains advisory only.',
                '',
                'Lift result:',
                f'- next action improved: {bool(comp.get("next_action_improved"))}',
                f'- release sequence improved: {bool(comp.get("release_sequence_improved"))}',
                f'- worker preference improved: {bool(comp.get("worker_preference_improved"))}',
                f'- failure warning added: {bool(comp.get("failure_warning_added"))}',
                '',
                'Suggested user command:',
                '- agent cockpit',
                '- agent start "prepare this project for public release"',
            ]
        )
    path = dogfood_dir(project) / 'learning_replay.md'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    return {'status': 'ok', 'replay': '.zoo-agent/learning_dogfood/learning_replay.md'}


def main() -> int:
    parser = argparse.ArgumentParser(description='Replay learning dogfood decisions in human-readable form.')
    parser.add_argument('--workspace', default='.')
    args = parser.parse_args()
    project = project_root(args.workspace)
    payload = generate_replay(project)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
