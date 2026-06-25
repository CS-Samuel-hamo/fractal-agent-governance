#!/usr/bin/env python3
from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
from pathlib import Path
from typing import Any

from project_map_evidence_collector import collect_evidence
from project_map_schema import (
    GENERATED_PATH_PATTERNS,
    MANIFEST_CANDIDATES,
    SOURCE_ROOT_CANDIDATES,
    TEST_ROOT_CANDIDATES,
    action_row,
    capability_row,
    default_project_map,
    default_project_state,
    map_dir,
    module_row,
    risk_row,
)
from runtime_common import latest_goal, load_json, project_root, utc_now, write_json


def _evidence_by_path(evidence: list[dict[str, Any]], path: str) -> list[dict[str, Any]]:
    return [item for item in evidence if str(item.get('path') or '') == path]


def detect_project_type(evidence: list[dict[str, Any]]) -> str:
    paths = {str(item.get('path') or '') for item in evidence}
    if any(item.get('kind') == 'seed_prompt' for item in evidence):
        return 'seed_prompt_project'
    if 'package.json' in paths:
        return 'javascript_or_typescript'
    if {'pyproject.toml', 'requirements.txt'} & paths:
        return 'python'
    if 'go.mod' in paths:
        return 'go'
    if 'Cargo.toml' in paths:
        return 'rust'
    return 'unknown'


