#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from runtime_common import load_json, project_root, utc_now, write_json


VAGUE_ACTION_WORDS = {'improve', 'review', 'optimize', 'polish', 'cleanup', 'thing', 'stuff', 'misc'}
VALID_CAPABILITY_STATUS = {'missing', 'partial', 'implemented', 'verified'}
VALID_MODULE_STATUS = {'unknown', 'mapped', 'working', 'complete', 'risky'}


def _has_evidence(row: dict[str, Any]) -> bool:
    return bool([item for item in row.get('evidence') or [] if isinstance(item, dict) and item.get('summary')])


def _action_is_vague(action: dict[str, Any]) -> bool:
    title = str(action.get('title') or '').strip().lower()
    if not title:
        return True
    words = {part.strip('.,:;!?') for part in title.split()}
    if words & VAGUE_ACTION_WORDS and len(words) <= 4:
        return True
    return not (action.get('why_now') and action.get('target_files') and action.get('expected_impact'))


def _evidence_paths(evidence_payload: dict[str, Any]) -> set[str]:
    return {str(item.get('path') or '').replace('\\', '/') for item in evidence_payload.get('evidence') or [] if isinstance(item, dict)}


def evaluate_map(project_map: dict[str, Any], evidence_payload: dict[str, Any]) -> dict[str, Any]:
    modules = [item for item in project_map.get('modules') or [] if isinstance(item, dict)]
    capabilities = [item for item in project_map.get('capabilities') or [] if isinstance(item, dict)]
    risks = [item for item in project_map.get('risks') or [] if isinstance(item, dict)]
    actions = [item for item in project_map.get('next_actions') or [] if isinstance(item, dict)]
    paths = _evidence_paths(evidence_payload)

    unsupported_modules: list[str] = []
    unsupported_capabilities: list[str] = []
    high_confidence_without_basis: list[str] = []
    invalid_status_count = 0

    for module in modules:
        module_id = str(module.get('module_id') or module.get('name') or '')
        if not _has_evidence(module) or module.get('status') == 'mapped' and not module.get('key_files'):
            unsupported_modules.append(module_id)
        key_files = [str(item).replace('\\', '/') for item in module.get('key_files') or []]
        if key_files and not any(path in paths for path in key_files):
            unsupported_modules.append(module_id)
        if float(module.get('confidence') or 0.0) > 0.8 and not _has_evidence(module):
            high_confidence_without_basis.append(module_id)
        if module.get('status') not in VALID_MODULE_STATUS:
            invalid_status_count += 1

    for capability in capabilities:
        capability_id = str(capability.get('capability_id') or capability.get('name') or '')
        if capability.get('status') not in VALID_CAPABILITY_STATUS:
            invalid_status_count += 1
        if capability.get('status') in {'implemented', 'verified', 'partial'} and not _has_evidence(capability):
            unsupported_capabilities.append(capability_id)

    risk_without_files = [str(item.get('risk_id') or item.get('description') or '') for item in risks if not item.get('affected_files')]
    vague_actions = [str(item.get('action_id') or item.get('title') or '') for item in actions if _action_is_vague(item)]
    unsupported_actions = [
        str(item.get('action_id') or item.get('title') or '')
        for item in actions
        if item.get('target_files') and not any(str(path).replace('\\', '/') in paths for path in item.get('target_files') or [])
    ]

    total_entities = max(1, len(modules) + len(capabilities) + len(actions) + len(risks))
    supported_entities = total_entities - len(set(unsupported_modules)) - len(set(unsupported_capabilities)) - len(vague_actions) - len(risk_without_files)
    evidence_coverage = round(max(0.0, supported_entities / total_entities), 3)
    penalties = (
        0.18 * len(set(unsupported_modules))
        + 0.14 * len(set(unsupported_capabilities))
        + 0.12 * len(vague_actions)
        + 0.08 * len(risk_without_files)
        + 0.1 * len(unsupported_actions)
        + 0.08 * invalid_status_count
        + 0.08 * len(high_confidence_without_basis)
    )
    score = round(max(0.0, min(1.0, evidence_coverage - penalties)), 3)
    if unsupported_modules or unsupported_capabilities or unsupported_actions:
        hallucination_risk = 'high'
    elif vague_actions or high_confidence_without_basis:
        hallucination_risk = 'medium'
    else:
        hallucination_risk = 'low'
    if score >= 0.75 and hallucination_risk == 'low' and not vague_actions:
        recommendation = 'pass'
    elif score >= 0.45:
        recommendation = 'fix_before_094'
    else:
        recommendation = 'fail'

    return {
        'schema_version': '1.0',
        'generated_by': 'map_quality_evaluator.py',
        'generated_at': utc_now(),
        'map_quality_score': score,
        'evidence_coverage': evidence_coverage,
        'hallucination_risk': hallucination_risk,
        'vague_action_count': len(vague_actions),
        'unsupported_module_count': len(set(unsupported_modules)),
        'unsupported_capability_count': len(set(unsupported_capabilities)),
        'risk_without_affected_files_count': len(risk_without_files),
        'unsupported_action_count': len(unsupported_actions),
        'high_confidence_without_basis': sorted(set(high_confidence_without_basis)),
        'invalid_status_count': invalid_status_count,
        'recommendation': recommendation,
        'details': {
            'unsupported_modules': sorted(set(unsupported_modules)),
            'unsupported_capabilities': sorted(set(unsupported_capabilities)),
            'vague_actions': vague_actions,
            'unsupported_actions': unsupported_actions,
            'risk_without_affected_files': risk_without_files,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description='Evaluate project map quality for dogfood readiness.')
    parser.add_argument('--workspace', default='.')
    parser.add_argument('--project-map', default='')
    parser.add_argument('--evidence', default='')
    parser.add_argument('--output', default='')
    args = parser.parse_args()
    project = project_root(args.workspace)
    map_path = Path(args.project_map).resolve() if args.project_map else project / '.zoo-agent' / 'map' / 'project_map.json'
    evidence_path = Path(args.evidence).resolve() if args.evidence else project / '.zoo-agent' / 'map' / 'map_evidence.json'
    payload = evaluate_map(load_json(map_path), load_json(evidence_path))
    output = Path(args.output).resolve() if args.output else project / '.zoo-agent' / 'dogfood' / 'map_quality_report.json'
    write_json(output, payload)
    print(json.dumps({'status': 'ok', 'map_quality_report': str(output), 'recommendation': payload['recommendation']}, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
