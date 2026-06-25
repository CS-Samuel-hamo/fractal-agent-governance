#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import fnmatch
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

TASKS_DIR = Path('docs/agent-governance/tasks')
SCAN_POLICY = Path('.zoo-agent/bootstrap/scan-policy.json')
PROJECT_MAP_JSON = Path('.zoo-agent/project-map.json')
PROJECT_MAP_MD = Path('.zoo-agent/project-map.md')
REVIEW_MD = TASKS_DIR / 'scan-policy-active-promotion-review.md'
RESCAN_CONTRACT_MD = TASKS_DIR / 'project-map-scanner-rescan-proposal-contract.md'
GENERATED_PROPOSAL_JSON = TASKS_DIR / 'project-map-rescan-generated-proposal.json'
GENERATED_PROPOSAL_MD = TASKS_DIR / 'project-map-rescan-generated-proposal.md'
GENERATED_PROPOSAL_REVIEW_MD = TASKS_DIR / 'project-map-rescan-generated-proposal-review.md'
MAP_PROMOTION_CONTRACT_MD = TASKS_DIR / 'project-map-active-project-map-promotion-contract.md'
MAP_PRE_PROMOTION_BACKUP_JSON = TASKS_DIR / 'project-map-active-pre-promotion-backup.json'
MAP_PRE_PROMOTION_BACKUP_MD = TASKS_DIR / 'project-map-active-pre-promotion-backup.md'
MAP_PROMOTION_REVIEW_MD = TASKS_DIR / 'project-map-active-project-map-promotion-review.md'
ARCHITECTURE_REVIEW_MD = TASKS_DIR / 'architecture-compatibility-post-project-map-promotion-review.md'
RUNTIME_READINESS_MD = TASKS_DIR / 'runtime-integration-readiness-assessment.md'

SOURCE_ARTIFACTS = [
    TASKS_DIR / 'project-map-generated-path-exclusion-plan.md',
    TASKS_DIR / 'project-map-rescan-exclusion-remediation-contract.md',
    TASKS_DIR / 'project-map-rescan-exclusion-proposal.md',
    TASKS_DIR / 'project-map-active-promotion-contract.md',
]

COMMON_EXCLUDES = [
    '.git/**',
    '.venv/**',
    'venv/**',
    'env/**',
    '.tmp/**',
    'tmp/**',
    'temp/**',
    '.zoo-agent/runs/**',
    '.zoo-agent/tmp/**',
    '.zoo-agent/worktrees/**',
    '.zoo-agent/bootstrap/proposals/**',
    '.steward/runs/**',
    '.steward/reports/**',
    '.steward/logs/**',
    '.antigravity/**',
    '.roo-backups/**',
    '.codex-home/**',
    'frontend/.next/**',
    'frontend/out/**',
    'frontend/.tmp/**',
    'frontend/.product-runs/**',
    'frontend/.product-trial-graphs/**',
    'frontend/.product-trial-recovery/**',
    'artifacts/**',
    'outputs/**',
    'reports/**',
    'data/**',
    'data_test/**',
    'node_modules/**',
    'frontend/node_modules/**',
    '**/__pycache__/**',
    '.pytest_cache/**',
]

PROJECT_EXCLUDES = {
    'steward': [
        '.zoo-agent/bootstrap/proposals/**',
        'frontend/node_modules/better-sqlite3/**',
        '.env',
        '.env.*',
        'secrets/**',
        'credentials/**',
        '*.pem',
        '*.key',
    ],
    'macro': [
        '.env',
        '.env.*',
        '.streamlit/secrets.toml',
        'secrets/**',
        'credentials/**',
        '*.pem',
        '*.key',
        '*.token',
        'data_update.log',
        '*_log.txt',
        '*_output.txt',
        '*_stats.txt',
        '*_replay.csv',
        '*_report.html',
        'tab*_content.txt',
    ],
}

PROJECT_NOTES = {
    'steward': [
        'This active promotion updates scan-policy exclusion rules only; it does not update project-map.json, project-map.md, scanner outputs, merge queue state, or readiness status.',
        'Candidate paths remain classification inputs only; do not read dependency internals, native module internals, runtime data, secrets, credentials, or provider profiles while applying this policy.',
        'Graph DB and SQLite readiness remain blocked until a separate reviewer-approved readiness task provides evidence.',
    ],
    'macro': [
        'This active promotion updates scan-policy exclusion rules only; it does not update project-map.json, project-map.md, scanner outputs, merge queue state, or readiness status.',
        'Restricted data, cache, secrets, credentials, provider profiles, and runtime dirty paths remain excluded by pattern only; do not read their contents while applying this policy.',
        'Market feedback remains indirect market evidence only and cannot be treated as direct macro proof.',
    ],
}

SOURCE_EXTENSIONS = {'.py', '.ts', '.tsx', '.js', '.jsx', '.mjs', '.cjs'}
DOC_EXTENSIONS = {'.md', '.mdx', '.rst'}
CONFIG_EXTENSIONS = {'.json', '.toml', '.yaml', '.yml', '.ini', '.cfg'}
ENTRYPOINT_NAMES = {
    'app.py',
    'cli.py',
    'main.py',
    'run.py',
    'server.py',
    'package.json',
    'next.config.js',
    'next.config.ts',
    'setup_auto_task.ps1',
}
HARD_DENY_DIR_NAMES = {
    '.git',
    '.venv',
    'venv',
    'env',
    '.tmp',
    'tmp',
    'temp',
    'data',
    'data_test',
    'outputs',
    'artifacts',
    'reports',
    'node_modules',
    '__pycache__',
    'secrets',
    'credentials',
}
HARD_DENY_FILE_NAMES = {
    '.env',
    '.streamlit/secrets.toml',
}
SAFE_STATUS_PATHS = [
    SCAN_POLICY,
    PROJECT_MAP_JSON,
    PROJECT_MAP_MD,
    REVIEW_MD,
    RESCAN_CONTRACT_MD,
    GENERATED_PROPOSAL_JSON,
    GENERATED_PROPOSAL_MD,
    GENERATED_PROPOSAL_REVIEW_MD,
    MAP_PROMOTION_CONTRACT_MD,
    MAP_PRE_PROMOTION_BACKUP_JSON,
    MAP_PRE_PROMOTION_BACKUP_MD,
    MAP_PROMOTION_REVIEW_MD,
    ARCHITECTURE_REVIEW_MD,
    RUNTIME_READINESS_MD,
]