def build_modules(evidence: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    dirs = {str(item.get('path') or ''): item for item in evidence if item.get('kind') == 'directory'}
    docs_evidence = [item for item in evidence if item.get('kind') == 'documentation_surface']
    seed_evidence = [item for item in evidence if item.get('kind') == 'seed_prompt']
    if seed_evidence:
        rows.append(
            module_row(
                'module-seed-prompt',
                'Seed prompt project brief',
                'User-provided project intent used to bootstrap a safe starter plan.',
                [str(item.get('path')) for item in seed_evidence],
                seed_evidence,
                status='mapped',
                confidence=0.72,
            )
        )
    if docs_evidence:
        rows.append(
            module_row(
                'module-docs',
                'Documentation',
                'User-facing project documentation.',
                [str(item.get('path')) for item in docs_evidence],
                docs_evidence,
                confidence=0.8,
            )
        )
    for module_id, name, purpose, roots in [
        (
            'module-source',
            'Source',
            'Main application or library code.',
            ['src', 'app', 'lib', 'frontend', 'backend', 'packages'],
        ),
        ('module-tests', 'Tests', 'Automated checks and test fixtures.', ['tests', 'test']),
        ('module-scripts', 'Local scripts', 'Local automation and developer scripts.', ['scripts']),
        ('module-examples', 'Examples', 'Runnable or readable examples.', ['examples']),
    ]:
        found = [root for root in roots if root in dirs]
        if found:
            ev = [dirs[root] for root in found]
            rows.append(module_row(module_id, name, purpose, found, ev, confidence=0.65))
    return rows


def build_capabilities(evidence: list[dict[str, Any]], modules: list[dict[str, Any]]) -> list[dict[str, Any]]:
    module_ids = [str(item.get('module_id')) for item in modules]
    paths = {str(item.get('path') or '') for item in evidence}
    seed_evidence = [item for item in evidence if item.get('kind') == 'seed_prompt']
    return [
        capability_row(
            'capability-seed-intent',
            'Seed prompt intent',
            'implemented' if seed_evidence else 'missing',
            seed_evidence,
            ['module-seed-prompt'] if 'module-seed-prompt' in module_ids else [],
        ),
        capability_row(
            'capability-onboarding-docs',
            'Onboarding documentation',
            'implemented' if 'README.md' in paths else 'missing',
            _evidence_by_path(evidence, 'README.md'),
            ['module-docs'] if 'module-docs' in module_ids else [],
        ),
        capability_row(
            'capability-test-surface',
            'Test surface',
            'partial' if {'tests', 'test'} & paths else 'missing',
            [item for item in evidence if item.get('path') in {'tests', 'test'}],
            ['module-tests'] if 'module-tests' in module_ids else [],
        ),
        capability_row(
            'capability-local-automation',
            'Local automation',
            'partial' if 'scripts' in paths else 'missing',
            _evidence_by_path(evidence, 'scripts'),
            ['module-scripts'] if 'module-scripts' in module_ids else [],
        ),
    ]


def build_risks(evidence_payload: dict[str, Any]) -> list[dict[str, Any]]:
    risks: list[dict[str, Any]] = []
    skipped = evidence_payload.get('skipped_sensitive_paths') or []
    if skipped:
        risks.append(
            risk_row(
                'risk-sensitive-surface',
                'Sensitive-looking files or directories exist and were intentionally not read.',
                'medium',
                ['<sensitive paths hidden>'],
                [
                    {
                        'kind': 'skip_record',
                        'path': '<hidden>',
                        'summary': 'Sensitive content was not read.',
                        'confidence': 1.0,
                    }
                ],
            )
        )
    return risks


def build_next_actions(evidence: list[dict[str, Any]], capabilities: list[dict[str, Any]]) -> list[dict[str, Any]]:
    paths = {str(item.get('path') or '') for item in evidence}
    actions: list[dict[str, Any]] = []
    seed_evidence = [item for item in evidence if item.get('kind') == 'seed_prompt']
    if seed_evidence:
        seed = seed_evidence[0]
        research_seed = bool(seed.get('research_seed'))
        targets = ['README.md', 'docs/project_plan.md']
        if research_seed:
            targets.append('docs/research_workflow.md')
        action = action_row(
            'action-seed-docs-bootstrap',
            'Create starter project documents from seed prompt',
            f'{seed.get("path")} is a safe seed prompt and the project needs a visible starting point.',
            'Turns the seed prompt into trusted documentation without running scripts or generating final paper content.',
            'low',
            targets,
            seed_evidence,
        )
        existing_targets = [target for target in targets if Path(target).as_posix() in paths]
        missing_targets = [target for target in targets if target not in existing_targets]
        all_targets_exist = bool(targets) and not missing_targets
        action.update(
            {
                'source': 'seed_prompt',
                'source_file': seed.get('path', ''),
                'action_type': 'create_or_preview_docs',
                'constraints': ['trusted_docs_only', 'no_script_execution', 'no_secret_access', 'no_overwrite'],
                'safety_constraints': [
                    'trusted_docs_only',
                    'no_script_execution',
                    'no_secret_access',
                    'no_external_network',
                    'no_fake_citations',
                    'no_final_paper_generation',
                ],
                'preview_only': all_targets_exist,
                'preview_reason': 'all starter docs already exist; no overwrite' if all_targets_exist else '',
                'existing_targets': existing_targets,
                'missing_targets': missing_targets,
                'fallback_behavior': {
                    'if_target_exists': 'skip_existing_create_missing',
                    'if_all_targets_exist': 'preview_only',
                    'if_ambiguous_intent': 'present_options',
                },
            }
        )
        actions.append(action)
    if 'README.md' in paths:
        actions.append(
            action_row(
                'action-readme-progress-note',
                'Add a concise README progress note',
                'README.md exists and can be updated without runtime behavior change.',
                'Improves project visibility without runtime behavior change.',
                'low',
                ['README.md'],
                _evidence_by_path(evidence, 'README.md'),
            )
        )
    if 'docs' in paths:
        docs_targets = sorted(path for path in paths if path.startswith('docs/') and path.endswith('.md'))
        target = 'docs/README.md' if 'docs/README.md' in paths else (docs_targets[0] if docs_targets else '')
        actions.append(
            action_row(
                'action-docs-index-review',
                'Clarify documentation guide wording',
                'docs/ exists and can be improved without touching runtime behavior.',
                'Improves documentation readiness.',
                'low',
                [target] if target else [],
                _evidence_by_path(evidence, 'docs'),
                autopilot_eligible=bool(target),
            )
        )
    if any(
        item.get('capability_id') == 'capability-test-surface' and item.get('status') == 'missing'
        for item in capabilities
    ):
        actions.append(
            action_row(
                'action-test-readiness-note',
                'Document test readiness gap',
                'No test directory was detected from safe evidence.',
                'Makes release readiness gaps visible.',
                'low',
                ['README.md'] if 'README.md' in paths else [],
                [item for item in evidence if item.get('path') == 'README.md'],
                autopilot_eligible='README.md' in paths,
            )
        )
    return actions


def render_markdown(project_map: dict[str, Any]) -> str:
    lines = [
        '# Project Map',
        '',
        f'- project: {project_map.get("project_name")}',
        f'- type: {project_map.get("project_type")}',
        f'- goal: {project_map.get("main_goal") or "unknown"}',
        '',
        '## Modules',
    ]
    for module in project_map.get('modules') or []:
        lines.append(f'- {module.get("name")}: {module.get("status")} ({module.get("confidence")})')
    lines += ['', '## Next Actions']
    for action in project_map.get('next_actions') or []:
        lines.append(f'- {action.get("title")} [{action.get("risk_level")}]')
    lines.append('')
    return '\n'.join(lines)


# ── Filesystem inventory (consolidated from check_project_map_alignment.py) ──


def _normalize(value: str) -> str:
    return value.replace('\\', '/').rstrip('/')


def _matches_any(path: str, patterns: list[str]) -> bool:
    return any(fnmatch.fnmatch(path, pat) for pat in patterns)


def _existing_paths(project: Path, candidates: list[str]) -> list[str]:
    return [item for item in candidates if (project / item).exists()]


def _source_roots(project: Path) -> list[str]:
    profile = load_json(project / '.zoo-agent' / 'project-profile.json')
    roots = [_normalize(str(item)) for item in profile.get('source_roots') or [] if str(item)]
    roots = [item for item in roots if (project / item).exists() and not _matches_any(item, GENERATED_PATH_PATTERNS)]
    return sorted(set(roots)) if roots else _existing_paths(project, SOURCE_ROOT_CANDIDATES)


def build_inventory(project: Path) -> dict[str, Any]:
    """Build a filesystem inventory snapshot, used for alignment checking."""
    roots = _source_roots(project)
    tests = _existing_paths(project, TEST_ROOT_CANDIDATES)
    manifests = _existing_paths(project, MANIFEST_CANDIDATES)
    rows: list[dict[str, Any]] = []
    for root in roots + tests + manifests:
        base = project / root
        if not base.exists():
            continue
        targets = [base] if base.is_file() else sorted(base.rglob('*'))
        for path in targets:
            if not path.is_file():
                continue
            rel = _normalize(str(path.relative_to(project)))
            if _matches_any(rel, GENERATED_PATH_PATTERNS):
                continue
            try:
                stat = path.stat()
                rows.append({'path': rel, 'size': stat.st_size, 'mtime_ns': stat.st_mtime_ns})
            except OSError:
                continue
    h = hashlib.sha256()
    for row in sorted(rows, key=lambda r: r['path']):
        h.update(f'{row["path"]}\0{row["size"]}\0{row["mtime_ns"]}\n'.encode())
    return {
        'source_roots': roots,
        'test_roots': tests,
        'manifests': manifests,
        'filesystem_digest': h.hexdigest(),
        'inventory_file_count': len(rows),
        'sample_files': [r['path'] for r in sorted(rows, key=lambda r: r['path'])][:100],
    }


def build_project_map(project: Path, *, main_goal: str = '') -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    evidence_payload = collect_evidence(project, main_goal=main_goal)
    evidence = list(evidence_payload.get('evidence') or [])
    goal = main_goal or str((latest_goal(project) or {}).get('goal') or '')
    project_map = default_project_map(project, main_goal=goal)
    project_map['project_type'] = detect_project_type(evidence)
    project_map['modules'] = build_modules(evidence)
    project_map['capabilities'] = build_capabilities(evidence, project_map['modules'])
    project_map['risks'] = build_risks(evidence_payload)
    project_map['next_actions'] = build_next_actions(evidence, project_map['capabilities'])
    project_map['last_updated'] = utc_now()
    project_map['inventory'] = build_inventory(project)
    project_state = default_project_state(project, main_goal=goal)
    project_state['status'] = 'mapped' if project_map['modules'] else 'unknown'
    project_state['progress'] = '10%' if project_map['modules'] else '0%'
    return project_map, project_state, evidence_payload


def main() -> int:
    parser = argparse.ArgumentParser(description='Build an evidence-backed project map.')
    parser.add_argument('--workspace', default='.')
    parser.add_argument('--goal', default='')
    parser.add_argument(
        '--check-alignment', action='store_true', help='Check alignment and exit with code 10 if misaligned.'
    )
    args = parser.parse_args()
    project = project_root(args.workspace)
    payload, state, evidence = build_project_map(project, main_goal=args.goal)
    out_dir = map_dir(project)
    write_json(out_dir / 'project_map.json', payload)
    write_json(out_dir / 'project_state.json', state)
    write_json(out_dir / 'map_evidence.json', evidence)
    md = out_dir / 'project_map.md'
    md.parent.mkdir(parents=True, exist_ok=True)
    md.write_text(render_markdown(payload), encoding='utf-8')

    # Write inventory separately for alignment checking
    inventory = payload.get('inventory') or {}
    write_json(out_dir / 'inventory.json', inventory)

    # Alignment check (compare current digest vs stored)
    if args.check_alignment:
        stored = load_json(out_dir / 'inventory.json')
        current = build_inventory(project)
        aligned = stored.get('filesystem_digest') == current.get('filesystem_digest')
        if not aligned:
            print(json.dumps({'status': 'misaligned', 'digest_changed': True}, ensure_ascii=False, indent=2))
            return 10

    print(
        json.dumps(
            {
                'status': 'ok',
                'project_map': str(out_dir / 'project_map.json'),
                'next_action_count': len(payload.get('next_actions') or []),
                'filesystem_digest': inventory.get('filesystem_digest', ''),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
