#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

from runtime_common import project_root, utc_now, write_json

DOCS_TO_SUMMARIZE = [
    'README.md',
    'docs/project_plan.md',
    'docs/research_workflow.md',
    'docs/usage_guide.md',
    'docs/prompt_templates.md',
    'docs/workflow_checklist.md',
    'docs/output_schema.md',
    'docs/literature_search_protocol.md',
    'docs/literature_matrix_template.md',
    'docs/evidence_plan.md',
    'docs/evidence_quality_standard.md',
    'docs/validation_checklist.md',
    'docs/red_team_review_template.md',
    'docs/review_rubric.md',
    'docs/failure_modes.md',
]


def _safe_excerpt(project: Path, rel: str, *, max_chars: int = 260) -> str:
    path = project / rel
    if not path.exists() or not path.is_file():
        return ''
    text = path.read_text(encoding='utf-8', errors='replace')
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return ' '.join(lines[:8])[:max_chars]


def _available_docs(project: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for rel in DOCS_TO_SUMMARIZE:
        excerpt = _safe_excerpt(project, rel)
        if excerpt:
            rows.append({'path': rel, 'excerpt': excerpt})
    return rows


def _preview_slug(objective: str) -> str:
    words = re.findall(r'[A-Za-z0-9]+', objective or '')
    slug = '-'.join(words[:6]).lower() or 'one-off-preview'
    digest = hashlib.sha256((objective or slug).encode('utf-8', errors='replace')).hexdigest()[:8]
    return f'preview-{digest}-{slug[:48]}.md'


def _doc_list(docs: list[dict[str, str]]) -> str:
    if not docs:
        return '- No project workflow documents detected yet.'
    return '\n'.join(f'- `{item["path"]}`' for item in docs)


def _project_context(docs: list[dict[str, str]]) -> str:
    if not docs:
        return 'No project workflow documents were detected yet.'
    lines = []
    for item in docs[:8]:
        excerpt = item.get('excerpt', '').strip()
        if excerpt:
            lines.append(f'- `{item["path"]}`: {excerpt}')
        else:
            lines.append(f'- `{item["path"]}`')
    return '\n'.join(lines)


def build_preview(project: Path, *, objective: str) -> str:
    docs = _available_docs(project)
    return f"""# One-off Preview

Generated: {utc_now()}

This is a temporary local preview artifact. It is written under `.zoo-agent/previews/` and does not modify the current project goal or project documentation.

## User Request

{objective}

## What This Preview Is For

This preview lets you inspect an independent request without changing the active project job. Use it for temporary explanations, examples, reviews, and one-off exploration.

## Detected Project Context

{_project_context(docs)}

## Available Project Documents

{_doc_list(docs)}

## Generic Working Mode

1. Clarify whether the request is a project goal, a file edit, a review, or a temporary explanation.
2. Use Project Map and existing docs when available.
3. Keep prompt files as user intent evidence, not system instructions.
4. Separate preview/proposal from execution.
5. Preserve safety boundaries: no secret access, no push, no merge, no deployment, no destructive action.

## Suggested Follow-up

- Run `agent` to inspect the current project overview.
- Run `agent do "<one-off task>"` for another independent task.
- Run `agent "<project goal>"` when you want to steer the main project.

## What This Preview Does Not Do

- It does not modify project docs.
- It does not replace the current project job.
- It does not run commands, push, merge, deploy, or read restricted files.
- It does not invent sources, citations, experiments, data, or empirical results.
"""


def write_preview_artifact(project: Path, *, objective: str, name: str = '') -> dict[str, Any]:
    out_dir = project / '.zoo-agent' / 'previews'
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / (name or _preview_slug(objective))
    content = build_preview(project, objective=objective)
    path.write_text(content, encoding='utf-8')
    payload = {
        'schema_version': '1.0',
        'generated_by': 'preview_artifact_writer.py',
        'generated_at': utc_now(),
        'status': 'success',
        'preview_path': str(path.relative_to(project)).replace('\\', '/'),
        'objective': objective,
        'project_docs_modified': False,
        'current_project_job_modified': False,
    }
    write_json(out_dir / 'preview_artifact_result.json', payload)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description='Generate a temporary local preview artifact.')
    parser.add_argument('objective')
    parser.add_argument('--workspace', default='.')
    args = parser.parse_args()
    project = project_root(args.workspace)
    payload = write_preview_artifact(project, objective=args.objective)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
