#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from runtime_common import project_root, utc_now, write_json

SOURCE_ROOT_CANDIDATES = [
    'src',
    'app',
    'lib',
    'packages',
    'services',
    'frontend/src',
    'scripts',
]
TEST_ROOT_CANDIDATES = ['tests', 'test', 'spec', 'frontend/tests', 'frontend/spec']
MANIFEST_CANDIDATES = [
    'package.json',
    'frontend/package.json',
    'pyproject.toml',
    'requirements.txt',
    'setup.cfg',
    'pytest.ini',
    'Cargo.toml',
    'go.mod',
]


def load_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding='utf-8-sig'))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def detect_existing(paths: list[str], project: Path) -> list[str]:
    return [item for item in paths if (project / item).exists()]


def package_scripts(project: Path, relative_path: str) -> dict[str, str]:
    payload = load_json(project / relative_path)
    scripts = payload.get('scripts') if isinstance(payload.get('scripts'), dict) else {}
    return {str(key): str(value) for key, value in scripts.items()}


def command_from_package(relative_path: str, name: str) -> str:
    prefix = 'cd frontend && ' if relative_path.startswith('frontend/') else ''
    runner = 'npm'
    return f'{prefix}{runner} run {name}'


def detect_commands(project: Path) -> dict[str, list[str]]:
    commands: dict[str, list[str]] = {'test': [], 'lint': [], 'format': [], 'typecheck': []}
    for package_path in ['package.json', 'frontend/package.json']:
        if not (project / package_path).exists():
            continue
        scripts = package_scripts(project, package_path)
        for script_name in scripts:
            lower = script_name.lower()
            if lower == 'test' or lower.startswith('test:'):
                commands['test'].append(command_from_package(package_path, script_name))
            elif lower == 'lint' or lower.startswith('lint:'):
                commands['lint'].append(command_from_package(package_path, script_name))
            elif lower in {'format', 'fmt'} or lower.startswith('format:'):
                commands['format'].append(command_from_package(package_path, script_name))
            elif lower in {'typecheck', 'type-check', 'check'} or lower.startswith('typecheck:'):
                commands['typecheck'].append(command_from_package(package_path, script_name))

    if (project / 'tests').exists() or (project / 'pytest.ini').exists() or (project / 'pyproject.toml').exists():
        commands['test'].append('python -m pytest')

    for key in list(commands):
        seen: set[str] = set()
        commands[key] = [item for item in commands[key] if item and not (item in seen or seen.add(item))]
    return commands


def build_code_standards(project: Path) -> dict[str, Any]:
    source_roots = detect_existing(SOURCE_ROOT_CANDIDATES, project)
    test_roots = detect_existing(TEST_ROOT_CANDIDATES, project)
    manifests = detect_existing(MANIFEST_CANDIDATES, project)
    commands = detect_commands(project)
    return {
        'schema_version': '1.0',
        'generated_by': 'init_project_instructions.py',
        'generated_at': utc_now(),
        'workspace': str(project),
        'role_contract': {
            'cli_runtime': 'control plane for routing, goal, loop, execution control, status, rollback, review, and metrics',
            'codex_cli': 'execution backend only; not planner, orchestrator, or merge decision maker',
            'gpt': 'final decision layer for governed work and review',
            'deepseek': 'cheap analysis worker',
            'zoo_code': 'optional visualization and control UI',
        },
        'project_layout': {
            'source_roots': source_roots,
            'test_roots': test_roots,
            'manifests': manifests,
        },
        'commands': commands,
        'coding_rules': [
            'Follow existing local style and framework conventions before introducing new abstractions.',
            'Keep changes inside the task allowed_files surface.',
            'Do not add dependencies unless the task explicitly requires and approves them.',
            'Do not change database schema, auth, security, public API, deployment, or release surfaces without governed approval.',
            'Prefer focused tests that match the changed surface.',
        ],
        'forbidden_actions': [
            'Do not run git push.',
            'Do not run git reset --hard.',
            'Do not delete project source files unless explicitly instructed.',
            'Do not read or print secrets, credentials, provider profiles, or auth tokens.',
            'Do not treat reviewer approval, tests, or record-only merge queues as merge/deploy/release authorization.',
        ],
        'done_criteria': [
            'Implementation is bounded to the assigned scope.',
            'Relevant tests or an explicit test deferral are recorded.',
            'Scope guard passes for merge candidates.',
            'Goal alignment evidence exists for reviewed or integrated work.',
            'Run evidence is available under .zoo-agent/runs/<run-id>/.',
        ],
        'sources': {
            'inspired_by': 'Codex /init style project-local instructions',
            'active_agents_md': 'AGENTS.md',
            'proposal_agents_md': 'AGENTS.md.new',
        },
    }


