#!/usr/bin/env python3
"""Release, publish, launch, and feedback command handlers."""

from __future__ import annotations

from pathlib import Path

from agent_utils import delegate_capture, parse_json_output, print_json


def run_release_pack(project: Path, *, debug: bool = False, pr_only: bool = False) -> tuple[int, dict]:
    common = ['--workspace', str(project)]
    steps = []
    if not pr_only:
        steps.extend(
            [
                'git_context_detector.py',
                'release_readiness_template_builder.py',
                'github_readiness_detector.py',
                'release_readiness_evaluator.py',
                'release_notes_generator.py',
                'changelog_draft_generator.py',
                'release_action_plan_generator.py',
            ]
        )
    else:
        steps.extend(['git_context_detector.py', 'github_readiness_detector.py', 'release_readiness_evaluator.py'])
    steps.extend(['pr_plan_generator.py', 'pr_draft_generator.py'])
    final_payload: dict = {}
    for script in steps:
        result = delegate_capture(script, common)
        if debug:
            print(str(result.get('stdout') or '').strip())
        if result.get('returncode') != 0:
            return int(result.get('returncode') or 1), {'failed_script': script}
        if script == 'pr_draft_generator.py':
            final_payload = parse_json_output(result)
    first_report = delegate_capture('release_workflow_report_generator.py', common)
    if debug:
        print(str(first_report.get('stdout') or '').strip())
    safety = delegate_capture('github_workflow_safety_gate.py', common)
    if debug:
        print(str(safety.get('stdout') or '').strip())
    if safety.get('returncode') != 0:
        return int(safety.get('returncode') or 1), parse_json_output(safety)
    report = delegate_capture('release_workflow_report_generator.py', common)
    if debug:
        print(str(report.get('stdout') or '').strip())
    if report.get('returncode') != 0:
        return int(report.get('returncode') or 1), parse_json_output(report)
    cockpit = delegate_capture('cockpit_renderer.py', common)
    if debug:
        print(str(cockpit.get('stdout') or '').strip())
    if cockpit.get('returncode') != 0:
        return int(cockpit.get('returncode') or 1), parse_json_output(cockpit)
    final_payload.update(parse_json_output(report))
    return 0, final_payload


def release_command(args) -> int:
    from runtime_common import project_root

    project = project_root(args.workspace)
    if getattr(args, 'dogfood', False):
        result = delegate_capture('release_workflow_dogfood_runner.py', ['--workspace', str(project)])
        if getattr(args, 'debug', False):
            print(str(result.get('stdout') or '').strip())
            return int(result.get('returncode') or 0)
        payload = parse_json_output(result)
        readiness = str(payload.get('readiness_value') or 'NOT_READY')
        print_json(
            {
                'task': 'release workflow dogfood',
                'mode': 'ready' if result.get('returncode') == 0 else 'blocked',
                'result': f'Report: .zoo-agent/release_dogfood/release_product_report.md; readiness: {readiness}',
            }
        )
        return int(result.get('returncode') or 0)
    if getattr(args, 'safety_check', False):
        result = delegate_capture('github_workflow_safety_gate.py', ['--workspace', str(project)])
        if getattr(args, 'debug', False):
            print(str(result.get('stdout') or '').strip())
            return int(result.get('returncode') or 0)
        payload = parse_json_output(result)
        print_json(
            {
                'task': 'release safety check',
                'mode': 'ready' if payload.get('safe') else 'blocked',
                'result': 'Safety report: .zoo-agent/release/github_workflow_safety_report.json',
            }
        )
        return int(result.get('returncode') or 0)
    code, payload = run_release_pack(project, debug=getattr(args, 'debug', False), pr_only=False)
    status = str(payload.get('status') or payload.get('readiness', {}).get('readiness') or 'unknown')
    print_json(
        {
            'task': 'release workflow',
            'mode': 'ready' if code == 0 else 'blocked',
            'result': f'Release pack: .zoo-agent/release/release_workflow_report.md; status: {status}; next: agent cockpit or agent pr',
        }
    )
    return code


