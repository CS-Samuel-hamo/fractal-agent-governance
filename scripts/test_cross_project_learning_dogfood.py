#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from cross_project_learning_dogfood_runner import run_dogfood
from learning_lift_evaluator import evaluate_lift
from runtime_common import write_json

PYTHON = sys.executable


def assert_true(value: bool, message: str) -> None:
    if not value:
        raise AssertionError(message)


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding='utf-8-sig'))


def run(command: list[str], cwd: Path = ROOT, *, expect_ok: bool = True) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(command, cwd=cwd, text=True, encoding='utf-8', errors='replace', capture_output=True)
    if expect_ok and proc.returncode != 0:
        raise AssertionError(f'command failed: {" ".join(command)}\nstdout={proc.stdout}\nstderr={proc.stderr}')
    return proc


def assert_no_private_content(project: Path) -> None:
    text = '\n'.join(
        path.read_text(encoding='utf-8', errors='replace')
        for path in (project / '.zoo-agent').rglob('*')
        if path.is_file()
    )
    forbidden = [
        'SHOULD-NOT-BE-READ',
        'FAKE_TOKEN_12345',
        'raw backend log that should not be stored',
        'sk-test-12345',
        str(project),
    ]
    for marker in forbidden:
        assert_true(marker not in text, f'private marker leaked: {marker}')


def main() -> int:
    with tempfile.TemporaryDirectory(prefix='agent-learning-dogfood-') as tmp:
        project = Path(tmp)
        result = run_dogfood(project)
        assert_true(
            result.get('readiness_value') == 'READY_FOR_098_GITHUB_PR_RELEASE_WORKFLOW',
            'dogfood did not reach 0.98 readiness',
        )

        dogfood = project / '.zoo-agent' / 'learning_dogfood'
        trace_path = dogfood / 'learning_dogfood_trace.json'
        comparison_path = dogfood / 'baseline_comparison.json'
        lift_path = dogfood / 'learning_lift_report.json'
        replay_path = dogfood / 'learning_replay.md'
        product_report_path = dogfood / 'learning_product_report.md'
        readiness_path = dogfood / 'readiness_for_098.json'
        for path in [trace_path, comparison_path, lift_path, replay_path, product_report_path, readiness_path]:
            assert_true(path.exists(), f'missing dogfood artifact: {path.name}')

        trace = load_json(trace_path)
        runs = trace.get('runs') or []
        assert_true(len(runs) >= 4, 'synthetic multi-project fixture missing scenarios')
        assert_true(
            all(item.get('baseline') and item.get('learning_enabled') for item in runs),
            'baseline or learning mode missing',
        )
        assert_true(
            all((item.get('safety') or {}).get('blocked_zone_respected') for item in runs),
            'blocked zone was not preserved',
        )
        assert_true(
            all((item.get('safety') or {}).get('checkpoint_required') for item in runs),
            'checkpoint requirement was not preserved',
        )

        comparison = load_json(comparison_path)
        comparisons = comparison.get('comparisons') or []
        assert_true(any(item.get('next_action_improved') for item in comparisons), 'no positive next_action lift')
        assert_true(
            any(item.get('release_sequence_improved') for item in comparisons), 'no positive release readiness lift'
        )
        assert_true(
            any(item.get('worker_preference_improved') for item in comparisons), 'no positive worker routing lift'
        )
        assert_true(any(item.get('failure_warning_added') for item in comparisons), 'no failure warning lift')
        assert_true(
            not any(item.get('negative_lift_detected') for item in comparisons), 'unexpected negative learning detected'
        )

        lift = load_json(lift_path)
        assert_true(lift.get('recommendation') == 'pass', 'lift report did not pass')
        assert_true(lift.get('learning_lift_score', 0) >= 0.85, 'learning lift score too low')
        assert_true(lift.get('privacy_score') == 1.0, 'privacy score must be 1.0')
        assert_true(lift.get('safety_preservation_score') == 1.0, 'safety score must be 1.0')

        readiness = load_json(readiness_path)
        assert_true(
            readiness.get('readiness') == 'READY_FOR_098_GITHUB_PR_RELEASE_WORKFLOW', 'readiness conclusion wrong'
        )
        assert_no_private_content(project)

        cockpit = project / '.zoo-agent' / 'cockpit' / 'index.html'
        assert_true(cockpit.exists(), 'cockpit was not generated')
        cockpit_text = cockpit.read_text(encoding='utf-8')
        assert_true('Cross-project Learning' in cockpit_text, 'cockpit missing learning section')
        assert_true('Release readiness path' in cockpit_text, 'cockpit missing release readiness path')
        assert_true('Suggested next action' in cockpit_text, 'cockpit missing next action learning')
        assert_true(
            'Worker preference' in cockpit_text or 'Worker' in cockpit_text, 'cockpit missing worker preference'
        )
        assert_true(
            'learning_insights.json' not in cockpit_text and 'raw learning artifacts' not in cockpit_text.lower(),
            'cockpit leaked raw learning artifacts',
        )

        negative_path = dogfood / 'negative_comparison.json'
        negative = {
            'comparisons': [
                {
                    'fixture_project': 'bad_fixture',
                    'next_action_improved': False,
                    'release_sequence_improved': False,
                    'worker_preference_improved': False,
                    'failure_warning_added': False,
                    'safety_boundary_preserved': False,
                    'negative_lift_detected': True,
                }
            ],
            'summary': {
                'total_projects': 1,
                'projects_with_positive_lift': 0,
                'projects_with_negative_lift': 1,
                'neutral_projects': 0,
            },
        }
        write_json(negative_path, negative)
        negative_lift = evaluate_lift(
            project, comparison_path=negative_path, output_path=dogfood / 'negative_lift_report.json'
        )
        assert_true(negative_lift.get('negative_learning_detected') is True, 'negative learning was not detected')
        assert_true(negative_lift.get('recommendation') == 'fail', 'negative learning did not fail')

        privacy_marker = dogfood / 'privacy_marker.json'
        privacy_marker.write_text('{"note":"SHOULD-NOT-BE-READ"}', encoding='utf-8')
        privacy_lift = evaluate_lift(
            project, comparison_path=comparison_path, output_path=dogfood / 'privacy_lift_report.json'
        )
        assert_true(privacy_lift.get('privacy_violation_detected') is True, 'privacy violation was not detected')
        assert_true(privacy_lift.get('recommendation') == 'fail', 'privacy violation did not fail')
        privacy_marker.unlink()

        help_text = run([PYTHON, str(ROOT / 'scripts' / 'agent.py'), '--help']).stdout
        assert_true(
            'learning --dogfood' not in help_text and 'learning --build' not in help_text,
            'ordinary help exposed hidden learning commands',
        )

        cli_workspace = project / 'cli_workspace'
        cli_workspace.mkdir()
        cli_result = run(
            [PYTHON, str(ROOT / 'scripts' / 'agent.py'), 'learning', '--dogfood', '--workspace', str(cli_workspace)]
        )
        assert_true(
            'READY_FOR_098_GITHUB_PR_RELEASE_WORKFLOW' in cli_result.stdout,
            'agent learning --dogfood did not report readiness',
        )

    print('cross project learning dogfood tests passed')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
