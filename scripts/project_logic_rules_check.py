#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from runtime_common import load_json, project_root, utc_now, write_json


EXPECTED_DOCS = {
    'project_beginning_prompt.md': 'seed_prompt',
    'docs/project_plan.md': 'project_plan',
    'docs/research_workflow.md': 'main_workflow',
    'docs/usage_guide.md': 'usage_guide',
    'docs/prompt_templates.md': 'prompt_templates',
    'docs/workflow_checklist.md': 'workflow_checklist',
    'docs/output_schema.md': 'output_schema',
    'docs/literature_search_protocol.md': 'literature_search_protocol',
    'docs/literature_matrix_template.md': 'literature_matrix',
    'docs/evidence_plan.md': 'evidence_plan',
    'docs/evidence_quality_standard.md': 'evidence_standard',
    'docs/validation_checklist.md': 'validation_checklist',
    'docs/red_team_review_template.md': 'red_team_review',
    'docs/review_rubric.md': 'review_rubric',
    'docs/failure_modes.md': 'failure_modes',
}

EXPECTED_LINKS = [
    ('project_beginning_prompt.md', 'docs/project_plan.md', 'seed prompt should produce a project plan'),
    ('docs/project_plan.md', 'docs/research_workflow.md', 'project plan should point to the main workflow'),
    ('docs/research_workflow.md', 'docs/prompt_templates.md', 'workflow should use prompt templates'),
    ('docs/research_workflow.md', 'docs/workflow_checklist.md', 'workflow should be executable as a checklist'),
    ('docs/prompt_templates.md', 'docs/output_schema.md', 'templates should produce the declared output schema'),
    ('docs/literature_search_protocol.md', 'docs/literature_matrix_template.md', 'search protocol should feed the literature matrix'),
    ('docs/evidence_plan.md', 'docs/evidence_quality_standard.md', 'evidence plan should follow evidence quality standards'),
    ('docs/evidence_quality_standard.md', 'docs/review_rubric.md', 'rubric should evaluate evidence quality'),
    ('docs/failure_modes.md', 'docs/red_team_review_template.md', 'red-team review should cover known failure modes'),
    ('docs/validation_checklist.md', 'docs/red_team_review_template.md', 'validation should feed red-team review'),
]

QUALITY_GATES = {
    'evidence_standard': 'docs/evidence_quality_standard.md',
    'validation_checklist': 'docs/validation_checklist.md',
    'red_team_review': 'docs/red_team_review_template.md',
    'review_rubric': 'docs/review_rubric.md',
    'failure_modes': 'docs/failure_modes.md',
}

RULE_KEYWORDS = {
    'no_fake_citations': ['fake citations', '伪引用', '虚构引用', 'invent citations'],
    'no_fake_results': ['fake data', 'fake empirical', '伪数据', '虚构数据', '虚构实验'],
    'evidence_separation': ['facts', 'assumptions', '事实', '假设', '证据'],
    'no_secret_access': ['secret', '.env', 'token', 'credential', 'secrets'],
}


def _exists(project: Path, rel: str) -> bool:
    return (project / rel).exists()


def _read_lower(project: Path, rel: str, *, limit: int = 120_000) -> str:
    path = project / rel
    if not path.exists() or not path.is_file():
        return ''
    try:
        return path.read_text(encoding='utf-8', errors='replace')[:limit].lower()
    except OSError:
        return ''


def _mentions(project: Path, source: str, target: str) -> bool:
    text = _read_lower(project, source)
    if not text:
        return False
    target_name = Path(target).name.lower()
    target_stem = Path(target).stem.lower().replace('_', ' ')
    normalized = target.lower().replace('\\', '/')
    return normalized in text or target_name in text or target_stem in text


def _status(done: int, total: int) -> str:
    if total and done >= total:
        return 'complete'
    if done:
        return 'partial'
    return 'missing'


