#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from runtime_common import load_json, project_root, utc_now, write_json


def _risk_level(impact: dict[str, Any], trust: dict[str, Any]) -> str:
    if trust.get('confidence_level') == 'low' or impact.get('backward_compatibility') == 'needs_review':
        return 'high'
    if impact.get('cross_module_risk') == 'medium' or impact.get('rollback_cost') == 'medium':
        return 'medium'
    return 'low'


def build_safety_summary(explanation: dict[str, Any], impact: dict[str, Any], trust: dict[str, Any], final_result: dict[str, Any]) -> dict[str, Any]:
    risk = _risk_level(impact, trust)
    affected = impact.get('affected_files') or []
    safe_to_deploy = risk == 'low' and str(final_result.get('final_verdict') or '') in {'COMPLETED', 'DRY_RUN_COMPLETE'}
    rollback_available = impact.get('rollback_cost') in {'low', 'medium'}
    if affected:
        changed = ', '.join(str(item) for item in affected[:8])
    else:
        changed = 'No business files changed.'
    summary_lines = [
        f"What changed: {changed}",
        f"Risk level: {risk}",
        f"Impact scope: {impact.get('cross_module_risk', 'unknown')}",
        f"Safe to deploy: {'yes' if safe_to_deploy else 'no'}",
        f"Rollback available: {'yes' if rollback_available else 'no'}",
    ]
    return {
        'schema_version': '1.0',
        'generated_by': 'safety_summary_generator.py',
        'generated_at': utc_now(),
        'run_id': final_result.get('run_id') or explanation.get('task_id') or '',
        'what_changed': changed,
        'risk_level': risk,
        'impact_scope': impact.get('cross_module_risk', 'unknown'),
        'safe_to_deploy': bool(safe_to_deploy),
        'rollback_available': bool(rollback_available),
        'trust_score': trust.get('trust_score', 0.0),
        'confidence_level': trust.get('confidence_level', 'unknown'),
        'summary': '\n'.join(summary_lines),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description='Generate a user-readable safety summary.')
    parser.add_argument('--workspace', default='.')
    parser.add_argument('--explanation', required=True)
    parser.add_argument('--impact', required=True)
    parser.add_argument('--trust', required=True)
    parser.add_argument('--final-result', required=True)
    parser.add_argument('--output', default='')
    parser.add_argument('--markdown-output', default='')
    args = parser.parse_args()
    project = project_root(args.workspace)
    payload = build_safety_summary(
        load_json(Path(args.explanation).resolve()),
        load_json(Path(args.impact).resolve()),
        load_json(Path(args.trust).resolve()),
        load_json(Path(args.final_result).resolve()),
    )
    output = Path(args.output).resolve() if args.output else project / '.zoo-agent' / 'explain' / 'safety_summary.json'
    write_json(output, payload)
    md_output = Path(args.markdown_output).resolve() if args.markdown_output else project / '.zoo-agent' / 'explain' / 'safety_summary.md'
    md_output.parent.mkdir(parents=True, exist_ok=True)
    md_output.write_text(payload['summary'] + '\n', encoding='utf-8')
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