def render_agents_md(standards: dict[str, Any]) -> str:
    layout = standards.get('project_layout') if isinstance(standards.get('project_layout'), dict) else {}
    commands = standards.get('commands') if isinstance(standards.get('commands'), dict) else {}

    def bullet_list(items: list[Any], fallback: str = 'none detected') -> list[str]:
        values = [str(item) for item in items if str(item)]
        return [f'- {item}' for item in values] or [f'- {fallback}']

    lines = [
        '# AGENTS.md',
        '',
        'This project is operated through the CLI-first Agent Runtime.',
        '',
        '## Runtime Roles',
        '',
        '- CLI Runtime: control plane for routing, goal, loop, execution control, status, rollback, review, and metrics.',
        '- Codex CLI: execution backend only; it is not the planner, orchestrator, or merge decision maker.',
        '- GPT: final decision layer for governed work and review.',
        '- DeepSeek: cheap analysis worker.',
        '- Zoo Code: optional visualization and control UI.',
        '',
        '## Project Map',
        '',
        'Source roots:',
        *bullet_list(layout.get('source_roots') or []),
        '',
        'Test roots:',
        *bullet_list(layout.get('test_roots') or []),
        '',
        'Manifests:',
        *bullet_list(layout.get('manifests') or []),
        '',
        '## Commands',
        '',
        'Test commands:',
        *bullet_list(commands.get('test') or []),
        '',
        'Lint commands:',
        *bullet_list(commands.get('lint') or []),
        '',
        'Format commands:',
        *bullet_list(commands.get('format') or []),
        '',
        'Typecheck commands:',
        *bullet_list(commands.get('typecheck') or []),
        '',
        '## Coding Rules',
        '',
        *bullet_list(standards.get('coding_rules') or []),
        '',
        '## Forbidden Actions',
        '',
        *bullet_list(standards.get('forbidden_actions') or []),
        '',
        '## Done Criteria',
        '',
        *bullet_list(standards.get('done_criteria') or []),
        '',
    ]
    return '\n'.join(lines)


def check_standards(project: Path) -> tuple[str, list[dict[str, str]], dict[str, Any]]:
    standards_path = project / '.zoo-agent' / 'code-standards.json'
    agents_path = project / 'AGENTS.md'
    standards = load_json(standards_path)
    blockers: list[dict[str, str]] = []
    if not standards:
        blockers.append({'id': 'missing_code_standards', 'message': 'Missing .zoo-agent/code-standards.json.'})
    if not agents_path.exists():
        blockers.append({'id': 'missing_agents_md', 'message': 'Missing AGENTS.md.'})
    role_contract = standards.get('role_contract') if isinstance(standards.get('role_contract'), dict) else {}
    for key in ['cli_runtime', 'codex_cli', 'gpt', 'deepseek', 'zoo_code']:
        if standards and key not in role_contract:
            blockers.append({'id': f'missing_role_{key}', 'message': f'Missing role contract for {key}.'})
    status = 'pass' if not blockers else 'blocked'
    return status, blockers, standards