def build_rules_check(project: Path) -> dict[str, Any]:
    standards = load_json(project / '.zoo-agent' / 'code-standards.json')
    agents = _read_lower(project, 'AGENTS.md')
    doc_rule_text = '\n'.join(_read_lower(project, rel) for rel in EXPECTED_DOCS if _exists(project, rel))
    forbidden_actions = standards.get('forbidden_actions') if isinstance(standards.get('forbidden_actions'), list) else []
    done_criteria = standards.get('done_criteria') if isinstance(standards.get('done_criteria'), list) else []
    combined = '\n'.join([agents, json.dumps(standards, ensure_ascii=False).lower(), doc_rule_text])
    coverage = {
        key: any(signal.lower() in combined for signal in signals)
        for key, signals in RULE_KEYWORDS.items()
    }
    docs_rule_present = any(coverage.values())
    checks = [
        {'name': 'AGENTS.md', 'status': 'present' if agents else 'missing', 'path': 'AGENTS.md'},
        {
            'name': 'Code standards',
            'status': 'present' if standards else 'missing',
            'path': '.zoo-agent/code-standards.json',
        },
        {
            'name': 'Forbidden actions',
            'status': 'present' if forbidden_actions else 'missing',
            'path': '.zoo-agent/code-standards.json',
        },
        {
            'name': 'Done criteria',
            'status': 'present' if done_criteria else 'missing',
            'path': '.zoo-agent/code-standards.json',
        },
        {
            'name': 'Project docs rules',
            'status': 'present' if docs_rule_present else 'missing',
            'path': 'docs/',
        },
    ]
    present = sum(1 for item in checks if item['status'] == 'present')
    return {
        'status': _status(present, len(checks)),
        'checks': checks,
        'coverage': coverage,
        'summary': (
            'Project rules are available and can guide safe execution.'
            if present == len(checks)
            else 'Project rules are partial; refresh AGENTS.md / code standards for stronger guidance.'
        ),
    }


def build_logic_check(project: Path) -> dict[str, Any]:
    existing = [rel for rel in EXPECTED_DOCS if _exists(project, rel)]
    modules = [{'file': rel, 'role': EXPECTED_DOCS[rel], 'status': 'present'} for rel in existing]
    links: list[dict[str, Any]] = []
    missing_links: list[str] = []
    weak_links: list[str] = []
    connected_count = 0
    applicable_count = 0
    for source, target, reason in EXPECTED_LINKS:
        source_exists = _exists(project, source)
        target_exists = _exists(project, target)
        if not source_exists and not target_exists:
            continue
        applicable_count += 1
        if not source_exists or not target_exists:
            status = 'missing'
            missing_links.append(f'{source} -> {target}')
        elif _mentions(project, source, target) or _mentions(project, target, source):
            status = 'connected'
            connected_count += 1
        else:
            status = 'implicit'
            connected_count += 1
            weak_links.append(f'{source} -> {target}')
        links.append({'source': source, 'target': target, 'status': status, 'reason': reason})

    known = set(EXPECTED_DOCS)
    orphan_docs = []
    docs_dir = project / 'docs'
    if docs_dir.exists():
        for path in sorted(docs_dir.glob('*.md')):
            rel = str(path.relative_to(project)).replace('\\', '/')
            if rel not in known:
                orphan_docs.append(rel)

    gate_rows = []
    for name, rel in QUALITY_GATES.items():
        gate_rows.append({'name': name, 'path': rel, 'status': 'covered' if _exists(project, rel) else 'missing'})
    covered_gates = sum(1 for item in gate_rows if item['status'] == 'covered')
    coverage_status = _status(covered_gates, len(gate_rows))
    if missing_links:
        workflow_status = 'broken'
    elif weak_links:
        workflow_status = 'partial'
    elif applicable_count and connected_count >= applicable_count:
        workflow_status = 'connected'
    elif applicable_count:
        workflow_status = 'partial'
    else:
        workflow_status = 'unknown'
    recommendations = []
    if missing_links:
        recommendations.append(f'Create or connect missing module link: {missing_links[0]}')
    if weak_links:
        recommendations.append('Add an explicit module relationship section to docs/usage_guide.md.')
    if coverage_status != 'complete':
        recommendations.append('Complete quality gate docs before trial use.')
    if orphan_docs:
        recommendations.append(f'Classify or link orphan document: {orphan_docs[0]}')
    if not recommendations:
        recommendations.append('Logic map is ready for trial use; run a concrete paper idea when ready.')
    return {
        'workflow_chain': workflow_status,
        'modules': modules,
        'links': links,
        'missing_links': missing_links,
        'weak_links': weak_links,
        'orphan_modules': orphan_docs,
        'quality_gates': gate_rows,
        'risk_coverage': coverage_status,
        'recommendations': recommendations[:3],
        'summary': (
            'Workflow modules are present, but some relationships should be made explicit.'
            if workflow_status == 'partial'
            else 'Workflow chain is connected.'
            if workflow_status == 'connected'
            else 'Workflow chain needs attention.'
        ),
    }


