from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any

from runtime_common import load_json, project_root, resolve_goal, safe_name, utc_now, write_json


ROOT = Path(__file__).resolve().parents[1]

BIG_TASK_TERMS = [
    'architecture', 'architectural', 'system', 'project', 'multi-module', 'cross-module',
    'end-to-end', 'e2e', 'refactor', 'migration', 'migrate', 'database', 'schema',
    'public api', 'api response', 'dto', 'auth', 'security', 'integration',
]
HIGH_RISK_TERMS = [
    'database', 'schema', 'migration', 'auth', 'security', 'public api', 'api response',
    'deployment', 'production', 'release', 'permission', 'token', 'secret',
]
CRITICAL_RISK_TERMS = ['production migration', 'deploy', 'release', 'delete data', 'payment']
DOC_TERMS = ['docs', 'documentation', 'readme', '.md']
CODE_TERMS = ['code', 'src', 'implementation', 'feature', 'bug', 'test']
DENIED_FILES = ['.env', '.env.*', '**/*.pem', '**/*.key', 'secrets/**', 'credentials/**']


PATH_RE = re.compile(
    r'(?P<path>(?:[A-Za-z0-9_.-]+[\\/])*[A-Za-z0-9_.@-]+\.(?:py|ts|tsx|js|jsx|json|md|yml|yaml|toml|css|scss|html|go|rs|java|cs))'
)


def read_text_safe(path: Path) -> str:
    try:
        return path.read_text(encoding='utf-8-sig')
    except Exception:
        return ''


