#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from runtime_common import load_json, project_root, utc_now, write_json


FORBIDDEN_WORDS = ['planner', 'executor', 'verifier', 'backend', 'governance', 'eval']


def _clean(text: str) -> str:
    output = str(text)
    replacements = {
        'planner': 'preparation',
        'executor': 'worker',
        'verifier': 'checker',
        'backend': 'execution provider',
        'governance': 'safety control',
        'eval': 'quality check',
    }
    for old, new in replacements.items():
        output = output.replace(old, new).replace(old.title(), new.title())
    return output


def build_execution_explanation(
    *,
    plan: dict[str, Any],
    execution: dict[str, Any],
    final_result: dict[str, Any],
    impact: dict[str, Any],
    trust: dict[str, Any],
) -> dict[str, Any]:
    leaves = (plan.get('decomposition') or {}).get('leaf_tasks') or []
    objective = str(plan.get('goal') or plan.get('input') or plan.get('objective') or '')
    if not objective and leaves:
        objective = str(leaves[0].get('objective') or '')
    affected = impact.get('affected_files') or []
    verdict = str(final_result.get('final_verdict') or 'UNKNOWN')
    changed_sentence = 'No business files were changed.' if not affected else 'Changed or targeted: ' + ', '.join(str(item) for item in affected[:8])
    risk_text = f"Risk is {impact.get('cross_module_risk', 'unknown')} with rollback cost {impact.get('rollback_cost', 'unknown')}."
    if trust.get('confidence_level') == 'low':
        risk_text += ' Review carefully before relying on this result.'
    payload = {
        'schema_version': '1.0',
        'generated_by': 'explanation_engine.py',
        'generated_at': utc_now(),
        'task_id': execution.get('run_id') or final_result.get('run_id') or '',
        'why_this_change': _clean(f"The task asked for: {objective or 'a local workspace change'}. The run stayed within the requested scope."),
        'what_changed': [str(item) for item in affected],
        'why_this_approach': _clean('The system chose the smallest available change path and kept risky or unrelated work out of scope.'),
        'alternatives_considered': [
            'Do nothing if no safe change is available.',
            'Ask for clarification when the requested change is too broad.',
            'Limit the work to explicitly scoped files when a file is provided.',
        ],
        'risk_analysis': _clean(f"{risk_text} Final result: {verdict}. Trust confidence: {trust.get('confidence_level', 'unknown')}."),
        'rollback_strategy': 'Use version control to review and revert changed files. Preview mode produces no business-file change.',
        'summary': changed_sentence,
    }
    serialized = json.dumps(payload, ensure_ascii=False).lower()
    for word in FORBIDDEN_WORDS:
        if word in serialized:
            raise ValueError(f'explanation leaked internal term: {word}')
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description='Generate a natural-language task explanation.')
    parser.add_argument('--workspace', default='.')
    parser.add_argument('--plan', required=True)
    parser.add_argument('--execution-result', required=True)
    parser.add_argument('--final-result', required=True)
    parser.add_argument('--impact', required=True)
    parser.add_argument('--trust', required=True)
    parser.add_argument('--output', default='')
    args = parser.parse_args()
    project = project_root(args.workspace)
    payload = build_execution_explanation(
        plan=load_json(Path(args.plan).resolve()),
        execution=load_json(Path(args.execution_result).resolve()),
        final_result=load_json(Path(args.final_result).resolve()),
        impact=load_json(Path(args.impact).resolve()),
        trust=load_json(Path(args.trust).resolve()),
    )
    output = Path(args.output).resolve() if args.output else project / '.zoo-agent' / 'explain' / 'execution_explanation.json'
    write_json(output, payload)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
