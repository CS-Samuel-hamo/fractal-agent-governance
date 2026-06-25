#!/usr/bin/env python3
from __future__ import annotations

import json
import tempfile
from pathlib import Path

from project_logic_rules_check import build_project_logic_rules_check, render_logic_rules_check


def repo(name: str) -> Path:
    return Path(tempfile.mkdtemp(prefix=f'{name}-', dir=tempfile.gettempdir())).resolve()


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding='utf-8')


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')


def assert_true(value: bool, message: str) -> None:
    if not value:
        raise AssertionError(message)


def make_toolkit(project: Path, *, explicit_links: bool = True) -> None:
    write(
        project / 'project_beginning_prompt.md',
        'Build a research workflow through docs/project_plan.md. Do not invent citations or fake data.',
    )
    write(project / 'docs/project_plan.md', 'Use docs/research_workflow.md as the main workflow.')
    write(project / 'docs/research_workflow.md', 'Use docs/prompt_templates.md and docs/workflow_checklist.md.')
    write(project / 'docs/usage_guide.md', 'Run the workflow.')
    write(
        project / 'docs/prompt_templates.md',
        'Templates produce docs/output_schema.md.' if explicit_links else 'Templates for paper workflow.',
    )
    write(project / 'docs/workflow_checklist.md', 'Checklist for the workflow.')
    write(project / 'docs/output_schema.md', 'Output schema.')
    write(project / 'docs/literature_search_protocol.md', 'Feed docs/literature_matrix_template.md.')
    write(project / 'docs/literature_matrix_template.md', 'Literature matrix.')
    write(project / 'docs/evidence_plan.md', 'Follow docs/evidence_quality_standard.md.')
    write(project / 'docs/evidence_quality_standard.md', 'Evidence standard for docs/review_rubric.md.')
    write(project / 'docs/validation_checklist.md', 'Use docs/red_team_review_template.md.')
    write(project / 'docs/red_team_review_template.md', 'Covers docs/failure_modes.md.')
    write(project / 'docs/review_rubric.md', 'Review rubric.')
    write(project / 'docs/failure_modes.md', 'Failure modes.')


def test_logic_rules_ready_when_rules_and_links_exist() -> None:
    project = repo('logic-rules-ready')
    make_toolkit(project)
    write(
        project / 'AGENTS.md', 'Do not read .env. Do not invent citations. Separate facts, assumptions, and evidence.'
    )
    write_json(
        project / '.zoo-agent' / 'code-standards.json',
        {
            'forbidden_actions': ['Do not read secrets.', 'Do not invent fake empirical results.'],
            'done_criteria': ['Evidence is checked.'],
        },
    )
    payload = build_project_logic_rules_check(project)
    assert_true(payload['rules']['status'] == 'complete', 'rules should be complete')
    assert_true(
        payload['logic']['workflow_chain'] == 'connected',
        f'unexpected workflow status: {payload["logic"]["workflow_chain"]}',
    )
    assert_true(payload['logic']['risk_coverage'] == 'complete', 'quality gates should be complete')
    assert_true(payload['overall_status'] == 'ready', 'overall status should be ready')
    lines = '\n'.join(render_logic_rules_check(project))
    assert_true('Project Rules:' in lines and 'Logic Check:' in lines, 'rendered logic check missing sections')


def test_logic_rules_flags_partial_rules_and_weak_links() -> None:
    project = repo('logic-rules-partial')
    make_toolkit(project, explicit_links=False)
    payload = build_project_logic_rules_check(project)
    assert_true(payload['rules']['status'] in {'missing', 'partial'}, 'rules should not be complete')
    assert_true(payload['logic']['workflow_chain'] in {'partial', 'connected'}, 'workflow should be known')
    assert_true(payload['logic']['recommendations'], 'recommendations should be present')
    assert_true(
        (project / '.zoo-agent' / 'map' / 'project_logic_rules_check.json').exists(), 'artifact was not written'
    )


def main() -> int:
    test_logic_rules_ready_when_rules_and_links_exist()
    test_logic_rules_flags_partial_rules_and_weak_links()
    print('project logic rules check tests passed')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