def build_project_logic_rules_check(project: Path) -> dict[str, Any]:
    rules = build_rules_check(project)
    logic = build_logic_check(project)
    payload = {
        'schema_version': '1.0',
        'generated_by': 'project_logic_rules_check.py',
        'generated_at': utc_now(),
        'project': project.name,
        'rules': rules,
        'logic': logic,
        'overall_status': 'needs_attention'
        if rules.get('status') == 'missing' or logic.get('workflow_chain') in {'broken', 'unknown'}
        else 'review'
        if rules.get('status') == 'partial' or logic.get('workflow_chain') == 'partial'
        else 'ready',
    }
    write_json(project / '.zoo-agent' / 'map' / 'project_logic_rules_check.json', payload)
    return payload


def render_logic_rules_check(project: Path) -> list[str]:
    payload = build_project_logic_rules_check(project)
    rules = payload.get('rules') if isinstance(payload.get('rules'), dict) else {}
    logic = payload.get('logic') if isinstance(payload.get('logic'), dict) else {}
    coverage = rules.get('coverage') if isinstance(rules.get('coverage'), dict) else {}
    lines = [
        '',
        'Project Rules:',
        f'- Status: {rules.get("status") or "unknown"}',
        f'- AGENTS.md: {next((item.get("status") for item in rules.get("checks", []) if item.get("name") == "AGENTS.md"), "unknown")}',
        f'- Code standards: {next((item.get("status") for item in rules.get("checks", []) if item.get("name") == "Code standards"), "unknown")}',
        f'- Research safety coverage: fake citations={str(bool(coverage.get("no_fake_citations"))).lower()}, fake results={str(bool(coverage.get("no_fake_results"))).lower()}, evidence separation={str(bool(coverage.get("evidence_separation"))).lower()}',
        '',
        'Logic Check:',
        f'- Workflow chain: {logic.get("workflow_chain") or "unknown"}',
        f'- Risk coverage: {logic.get("risk_coverage") or "unknown"}',
        f'- Orphan modules: {len(logic.get("orphan_modules") or [])}',
    ]
    weak = logic.get('weak_links') or []
    missing = logic.get('missing_links') or []
    if missing:
        lines.append(f'- Missing link: {missing[0]}')
    elif weak:
        lines.append(f'- Weak link: {weak[0]}')
    else:
        lines.append('- Missing link: none')
    recommendations = [str(item) for item in logic.get('recommendations') or [] if str(item).strip()]
    if recommendations:
        lines.extend(['', 'Recommended fix:'])
        lines.extend([f'- {item}' for item in recommendations[:2]])
    return lines


def main() -> int:
    parser = argparse.ArgumentParser(description='Check project rules and logic-map coverage.')
    parser.add_argument('--workspace', default='.')
    args = parser.parse_args()
    project = project_root(args.workspace)
    payload = build_project_logic_rules_check(project)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
