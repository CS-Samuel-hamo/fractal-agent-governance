#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from runtime_common import load_json, project_root, utc_now, write_json


def _norm(path: str) -> str:
    return str(path).replace('\\', '/').strip()


def _module_from_path(path: str) -> str:
    normalized = _norm(path)
    parts = [part for part in normalized.split('/') if part]
    if not parts:
        return 'workspace'
    if len(parts) == 1:
        return parts[0]
    if parts[0] in {'src', 'app', 'lib', 'tests', 'docs'}:
        return '/'.join(parts[:2])
    return parts[0]


def _changed_files(execution: dict[str, Any], plan: dict[str, Any]) -> list[str]:
    files: set[str] = set()
    for leaf in execution.get('leaf_results') or []:
        for key in ['business_changed_files', 'diff']:
            for item in leaf.get(key) or []:
                value = _norm(item)
                if value:
                    files.add(value)
    if files:
        return sorted(files)
    for leaf in ((plan.get('decomposition') or {}).get('leaf_tasks') or []):
        for item in leaf.get('allowed_files') or []:
            value = _norm(item)
            if value and not any(ch in value for ch in '*?[]'):
                files.add(value)
    return sorted(files)


def analyze_impact(plan: dict[str, Any], execution: dict[str, Any], final_result: dict[str, Any]) -> dict[str, Any]:
    affected_files = _changed_files(execution, plan)
    modules = sorted({_module_from_path(path) for path in affected_files})
    cross_module = len(modules) > 1
    has_runtime_code = any(path.startswith(('src/', 'app/', 'lib/')) or path.endswith(('.py', '.ts', '.tsx', '.js', '.jsx')) for path in affected_files)
    has_schema_or_api = any(term in path.lower() for path in affected_files for term in ['api', 'schema', 'migration', 'db', 'database'])
    docs_only = bool(affected_files) and all(path.endswith('.md') or path.startswith('docs/') for path in affected_files)
    if has_schema_or_api:
        compatibility = 'needs_review'
        rollback_cost = 'medium'
    elif docs_only:
        compatibility = 'not_expected_to_affect_runtime'
        rollback_cost = 'low'
    elif has_runtime_code:
        compatibility = 'unknown_without_tests'
        rollback_cost = 'medium'
    else:
        compatibility = 'low_risk_or_preview_only'
        rollback_cost = 'low'
    return {
        'schema_version': '1.0',
        'generated_by': 'impact_analyzer.py',
        'generated_at': utc_now(),
        'run_id': execution.get('run_id') or final_result.get('run_id') or plan.get('run_id') or '',
        'affected_files': affected_files,
        'affected_modules': modules,
        'cross_module_risk': 'medium' if cross_module else 'low',
        'backward_compatibility': compatibility,
        'rollback_cost': rollback_cost,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description='Build a human-readable impact summary from task evidence.')
    parser.add_argument('--workspace', default='.')
    parser.add_argument('--plan', required=True)
    parser.add_argument('--execution-result', required=True)
    parser.add_argument('--final-result', required=True)
    parser.add_argument('--output', default='')
    args = parser.parse_args()
    project = project_root(args.workspace)
    payload = analyze_impact(
        load_json(Path(args.plan).resolve()),
        load_json(Path(args.execution_result).resolve()),
        load_json(Path(args.final_result).resolve()),
    )
    output = Path(args.output).resolve() if args.output else project / '.zoo-agent' / 'impact' / 'impact_summary.json'
    write_json(output, payload)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