def write_init(project: Path, *, refresh: bool, dry_run: bool) -> dict[str, Any]:
    standards = build_code_standards(project)
    agents_text = render_agents_md(standards)
    zoo_dir = project / '.zoo-agent'
    standards_path = zoo_dir / 'code-standards.json'
    standards_proposal_path = zoo_dir / 'code-standards.json.new'
    agents_path = project / 'AGENTS.md'
    agents_proposal_path = project / 'AGENTS.md.new'

    actions: list[dict[str, str]] = []
    if agents_path.exists():
        target_agents = agents_proposal_path
        actions.append({'action': 'write_proposal', 'path': str(target_agents), 'reason': 'AGENTS.md already exists'})
    else:
        target_agents = agents_path
        actions.append({'action': 'write_active', 'path': str(target_agents), 'reason': 'AGENTS.md missing'})

    if standards_path.exists() and refresh:
        target_standards = standards_proposal_path
        actions.append(
            {'action': 'write_proposal', 'path': str(target_standards), 'reason': 'code standards refresh requested'}
        )
    elif standards_path.exists():
        target_standards = standards_path
        actions.append(
            {'action': 'keep_active', 'path': str(target_standards), 'reason': 'code standards already exist'}
        )
    else:
        target_standards = standards_path
        actions.append({'action': 'write_active', 'path': str(target_standards), 'reason': 'code standards missing'})

    if not dry_run:
        if target_agents == agents_path or refresh or not target_agents.exists():
            target_agents.write_text(agents_text, encoding='utf-8')
        if target_standards != standards_path or not standards_path.exists() or refresh:
            write_json(target_standards, standards)

    report = {
        'schema_version': '1.0',
        'generated_by': 'init_project_instructions.py',
        'generated_at': utc_now(),
        'workspace': str(project),
        'status': 'dry_run' if dry_run else 'ok',
        'refresh': refresh,
        'actions': actions,
        'agents_path': str(agents_path),
        'agents_proposal_path': str(agents_proposal_path),
        'code_standards_path': str(standards_path),
        'code_standards_proposal_path': str(standards_proposal_path),
        'code_standards': standards,
    }
    if not dry_run:
        write_json(zoo_dir / 'init-report.json', report)
    return report


def promote(project: Path, *, dry_run: bool) -> dict[str, Any]:
    actions: list[dict[str, str]] = []
    agents_path = project / 'AGENTS.md'
    agents_proposal = project / 'AGENTS.md.new'
    standards_path = project / '.zoo-agent' / 'code-standards.json'
    standards_proposal = project / '.zoo-agent' / 'code-standards.json.new'

    if agents_proposal.exists():
        actions.append({'action': 'promote', 'from': str(agents_proposal), 'to': str(agents_path)})
        if not dry_run:
            agents_path.write_text(agents_proposal.read_text(encoding='utf-8'), encoding='utf-8')
            agents_proposal.unlink()
    if standards_proposal.exists():
        actions.append({'action': 'promote', 'from': str(standards_proposal), 'to': str(standards_path)})
        if not dry_run:
            write_json(standards_path, load_json(standards_proposal))
            standards_proposal.unlink()
    status = 'no_proposals' if not actions else ('dry_run' if dry_run else 'promoted')
    report = {
        'schema_version': '1.0',
        'generated_by': 'init_project_instructions.py',
        'generated_at': utc_now(),
        'workspace': str(project),
        'status': status,
        'actions': actions,
    }
    if not dry_run:
        write_json(project / '.zoo-agent' / 'init-report.json', report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description='Initialize or validate project-local agent instructions.')
    parser.add_argument('--workspace', default='.')
    parser.add_argument('--refresh', action='store_true')
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--promote', action='store_true')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()

    actions = [args.check, args.promote]
    if sum(1 for item in actions if item) > 1:
        raise SystemExit('Choose at most one of --check or --promote.')

    project = project_root(args.workspace)
    if args.check:
        status, blockers, standards = check_standards(project)
        report = {
            'schema_version': '1.0',
            'generated_by': 'init_project_instructions.py',
            'generated_at': utc_now(),
            'workspace': str(project),
            'status': status,
            'blockers': blockers,
            'code_standards_path': str(project / '.zoo-agent' / 'code-standards.json'),
            'agents_path': str(project / 'AGENTS.md'),
            'code_standards': standards,
        }
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if status == 'pass' else 20
    if args.promote:
        report = promote(project, dry_run=args.dry_run)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0

    report = write_init(project, refresh=args.refresh, dry_run=args.dry_run)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