def pr_command(args) -> int:
    from runtime_common import project_root

    project = project_root(args.workspace)
    code, payload = run_release_pack(project, debug=getattr(args, 'debug', False), pr_only=True)
    status = str(payload.get('status') or payload.get('readiness', {}).get('readiness') or 'unknown')
    print_json(
        {
            'task': 'pr draft',
            'mode': 'ready' if code == 0 else 'blocked',
            'result': f'PR draft: .zoo-agent/release/pr_draft.md; status: {status}',
        }
    )
    return code


def alpha_command(args) -> int:
    from runtime_common import project_root

    project = project_root(args.workspace)
    if getattr(args, 'package', False):
        demo = delegate_capture('demo_fixture_packager.py', ['--workspace', str(project)])
        result = delegate_capture('public_alpha_packager.py', ['--workspace', str(project)])
        if getattr(args, 'debug', False):
            print(str(demo.get('stdout') or '').strip())
            print(str(result.get('stdout') or '').strip())
            return int(result.get('returncode') or demo.get('returncode') or 0)
        print_json(
            {
                'task': 'public alpha package',
                'mode': 'ready' if result.get('returncode') == 0 and demo.get('returncode') == 0 else 'blocked',
                'result': 'Manifest: .zoo-agent/public_alpha/public_alpha_package_manifest.json',
            }
        )
        return int(result.get('returncode') or demo.get('returncode') or 0)
    if getattr(args, 'audit', False) or getattr(args, 'report', False):
        result = delegate_capture('public_alpha_report_generator.py', ['--workspace', str(project)])
        payload = parse_json_output(result)
        readiness = payload.get('status') or payload.get('readiness', {}).get('readiness') or 'unknown'
        if getattr(args, 'debug', False):
            print(str(result.get('stdout') or '').strip())
            return int(result.get('returncode') or 0)
        print_json(
            {
                'task': 'public alpha audit',
                'mode': 'ready' if readiness == 'READY_FOR_100_PUBLIC_ALPHA_RELEASE' else 'blocked',
                'result': f'Report: .zoo-agent/public_alpha/public_alpha_report.md; readiness: {readiness}',
            }
        )
        return int(result.get('returncode') or 0)
    print_json({'task': 'public alpha', 'mode': 'blocked', 'result': 'unknown alpha command'})
    return 2


def publish_command(args) -> int:
    from runtime_common import project_root

    project = project_root(args.workspace)
    if getattr(args, 'package', False):
        result = delegate_capture('public_release_packager.py', ['--workspace', str(project)])
        if getattr(args, 'debug', False):
            print(str(result.get('stdout') or '').strip())
            return int(result.get('returncode') or 0)
        print_json(
            {
                'task': 'public release package',
                'mode': 'ready' if result.get('returncode') == 0 else 'blocked',
                'result': 'Manifest: .zoo-agent/public_release/public_release_package_manifest.json',
            }
        )
        return int(result.get('returncode') or 0)
    if getattr(args, 'preflight', False):
        result = delegate_capture('public_release_gate.py', ['--workspace', str(project)])
        if result.get('returncode') == 0:
            preflight = delegate_capture('release_tag_preflight.py', ['--workspace', str(project)])
        else:
            preflight = {'returncode': 0, 'stdout': '{}'}
        payload = parse_json_output(result)
        if getattr(args, 'debug', False):
            print(str(result.get('stdout') or '').strip())
            print(str(preflight.get('stdout') or '').strip())
            return int(result.get('returncode') or preflight.get('returncode') or 0)
        print_json(
            {
                'task': 'public release preflight',
                'mode': 'ready' if payload.get('recommendation') == 'pass' else 'blocked',
                'result': f'Gate: .zoo-agent/public_release/public_release_gate.json; recommendation: {payload.get("recommendation") or "unknown"}',
            }
        )
        return int(result.get('returncode') or preflight.get('returncode') or 0)
    if getattr(args, 'report', False):
        result = delegate_capture('public_release_report_generator.py', ['--workspace', str(project)])
        payload = parse_json_output(result)
        readiness = payload.get('status') or payload.get('readiness', {}).get('readiness') or 'unknown'
        if getattr(args, 'debug', False):
            print(str(result.get('stdout') or '').strip())
            return int(result.get('returncode') or 0)
        print_json(
            {
                'task': 'public release report',
                'mode': 'ready' if readiness == 'READY_TO_PUBLISH_GITHUB_ALPHA' else 'blocked',
                'result': f'Report: .zoo-agent/public_release/public_release_report.md; readiness: {readiness}',
            }
        )
        return int(result.get('returncode') or 0)
    print_json({'task': 'public release', 'mode': 'blocked', 'result': 'unknown publish command'})
    return 2