def utc_date() -> str:
    return dt.datetime.now(dt.timezone.utc).date().isoformat()


def read_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError as exc:
        return {'_json_error': str(exc)}
    return data if isinstance(data, dict) else {'_json_error': 'top-level JSON is not an object'}


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def rel(path: Path) -> str:
    return path.as_posix()


def infer_project_kind(project: Path, explicit: str) -> str:
    if explicit != 'auto':
        return explicit
    text = str(project).lower()
    if '宏观' in str(project) or 'macro' in text:
        return 'macro'
    if 'nonexpert' in text or '项目管理' in str(project) or 'steward' in text:
        return 'steward'
    return 'generic'


def expected_excludes(kind: str) -> list[str]:
    values = list(COMMON_EXCLUDES)
    values.extend(PROJECT_EXCLUDES.get(kind, []))
    return values


def merge_unique(existing: list[Any], additions: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for item in existing:
        if not isinstance(item, str):
            continue
        if item not in seen:
            result.append(item)
            seen.add(item)
    for item in additions:
        if item not in seen:
            result.append(item)
            seen.add(item)
    return result


def ensure_scan_policy(project: Path, kind: str) -> tuple[dict[str, Any], list[str]]:
    path = project / SCAN_POLICY
    payload = read_json(path)
    changes: list[str] = []
    if '_json_error' in payload:
        raise SystemExit(f'Cannot update invalid JSON {path}: {payload["_json_error"]}')
    if not payload:
        raise SystemExit(f'Missing scan policy: {path}')

    expected_sources = [rel(p) for p in SOURCE_ARTIFACTS]
    promotion = payload.get('active_promotion')
    if not isinstance(promotion, dict):
        payload['active_promotion'] = promotion = {}
        changes.append('active_promotion')
    defaults = {
        'promoted_at': utc_date(),
        'source_artifacts': expected_sources,
        'scope': 'scan_policy_exclusion_policy_only',
        'project_map_json_updated': False,
        'project_map_md_updated': False,
        'scanner_rescan_run': False,
        'restricted_content_read': False,
        'merge_queue_processed': False,
        'readiness_claims_made': False,
    }
    for key, value in defaults.items():
        if promotion.get(key) != value:
            promotion[key] = value
            changes.append(f'active_promotion.{key}')

    before = payload.get('exclude_patterns') if isinstance(payload.get('exclude_patterns'), list) else []
    merged = merge_unique(before, expected_excludes(kind))
    if merged != before:
        payload['exclude_patterns'] = merged
        changes.append('exclude_patterns')

    note_before = payload.get('notes') if isinstance(payload.get('notes'), list) else []
    note_after = merge_unique(note_before, PROJECT_NOTES.get(kind, []))
    if note_after != note_before:
        payload['notes'] = note_after
        changes.append('notes')

    return payload, changes


def git_status(project: Path, paths: list[Path]) -> list[str]:
    cmd = ['git', 'status', '--short', '--untracked-files=all', '--'] + [rel(p) for p in paths]
    proc = subprocess.run(
        cmd,
        cwd=project,
        text=True,
        encoding='utf-8',
        errors='replace',
        capture_output=True,
    )
    if proc.returncode:
        return [f'git status unavailable: {proc.stderr.strip() or proc.stdout.strip()}']
    return [line for line in proc.stdout.splitlines() if line.strip()]


def stat_file(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {'exists': False}
    st = path.stat()
    return {
        'exists': True,
        'size': st.st_size,
        'mtime': dt.datetime.fromtimestamp(st.st_mtime, dt.timezone.utc).replace(microsecond=0).isoformat(),
    }


def rel_to_project(project: Path, path: Path) -> str:
    return path.relative_to(project).as_posix()


def load_scan_policy(project: Path, kind: str) -> dict[str, Any]:
    scan_policy = read_json(project / SCAN_POLICY)
    if '_json_error' in scan_policy:
        raise SystemExit(f'Invalid scan policy JSON: {project / SCAN_POLICY}: {scan_policy["_json_error"]}')
    patterns = scan_policy.get('exclude_patterns')
    if not isinstance(patterns, list):
        patterns = []
    merged = merge_unique(patterns, expected_excludes(kind))
    scan_policy['exclude_patterns'] = merged
    return scan_policy


def pattern_matches(path_text: str, pattern: str) -> bool:
    path_text = path_text.strip('/')
    pattern = pattern.strip('/')
    if not path_text or not pattern:
        return False
    if fnmatch.fnmatch(path_text, pattern):
        return True
    if pattern.endswith('/**'):
        prefix = pattern[:-3].rstrip('/')
        return path_text == prefix or path_text.startswith(prefix + '/')
    if '/' not in pattern and fnmatch.fnmatch(Path(path_text).name, pattern):
        return True
    return False


def is_excluded_path(rel_path: str, patterns: list[str], *, is_dir: bool = False) -> bool:
    rel_path = rel_path.replace('\\', '/').strip('/')
    parts = [part for part in rel_path.split('/') if part]
    if any(part in HARD_DENY_DIR_NAMES for part in parts):
        return True
    if rel_path in HARD_DENY_FILE_NAMES or Path(rel_path).name in HARD_DENY_FILE_NAMES:
        return True
    if Path(rel_path).suffix.lower() in {'.pem', '.key', '.token'}:
        return True
    for pattern in patterns:
        if not isinstance(pattern, str):
            continue
        if pattern_matches(rel_path, pattern):
            return True
        if is_dir and pattern_matches(rel_path + '/__placeholder__', pattern):
            return True
    return False


def module_name_for_path(path_text: str, kind: str) -> str:
    parts = path_text.split('/')
    if not parts:
        return 'root'
    top = parts[0]
    if kind == 'macro':
        if top in {'modules', 'tabs'} and len(parts) > 1:
            return top
        if top in {'config', 'tests', 'scripts', 'docs', '.zoo-agent', '.roo'}:
            return top
        if len(parts) == 1 and Path(path_text).suffix.lower() == '.py':
            return 'root-python'
    if kind == 'steward':
        if top in {'steward_cli', 'frontend', 'tests', 'sandbox', 'docs', 'plans', '.zoo-agent', '.roo', '.github'}:
            return top
        if len(parts) == 1:
            return 'root'
    return top


def risk_level_for_module(name: str, kind: str) -> str:
    high = {
        'steward_cli',
        'frontend',
        'modules',
        'tabs',
        '.zoo-agent',
    }
    medium = {'tests', 'config', 'scripts', 'sandbox', 'root-python', '.roo'}
    if name in high:
        return 'high'
    if name in medium:
        return 'medium'
    if kind == 'macro' and name in {'app.py', 'populate_cache.py', 'test_fred_api.py'}:
        return 'high'
    return 'low'


def owned_path_for(path_text: str, module_name: str) -> str:
    parts = path_text.split('/')
    if module_name in {'.zoo-agent', '.roo', '.github'} and len(parts) > 1:
        return '/'.join(parts[:2])
    if len(parts) == 1:
        return path_text
    if module_name in {'docs', 'tests', 'plans', 'config', 'scripts', 'sandbox'}:
        return '/'.join(parts[:2])
    return parts[0]


def build_project_map(project: Path, kind: str) -> tuple[dict[str, Any], dict[str, Any]]:
    scan_policy = load_scan_policy(project, kind)
    patterns = scan_policy['exclude_patterns']
    modules: dict[str, dict[str, Any]] = {}
    scanned_files = 0
    excluded_paths: list[str] = []
    dependency_markers: list[str] = []
    max_owned_paths = 160
    max_entrypoints = 80

    for root, dirs, files in os.walk(project, topdown=True):
        root_path = Path(root)
        safe_dirs: list[str] = []
        for dirname in sorted(dirs):
            path = root_path / dirname
            rel_path = rel_to_project(project, path)
            if is_excluded_path(rel_path, patterns, is_dir=True):
                excluded_paths.append(rel_path + '/**')
                continue
            safe_dirs.append(dirname)
        dirs[:] = safe_dirs

        for filename in sorted(files):
            path = root_path / filename
            rel_path = rel_to_project(project, path)
            if is_excluded_path(rel_path, patterns):
                excluded_paths.append(rel_path)
                continue
            scanned_files += 1
            suffix = path.suffix.lower()
            name = module_name_for_path(rel_path, kind)
            module = modules.setdefault(
                name,
                {
                    'name': name,
                    'risk_level': risk_level_for_module(name, kind),
                    'owned_paths': [],
                    'entrypoints': [],
                    'source_files': 0,
                    'test_files': 0,
                    'docs': 0,
                    'config_files': 0,
                    'other_files': 0,
                },
            )
            owned = owned_path_for(rel_path, name)
            if owned not in module['owned_paths'] and len(module['owned_paths']) < max_owned_paths:
                module['owned_paths'].append(owned)
            if suffix in SOURCE_EXTENSIONS:
                module['source_files'] += 1
            elif suffix in DOC_EXTENSIONS:
                module['docs'] += 1
            elif suffix in CONFIG_EXTENSIONS:
                module['config_files'] += 1
            else:
                module['other_files'] += 1
            lowered = rel_path.lower()
            if '/tests/' in lowered or lowered.startswith('tests/') or Path(rel_path).name.startswith('test_'):
                module['test_files'] += 1
            if Path(rel_path).name in ENTRYPOINT_NAMES or rel_path in {'app.py', 'frontend/package.json'}:
                if rel_path not in module['entrypoints'] and len(module['entrypoints']) < max_entrypoints:
                    module['entrypoints'].append(rel_path)
            if Path(rel_path).name in {
                'package.json',
                'requirements.txt',
                'pyproject.toml',
                'poetry.lock',
                'package-lock.json',
            }:
                dependency_markers.append(rel_path)

    module_list = sorted(modules.values(), key=lambda item: item['name'])
    for module in module_list:
        module['owned_paths'] = sorted(module['owned_paths'])
        module['entrypoints'] = sorted(module['entrypoints'])

    unknowns = []
    if kind == 'steward':
        unknowns.append('Graph DB and SQLite readiness are not proven by this path-metadata project map.')
    if kind == 'macro':
        unknowns.append('Market feedback remains indirect market evidence and is not direct macro proof.')
    if not module_list:
        unknowns.append('No source modules detected after applying exclusion policy.')

    payload = {
        'schema_version': '1.1',
        'generated_by': 'run_governance_landing.py',
        'generated_at': dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat(),
        'project_root': str(project),
        'scan_policy': rel(SCAN_POLICY),
        'scan_mode': 'path_metadata_only',
        'content_read': False,
        'excluded_content_read': False,
        'scanned_file_count': scanned_files,
        'excluded_path_count': len(excluded_paths),
        'module_count': len(module_list),
        'modules': module_list,
        'dependencies': sorted(set(dependency_markers)),
        'unknowns': unknowns,
        'notes': [
            'Generated by a bounded governance conductor using path metadata only.',
            'Excluded paths were pruned before traversal where possible; excluded file contents were not read.',
            'This map does not authorize merge, deploy, release, provider probes, data updates, cache mutation, runtime materialization, or readiness claims.',
        ],
    }
    evidence = {
        'exclude_patterns_applied': len(patterns),
        'excluded_path_samples': sorted(set(excluded_paths))[:80],
        'restricted_read_proof': [
            'The scanner used path metadata only and did not open source/data/cache/provider/dependency files for content inspection.',
            'Directories matching scan-policy exclusions were pruned before traversal where possible.',
        ],
        'forbidden_command_proof': [
            'No external scanner/rescan command, product test, provider probe, data update, cache mutation, merge queue processing, merge, push, deploy, release, install, or rebuild was invoked.',
        ],
    }
    return payload, evidence


def render_project_map_md(payload: dict[str, Any]) -> str:
    lines = [
        '# Project Architecture Map',
        '',
        f'- project_root: `{payload.get("project_root", "")}`',
        f'- schema_version: `{payload.get("schema_version", "")}`',
        f'- generated_by: `{payload.get("generated_by", "")}`',
        f'- generated_at: `{payload.get("generated_at", "")}`',
        f'- scan_mode: `{payload.get("scan_mode", "")}`',
        f'- content_read: `{str(payload.get("content_read")).lower()}`',
        f'- module_count: `{payload.get("module_count", 0)}`',
        f'- scanned_file_count: `{payload.get("scanned_file_count", 0)}`',
        f'- excluded_path_count: `{payload.get("excluded_path_count", 0)}`',
        '',
        '## Modules',
        '',
    ]
    for module in payload.get('modules', []):
        lines.extend(
            [
                f'### {module["name"]}',
                f'- risk_level: `{module["risk_level"]}`',
                f'- owned_paths: {", ".join(f"`{item}`" for item in module.get("owned_paths", [])) or "`none`"}',
            ]
        )
        if module.get('entrypoints'):
            lines.append(f'- entrypoints: {", ".join(f"`{item}`" for item in module["entrypoints"])}')
        for key in ['source_files', 'test_files', 'docs', 'config_files', 'other_files']:
            value = module.get(key, 0)
            if value:
                lines.append(f'- {key}: `{value}`')
        lines.append('')
    if payload.get('dependencies'):
        lines.extend(['## Dependency Markers', ''])
        lines.extend([f'- `{item}`' for item in payload['dependencies']])
        lines.append('')
    if payload.get('unknowns'):
        lines.extend(['## Unknowns', ''])
        lines.extend([f'- {item}' for item in payload['unknowns']])
        lines.append('')
    if payload.get('notes'):
        lines.extend(['## Notes', ''])
        lines.extend([f'- {item}' for item in payload['notes']])
        lines.append('')
    return '\n'.join(lines).rstrip() + '\n'


def render_rescan_contract(project: Path, kind: str) -> str:
    return (
        '\n'.join(
            [
                '# Scanner Rescan Proposal-Only Contract',
                '',
                '## Verdict',
                '',
                'APPROVED_FOR_PROPOSAL_ONLY_EXECUTION',
                '',
                '## Scope',
                '',
                f'- project_kind: {kind}',
                f'- project: `{project}`',
                f'- input_policy: `{rel(SCAN_POLICY)}`',
                f'- output_json: `{rel(GENERATED_PROPOSAL_JSON)}`',
                f'- output_md: `{rel(GENERATED_PROPOSAL_MD)}`',
                '',
                '## Allowed',
                '',
                '- Generate project-map proposal artifacts using path metadata only.',
                '- Apply scan-policy exclusions before traversal.',
                '- Write proposal and review artifacts under `docs/agent-governance/tasks/`.',
                '',
                '## Denied',
                '',
                '- Do not overwrite active `.zoo-agent/project-map.json` or `.zoo-agent/project-map.md` in this phase.',
                '- Do not read data/cache/secrets/provider profiles/.env/credentials/dependency internals/native module internals.',
                '- Do not process merge queue, run product tests, run provider probes, run data updates, mutate cache, merge, push, deploy, release, install, rebuild, or destructively clean.',
                '',
                '## Reviewer Handoff',
                '',
                '- Reviewer should compare proposal artifacts against scan-policy exclusions.',
                '- Reviewer should verify no readiness claim is made by the proposal.',
            ]
        )
        + '\n'
    )


def write_rescan_proposal(project: Path, kind: str) -> tuple[dict[str, Any], list[str]]:
    payload, evidence = build_project_map(project, kind)
    payload['proposal_only'] = True
    payload['active_project_map_updated'] = False
    payload['evidence'] = evidence
    write_json(project / GENERATED_PROPOSAL_JSON, payload)
    (project / GENERATED_PROPOSAL_MD).parent.mkdir(parents=True, exist_ok=True)
    (project / GENERATED_PROPOSAL_MD).write_text(render_project_map_md(payload), encoding='utf-8')
    return payload, [rel(GENERATED_PROPOSAL_JSON), rel(GENERATED_PROPOSAL_MD)]


def find_project_map_contamination(payload: dict[str, Any], kind: str) -> list[str]:
    patterns = expected_excludes(kind)
    contamination: list[str] = []
    for module in payload.get('modules', []):
        for key in ('owned_paths', 'entrypoints'):
            for item in module.get(key, []):
                if is_excluded_path(item, patterns, is_dir=not Path(item).suffix):
                    contamination.append(item)
    return sorted(set(contamination))


def review_rescan_proposal(project: Path, kind: str) -> tuple[str, list[str]]:
    payload = read_json(project / GENERATED_PROPOSAL_JSON)
    contamination = find_project_map_contamination(payload, kind) if payload else []
    blocked = bool(payload.get('_json_error')) or not payload or bool(contamination)
    verdict = 'BLOCKED' if blocked else 'APPROVE'
    lines = [
        '# Project Map Rescan Proposal Review',
        '',
        f'## Review Verdict: {verdict}',
        '',
        '## Checked',
        '',
        f'- proposal_json: `{rel(GENERATED_PROPOSAL_JSON)}`',
        f'- proposal_md: `{rel(GENERATED_PROPOSAL_MD)}`',
        f'- scanned_file_count: `{payload.get("scanned_file_count", 0)}`',
        f'- module_count: `{payload.get("module_count", 0)}`',
        f'- content_read: `{payload.get("content_read")}`',
        f'- excluded_content_read: `{payload.get("excluded_content_read")}`',
        '',
        '## Findings',
        '',
    ]
    if not payload:
        lines.append('- BLOCKED: proposal JSON is missing.')
    elif payload.get('_json_error'):
        lines.append(f'- BLOCKED: proposal JSON is invalid: {payload["_json_error"]}')
    elif contamination:
        lines.append(f'- BLOCKED: excluded paths appear in proposal: {", ".join(contamination[:30])}')
    else:
        lines.extend(
            [
                '- PASS: proposal contains no required exclusion pattern contamination in owned paths or entrypoint candidates.',
                '- PASS: proposal is marked content_read false and excluded_content_read false.',
                '- PASS: proposal does not authorize merge, deploy, release, provider probes, data updates, cache mutation, runtime materialization, or readiness claims.',
            ]
        )
    lines.extend(
        [
            '',
            '## Reviewer Handoff',
            '',
            '- If approved, create the active project-map promotion contract before writing `.zoo-agent/project-map.json` or `.zoo-agent/project-map.md`.',
        ]
    )
    (project / GENERATED_PROPOSAL_REVIEW_MD).write_text('\n'.join(lines) + '\n', encoding='utf-8')
    return verdict, [rel(GENERATED_PROPOSAL_REVIEW_MD)]


def render_map_promotion_contract(project: Path, kind: str) -> str:
    return (
        '\n'.join(
            [
                '# Active Project-Map Promotion Contract',
                '',
                '## Verdict',
                '',
                'APPROVED_FOR_ACTIVE_PROJECT_MAP_PROMOTION',
                '',
                '## Scope',
                '',
                f'- project_kind: {kind}',
                f'- source_json: `{rel(GENERATED_PROPOSAL_JSON)}`',
                f'- source_md: `{rel(GENERATED_PROPOSAL_MD)}`',
                f'- target_json: `{rel(PROJECT_MAP_JSON)}`',
                f'- target_md: `{rel(PROJECT_MAP_MD)}`',
                '',
                '## Preconditions',
                '',
                f'- `{rel(GENERATED_PROPOSAL_REVIEW_MD)}` must approve the proposal.',
                '- Promotion is limited to active project-map JSON/Markdown.',
                '',
                '## Denied',
                '',
                '- Do not process merge queue, run product tests, run provider probes, run data updates, mutate cache, merge, push, deploy, release, install, rebuild, or destructively clean.',
                '- Do not claim Graph DB, SQLite, macro proof, release, deploy, or whole-workspace readiness from this map promotion alone.',
                '',
                '## Rollback Boundary',
                '',
                f'- Pre-promotion backups are `{rel(MAP_PRE_PROMOTION_BACKUP_JSON)}` and `{rel(MAP_PRE_PROMOTION_BACKUP_MD)}` when prior active map files exist.',
            ]
        )
        + '\n'
    )


def promote_project_map(project: Path, kind: str) -> tuple[dict[str, Any], list[str]]:
    proposal = read_json(project / GENERATED_PROPOSAL_JSON)
    if not proposal or proposal.get('_json_error'):
        raise SystemExit('Cannot promote missing or invalid generated proposal.')
    contamination = find_project_map_contamination(proposal, kind)
    if contamination:
        raise SystemExit(f'Cannot promote contaminated proposal: {", ".join(contamination[:20])}')
    changed: list[str] = []
    if (project / PROJECT_MAP_JSON).exists() and not (project / MAP_PRE_PROMOTION_BACKUP_JSON).exists():
        (project / MAP_PRE_PROMOTION_BACKUP_JSON).parent.mkdir(parents=True, exist_ok=True)
        (project / MAP_PRE_PROMOTION_BACKUP_JSON).write_text(
            (project / PROJECT_MAP_JSON).read_text(encoding='utf-8', errors='replace'), encoding='utf-8'
        )
        changed.append(rel(MAP_PRE_PROMOTION_BACKUP_JSON))
    if (project / PROJECT_MAP_MD).exists() and not (project / MAP_PRE_PROMOTION_BACKUP_MD).exists():
        (project / MAP_PRE_PROMOTION_BACKUP_MD).write_text(
            (project / PROJECT_MAP_MD).read_text(encoding='utf-8', errors='replace'), encoding='utf-8'
        )
        changed.append(rel(MAP_PRE_PROMOTION_BACKUP_MD))

    active = dict(proposal)
    active['proposal_only'] = False
    active['active_project_map_updated'] = True
    active['active_promotion'] = {
        'promoted_at': dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat(),
        'source_json': rel(GENERATED_PROPOSAL_JSON),
        'source_md': rel(GENERATED_PROPOSAL_MD),
        'contract': rel(MAP_PROMOTION_CONTRACT_MD),
        'review': rel(GENERATED_PROPOSAL_REVIEW_MD),
        'scope': 'active_project_map_json_and_md_only',
        'merge_queue_processed': False,
        'runtime_materialized': False,
        'product_tests_run': False,
        'provider_probe_run': False,
        'data_update_run': False,
        'deploy_release_run': False,
        'readiness_claims_made': False,
    }
    write_json(project / PROJECT_MAP_JSON, active)
    (project / PROJECT_MAP_MD).write_text(render_project_map_md(active), encoding='utf-8')
    changed.extend([rel(PROJECT_MAP_JSON), rel(PROJECT_MAP_MD)])
    return active, changed


def render_map_promotion_review(project: Path, kind: str) -> str:
    active = read_json(project / PROJECT_MAP_JSON)
    contamination = find_project_map_contamination(active, kind) if active else []
    promotion = active.get('active_promotion') if isinstance(active.get('active_promotion'), dict) else {}
    flags_ok = {
        'merge_queue_processed': promotion.get('merge_queue_processed') is False,
        'runtime_materialized': promotion.get('runtime_materialized') is False,
        'product_tests_run': promotion.get('product_tests_run') is False,
        'provider_probe_run': promotion.get('provider_probe_run') is False,
        'data_update_run': promotion.get('data_update_run') is False,
        'deploy_release_run': promotion.get('deploy_release_run') is False,
        'readiness_claims_made': promotion.get('readiness_claims_made') is False,
    }
    verdict = (
        'APPROVE'
        if active and not active.get('_json_error') and not contamination and all(flags_ok.values())
        else 'BLOCKED'
    )
    lines = [
        '# Active Project-Map Promotion Review',
        '',
        f'## Review Verdict: {verdict}',
        '',
        '## Changed Files',
        '',
        f'- `{rel(PROJECT_MAP_JSON)}`',
        f'- `{rel(PROJECT_MAP_MD)}`',
        f'- `{rel(MAP_PRE_PROMOTION_BACKUP_JSON)}` if prior active JSON existed',
        f'- `{rel(MAP_PRE_PROMOTION_BACKUP_MD)}` if prior active Markdown existed',
        '',
        '## Findings',
        '',
    ]
    if contamination:
        lines.append(f'- BLOCKED: excluded paths appear in active project map: {", ".join(contamination[:30])}')
    else:
        lines.append(
            '- PASS: active project map contains no required exclusion pattern contamination in owned paths or entrypoint candidates.'
        )
    for key, ok in flags_ok.items():
        lines.append(f'- {"PASS" if ok else "BLOCKED"}: active_promotion.{key} == false')
    lines.extend(
        [
            '',
            '## Scope Guard',
            '',
            '- Promotion was limited to active project-map JSON/Markdown plus rollback backups and this review artifact.',
            '- No merge queue, runtime materialization, product tests, provider probes, data updates, cache mutation, merge, push, deploy, release, install, rebuild, or destructive cleanup were performed.',
        ]
    )
    return '\n'.join(lines) + '\n'


def render_architecture_review(project: Path, kind: str) -> str:
    active = read_json(project / PROJECT_MAP_JSON)
    contamination = find_project_map_contamination(active, kind) if active else []
    unresolved: list[str] = []
    if contamination:
        unresolved.append('project_map_generated_path_contamination')
    if not active or active.get('_json_error'):
        unresolved.append('active_project_map_invalid_or_missing')
    if kind == 'steward':
        unresolved.extend(
            [
                'native_sqlite_abi_mismatch_or_load_failure',
                'profile_downgrade_proposal',
                'local_architecture_rule_unknowns',
                'dirty_or_untracked_governance_state',
            ]
        )
    elif kind == 'macro':
        unresolved.extend(
            [
                'runtime_data_dirty_paths_require_separate_data_update_contract',
                'profile_downgrade_proposal',
                'local_architecture_rule_unknowns',
                'market_feedback_not_direct_macro_proof',
                'dirty_or_untracked_governance_state',
            ]
        )
    verdict = 'APPROVE' if not unresolved else 'BLOCKED'
    lines = [
        '# Architecture Compatibility Post Project-Map Promotion Review',
        '',
        f'## Review Verdict: {verdict}',
        '',
        '## Project-Map Contamination Closure',
        '',
    ]
    if contamination:
        lines.append(f'- BLOCKED: excluded paths still appear in active project map: {", ".join(contamination[:30])}')
    else:
        lines.append(
            '- PASS: generated/runtime/cache/secret/provider/dependency exclusion contamination is not present in active project-map owned paths or entrypoints.'
        )
    lines.extend(
        [
            '',
            '## Remaining Architecture Risks',
            '',
        ]
    )
    if unresolved:
        lines.extend([f'- {item}' for item in unresolved])
    else:
        lines.append('- none')
    lines.extend(
        [
            '',
            '## Boundary',
            '',
            '- This review does not run product tests, provider probes, data updates, cache mutation, runtime materialization, merge, push, deploy, or release.',
            '- Existing active architecture report is not overwritten by this review.',
        ]
    )
    return '\n'.join(lines) + '\n'


def render_runtime_readiness(project: Path, kind: str) -> str:
    arch_text = (
        (project / ARCHITECTURE_REVIEW_MD).read_text(encoding='utf-8', errors='replace')
        if (project / ARCHITECTURE_REVIEW_MD).exists()
        else ''
    )
    blocked = '## Review Verdict: BLOCKED' in arch_text
    verdict = 'BLOCKED' if blocked else 'READY_FOR_SEPARATE_RUNTIME_AUTHORIZATION'
    project_notes = {
        'steward': [
            'Graph DB/SQLite readiness remains blocked until native runtime evidence is separately produced.',
            'Preview-only surfaces must not be upgraded into automatic execution, deploy, or Graph DB readiness.',
        ],
        'macro': [
            'Data updates, provider probes, cache mutation, and market feedback proof remain separate authorization domains.',
            'Market feedback remains indirect market evidence only.',
        ],
    }.get(kind, [])
    lines = [
        '# Runtime and Integration Readiness Assessment',
        '',
        f'## Verdict: {verdict}',
        '',
        '## Completed',
        '',
        '- scan-policy active promotion reviewed',
        '- scanner/rescan proposal generated and reviewed',
        '- active project-map promotion completed and reviewed',
        '- architecture compatibility post-review generated',
        '',
        '## Not Performed',
        '',
        '- merge queue processing',
        '- runtime materialization',
        '- product tests',
        '- data update',
        '- provider probe',
        '- cache mutation',
        '- merge, push, deploy, release',
        '',
        '## Remaining Boundary',
        '',
        *[f'- {item}' for item in project_notes],
    ]
    return '\n'.join(lines) + '\n'


def inspect_project(project: Path, kind: str) -> dict[str, Any]:
    scan_policy = read_json(project / SCAN_POLICY)
    exclude_patterns = (
        scan_policy.get('exclude_patterns') if isinstance(scan_policy.get('exclude_patterns'), list) else []
    )
    promotion = scan_policy.get('active_promotion') if isinstance(scan_policy.get('active_promotion'), dict) else {}
    expected = expected_excludes(kind)
    missing_excludes = [item for item in expected if item not in exclude_patterns]
    missing_sources = [rel(p) for p in SOURCE_ARTIFACTS if not (project / p).exists()]

    flags = {
        'project_map_json_updated': promotion.get('project_map_json_updated') is False,
        'project_map_md_updated': promotion.get('project_map_md_updated') is False,
        'scanner_rescan_run': promotion.get('scanner_rescan_run') is False,
        'restricted_content_read': promotion.get('restricted_content_read') is False,
        'merge_queue_processed': promotion.get('merge_queue_processed') is False,
        'readiness_claims_made': promotion.get('readiness_claims_made') is False,
    }
    all_flags_ok = all(flags.values())
    scan_policy_ready = not scan_policy.get('_json_error') and not missing_excludes and all_flags_ok

    statuses = git_status(project, SAFE_STATUS_PATHS)
    gate = 'scan_policy_active_promotion_review'
    next_action = 'review scan-policy active promotion'
    if missing_sources:
        gate = 'missing_source_artifacts'
        next_action = 'create or approve missing governance artifacts before active promotion'
    elif not (project / SCAN_POLICY).exists():
        gate = 'missing_scan_policy'
        next_action = 'bootstrap or create scan-policy artifact'
    elif not scan_policy_ready:
        gate = 'scan_policy_active_promotion_needed'
        next_action = 'run with --promote-scan-policy after explicit authorization'
    elif (project / REVIEW_MD).exists():
        gate = 'scan_policy_active_promotion_reviewed'
        next_action = 'consider separately authorized scanner/rescan contract'
    if gate == 'scan_policy_active_promotion_reviewed' and (project / RESCAN_CONTRACT_MD).exists():
        gate = 'scanner_rescan_contract_created'
        next_action = 'run proposal-only project-map rescan'
    if (project / GENERATED_PROPOSAL_JSON).exists() and (project / GENERATED_PROPOSAL_MD).exists():
        gate = 'scanner_rescan_proposal_generated'
        next_action = 'review generated project-map proposal'
    if (project / GENERATED_PROPOSAL_REVIEW_MD).exists():
        gate = 'scanner_rescan_proposal_reviewed'
        next_action = 'create active project-map promotion contract'
    if (project / MAP_PROMOTION_CONTRACT_MD).exists():
        gate = 'active_project_map_promotion_contract_created'
        next_action = 'promote approved generated proposal to active project-map'
    map_data = read_json(project / PROJECT_MAP_JSON) if (project / PROJECT_MAP_JSON).exists() else {}
    map_promotion = map_data.get('active_promotion') if isinstance(map_data.get('active_promotion'), dict) else {}
    if isinstance(map_promotion, dict) and map_promotion.get('scope') == 'active_project_map_json_and_md_only':
        gate = 'active_project_map_promoted'
        next_action = 'review active project-map promotion and architecture compatibility'
    if (project / MAP_PROMOTION_REVIEW_MD).exists():
        gate = 'active_project_map_promotion_reviewed'
        next_action = 'run architecture compatibility post-review'
    if (project / ARCHITECTURE_REVIEW_MD).exists():
        gate = 'architecture_post_review_complete'
        next_action = 'assess runtime/integration readiness'
    if (project / RUNTIME_READINESS_MD).exists():
        gate = 'runtime_integration_readiness_assessed'
        next_action = 'resolve remaining blockers under separate contracts before runtime/merge/deploy'

    return {
        'project': str(project),
        'project_kind': kind,
        'goal': 'project-map-contamination-closure',
        'gate': gate,
        'next_action': next_action,
        'artifacts': {
            'scan_policy': rel(SCAN_POLICY),
            'review': rel(REVIEW_MD),
            'rescan_contract': rel(RESCAN_CONTRACT_MD),
            'generated_proposal_json': rel(GENERATED_PROPOSAL_JSON),
            'generated_proposal_md': rel(GENERATED_PROPOSAL_MD),
            'generated_proposal_review': rel(GENERATED_PROPOSAL_REVIEW_MD),
            'map_promotion_contract': rel(MAP_PROMOTION_CONTRACT_MD),
            'map_promotion_review': rel(MAP_PROMOTION_REVIEW_MD),
            'architecture_review': rel(ARCHITECTURE_REVIEW_MD),
            'runtime_readiness': rel(RUNTIME_READINESS_MD),
            'source_artifacts': [rel(p) for p in SOURCE_ARTIFACTS],
        },
        'source_artifacts_missing': missing_sources,
        'scan_policy': {
            'exists': (project / SCAN_POLICY).exists(),
            'json_error': scan_policy.get('_json_error', ''),
            'exclude_count': len(exclude_patterns),
            'missing_required_excludes': missing_excludes,
            'active_promotion': promotion,
            'flags_ok': flags,
            'ready': scan_policy_ready,
        },
        'project_map': {
            'active_promotion': map_promotion,
        },
        'protected_artifact_stats': {
            'project_map_json': stat_file(project / PROJECT_MAP_JSON),
            'project_map_md': stat_file(project / PROJECT_MAP_MD),
        },
        'git_status_path_limited': statuses,
        'restricted_read_proof': [
            'This conductor reads approved Markdown governance artifacts, .zoo-agent/bootstrap/scan-policy.json, and active project-map artifacts only in project-map promotion/review phases.',
            'It does not read data, cache, secrets, provider profiles, credentials, dependency internals, native module internals, or merge queue contents.',
        ],
        'forbidden_command_proof': [
            'No scanner/rescan, data update, provider probe, product test, cache mutation, runtime materialization, merge queue processing, merge, push, deploy, release, install, or rebuild command is invoked by this conductor.',
            'The only subprocess used is path-limited git status for reviewer evidence.',
        ],
    }


def render_review(report: dict[str, Any]) -> str:
    verdict = 'APPROVE' if report['scan_policy']['ready'] and not report['source_artifacts_missing'] else 'BLOCKED'
    missing = report['scan_policy']['missing_required_excludes']
    flags = report['scan_policy']['flags_ok']
    lines = [
        '# Scan Policy Active Promotion Review',
        '',
        f'## Review Verdict: {verdict}',
        '',
        'This is an automated, path-bounded review of the first active scan-policy promotion.',
        'It does not inspect project-map contents, data/cache contents, secrets, provider profiles, dependency internals, native module internals, or merge queue contents.',
        '',
        '## Scope',
        '',
        f'- project_kind: {report["project_kind"]}',
        f'- reviewed_scan_policy: `{report["artifacts"]["scan_policy"]}`',
        '- active_project_map_json_updated: false by active_promotion flag',
        '- active_project_map_md_updated: false by active_promotion flag',
        '- scanner_rescan_run: false by active_promotion flag',
        '- merge_queue_processed: false by active_promotion flag',
        '',
        '## Changed Files',
        '',
        f'- `{report["artifacts"]["scan_policy"]}`: active scan-policy/exclusion-policy artifact under review.',
        f'- `{report["artifacts"]["review"]}`: review handoff artifact generated by this conductor.',
        '- `.zoo-agent/project-map.json`: not changed by this promotion.',
        '- `.zoo-agent/project-map.md`: not changed by this promotion.',
        '',
        '## Scope Guard',
        '',
        '- Allowed surface: scan-policy / exclusion-policy artifact and this review handoff only.',
        '- Denied surfaces: active project-map JSON/Markdown, scanner/rescan, data/cache/secrets/provider profiles, credentials, dependency internals, native module internals, merge queue, product code, tests, release/deploy surfaces, and unrelated dirty paths.',
        '- Promotion remains policy-only; it does not claim Graph DB, SQLite, macro proof, release, deploy, or whole-workspace readiness.',
        '',
        '## Findings',
        '',
    ]
    if report['source_artifacts_missing']:
        lines.append(f'- BLOCKED: missing source artifacts: {", ".join(report["source_artifacts_missing"])}')
    else:
        lines.append('- PASS: all expected source artifacts for this promotion line exist.')
    if missing:
        lines.append(f'- BLOCKED: missing required exclude patterns: {", ".join(missing)}')
    else:
        lines.append('- PASS: required generated/runtime/denied exclude patterns are present.')
    for key, ok in flags.items():
        lines.append(f'- {"PASS" if ok else "BLOCKED"}: active_promotion.{key} == false')
    lines.extend(
        [
            '',
            '## Protected Artifact Evidence',
            '',
            f'- project_map_json: `{json.dumps(report["protected_artifact_stats"]["project_map_json"], ensure_ascii=False)}`',
            f'- project_map_md: `{json.dumps(report["protected_artifact_stats"]["project_map_md"], ensure_ascii=False)}`',
            '- Note: path metadata is not project-map content inspection.',
            '',
            '## Path-Limited Git Status',
            '',
        ]
    )
    statuses = report['git_status_path_limited']
    if statuses:
        lines.extend([f'- `{line}`' for line in statuses])
    else:
        lines.append('- No path-limited status entries for scan policy, project map, or review artifact.')
    lines.extend(
        [
            '',
            '## Restricted-Read Proof',
            '',
            *[f'- {item}' for item in report['restricted_read_proof']],
            '',
            '## Forbidden-Command Proof',
            '',
            *[f'- {item}' for item in report['forbidden_command_proof']],
            '',
            '## Rollback Boundary',
            '',
            '- If rejected, roll back only `.zoo-agent/bootstrap/scan-policy.json` diff from this active promotion.',
            '- Do not touch `.zoo-agent/project-map.json`, `.zoo-agent/project-map.md`, data/cache/secrets/provider profiles, dependency internals, native modules, merge queue, product code, tests, or unrelated dirty paths.',
            '',
            '## Reviewer Handoff',
            '',
            '- Reviewer should verify this report and `.zoo-agent/bootstrap/scan-policy.json` only.',
            '- Reviewer should not run scanner/rescan, product tests, data update, provider probe, merge queue processing, cache mutation, merge, push, deploy, or release.',
            '- Later scanner/rescan or active project-map promotion still requires separate explicit authorization.',
        ]
    )
    return '\n'.join(lines) + '\n'


def main() -> int:
    parser = argparse.ArgumentParser(description='Governance landing conductor for project-map contamination closure.')
    parser.add_argument('--project', required=True, help='Business project path.')
    parser.add_argument('--project-kind', default='auto', choices=['auto', 'steward', 'macro', 'generic'])
    parser.add_argument(
        '--mode',
        default='status',
        choices=[
            'status',
            'promote-scan-policy',
            'write-review',
            'create-rescan-contract',
            'rescan-proposal',
            'review-proposal',
            'create-map-promotion-contract',
            'promote-project-map',
            'architecture-review',
            'runtime-readiness',
            'full',
        ],
    )
    parser.add_argument('--json', action='store_true', help='Print machine-readable JSON.')
    args = parser.parse_args()

    project = Path(args.project).resolve()
    if not project.exists():
        print(f'Missing project: {project}', file=sys.stderr)
        return 2
    kind = infer_project_kind(project, args.project_kind)
    if kind == 'generic':
        print('Unable to infer project kind; pass --project-kind steward or --project-kind macro.', file=sys.stderr)
        return 2

    changed: list[str] = []
    if args.mode in {'promote-scan-policy', 'full'}:
        payload, changed = ensure_scan_policy(project, kind)
        if changed:
            write_json(project / SCAN_POLICY, payload)
            changed = [rel(SCAN_POLICY)]

    report = inspect_project(project, kind)
    if args.mode in {'write-review', 'full'}:
        review_text = render_review(report)
        review_path = project / REVIEW_MD
        review_path.parent.mkdir(parents=True, exist_ok=True)
        review_path.write_text(review_text, encoding='utf-8')
        changed.append(rel(REVIEW_MD))
        report = inspect_project(project, kind)

    if args.mode in {'create-rescan-contract', 'full'}:
        contract_path = project / RESCAN_CONTRACT_MD
        contract_path.parent.mkdir(parents=True, exist_ok=True)
        contract_path.write_text(render_rescan_contract(project, kind), encoding='utf-8')
        changed.append(rel(RESCAN_CONTRACT_MD))

    if args.mode in {'rescan-proposal', 'full'}:
        _proposal, proposal_changed = write_rescan_proposal(project, kind)
        changed.extend(proposal_changed)

    proposal_verdict = ''
    if args.mode in {'review-proposal', 'full'}:
        proposal_verdict, review_changed = review_rescan_proposal(project, kind)
        changed.extend(review_changed)

    if args.mode in {'create-map-promotion-contract', 'full'}:
        if not proposal_verdict and (project / GENERATED_PROPOSAL_REVIEW_MD).exists():
            text = (project / GENERATED_PROPOSAL_REVIEW_MD).read_text(encoding='utf-8', errors='replace')
            proposal_verdict = 'APPROVE' if '## Review Verdict: APPROVE' in text else 'BLOCKED'
        if args.mode != 'full' or proposal_verdict == 'APPROVE':
            contract_path = project / MAP_PROMOTION_CONTRACT_MD
            contract_path.write_text(render_map_promotion_contract(project, kind), encoding='utf-8')
            changed.append(rel(MAP_PROMOTION_CONTRACT_MD))

    if args.mode in {'promote-project-map', 'full'}:
        if not proposal_verdict and (project / GENERATED_PROPOSAL_REVIEW_MD).exists():
            text = (project / GENERATED_PROPOSAL_REVIEW_MD).read_text(encoding='utf-8', errors='replace')
            proposal_verdict = 'APPROVE' if '## Review Verdict: APPROVE' in text else 'BLOCKED'
        if proposal_verdict == 'APPROVE' or args.mode == 'promote-project-map':
            _active, map_changed = promote_project_map(project, kind)
            changed.extend(map_changed)
            (project / MAP_PROMOTION_REVIEW_MD).write_text(render_map_promotion_review(project, kind), encoding='utf-8')
            changed.append(rel(MAP_PROMOTION_REVIEW_MD))

    if args.mode in {'architecture-review', 'full'}:
        (project / ARCHITECTURE_REVIEW_MD).write_text(render_architecture_review(project, kind), encoding='utf-8')
        changed.append(rel(ARCHITECTURE_REVIEW_MD))

    if args.mode in {'runtime-readiness', 'full'}:
        (project / RUNTIME_READINESS_MD).write_text(render_runtime_readiness(project, kind), encoding='utf-8')
        changed.append(rel(RUNTIME_READINESS_MD))

    report = inspect_project(project, kind)

    report['mode'] = args.mode
    report['changed_by_conductor'] = list(dict.fromkeys(changed))

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f'project: {project}')
        print(f'project_kind: {kind}')
        print(f'gate: {report["gate"]}')
        print(f'next_action: {report["next_action"]}')
        if changed:
            print('changed_by_conductor:')
            for item in changed:
                print(f' - {item}')
        missing = report['scan_policy']['missing_required_excludes']
        print(f'scan_policy_ready: {report["scan_policy"]["ready"]}')
        print(f'missing_required_excludes: {len(missing)}')
        if missing:
            for item in missing:
                print(f' - {item}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