def rel(project: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(project.resolve()).as_posix()
    except Exception:
        return path.as_posix()


def git_head(project: Path) -> str:
    proc = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=project, text=True, encoding='utf-8', errors='replace', stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return proc.stdout.strip() if proc.returncode == 0 else ''


def is_git_repo(project: Path) -> bool:
    proc = subprocess.run(['git', 'rev-parse', '--show-toplevel'], cwd=project, text=True, encoding='utf-8', errors='replace', stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return proc.returncode == 0


def load_backend_profile(project: Path) -> dict[str, Any]:
    return load_json(project / '.zoo-agent' / 'backend' / 'codex-backend-profile.json')


def load_project_readiness(project: Path) -> dict[str, Any]:
    return load_json(project / '.zoo-agent' / 'project-readiness.json')


def source_roots(project: Path) -> list[str]:
    candidates = ['src', 'app', 'lib', 'packages', 'services', 'backend', 'frontend', 'scripts']
    return [item for item in candidates if (project / item).exists()]


def test_roots(project: Path) -> list[str]:
    candidates = ['tests', 'test', 'spec', 'frontend/tests', 'backend/tests']
    return [item for item in candidates if (project / item).exists()]


def infer_paths(text: str) -> list[str]:
    paths = [match.group('path').replace('\\', '/') for match in PATH_RE.finditer(text)]
    lowered = text.lower()
    if 'readme' in lowered and not any(path.lower().startswith('readme') for path in paths):
        paths.append('README.md')
    if 'docs' in lowered and not any(path.startswith('docs/') for path in paths):
        paths.append('docs/**')
    if any(term in lowered for term in ['api', 'dto', 'schema']) and 'api/**' not in paths:
        paths.append('api/**')
    if any(term in lowered for term in ['database', 'migration', 'table']) and 'database/**' not in paths:
        paths.append('database/**')
    return sorted(set(paths))


def infer_domains(text: str, paths: list[str]) -> list[str]:
    lowered = ' '.join([text, *paths]).lower()
    domains: set[str] = set()
    if any(term in lowered for term in ['api', 'dto', 'schema', 'response']):
        domains.add('api_contract')
    if any(term in lowered for term in ['database', 'table', 'migration']):
        domains.add('database')
    if any(term in lowered for term in ['auth', 'security', 'permission']):
        domains.add('auth_security')
    if any(term in lowered for term in DOC_TERMS):
        domains.add('documentation')
    if any(term in lowered for term in CODE_TERMS):
        domains.add('implementation')
    roots = source_roots(Path.cwd())
    if any(path.split('/')[0] in roots for path in paths if '/' in path):
        domains.add('source')
    return sorted(domains or {'unknown'})


def risk_level(text: str, paths: list[str] | None = None) -> str:
    surface = ' '.join([text, *(paths or [])]).lower()
    if any(term in surface for term in CRITICAL_RISK_TERMS):
        return 'critical'
    if any(term in surface for term in HIGH_RISK_TERMS):
        return 'high'
    if any(term in surface for term in BIG_TASK_TERMS) or len(paths or []) > 3:
        return 'medium'
    return 'low'


def is_big_task(text: str, paths: list[str] | None = None) -> bool:
    surface = text.lower()
    if any(term in surface for term in BIG_TASK_TERMS):
        return True
    return len(paths or []) > 3


def test_capability(project: Path) -> str:
    if test_roots(project):
        return 'known'
    if any((project / name).exists() for name in ['package.json', 'pyproject.toml', 'pytest.ini', 'requirements.txt']):
        return 'partial'
    return 'unknown'


def rollback_capability(project: Path) -> str:
    if is_git_repo(project) and git_head(project):
        return 'known'
    if is_git_repo(project):
        return 'partial'
    return 'unknown'


def architecture_known(project: Path) -> bool:
    candidates = ['docs/architecture.md', 'ARCHITECTURE.md', '.zoo-agent/project-map.json', '.zoo-agent/project-resource-map.json']
    return any((project / item).exists() for item in candidates)


def success_criteria_from_goal(goal: dict[str, Any], text: str) -> list[str]:
    criteria = [str(item) for item in goal.get('success_criteria') or [] if str(item).strip()]
    if criteria:
        return criteria
    lowered = text.lower()
    if any(term in lowered for term in DOC_TERMS):
        return ['Target documentation changes are explicitly scoped and reviewable.']
    if any(term in lowered for term in CODE_TERMS + HIGH_RISK_TERMS):
        return ['Each required behavior is represented by a ready leaf contract and test policy.']
    return []


def non_goals_from_goal(goal: dict[str, Any]) -> list[str]:
    return [str(item) for item in goal.get('non_goals') or [] if str(item).strip()]


def big_loop_state(project: Path, run_id: str, goal_id: str, phase: str, *, max_iterations: int = 5) -> dict[str, Any]:
    path = project / '.zoo-agent' / 'runs' / run_id / 'loop-state.json'
    state = load_json(path)
    if not state:
        state = {
            'run_id': run_id,
            'goal_id': goal_id,
            'phase': phase,
            'iteration': 0,
            'max_iterations': max_iterations,
            'decomposition_rounds': 0,
            'max_decomposition_rounds': 2,
            'leaf_redo_count': 0,
            'max_leaf_redo_count': 2,
            'status': 'active',
            'no_delivery_count': 0,
            'backend_failure_count': 0,
            'doc_only_count': 0,
            'local_optimization_count': 0,
            'last_verdict': '',
            'next_action': '',
        }
    state['phase'] = phase
    state['updated_at'] = utc_now()
    write_json(path, state)
    return state


def classify_readiness(contract: dict[str, Any]) -> tuple[str, str, list[str], str]:
    blockers = list(contract.get('blocking_reasons') or [])
    risk = contract.get('risk_level') or 'medium'
    backend = load_json(Path(str(contract.get('backend_profile_ref')))) if contract.get('backend_profile_ref') else {}
    backend_status = str(backend.get('health_status') or 'unknown')
    readiness = load_json(Path(str(contract.get('project_readiness_ref')))) if contract.get('project_readiness_ref') else {}
    test_status = contract.get('test_capability') or 'unknown'
    rollback_status = contract.get('rollback_capability') or 'unknown'
    criteria = [item for item in contract.get('success_criteria') or [] if str(item).strip()]
    readiness_blockers = []
    if readiness:
        raw_blockers = readiness.get('blockers') or readiness.get('blocking_issues') or []
        if isinstance(raw_blockers, list):
            for item in raw_blockers:
                if isinstance(item, dict) and item.get('severity') == 'blocking':
                    readiness_blockers.append(str(item.get('type') or item.get('message') or 'project_readiness_blocker'))
                elif isinstance(item, str):
                    readiness_blockers.append(item)
        for key in ['safe_for_bootstrap', 'safe_for_level_0_1_trial', 'safe_for_codex_actual_run']:
            if readiness.get(key) is False:
                readiness_blockers.append(key)

    if not contract.get('goal_id'):
        blockers.append('missing_goal')
        return 'BLOCKED_GOAL_UNCLEAR', 'blocked', blockers, 'Set an explicit /goal with success criteria and non-goals.'
    if readiness_blockers:
        blockers.extend(f'project_not_ready:{item}' for item in readiness_blockers)
        return 'BLOCKED_PROJECT_NOT_READY', 'blocked', blockers, 'Resolve project readiness blockers before big task decomposition.'
    if risk in {'high', 'critical'}:
        blockers.append('high_or_critical_risk_requires_human_gate')
        return 'BLOCKED_HIGH_RISK_HUMAN_GATE', 'blocked', blockers, 'Use GPT/human architecture review before leaf execution.'
    if not contract.get('architecture_known') and len(contract.get('affected_domains') or []) > 1:
        blockers.append('architecture_unknown_for_cross_domain_change')
        return 'READY_FOR_DECOMPOSITION_ONLY', 'decomposition_only', blockers, 'Generate leaf contracts; do not execute leaves yet.'
    if not criteria:
        blockers.append('success_criteria_not_verifiable')
        return 'READY_FOR_DECOMPOSITION_ONLY', 'decomposition_only', blockers, 'Clarify success criteria before leaf dry-run.'
    if backend_status not in {'healthy', 'healthy_with_warnings'}:
        blockers.append(f'backend_not_ready:{backend_status}')
        return 'READY_FOR_LEAF_DRY_RUN', 'leaf_dry_run', blockers, 'Use dry-run/manual task packs until backend health is healthy enough for actual execution.'
    if test_status == 'unknown':
        blockers.append('testability_unknown')
        return 'READY_FOR_LEAF_DRY_RUN', 'leaf_dry_run', blockers, 'Leaf actual requires known or explicit test policy.'
    if rollback_status == 'unknown':
        blockers.append('rollback_unknown')
        return 'READY_FOR_LEAF_DRY_RUN', 'leaf_dry_run', blockers, 'Leaf actual requires git rollback/worktree capability.'
    return 'READY_FOR_LEAF_ACTUAL_WITH_CONFIRMATION', 'leaf_actual_allowed', blockers, 'Leaf actual is allowed only with --allow-leaf-actual and ready low-risk leaves.'


def decomposition_gate(contract: dict[str, Any]) -> tuple[bool, list[str]]:
    """Return whether a big task contract may be decomposed into leaf contracts."""
    blockers: list[str] = []
    if not contract.get('goal_id'):
        blockers.append('missing_goal')
    if not contract.get('success_criteria'):
        blockers.append('missing_success_criteria')
    verdict = str(contract.get('readiness_verdict') or '')
    decomposition_blocking_verdicts = {
        'BLOCKED_GOAL_UNCLEAR',
        'BLOCKED_PROJECT_NOT_READY',
        'BLOCKED_NEEDS_ARCHITECTURE',
    }
    if verdict in decomposition_blocking_verdicts:
        blockers.append(f'readiness_blocked:{verdict or "unknown"}')
    return not blockers, blockers


def build_big_task_contract(project: Path, run_id: str, raw_input: str, goal_id: str = '') -> dict[str, Any]:
    goal = resolve_goal(project, goal_id)
    paths = infer_paths(raw_input)
    domains = infer_domains(raw_input, paths)
    backend_path = project / '.zoo-agent' / 'backend' / 'codex-backend-profile.json'
    readiness_path = project / '.zoo-agent' / 'project-readiness.json'
    loop_state = big_loop_state(project, run_id, str(goal.get('goal_id') or goal_id or ''), 'readiness')
    non_goals = non_goals_from_goal(goal)
    warnings = []
    if not non_goals:
        warnings.append('non_goals_missing')
    contract = {
        'schema_version': '1.0',
        'generated_by': 'big_task_common.py',
        'generated_at': utc_now(),
        'run_id': run_id,
        'goal_id': str(goal.get('goal_id') or goal_id or ''),
        'raw_input': raw_input,
        'root_goal': str(goal.get('root_goal') or goal.get('goal') or ''),
        'success_criteria': success_criteria_from_goal(goal, raw_input),
        'non_goals': non_goals,
        'risk_level': risk_level(raw_input, paths),
        'project_readiness_ref': str(readiness_path) if readiness_path.exists() else '',
        'backend_profile_ref': str(backend_path) if backend_path.exists() else '',
        'loop_state_ref': str(project / '.zoo-agent' / 'runs' / run_id / 'loop-state.json'),
        'architecture_known': architecture_known(project),
        'test_capability': test_capability(project),
        'rollback_capability': rollback_capability(project),
        'affected_domains': domains,
        'affected_resources': paths,
        'requires_architecture_decision': len(domains) > 1 or any(item in domains for item in ['api_contract', 'database', 'auth_security']),
        'requires_human_gate': risk_level(raw_input, paths) in {'high', 'critical'},
        'allowed_execution_mode': 'decomposition_only',
        'blocking_reasons': [],
        'warnings': warnings,
        'next_action': '',
        'loop_state': loop_state,
    }
    verdict, mode, blockers, next_action = classify_readiness(contract)
    contract.update({'readiness_verdict': verdict, 'allowed_execution_mode': mode, 'blocking_reasons': sorted(set(blockers)), 'next_action': next_action})
    return contract


def render_contract_md(contract: dict[str, Any]) -> str:
    lines = [
        '# Big Task Contract',
        '',
        f"- run_id: {contract.get('run_id')}",
        f"- goal_id: {contract.get('goal_id') or 'missing'}",
        f"- readiness_verdict: {contract.get('readiness_verdict')}",
        f"- allowed_execution_mode: {contract.get('allowed_execution_mode')}",
        f"- risk_level: {contract.get('risk_level')}",
        '',
        '## Root Goal',
        '',
        str(contract.get('root_goal') or 'MISSING_GOAL'),
        '',
        '## Success Criteria',
        '',
        *[f"- {item}" for item in contract.get('success_criteria') or ['MISSING_VERIFIABLE_CRITERIA']],
        '',
        '## Non-goals',
        '',
        *[f"- {item}" for item in contract.get('non_goals') or ['WARNING: non_goals_missing']],
        '',
        '## Affected Resources',
        '',
        *[f"- {item}" for item in contract.get('affected_resources') or ['unknown']],
        '',
        '## Blocking Reasons',
        '',
        *[f"- {item}" for item in contract.get('blocking_reasons') or ['none']],
        '',
        '## Policy',
        '',
        '- Do not run Codex on the root big task.',
        '- Codex may only execute ready low-risk leaf task contracts after explicit confirmation.',
        '- Parent aggregation is required before any integration worktree.',
    ]
    return '\n'.join(lines) + '\n'


def contract_paths(project: Path, run_id: str) -> tuple[Path, Path]:
    run_dir = project / '.zoo-agent' / 'runs' / run_id
    return run_dir / 'big-task-contract.json', run_dir / 'big-task-contract.md'


def write_big_task_contract(project: Path, contract: dict[str, Any]) -> dict[str, str]:
    json_path, md_path = contract_paths(project, str(contract.get('run_id') or 'run'))
    write_json(json_path, contract)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text(render_contract_md(contract), encoding='utf-8')
    return {'json': str(json_path), 'markdown': str(md_path)}


def load_big_task_contract(project: Path, run_id: str) -> dict[str, Any]:
    return load_json(project / '.zoo-agent' / 'runs' / run_id / 'big-task-contract.json')


def resource_type_for_path(path: str) -> str:
    lower = path.lower()
    if lower.startswith('docs/') or lower.startswith('readme') or lower.endswith('.md'):
        return 'documentation_surface'
    if 'api' in lower:
        return 'public_api'
    if 'dto' in lower or 'schema' in lower:
        return 'dto_schema'
    if 'database' in lower or 'migration' in lower:
        return 'database_table'
    if 'fixture' in lower or 'testdata' in lower:
        return 'test_fixture'
    if lower.endswith(('.toml', '.yml', '.yaml', '.json')):
        return 'config_key'
    return 'file_path'


def generate_resource_map(project: Path, raw_input: str = '') -> dict[str, Any]:
    resources: list[dict[str, Any]] = []
    unknowns: list[str] = []
    paths = infer_paths(raw_input)
    for item in paths:
        resources.append(
            {
                'resource_id': safe_name(item).lower(),
                'type': resource_type_for_path(item),
                'name': item,
                'paths': [item],
                'providers': [],
                'consumers': [],
                'owner_hint': '',
                'risk_level': risk_level(raw_input, [item]),
                'confidence': 'medium' if '*' not in item else 'low',
                'notes': 'Inferred from task text; no file contents were scanned.',
            }
        )
    if not resources:
        unknowns.append('no_explicit_resources_detected')
    confidence = 'low' if unknowns or any('*' in path for path in paths) else 'medium'
    return {'project_root': str(project), 'created_at': utc_now(), 'confidence': confidence, 'resources': resources, 'unknowns': unknowns}


def write_resource_map(project: Path, resource_map: dict[str, Any]) -> dict[str, str]:
    path = project / '.zoo-agent' / 'project-resource-map.json'
    write_json(path, resource_map)
    md = project / '.zoo-agent' / 'project-resource-map.md'
    md.write_text(render_resource_map_md(resource_map), encoding='utf-8')
    return {'json': str(path), 'markdown': str(md)}


def render_resource_map_md(resource_map: dict[str, Any]) -> str:
    lines = ['# Semantic Resource Map', '', f"- confidence: {resource_map.get('confidence')}", '', '## Resources']
    for item in resource_map.get('resources') or []:
        lines.append(f"- {item.get('resource_id')}: {item.get('type')} `{item.get('name')}` confidence={item.get('confidence')}")
    if resource_map.get('unknowns'):
        lines.extend(['', '## Unknowns', *[f"- {item}" for item in resource_map.get('unknowns') or []]])
    lines.extend(['', '## Boundary', '', '- This lightweight map uses paths and task text only; secret file contents are not read.'])
    return '\n'.join(lines) + '\n'


def leaf_task_type(objective: str, allowed_files: list[str]) -> str:
    surface = ' '.join([objective, *allowed_files]).lower()
    if any(term in surface for term in ['review', 'audit']):
        return 'review'
    if any(term in surface for term in ['research', 'investigate']):
        return 'research'
    if any(term in surface for term in DOC_TERMS) or all(path.endswith('.md') or path.startswith('docs/') for path in allowed_files if path):
        return 'docs'
    if any(term in surface for term in ['test', 'pytest', 'spec']):
        return 'test'
    if any(term in surface for term in ['config', '.toml', '.yml', '.yaml']):
        return 'config'
    return 'code'


def split_leaf_objectives(contract: dict[str, Any], resource_map: dict[str, Any]) -> list[tuple[str, list[str], list[str]]]:
    raw = str(contract.get('raw_input') or '')
    resources = resource_map.get('resources') or []
    leaves: list[tuple[str, list[str], list[str]]] = []
    if resources:
        for item in resources:
            paths = [str(path) for path in item.get('paths') or []]
            leaves.append((f"Implement bounded change for {item.get('name')}", paths, [str(item.get('resource_id'))]))
    else:
        paths = infer_paths(raw)
        if paths:
            for path in paths:
                leaves.append((f"Implement bounded change for {path}", [path], [safe_name(path).lower()]))
    if not leaves and 'documentation' in (contract.get('affected_domains') or []):
        leaves.append(('Update documentation surface with explicit scoped edits', ['README.md', 'docs/**'], ['documentation_surface']))
    if not leaves:
        leaves.append(('Clarify big task into executable leaf contracts', [], ['unknown']))
    return leaves


def build_leaf_contracts(project: Path, contract: dict[str, Any], resource_map: dict[str, Any], *, allow_leaf_actual: bool = False) -> list[dict[str, Any]]:
    leaves: list[dict[str, Any]] = []
    base_risk = str(contract.get('risk_level') or 'medium')
    for index, (objective, paths, resources) in enumerate(split_leaf_objectives(contract, resource_map), start=1):
        leaf_id = f"leaf-{index:03d}"
        leaf_risk = risk_level(objective, paths)
        if base_risk in {'high', 'critical'}:
            leaf_risk = base_risk
        task_type = leaf_task_type(objective, paths)
        acceptance = [f"Satisfies parent success criteria for {', '.join(resources)}."] if paths else []
        test_policy = 'not_applicable' if task_type in {'docs', 'research', 'review'} else contract.get('test_capability', 'unknown')
        if test_policy in {'known', 'partial'}:
            test_policy = 'required' if task_type in {'code', 'test'} else 'optional'
        preferred_route = 'dry_run_only'
        execution_mode = 'dry_run_only'
        execution_allowed = False
        if allow_leaf_actual and leaf_risk == 'low' and paths and acceptance and task_type not in {'research', 'review'}:
            preferred_route = 'fast'
            execution_mode = 'actual_allowed'
            execution_allowed = True
        leaf = {
            'schema_version': '1.0',
            'generated_by': 'big_task_common.py',
            'leaf_id': leaf_id,
            'run_id': contract.get('run_id'),
            'parent_goal_id': contract.get('goal_id'),
            'objective': objective,
            'task_type': task_type,
            'risk_level': leaf_risk,
            'owned_resources': resources,
            'allowed_files': paths,
            'denied_files': DENIED_FILES,
            'provides': resources,
            'consumes': [],
            'acceptance': acceptance,
            'test_policy': test_policy if test_policy in {'required', 'optional', 'not_applicable', 'unknown'} else 'unknown',
            'test_commands': [],
            'rollback_note': 'Use isolated worktree discard; do not reset main branch.',
            'preferred_route': preferred_route,
            'task_readiness_ref': '',
            'execution_allowed': execution_allowed,
            'execution_mode': execution_mode,
            'blocking_reasons': [],
            'success_criteria_ids': [f"sc-{i + 1}" for i, _ in enumerate(contract.get('success_criteria') or [])],
            'non_goals': contract.get('non_goals') or [],
        }
        leaves.append(leaf)
    return leaves


def leaf_readiness(leaf: dict[str, Any], backend_profile: dict[str, Any] | None = None) -> dict[str, Any]:
    blockers: list[str] = []
    verdict = 'READY_FOR_DRY_RUN'
    backend_status = str((backend_profile or {}).get('health_status') or 'unknown')
    if not leaf.get('acceptance'):
        blockers.append('missing_acceptance')
        verdict = 'BLOCKED_MISSING_ACCEPTANCE'
    elif not leaf.get('allowed_files') or not leaf.get('denied_files'):
        blockers.append('missing_scope')
        verdict = 'BLOCKED_MISSING_SCOPE'
    elif any(str(item).lower() == 'unknown' for item in leaf.get('consumes') or []):
        blockers.append('unstable_consumes')
        verdict = 'BLOCKED_UNSTABLE_CONSUMES'
    elif leaf.get('risk_level') in {'high', 'critical'}:
        blockers.append('high_risk_leaf')
        verdict = 'BLOCKED_HIGH_RISK'
    elif leaf.get('execution_mode') == 'actual_allowed' and backend_status not in {'healthy', 'healthy_with_warnings'}:
        blockers.append(f'backend_not_ready:{backend_status}')
        verdict = 'BLOCKED_BACKEND_UNHEALTHY'
    elif leaf.get('test_policy') == 'unknown':
        blockers.append('test_policy_unknown')
        verdict = 'BLOCKED_TEST_POLICY_UNKNOWN'
    elif leaf.get('task_type') in {'research', 'review'}:
        verdict = 'READY_FOR_MANUAL_REVIEW'
    elif leaf.get('execution_mode') == 'actual_allowed':
        verdict = 'READY_FOR_ACTUAL_CODEX'
    return {
        'leaf_id': leaf.get('leaf_id'),
        'verdict': verdict,
        'execution_allowed': verdict == 'READY_FOR_ACTUAL_CODEX',
        'blocking_reasons': blockers,
        'next_action': 'generate_codex_task_pack' if verdict == 'READY_FOR_ACTUAL_CODEX' else 'keep_as_dry_run_or_review',
    }


def write_leaf_contracts(project: Path, run_id: str, leaves: list[dict[str, Any]]) -> dict[str, Any]:
    leaf_dir = project / '.zoo-agent' / 'runs' / run_id / 'leaf-tasks'
    leaf_dir.mkdir(parents=True, exist_ok=True)
    index = []
    for leaf in leaves:
        path = leaf_dir / f"{safe_name(str(leaf.get('leaf_id')))}.json"
        md = path.with_suffix('.md')
        write_json(path, leaf)
        md.write_text(render_leaf_md(leaf), encoding='utf-8')
        index.append({'leaf_id': leaf.get('leaf_id'), 'json': str(path), 'markdown': str(md), 'execution_mode': leaf.get('execution_mode'), 'risk_level': leaf.get('risk_level')})
    payload = {'run_id': run_id, 'leaf_count': len(index), 'leaves': index, 'directory': str(leaf_dir)}
    write_json(leaf_dir / 'leaf-tasks.json', payload)
    return payload


def render_leaf_md(leaf: dict[str, Any]) -> str:
    lines = [
        f"# Leaf Task Contract: {leaf.get('leaf_id')}",
        '',
        f"- task_type: {leaf.get('task_type')}",
        f"- risk_level: {leaf.get('risk_level')}",
        f"- execution_mode: {leaf.get('execution_mode')}",
        '',
        '## Objective',
        '',
        str(leaf.get('objective') or ''),
        '',
        '## Scope',
        '',
        *[f"- allowed: {item}" for item in leaf.get('allowed_files') or []],
        *[f"- denied: {item}" for item in leaf.get('denied_files') or []],
        '',
        '## Acceptance',
        '',
        *[f"- {item}" for item in leaf.get('acceptance') or ['MISSING_ACCEPTANCE']],
    ]
    return '\n'.join(lines) + '\n'


def load_leaf_contracts(project: Path, run_id: str) -> list[dict[str, Any]]:
    leaf_dir = project / '.zoo-agent' / 'runs' / run_id / 'leaf-tasks'
    leaves = []
    for path in sorted(leaf_dir.glob('leaf-*.json')):
        payload = load_json(path)
        if payload and payload.get('leaf_id'):
            payload['_path'] = str(path)
            leaves.append(payload)
    return leaves


def detect_independence(leaves: list[dict[str, Any]], resource_map: dict[str, Any], backend_profile: dict[str, Any] | None = None, *, actual: bool = False) -> dict[str, Any]:
    parallel_groups: list[list[str]] = []
    serial_order: list[str] = []
    denials: list[dict[str, Any]] = []
    seen_files: dict[str, str] = {}
    seen_resources: dict[str, str] = {}
    backend_status = str((backend_profile or {}).get('health_status') or 'unknown')
    resource_confidence = str(resource_map.get('confidence') or 'low')
    current_group: list[str] = []
    for leaf in leaves:
        leaf_id = str(leaf.get('leaf_id'))
        serial_order.append(leaf_id)
        blockers: list[str] = []
        files = [str(item) for item in leaf.get('allowed_files') or []]
        resources = [str(item) for item in leaf.get('owned_resources') or leaf.get('provides') or []]
        for file in files:
            if file in seen_files:
                blockers.append('shared_files')
        for resource in resources:
            if resource in seen_resources:
                blockers.append('shared_semantic_resources')
            if resource == 'unknown':
                blockers.append('unknown_resource_dependency')
        if leaf.get('risk_level') in {'high', 'critical'} and actual:
            blockers.append('high_risk_leaf_no_parallel_actual')
        if actual and backend_status != 'healthy':
            blockers.append('backend_not_healthy_for_parallel_actual')
        if actual and resource_confidence == 'low':
            blockers.append('resource_map_low_confidence')
        if blockers:
            denials.append({'leaf_ids': [leaf_id], 'reason': ';'.join(sorted(set(blockers))), 'blocking_resources': resources, 'blocking_dependencies': [], 'how_to_make_parallel_safe': 'Clarify resource ownership and run serial or dry-run.'})
        else:
            current_group.append(leaf_id)
        for file in files:
            seen_files[file] = leaf_id
        for resource in resources:
            seen_resources[resource] = leaf_id
    if len(current_group) > 1:
        parallel_groups.append(current_group)
    return {'parallel_groups': parallel_groups, 'serial_order': serial_order, 'parallel_denials': denials}


def load_leaf_outcomes(project: Path, run_id: str) -> dict[str, dict[str, Any]]:
    outcomes: dict[str, dict[str, Any]] = {}
    outcome_dir = project / '.zoo-agent' / 'runs' / run_id / 'leaf-results'
    for path in sorted(outcome_dir.glob('*.json')):
        payload = load_json(path)
        if payload:
            outcomes[path.stem] = payload
    return outcomes


def load_leaf_convergence(project: Path, run_id: str) -> dict[str, Any]:
    return load_json(project / '.zoo-agent' / 'runs' / run_id / 'leaf-convergence-report.json')


def goal_coverage(contract: dict[str, Any], leaves: list[dict[str, Any]], outcomes: dict[str, dict[str, Any]]) -> dict[str, Any]:
    criteria = contract.get('success_criteria') or []
    delivered_leaf_ids = {leaf_id for leaf_id, payload in outcomes.items() if payload.get('delivery_outcome') == 'delivered'}
    covered = []
    missing = []
    for index, criterion in enumerate(criteria, start=1):
        leaf_id = f'leaf-{index:03d}'
        if leaf_id in delivered_leaf_ids:
            covered.append({'criterion': criterion, 'evidence': leaf_id})
        else:
            missing.append({'criterion': criterion, 'expected_leaf': leaf_id})
    return {'covered': covered, 'missing': missing, 'coverage_rate': round(len(covered) / max(len(criteria), 1), 3)}


def parent_aggregation(project: Path, run_id: str) -> dict[str, Any]:
    contract = load_big_task_contract(project, run_id)
    leaves = load_leaf_contracts(project, run_id)
    outcomes = load_leaf_outcomes(project, run_id)
    convergence = load_leaf_convergence(project, run_id)
    resolutions = convergence.get('resolutions') if isinstance(convergence.get('resolutions'), list) else []
    resolved_by_leaf = {str(item.get('leaf_id')): item for item in resolutions if isinstance(item, dict)}
    coverage = goal_coverage(contract, leaves, outcomes)
    no_delivery = [leaf_id for leaf_id, payload in outcomes.items() if payload.get('delivery_outcome') == 'no_delivery']
    backend_failures = [leaf_id for leaf_id, payload in outcomes.items() if payload.get('delivery_outcome') == 'blocked' and payload.get('failure_type')]
    blocked = [
        leaf.get('leaf_id')
        for leaf in leaves
        if leaf.get('blocking_reasons') and (resolved_by_leaf.get(str(leaf.get('leaf_id'))) or {}).get('status') == 'stuck'
    ]
    deferred = [leaf_id for leaf_id, item in resolved_by_leaf.items() if item.get('final_resolution') == 'defer']
    merged = [leaf_id for leaf_id, item in resolved_by_leaf.items() if item.get('final_resolution') == 'merge']
    collapsed = [leaf_id for leaf_id, item in resolved_by_leaf.items() if item.get('final_resolution') == 'collapse']
    high_risk = [leaf.get('leaf_id') for leaf in leaves if leaf.get('risk_level') in {'high', 'critical'}]
    unresolved_convergence = [item.get('leaf_id') for item in resolutions if item.get('status') == 'stuck']
    if unresolved_convergence:
        verdict = 'BLOCKED'
    elif high_risk and not all(str(item) in deferred for item in high_risk):
        verdict = 'HUMAN_DECISION_REQUIRED'
    elif backend_failures:
        verdict = 'BLOCKED'
    elif no_delivery or blocked:
        verdict = 'NEEDS_LEAF_REDO'
    elif coverage.get('missing'):
        verdict = 'NEEDS_REPLANNING'
    else:
        verdict = 'READY_FOR_INTEGRATION_WORKTREE'
    return {
        'schema_version': '1.0',
        'generated_by': 'big_task_common.py',
        'generated_at': utc_now(),
        'run_id': run_id,
        'root_goal_coverage': coverage,
        'success_criteria_coverage': coverage,
        'non_goal_violations': [],
        'leaf_delivery_outcomes': outcomes,
        'open_obligations': coverage.get('missing') or [],
        'unresolved_blockers': blocked,
        'leaf_convergence_status': convergence.get('status', 'missing'),
        'leaf_resolutions': resolutions,
        'deferred_leaf_count': len(deferred),
        'merged_leaf_count': len(merged),
        'collapsed_leaf_count': len(collapsed),
        'convergence_failure_leaf_count': len(unresolved_convergence),
        'resource_conflicts': [],
        'dependency_satisfaction': 'unknown' if not leaves else 'checked',
        'tests_coverage': 'partial',
        'rollback_readiness': contract.get('rollback_capability', 'unknown'),
        'integration_order': [leaf.get('leaf_id') for leaf in leaves],
        'no_delivery_leaf_count': len(no_delivery),
        'backend_failure_leaf_count': len(backend_failures),
        'local_optimization_deferred_count': 0,
        'verdict': verdict,
        'next_action': 'create integration worktree only after review' if verdict == 'READY_FOR_INTEGRATION_WORKTREE' else 'resolve aggregation blockers',
    }


def render_parent_aggregation_md(report: dict[str, Any]) -> str:
    missing_items = (report.get('root_goal_coverage') or {}).get('missing') or []
    missing_lines = [f"- {item.get('criterion')}" for item in missing_items if isinstance(item, dict)]
    if not missing_lines:
        missing_lines = ['- none']
    lines = [
        '# Parent Aggregation Report',
        '',
        f"- run_id: {report.get('run_id')}",
        f"- verdict: {report.get('verdict')}",
        f"- no_delivery_leaf_count: {report.get('no_delivery_leaf_count')}",
        f"- backend_failure_leaf_count: {report.get('backend_failure_leaf_count')}",
        f"- deferred_leaf_count: {report.get('deferred_leaf_count', 0)}",
        f"- merged_leaf_count: {report.get('merged_leaf_count', 0)}",
        f"- collapsed_leaf_count: {report.get('collapsed_leaf_count', 0)}",
        f"- convergence_failure_leaf_count: {report.get('convergence_failure_leaf_count', 0)}",
        '',
        '## Missing Coverage',
        '',
        *missing_lines,
        '',
        '## Boundary',
        '',
        '- This report does not merge or push changes.',
    ]
    return '\n'.join(lines) + '\n'


def write_parent_aggregation(project: Path, run_id: str, report: dict[str, Any]) -> dict[str, str]:
    json_path = project / '.zoo-agent' / 'runs' / run_id / 'parent-aggregation-report.json'
    md_path = project / '.zoo-agent' / 'runs' / run_id / 'parent-aggregation-report.md'
    write_json(json_path, report)
    md_path.write_text(render_parent_aggregation_md(report), encoding='utf-8')
    return {'json': str(json_path), 'markdown': str(md_path)}


def integration_candidate(project: Path, run_id: str, *, create: bool = False) -> dict[str, Any]:
    aggregation = load_json(project / '.zoo-agent' / 'runs' / run_id / 'parent-aggregation-report.json')
    repo_name = project.name
    worktree_path = Path(os.environ.get('ZOO_INTEGRATION_WORKTREE_ROOT', 'D:/AI_DEV/worktrees')) / f'{repo_name}-integration-{safe_name(run_id)}'
    verdict = 'NEEDS_PARENT_REAGGREGATION'
    created = False
    if aggregation.get('verdict') == 'READY_FOR_INTEGRATION_WORKTREE':
        verdict = 'INTEGRATION_CANDIDATE_READY'
        if create:
            worktree_path.parent.mkdir(parents=True, exist_ok=True)
            proc = subprocess.run(['git', 'worktree', 'add', str(worktree_path), 'HEAD'], cwd=project, text=True, encoding='utf-8', errors='replace', stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            created = proc.returncode == 0
            if not created:
                verdict = 'INTEGRATION_CONFLICTS'
    report = {
        'schema_version': '1.0',
        'generated_by': 'big_task_common.py',
        'generated_at': utc_now(),
        'run_id': run_id,
        'integration_worktree_path': str(worktree_path),
        'worktree_created': created,
        'merge_performed': False,
        'push_performed': False,
        'integration_checks': [],
        'verdict': verdict,
        'next_action': 'human/GPT review before merge suggestion',
    }
    return report


def render_integration_md(report: dict[str, Any]) -> str:
    return '\n'.join(
        [
            '# Integration Candidate Report',
            '',
            f"- run_id: {report.get('run_id')}",
            f"- verdict: {report.get('verdict')}",
            f"- integration_worktree_path: {report.get('integration_worktree_path')}",
            f"- worktree_created: {report.get('worktree_created')}",
            '',
            '## Boundary',
            '',
            '- No merge was performed.',
            '- No push was performed.',
            '- Worktree removal requires explicit user confirmation.',
        ]
    ) + '\n'


def write_integration_report(project: Path, run_id: str, report: dict[str, Any]) -> dict[str, str]:
    json_path = project / '.zoo-agent' / 'runs' / run_id / 'integration-candidate-report.json'
    md_path = project / '.zoo-agent' / 'runs' / run_id / 'integration-candidate-report.md'
    write_json(json_path, report)
    md_path.write_text(render_integration_md(report), encoding='utf-8')
    return {'json': str(json_path), 'markdown': str(md_path)}


def common_big_task_parser(description: str) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument('input', nargs='*')
    parser.add_argument('--workspace', default='.')
    parser.add_argument('--run-id', default='')
    parser.add_argument('--goal-id', default='')
    parser.add_argument('--input-text', default='')
    parser.add_argument('--allow-leaf-actual', action='store_true')
    parser.add_argument('--json-output', default='')
    return parser