def launch_command(args) -> int:
    from runtime_common import project_root

    project = project_root(args.workspace)
    if getattr(args, 'package', False):
        result = delegate_capture('public_launch_packager.py', ['--workspace', str(project)])
        if getattr(args, 'debug', False):
            print(str(result.get('stdout') or '').strip())
            return int(result.get('returncode') or 0)
        print_json(
            {
                'task': 'public launch package',
                'mode': 'ready' if result.get('returncode') == 0 else 'blocked',
                'result': 'Package: .zoo-agent/public_launch/public_launch_package.json',
            }
        )
        return int(result.get('returncode') or 0)
    if getattr(args, 'smoke', False):
        result = delegate_capture('post_publish_smoke_test.py', ['--workspace', str(project)])
        payload = parse_json_output(result)
        if getattr(args, 'debug', False):
            print(str(result.get('stdout') or '').strip())
            return int(result.get('returncode') or 0)
        print_json(
            {
                'task': 'public launch smoke',
                'mode': 'ready' if payload.get('post_publish_smoke_passed') else 'blocked',
                'result': 'Smoke report: .zoo-agent/public_launch/post_publish_smoke_report.json',
            }
        )
        return int(result.get('returncode') or 0)
    if getattr(args, 'audit', False):
        result = delegate_capture('public_launch_audit.py', ['--workspace', str(project)])
        payload = parse_json_output(result)
        if getattr(args, 'debug', False):
            print(str(result.get('stdout') or '').strip())
            return int(result.get('returncode') or 0)
        print_json(
            {
                'task': 'public launch audit',
                'mode': 'ready' if payload.get('recommendation') == 'pass' else 'blocked',
                'result': f'Audit: .zoo-agent/public_launch/public_launch_audit.json; recommendation: {payload.get("recommendation") or "unknown"}',
            }
        )
        return int(result.get('returncode') or 0)
    if getattr(args, 'report', False):
        result = delegate_capture('launch_report_generator.py', ['--workspace', str(project)])
        payload = parse_json_output(result)
        readiness = payload.get('status') or payload.get('readiness', {}).get('readiness') or 'unknown'
        if getattr(args, 'debug', False):
            print(str(result.get('stdout') or '').strip())
            return int(result.get('returncode') or 0)
        print_json(
            {
                'task': 'public launch report',
                'mode': 'ready' if readiness == 'READY_FOR_MANUAL_GITHUB_PUBLISH' else 'blocked',
                'result': f'Report: .zoo-agent/public_launch/public_launch_report.md; readiness: {readiness}',
            }
        )
        return int(result.get('returncode') or 0)
    print_json({'task': 'public launch', 'mode': 'blocked', 'result': 'unknown launch command'})
    return 2


