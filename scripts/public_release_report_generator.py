#!/usr/bin/env python3
from __future__ import annotations

import argparse
import contextlib
import io
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from demo_flow_verifier import verify as verify_demo_flow  # noqa: E402
from fresh_clone_verifier import verify as verify_fresh_clone  # noqa: E402
from github_release_draft_generator import generate as generate_github_release_draft  # noqa: E402
from public_release_gate import evaluate_gate  # noqa: E402
from public_release_packager import VERSION, public_release_dir, write_release_manifest  # noqa: E402
from release_tag_preflight import preflight as tag_preflight  # noqa: E402
from runtime_common import load_json, project_root, utc_now, write_json  # noqa: E402


def final_status(gate: dict[str, Any], fresh: dict[str, Any], demo: dict[str, Any], package: dict[str, Any]) -> str:
    if (
        gate.get('recommendation') == 'pass'
        and fresh.get('fresh_clone_passed')
        and demo.get('demo_flow_passed')
        and package.get('safe_to_package')
    ):
        return 'READY_TO_PUBLISH_GITHUB_ALPHA'
    if gate.get('recommendation') == 'fail' or fresh.get('unsafe_behavior_detected') or demo.get('unsafe_behavior_detected'):
        return 'NOT_READY'
    return 'FIX_BEFORE_PUBLISH'


def generate_report(project: Path, *, run_fresh_clone: bool = True, run_demo: bool = True) -> dict[str, Any]:
    with contextlib.redirect_stdout(io.StringIO()):
        generate_github_release_draft(project)
        package = write_release_manifest(project)
        fresh = verify_fresh_clone(project) if run_fresh_clone else load_json(public_release_dir(project) / 'fresh_clone_verification.json')
        demo = verify_demo_flow(project) if run_demo else load_json(public_release_dir(project) / 'demo_flow_verification.json')
        gate = evaluate_gate(project)
        tag = tag_preflight(project)
    status = final_status(gate, fresh, demo, package)
    suggested = tag.get('suggested_commands') or [
        f'git tag -a v{VERSION} -m "AI Project Operator v{VERSION}"',
        f'git push origin HEAD:refs/heads/release/v{VERSION}',
        f'git push origin v{VERSION}',
    ]
    report = '\n'.join(
        [
            '# Public Release Report',
            '',
            f'Generated: {utc_now()}',
            '',
            f'Release version: `v{VERSION}`',
            '',
            '## Final Recommendation',
            '',
            status,
            '',
            '## Public Positioning',
            '',
            '- AI Project Operator',
            '- Give it a project. It keeps moving it forward.',
            '- Project-level Autopilot, not task-level coding agent.',
            '',
            '## Public Command Surface',
            '',
            '- `agent "<task>"`',
            '- `agent "<task>" --preview`',
            '- `agent "<task>" --apply`',
            '- `agent start "<project goal>"`',
            '- `agent status`',
            '- `agent continue`',
            '- `agent stop`',
            '- `agent undo`',
            '- `agent cockpit`',
            '- `agent release`',
            '- `agent pr`',
            '',
            '## Demo Verification',
            '',
            f"- passed: {demo.get('demo_flow_passed')}",
            f"- outputs: {', '.join(demo.get('generated_outputs') or []) or 'none'}",
            '',
            '## Fresh Clone Verification',
            '',
            f"- passed: {fresh.get('fresh_clone_passed')}",
            f"- failed commands: {len(fresh.get('failed_commands') or [])}",
            '',
            '## Docs Safety',
            '',
            f"- docs safety score: {gate.get('docs_safety_score')}",
            f"- must fix: {', '.join(gate.get('must_fix') or []) or 'none'}",
            '',
            '## Package Manifest',
            '',
            f"- safe to package: {package.get('safe_to_package')}",
            f"- included files: {len(package.get('included_files') or [])}",
            '',
            '## Known Limitations',
            '',
            '- Local release and PR workflow only.',
            '- No remote GitHub PR creation.',
            '- Product release and PR workflows do not call the GitHub API.',
            '- No automatic push, merge, deployment, or remote release.',
            '- Human review remains required before publishing.',
            '',
            '## Tag Preflight',
            '',
            f"- working tree clean: {tag.get('working_tree_clean')}",
            f"- tag exists: {tag.get('tag_exists')}",
            f"- auto tag created: {tag.get('auto_tag_created')}",
            '',
            '## Suggested Publish Commands',
            '',
            'Review these commands before running them manually:',
            '',
            '```bash',
            *suggested,
            '```',
            '',
        ]
    )
    out = public_release_dir(project)
    out.mkdir(parents=True, exist_ok=True)
    (out / 'public_release_report.md').write_text(report, encoding='utf-8')
    readiness = {
        'generated_at': utc_now(),
        'readiness': status,
        'version': VERSION,
        'safe_to_release': gate.get('safe_to_release'),
        'fresh_clone_passed': fresh.get('fresh_clone_passed'),
        'demo_flow_passed': demo.get('demo_flow_passed'),
        'suggested_publish_commands': suggested,
        'must_fix': gate.get('must_fix') or [],
    }
    write_json(out / 'readiness_for_github_publish.json', readiness)
    payload = {'status': status, 'report_path': '.zoo-agent/public_release/public_release_report.md', 'readiness': readiness}
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--workspace', default='.')
    parser.add_argument('--skip-fresh-clone', action='store_true')
    parser.add_argument('--skip-demo', action='store_true')
    args = parser.parse_args(argv)
    payload = generate_report(project_root(args.workspace), run_fresh_clone=not args.skip_fresh_clone, run_demo=not args.skip_demo)
    return 0 if payload.get('status') == 'READY_TO_PUBLISH_GITHUB_ALPHA' else 1


if __name__ == '__main__':
    raise SystemExit(main())