def postlaunch_command(args) -> int:
    from runtime_common import project_root

    project = project_root(args.workspace)
    if getattr(args, 'verify', False):
        result = delegate_capture('post_publish_remote_verifier.py', ['--workspace', str(project)])
        payload = parse_json_output(result)
        if getattr(args, 'debug', False):
            print(str(result.get('stdout') or '').strip())
            return int(result.get('returncode') or 0)
        mode = 'ready' if payload.get('remote_verification_passed') or payload.get('tree_equal') else 'blocked'
        print_json(
            {
                'task': 'post-launch remote verification',
                'mode': mode,
                'result': 'Report: .zoo-agent/post_launch/remote_publish_verification.json',
            }
        )
        return int(result.get('returncode') or 0)
    if getattr(args, 'branch_audit', False):
        result = delegate_capture('branch_hygiene_audit.py', ['--workspace', str(project)])
        payload = parse_json_output(result)
        if getattr(args, 'debug', False):
            print(str(result.get('stdout') or '').strip())
            return int(result.get('returncode') or 0)
        recommendation = payload.get('recommendation') or 'unknown'
        print_json(
            {
                'task': 'post-launch branch hygiene',
                'mode': 'ready' if recommendation in {'pass', 'manual_action_needed'} else 'blocked',
                'result': f'Branch report: .zoo-agent/post_launch/branch_hygiene_report.json; recommendation: {recommendation}',
            }
        )
        return int(result.get('returncode') or 0)
    if getattr(args, 'report', False):
        result = delegate_capture('post_publish_report_generator.py', ['--workspace', str(project)])
        payload = parse_json_output(result)
        readiness = payload.get('status') or payload.get('readiness', {}).get('readiness') or 'unknown'
        if getattr(args, 'debug', False):
            print(str(result.get('stdout') or '').strip())
            return int(result.get('returncode') or 0)
        print_json(
            {
                'task': 'post-launch report',
                'mode': 'ready' if readiness == 'READY_FOR_POST_LAUNCH_FEEDBACK_TRIAGE' else 'blocked',
                'result': f'Report: .zoo-agent/post_launch/post_publish_report.md; readiness: {readiness}',
            }
        )
        return int(result.get('returncode') or 0)
    print_json({'task': 'post-launch', 'mode': 'blocked', 'result': 'unknown postlaunch command'})
    return 2


def feedback_command(args) -> int:
    from runtime_common import project_root

    project = project_root(args.workspace)
    if getattr(args, 'triage', False):
        result = delegate_capture('feedback_triage_engine.py', ['--workspace', str(project)])
        payload = parse_json_output(result)
        if getattr(args, 'debug', False):
            print(str(result.get('stdout') or '').strip())
            return int(result.get('returncode') or 0)
        recommendation = payload.get('recommendation') or 'unknown'
        print_json(
            {
                'task': 'feedback triage',
                'mode': 'ready' if recommendation != 'fix_feedback_pipeline' else 'blocked',
                'result': f'Triage report: .zoo-agent/feedback/feedback_triage_report.json; recommendation: {recommendation}',
            }
        )
        return int(result.get('returncode') or 0)
    if getattr(args, 'signals', False):
        result = delegate_capture('feedback_signal_classifier.py', ['--workspace', str(project)])
        payload = parse_json_output(result)
        if getattr(args, 'debug', False):
            print(str(result.get('stdout') or '').strip())
            return int(result.get('returncode') or 0)
        print_json(
            {
                'task': 'feedback signals',
                'mode': 'ready' if result.get('returncode') == 0 else 'blocked',
                'result': f'Signals: .zoo-agent/feedback/feedback_signal_report.json; count: {len(payload.get("signals") or [])}',
            }
        )
        return int(result.get('returncode') or 0)
    if getattr(args, 'report', False):
        result = delegate_capture('post_launch_feedback_report_generator.py', ['--workspace', str(project)])
        payload = parse_json_output(result)
        readiness = payload.get('status') or payload.get('readiness', {}).get('readiness') or 'unknown'
        if getattr(args, 'debug', False):
            print(str(result.get('stdout') or '').strip())
            return int(result.get('returncode') or 0)
        print_json(
            {
                'task': 'feedback report',
                'mode': 'ready'
                if readiness in {'READY_FOR_104_PATCH_PLANNING', 'COLLECT_MORE_FEEDBACK_FIRST'}
                else 'blocked',
                'result': f'Report: .zoo-agent/feedback/post_launch_feedback_report.md; readiness: {readiness}',
            }
        )
        return int(result.get('returncode') or 0)
    print_json({'task': 'feedback', 'mode': 'blocked', 'result': 'unknown feedback command'})
    return 2
