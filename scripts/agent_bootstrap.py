#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GLOBAL_KIT = Path.home() / '.roo' / 'agent-governance-kit'
PUBLIC_ZOO_CODE = Path.home() / 'zoo-global-agent-kit' / 'public' / 'fractal-agent-governance' / 'packages' / 'zoo-code'
KIT_VERSION = '0.3.11-architecture-feedback-hardening-windows-probes'

GENERATED_PATH_PATTERNS = [
    '.zoo-agent/runs/**',
    '.zoo-agent/tmp/**',
    '.zoo-agent/worktrees/**',
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

PROFILE_PROPOSAL_RELATIVE = Path('zoo-agent') / 'project-profile.json'


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')


def first_existing(paths: list[Path]) -> Path | None:
    for path in paths:
        if path.exists():
            return path
    return None


def run_command(command: list[str], cwd: Path) -> dict:
    proc = subprocess.run(
        command,
        cwd=cwd,
        text=True,
        encoding='utf-8',
        errors='replace',
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    return {
        'command': command,
        'cwd': str(cwd),
        'returncode': proc.returncode,
        'stdout': proc.stdout.strip(),
    }


def windows_command_variants(command: list[str]) -> list[list[str]]:
    if not command or sys.platform != 'win32' or Path(command[0]).suffix:
        return [command]
    variants = [command]
    for suffix in ['.cmd', '.exe', '.bat']:
        variants.append([f'{command[0]}{suffix}', *command[1:]])
    return variants


def command_available(name: str) -> bool:
    return any(shutil.which(variant[0]) is not None for variant in windows_command_variants([name]))


def run_probe_once(command: list[str], cwd: Path) -> dict:
    try:
        proc = subprocess.run(
            command,
            cwd=cwd,
            text=True,
            encoding='utf-8',
            errors='replace',
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=15,
        )
        return {
            'command': command,
            'cwd': str(cwd),
            'returncode': proc.returncode,
            'stdout': proc.stdout.strip(),
        }
    except FileNotFoundError:
        return {
            'command': command,
            'cwd': str(cwd),
            'returncode': 127,
            'stdout': f'{command[0]} not found',
        }
    except OSError as exc:
        return {
            'command': command,
            'cwd': str(cwd),
            'returncode': getattr(exc, 'winerror', 1) or 1,
            'stdout': f'{type(exc).__name__}: {exc}',
        }
    except subprocess.TimeoutExpired as exc:
        return {
            'command': command,
            'cwd': str(cwd),
            'returncode': 124,
            'stdout': (exc.stdout or '').strip() if isinstance(exc.stdout, str) else 'probe timed out',
        }


def should_try_probe_fallback(result: dict) -> bool:
    stdout = str(result.get('stdout', ''))
    return result.get('returncode') in {5, 127} or 'PermissionError' in stdout or 'not found' in stdout


def run_probe(command: list[str], cwd: Path) -> dict:
    attempts: list[dict] = []
    for variant in windows_command_variants(command):
        result = run_probe_once(variant, cwd)
        attempts.append(result)
        if result['returncode'] == 0 or not should_try_probe_fallback(result):
            if len(attempts) > 1:
                result['fallback_attempts'] = attempts[:-1]
            return result
    result = attempts[-1]
    if len(attempts) > 1:
        result['fallback_attempts'] = attempts[:-1]
    return result


def print_json(payload: dict) -> None:
    print(json.dumps(payload, ensure_ascii=True, indent=2))


def read_json(path: Path) -> dict | list | None:
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError):
        return None


def listify(value: object) -> list:
    if isinstance(value, list):
        return value
    if value in (None, ''):
        return []
    return [value]


def profile_score(profile: object) -> int:
    if not isinstance(profile, dict):
        return 0
    score = 0
    score += len(listify(profile.get('languages')))
    score += len(listify(profile.get('frameworks'))) * 2
    score += len(listify(profile.get('source_roots'))) * 3
    score += len(listify(profile.get('test_roots'))) * 2
    score += len(listify(profile.get('api_entrypoints'))) * 3
    score += len(listify(profile.get('repository_manifests'))) * 3
    commands = profile.get('commands')
    if isinstance(commands, dict):
        score += sum(1 for value in commands.values() if value) * 2
    risk_paths = profile.get('risk_paths')
    if isinstance(risk_paths, dict):
        score += len(risk_paths) * 2
    if profile.get('project_summary'):
        score += 2
    if profile.get('architecture_boundaries_path'):
        score += 2
    return score


def profile_has_frontend(profile: object) -> bool:
    if not isinstance(profile, dict):
        return False
    haystack = json.dumps(profile, ensure_ascii=False).lower()
    return 'frontend' in haystack or 'next.js' in haystack or 'react' in haystack


def find_profile_proposals(project: Path) -> list[Path]:
    proposals = []
    direct = project / '.zoo-agent' / 'project-profile.json.new'
    if direct.exists():
        proposals.append(direct)
    inbox = project / '.zoo-agent' / 'bootstrap' / 'proposals'
    if inbox.exists():
        candidate = inbox / PROFILE_PROPOSAL_RELATIVE
        if candidate.exists():
            proposals.append(candidate)
        proposals.extend(path for path in inbox.rglob('project-profile*.json') if path not in proposals)
    unique: list[Path] = []
    seen: set[str] = set()
    for path in proposals:
        try:
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
        except OSError:
            digest = str(path)
        if digest in seen:
            continue
        seen.add(digest)
        unique.append(path)
    return unique


def normalize_pattern_for_search(pattern: str) -> str:
    return pattern.replace('\\', '/').replace('**', '').strip('/')


def git_status_lines(project: Path) -> list[str]:
    if not (project / '.git').exists():
        return []
    result = run_command(['git', 'status', '--porcelain=v1'], project)
    if result['returncode'] != 0:
        return []
    return [line for line in result['stdout'].splitlines() if line.strip()]


def git_status_path(line: str) -> str:
    text = line[3:] if len(line) > 3 else line
    if ' -> ' in text:
        text = text.split(' -> ', 1)[1]
    return text.strip().replace('\\', '/')


def project_readiness(project: Path) -> dict:
    data = read_json(project / '.zoo-agent' / 'project-readiness.json')
    return data if isinstance(data, dict) else {}


def task_board_warnings(project: Path) -> list[str]:
    warnings = []
    runs_dir = project / '.zoo-agent' / 'runs'
    if runs_dir.exists():
        for path in sorted(runs_dir.glob('*/task-board-consistency.json')):
            data = read_json(path)
            if isinstance(data, dict):
                for item in listify(data.get('warnings')):
                    text = str(item)
                    if text not in warnings:
                        warnings.append(text)
    return warnings


def suspicious_root_files(project: Path) -> list[str]:
    suspicious = []
    for path in project.iterdir() if project.exists() else []:
        if not path.is_file():
            continue
        name = path.name
        if name in {'$null', 'null', 'undefined'}:
            suspicious.append(name)
        elif any(ch in name for ch in '[](){}') and not name.lower().endswith(('.md', '.json', '.py', '.txt')):
            suspicious.append(name)
    return suspicious


def package_declares_or_installs(frontend: Path, package_name: str) -> bool:
    package_json = read_json(frontend / 'package.json')
    if isinstance(package_json, dict):
        for key in ['dependencies', 'devDependencies', 'optionalDependencies', 'peerDependencies']:
            deps = package_json.get(key)
            if isinstance(deps, dict) and package_name in deps:
                return True
    return (frontend / 'node_modules' / package_name / 'package.json').exists()


def probe_environment(project: Path) -> dict:
    frontend = project / 'frontend'
    node_available = command_available('node')
    npm_available = command_available('npm')
    codex_available = command_available('codex')
    payload: dict = {
        'python': {
            'executable': sys.executable,
            'version': sys.version.split()[0],
        },
        'codex_cli': {
            'available': codex_available,
            'version_probe': run_probe(['codex', '--version'], project) if codex_available else None,
        },
        'node': {
            'available': node_available,
            'version_probe': run_probe(['node', '-v'], frontend if frontend.exists() else project)
            if node_available
            else None,
            'abi_probe': run_probe(
                ['node', '-p', 'process.versions.modules'], frontend if frontend.exists() else project
            )
            if node_available
            else None,
        },
        'npm': {
            'available': npm_available,
            'version_probe': run_probe(['npm', '-v'], frontend if frontend.exists() else project)
            if npm_available
            else None,
        },
        'native_dependencies': {},
    }
    if (
        frontend.exists()
        and (frontend / 'package.json').exists()
        and node_available
        and package_declares_or_installs(frontend, 'better-sqlite3')
    ):
        payload['native_dependencies']['better-sqlite3'] = {
            'package_version_probe': run_probe(
                ['node', '-p', "require('./node_modules/better-sqlite3/package.json').version"],
                frontend,
            ),
            'load_probe': run_probe(
                [
                    'node',
                    '-e',
                    "try { const Database = require('better-sqlite3'); const db = new Database(':memory:'); db.close(); console.log('load_ok') } catch (error) { console.error(error && error.message ? error.message : error); process.exit(1) }",
                ],
                frontend,
            ),
        }
    return payload


def architecture_issues(project: Path, proposal_result: dict, environment: dict) -> list[dict]:
    issues: list[dict] = []
    readiness = project_readiness(project)
    status_lines = git_status_lines(project)
    dirty_paths = [git_status_path(line) for line in status_lines]

    if not environment.get('codex_cli', {}).get('available'):
        issues.append(
            {
                'id': 'codex_cli_unavailable',
                'severity': 'medium',
                'status': 'blocks_codex_worker_execution',
                'basis': ['PATH/codex --version probe'],
                'message': 'Codex CLI is not available in the current environment; Level 0/1 worker loops can prepare governance artifacts but cannot execute Codex worker tasks.',
            }
        )
    else:
        codex_probe = environment.get('codex_cli', {}).get('version_probe') or {}
        if codex_probe.get('returncode') != 0:
            issues.append(
                {
                    'id': 'codex_cli_probe_failed',
                    'severity': 'medium',
                    'status': 'blocks_codex_worker_execution',
                    'basis': ['PATH/codex --version probe'],
                    'message': 'Codex CLI was found but its version probe failed; worker execution evidence is conditional until the executable shim is fixed.',
                    'probe': codex_probe,
                }
            )

    if readiness.get('safe_for_level_0_1_trial') is False or readiness.get('codex_cli_ready') is False:
        issues.append(
            {
                'id': 'project_readiness_blocks_fast_trial',
                'severity': 'medium',
                'status': 'needs_operator_action',
                'basis': [str(project / '.zoo-agent' / 'project-readiness.json')],
                'message': 'Project readiness says Level 0/1 trial execution is not safe yet.',
                'blocking_issues': readiness.get('blocking_issues') or [],
                'next_actions': readiness.get('next_actions') or [],
            }
        )

    retired_dirty = [path for path in dirty_paths if path.startswith('.antigravity/') or path.startswith('.steward/')]
    if retired_dirty:
        issues.append(
            {
                'id': 'retired_governance_dirty_paths',
                'severity': 'medium',
                'status': 'exclude_from_current_attribution',
                'basis': ['git status --porcelain=v1'],
                'message': 'Retired governance framework paths are dirty; do not stage, revert, or attribute them to current Zoo work without a migration contract.',
                'paths': retired_dirty,
            }
        )

    data_dirty = [
        path for path in dirty_paths if path.startswith(('data/', 'data_test/', 'outputs/', 'artifacts/', 'reports/'))
    ]
    if data_dirty:
        issues.append(
            {
                'id': 'runtime_data_dirty_paths',
                'severity': 'medium',
                'status': 'requires_data_update_contract',
                'basis': ['git status --porcelain=v1'],
                'message': 'Runtime data or generated artifacts are dirty; keep them outside code-task attribution unless a data/update contract authorizes mutation.',
                'paths': data_dirty,
            }
        )

    root_noise = suspicious_root_files(project)
    if root_noise:
        issues.append(
            {
                'id': 'suspicious_root_artifacts',
                'severity': 'low',
                'status': 'review_before_cleanup',
                'basis': [str(project)],
                'message': 'Suspicious root-level files look like accidental command/output artifacts. Do not delete them automatically; isolate them from task attribution.',
                'paths': root_noise,
            }
        )

    governance_dirty = [
        path
        for path in dirty_paths
        if path in {'AGENTS.md', '.gitignore'} or path.startswith(('.roo/', '.zoo-agent/', 'docs/agent-governance/'))
    ]
    if governance_dirty:
        issues.append(
            {
                'id': 'governance_runtime_dirty_paths',
                'severity': 'low',
                'status': 'path_scoped_review_required',
                'basis': ['git status --porcelain=v1'],
                'message': 'Governance runtime or local rule files are dirty; integration should use path-scoped attribution instead of broad staging.',
                'paths': governance_dirty[:80],
            }
        )

    board_warnings = task_board_warnings(project)
    if board_warnings:
        issues.append(
            {
                'id': 'task_board_consistency_warnings',
                'severity': 'low',
                'status': 'review_before_continuation',
                'basis': ['.zoo-agent/runs/*/task-board-consistency.json'],
                'message': 'Task-board consistency checks produced warnings; review before continuing stale redirect plans.',
                'warnings': board_warnings,
            }
        )

    active_profile_path = project / '.zoo-agent' / 'project-profile.json'
    active_profile = read_json(active_profile_path)
    active_score = profile_score(active_profile)
    profile_proposals = find_profile_proposals(project)
    downgrade_proposals: list[dict] = []
    frontend_lost_proposals: list[str] = []
    for proposal_path in profile_proposals:
        proposal = read_json(proposal_path)
        proposal_score = profile_score(proposal)
        if active_score and proposal_score < active_score:
            downgrade_proposals.append({'path': str(proposal_path), 'score': proposal_score})
        if profile_has_frontend(active_profile) and not profile_has_frontend(proposal):
            frontend_lost_proposals.append(str(proposal_path))
    if downgrade_proposals:
        issues.append(
            {
                'id': 'profile_downgrade_proposal',
                'severity': 'high',
                'status': 'blocked',
                'basis': [str(active_profile_path), *[item['path'] for item in downgrade_proposals[:8]]],
                'message': 'Bootstrap produced lower-information project-profile proposals; keep the active profile and review proposals manually.',
                'active_score': active_score,
                'worst_proposal_score': min(item['score'] for item in downgrade_proposals),
                'proposal_count': len(downgrade_proposals),
            }
        )
    if frontend_lost_proposals:
        issues.append(
            {
                'id': 'frontend_stack_lost_in_profile_proposal',
                'severity': 'high',
                'status': 'blocked',
                'basis': [str(active_profile_path), *frontend_lost_proposals[:8]],
                'message': 'Active profile contains frontend/Next/React evidence, but profile proposals do not.',
                'proposal_count': len(frontend_lost_proposals),
            }
        )

    local_arch_rule = project / '.roo' / 'rules' / '10-project-architecture.md'
    if local_arch_rule.exists():
        text = local_arch_rule.read_text(encoding='utf-8', errors='replace').lower()
        if 'source roots: unknown' in text or 'api entrypoints: unknown' in text:
            issues.append(
                {
                    'id': 'local_architecture_rule_unknowns',
                    'severity': 'medium',
                    'status': 'needs_review',
                    'basis': [str(local_arch_rule)],
                    'message': 'Local project architecture rule still says source roots or API entrypoints are unknown.',
                }
            )

    profile_new = read_json(project / '.zoo-agent' / 'project-profile.json.new')
    if isinstance(profile_new, dict) and not listify(profile_new.get('source_roots')):
        issues.append(
            {
                'id': 'profile_proposal_empty_source_roots',
                'severity': 'medium',
                'status': 'needs_review',
                'basis': [str(project / '.zoo-agent' / 'project-profile.json.new')],
                'message': 'Project profile proposal has empty source_roots.',
            }
        )

    project_map_md = project / '.zoo-agent' / 'project-map.md'
    project_map_json = project / '.zoo-agent' / 'project-map.json'
    map_text_parts = []
    for path in [project_map_md, project_map_json]:
        if path.exists():
            map_text_parts.append(path.read_text(encoding='utf-8', errors='replace').replace('\\', '/'))
    map_text = '\n'.join(map_text_parts)
    contaminated = []
    for pattern in GENERATED_PATH_PATTERNS:
        needle = normalize_pattern_for_search(pattern)
        if needle and needle in map_text:
            contaminated.append(pattern)
    if contaminated:
        issues.append(
            {
                'id': 'project_map_generated_path_contamination',
                'severity': 'high',
                'status': 'needs_rescan',
                'basis': [str(project_map_md), str(project_map_json)],
                'message': 'Project map includes generated/runtime paths; source scanning should exclude them before module/entrypoint detection.',
                'generated_patterns_found': sorted(set(contaminated)),
            }
        )
    if 'scan_file_limit_reached' in map_text:
        issues.append(
            {
                'id': 'project_map_scan_limit_reached',
                'severity': 'medium',
                'status': 'needs_rescan',
                'basis': [str(project_map_md), str(project_map_json)],
                'message': 'Project map hit the scan file limit; generated path exclusion or source-root narrowing is required.',
            }
        )

    if (project / '.steward').exists() and (project / '.zoo-agent').exists():
        issues.append(
            {
                'id': 'dual_governance_state_requires_resolver',
                'severity': 'medium',
                'status': 'resolver_written',
                'basis': [str(project / '.steward'), str(project / '.zoo-agent')],
                'message': '.steward and .zoo-agent both exist; use the source-of-truth resolver before durable state decisions.',
            }
        )

    better_sqlite = environment.get('native_dependencies', {}).get('better-sqlite3')
    if isinstance(better_sqlite, dict):
        load_probe = better_sqlite.get('load_probe') or {}
        if load_probe.get('returncode') not in (None, 0):
            issues.append(
                {
                    'id': 'native_sqlite_abi_mismatch_or_load_failure',
                    'severity': 'high',
                    'status': 'blocks_graph_db_readiness_claims',
                    'basis': ['frontend/node_modules/better-sqlite3'],
                    'message': 'better-sqlite3 could not load in the current Node runtime; Graph DB/SQLite readiness evidence is conditional until rebuilt or reinstalled.',
                    'probe': load_probe,
                }
            )

    if proposal_result.get('moved_count', 0):
        issues.append(
            {
                'id': 'inactive_bootstrap_proposals_present',
                'severity': 'low',
                'status': 'review_before_apply',
                'basis': [proposal_result.get('inbox', '')],
                'message': 'Bootstrap proposals were moved to the inactive inbox and are not active project rules.',
                'moved_count': proposal_result.get('moved_count', 0),
            }
        )
    return issues


def write_architecture_hardening_artifacts(project: Path, proposal_result: dict) -> dict:
    zoo_dir = project / '.zoo-agent'
    bootstrap_dir = zoo_dir / 'bootstrap'
    zoo_dir.mkdir(parents=True, exist_ok=True)
    bootstrap_dir.mkdir(parents=True, exist_ok=True)

    generated_at = now()
    environment = probe_environment(project)
    issues = architecture_issues(project, proposal_result, environment)
    hard_issue_ids = {
        'profile_downgrade_proposal',
        'frontend_stack_lost_in_profile_proposal',
        'native_sqlite_abi_mismatch_or_load_failure',
    }
    status = (
        'blocked' if any(item['id'] in hard_issue_ids for item in issues) else ('needs_review' if issues else 'ready')
    )
    scan_policy = {
        'schema_version': '1.0',
        'generated_by': 'agent_bootstrap.py',
        'generated_at': generated_at,
        'policy': 'exclude_generated_and_runtime_paths_before_project_mapping',
        'exclude_patterns': GENERATED_PATH_PATTERNS,
        'notes': [
            'Generated/runtime paths must not be module owners, API entrypoints, or source roots.',
            'If source_roots are empty after excluding generated paths, keep the previous high-confidence profile and ask for planner review.',
        ],
    }
    agents_text = ''
    try:
        agents_text = (project / 'AGENTS.md').read_text(encoding='utf-8', errors='replace').lower()
    except OSError:
        agents_text = ''
    docs_agent_governance_role = (
        'historical branch and integration evidence'
        if 'docs/agent-governance' in agents_text and 'historical' in agents_text
        else 'decision, evidence, and planning records'
    )
    retired_framework_role = (
        'retired governance evidence; do not use for new work'
        if '.antigravity' in agents_text or 'retired' in agents_text
        else 'legacy governance evidence'
    )
    resolver = {
        'schema_version': '1.0',
        'generated_by': 'agent_bootstrap.py',
        'generated_at': generated_at,
        'precedence': [
            {
                'surface': '.zoo-agent/runs/<run-id>/*.json and .zoo-agent/current-run.json',
                'role': 'current Zoo runtime state',
                'write_policy': 'only dispatcher/bootstrap tools with explicit durable-state authority',
            },
            {
                'surface': '.zoo-agent/project-charter.json, project-profile.json, project-map.json, architecture-boundaries.json',
                'role': 'current project governance facts',
                'write_policy': 'read-only by workers; update only through bootstrap/profile refresh with proposal review',
            },
            {
                'surface': '.steward/**',
                'role': 'legacy/runtime evidence and existing Steward state',
                'write_policy': 'do not mutate during bootstrap unless a separate migration contract authorizes it',
            },
            {
                'surface': '.antigravity/**',
                'role': retired_framework_role,
                'write_policy': 'do not mutate, restore, or delete during bootstrap unless a separate migration/cleanup contract authorizes it',
            },
            {
                'surface': 'docs/agent-governance/** and plans/**',
                'role': docs_agent_governance_role,
                'write_policy': 'branch-owned evidence only',
            },
            {
                'surface': 'docs/archive/**',
                'role': 'historical/superseded evidence',
                'write_policy': 'no-delete archive policy; restore only through rollback contract',
            },
        ],
        'conflict_rule': 'If surfaces disagree, prefer current runtime facts for active execution, release docs for release boundary, and archived docs only as historical evidence.',
    }
    version_payload = {
        'schema_version': '1.0',
        'kit_version': KIT_VERSION,
        'installed_at': generated_at,
        'project': str(project),
        'artifacts': {
            'compatibility_check': '.zoo-agent/architecture-compatibility-report.json',
            'scan_policy': '.zoo-agent/bootstrap/scan-policy.json',
            'source_of_truth_resolver': '.zoo-agent/bootstrap/source-of-truth-resolver.json',
            'migration_report': '.zoo-agent/bootstrap/migration-report.md',
            'rollback_anchor': '.zoo-agent/bootstrap/rollback-anchor.md',
        },
    }
    compatibility = {
        'schema_version': '1.0',
        'generated_by': 'agent_bootstrap.py',
        'generated_at': generated_at,
        'kit_version': KIT_VERSION,
        'project': str(project),
        'status': status,
        'environment_fingerprint': environment,
        'profile_guard': {
            'active_profile': str(project / '.zoo-agent' / 'project-profile.json'),
            'proposal_paths': [str(path) for path in find_profile_proposals(project)],
        },
        'scan_policy_path': '.zoo-agent/bootstrap/scan-policy.json',
        'source_of_truth_resolver_path': '.zoo-agent/bootstrap/source-of-truth-resolver.json',
        'issues': issues,
    }

    (bootstrap_dir / 'scan-policy.json').write_text(
        json.dumps(scan_policy, ensure_ascii=False, indent=2), encoding='utf-8'
    )
    (bootstrap_dir / 'source-of-truth-resolver.json').write_text(
        json.dumps(resolver, ensure_ascii=False, indent=2), encoding='utf-8'
    )
    (zoo_dir / 'installed-kit-version.json').write_text(
        json.dumps(version_payload, ensure_ascii=False, indent=2), encoding='utf-8'
    )
    (zoo_dir / 'architecture-compatibility-report.json').write_text(
        json.dumps(compatibility, ensure_ascii=False, indent=2), encoding='utf-8'
    )

    md_lines = [
        '# Architecture Compatibility Report',
        '',
        f'- status: {status}',
        f'- kit_version: {KIT_VERSION}',
        f'- generated_at: {generated_at}',
        f'- project: {project}',
        '',
        '## Environment Fingerprint',
        '',
        f'- python: {environment["python"]["version"]} ({environment["python"]["executable"]})',
        f'- node: {(environment.get("node", {}).get("version_probe") or {}).get("stdout", "unknown")}',
        f'- node_abi: {(environment.get("node", {}).get("abi_probe") or {}).get("stdout", "unknown")}',
        f'- npm: {(environment.get("npm", {}).get("version_probe") or {}).get("stdout", "unknown")}',
        '',
        '## Issues',
        '',
    ]
    if not issues:
        md_lines.append('- none')
    else:
        for issue in issues:
            md_lines.extend(
                [
                    f'### {issue["id"]}',
                    '',
                    f'- severity: {issue["severity"]}',
                    f'- status: {issue["status"]}',
                    f'- message: {issue["message"]}',
                    f'- basis: {", ".join(issue.get("basis", []))}',
                    '',
                ]
            )
    md_lines.extend(
        [
            '## Guardrails Written',
            '',
            '- `.zoo-agent/bootstrap/scan-policy.json`',
            '- `.zoo-agent/bootstrap/source-of-truth-resolver.json`',
            '- `.zoo-agent/installed-kit-version.json`',
            '',
        ]
    )
    (zoo_dir / 'architecture-compatibility-report.md').write_text('\n'.join(md_lines), encoding='utf-8')

    migration_lines = [
        '# Bootstrap Migration Report',
        '',
        f'- kit_version: {KIT_VERSION}',
        f'- generated_at: {generated_at}',
        f'- project: {project}',
        '',
        '## Migration Behavior',
        '',
        '- Existing project facts remain active unless a proposal is reviewed and applied.',
        '- Lower-information project-profile proposals are blocked by the compatibility report.',
        '- Generated/runtime paths are recorded in scan-policy.json for future project mapping.',
        '- Source-of-truth precedence is recorded before any durable state reconciliation.',
        '- Native dependency readiness is conditional on the captured environment fingerprint.',
        '',
        '## Proposal Inbox',
        '',
        f'- inbox: {proposal_result.get("inbox", "")}',
        f'- moved_count: {proposal_result.get("moved_count", 0)}',
        '',
    ]
    (bootstrap_dir / 'migration-report.md').write_text('\n'.join(migration_lines), encoding='utf-8')

    rollback_lines = [
        '# Bootstrap Rollback Anchor',
        '',
        f'- kit_version: {KIT_VERSION}',
        f'- generated_at: {generated_at}',
        f'- project: {project}',
        '',
        '## Rollback Scope',
        '',
        'To roll back this hardening layer, remove only these governance artifacts after reviewer approval:',
        '',
        '- `.zoo-agent/architecture-compatibility-report.json`',
        '- `.zoo-agent/architecture-compatibility-report.md`',
        '- `.zoo-agent/installed-kit-version.json`',
        '- `.zoo-agent/bootstrap/scan-policy.json`',
        '- `.zoo-agent/bootstrap/source-of-truth-resolver.json`',
        '- `.zoo-agent/bootstrap/migration-report.md`',
        '- `.zoo-agent/bootstrap/rollback-anchor.md`',
        '',
        'Do not delete project source, runtime evidence, archived docs, `.steward`, or proposal inbox files as part of this rollback.',
        '',
    ]
    (bootstrap_dir / 'rollback-anchor.md').write_text('\n'.join(rollback_lines), encoding='utf-8')
    return compatibility


def proposal_relative_path(project: Path, source: Path) -> Path:
    rel = source.relative_to(project)
    parts = list(rel.parts)
    if parts[0] == '.roo':
        parts[0] = 'roo'
    elif parts[0] == '.zoo-agent':
        parts[0] = 'zoo-agent'
    else:
        parts.insert(0, 'root')
    name = parts[-1]
    if name.endswith('.new'):
        name = name[:-4]
    if name == '.gitignore.agent.patch':
        name = 'gitignore.agent.patch'
    parts[-1] = name
    return Path(*parts)


def unique_destination(path: Path, timestamp: str) -> Path:
    if not path.exists():
        return path
    stem = path.stem
    suffix = path.suffix
    candidate = path.with_name(f'{stem}.{timestamp}{suffix}')
    counter = 2
    while candidate.exists():
        candidate = path.with_name(f'{stem}.{timestamp}.{counter}{suffix}')
        counter += 1
    return candidate


def relocate_proposals(project: Path) -> dict:
    inbox = project / '.zoo-agent' / 'bootstrap' / 'proposals'
    timestamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    candidates: list[Path] = []
    for path in [
        project / 'AGENTS.md.new',
        project / 'README.md.new',
        project / 'TASKS.md.new',
        project / '.gitignore.agent.patch',
    ]:
        if path.exists() and path.is_file():
            candidates.append(path)
    for root in [project / '.roo', project / '.zoo-agent']:
        if root.exists():
            candidates.extend(path for path in root.rglob('*.new') if path.is_file())

    actions: list[dict] = []
    seen: set[Path] = set()
    for source in candidates:
        source = source.resolve()
        if source in seen or not source.exists():
            continue
        seen.add(source)
        try:
            source.relative_to(inbox.resolve())
            continue
        except ValueError:
            pass
        target = inbox / proposal_relative_path(project, source)
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists() and target.read_bytes() == source.read_bytes():
            source.unlink()
            actions.append({'action': 'dedupe_existing', 'source': str(source), 'target': str(target)})
            continue
        final_target = unique_destination(target, timestamp)
        shutil.move(str(source), str(final_target))
        actions.append({'action': 'move', 'source': str(source), 'target': str(final_target)})
    return {
        'inbox': str(inbox),
        'moved_count': sum(1 for item in actions if item['action'] == 'move'),
        'actions': actions,
    }


def write_report(project: Path, payload: dict) -> None:
    out_dir = project / '.zoo-agent'
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / 'agent-bootstrap-report.json'
    md_path = out_dir / 'agent-bootstrap-report.md'
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')

    lines = [
        '# Agent Bootstrap Report',
        '',
        f'- status: {payload["status"]}',
        f'- project: {payload["project"]}',
        f'- generated_at: {payload["generated_at"]}',
        '',
        '## Steps',
        '',
    ]
    for step in payload['steps']:
        lines.extend(
            [
                f'### {step["name"]}',
                '',
                f'- status: {step["status"]}',
                f'- returncode: {step.get("returncode", "n/a")}',
                '',
            ]
        )
        output = step.get('stdout') or step.get('message') or ''
        if output:
            lines.extend(['```text', output, '```', ''])
    compatibility = payload.get('architecture_compatibility')
    if compatibility:
        lines.extend(
            [
                '## Architecture Compatibility',
                '',
                f'- status: {compatibility.get("status", "unknown")}',
                '- report: `.zoo-agent/architecture-compatibility-report.md`',
                f'- issue_count: {len(compatibility.get("issues", []))}',
                '',
            ]
        )
    lines.extend(
        [
            '## Next',
            '',
            '- Reload the project so Roo/Zoo re-reads local command and rule files.',
            '- Run `agent run <input>` for normal CLI runtime work.',
            '- Review `.zoo-agent/architecture-compatibility-report.md` before trusting refreshed profile, map, Graph DB, or runtime readiness claims.',
            '- Review proposal files before applying them; .new files are not active rules.',
            '',
        ]
    )
    md_path.write_text('\n'.join(lines), encoding='utf-8')


def main() -> int:
    parser = argparse.ArgumentParser(description='One-step Zoo agent bootstrap for new and existing projects.')
    parser.add_argument('--project', default='.')
    parser.add_argument('--mode', choices=['auto', 'existing', 'new'], default='auto')
    parser.add_argument('--goal', default='')
    parser.add_argument('--stack', default='')
    parser.add_argument('--codex-home', default='')
    parser.add_argument('--force-new-project', action='store_true')
    parser.add_argument('--no-git-init', action='store_true')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()

    project = Path(args.project).resolve()
    bootstrap_script = first_existing(
        [
            ROOT / 'scripts' / 'bootstrap_project.py',
            GLOBAL_KIT / 'scripts' / 'bootstrap_project.py',
            PUBLIC_ZOO_CODE / 'scripts' / 'bootstrap_project.py',
        ]
    )
    sync_script = first_existing(
        [
            ROOT / 'scripts' / 'sync_zoo_entrypoints.py',
            GLOBAL_KIT / 'scripts' / 'sync_zoo_entrypoints.py',
        ]
    )

    steps: list[dict] = []
    payload = {
        'status': 'dry_run' if args.dry_run else 'running',
        'project': str(project),
        'generated_at': now(),
        'kit_version': KIT_VERSION,
        'bootstrap_script': str(bootstrap_script) if bootstrap_script else '',
        'sync_script': str(sync_script) if sync_script else '',
        'steps': steps,
    }

    if not bootstrap_script:
        steps.append(
            {'name': 'project_context_bootstrap', 'status': 'blocked', 'message': 'bootstrap_project.py not found'}
        )
        payload['status'] = 'blocked'
        if not args.dry_run:
            write_report(project, payload)
        print_json(payload)
        return 2
    if not sync_script:
        steps.append(
            {'name': 'entrypoint_bridge_repair', 'status': 'blocked', 'message': 'sync_zoo_entrypoints.py not found'}
        )
        payload['status'] = 'blocked'
        if not args.dry_run:
            write_report(project, payload)
        print_json(payload)
        return 2

    bootstrap_cmd = [
        sys.executable,
        str(bootstrap_script),
        '--project',
        str(project),
        '--mode',
        args.mode,
    ]
    if args.goal:
        bootstrap_cmd.extend(['--goal', args.goal])
    if args.stack:
        bootstrap_cmd.extend(['--stack', args.stack])
    if args.codex_home:
        bootstrap_cmd.extend(['--codex-home', args.codex_home])
    if args.force_new_project:
        bootstrap_cmd.append('--force-new-project')
    if args.no_git_init:
        bootstrap_cmd.append('--no-git-init')
    if not args.dry_run:
        bootstrap_cmd.append('--apply')

    repair_cmd = [
        sys.executable,
        str(sync_script),
        '--project-root',
        str(project),
        '--project-only',
        '--backup-root',
        str(project / '.roo-backups' / 'ai-native-bootstrap'),
    ]
    if args.dry_run:
        steps.append({'name': 'project_context_bootstrap', 'status': 'would_run', 'command': bootstrap_cmd})
        steps.append({'name': 'entrypoint_bridge_repair', 'status': 'would_run', 'command': repair_cmd})
        payload['status'] = 'dry_run'
        print_json(payload)
        return 0

    if not project.exists():
        project.mkdir(parents=True)

    bootstrap_result = run_command(bootstrap_cmd, project)
    steps.append(
        {
            'name': 'project_context_bootstrap',
            'status': 'ok' if bootstrap_result['returncode'] == 0 else 'failed',
            **bootstrap_result,
        }
    )
    if bootstrap_result['returncode'] != 0:
        payload['status'] = 'failed'
        write_report(project, payload)
        print_json(payload)
        return bootstrap_result['returncode']

    proposal_result = relocate_proposals(project)
    steps.append(
        {
            'name': 'proposal_inbox',
            'status': 'ok',
            'returncode': 0,
            'stdout': json.dumps(proposal_result, ensure_ascii=False, indent=2),
        }
    )

    repair_result = run_command(repair_cmd, project)
    steps.append(
        {
            'name': 'entrypoint_bridge_repair',
            'status': 'ok' if repair_result['returncode'] == 0 else 'failed',
            **repair_result,
        }
    )
    compatibility_status = ''
    if repair_result['returncode'] == 0:
        compatibility = write_architecture_hardening_artifacts(project, proposal_result)
        compatibility_status = compatibility['status']
        payload['architecture_compatibility'] = {
            'status': compatibility['status'],
            'issues': compatibility['issues'],
        }
        steps.append(
            {
                'name': 'architecture_feedback_hardening',
                'status': compatibility['status'],
                'returncode': 0 if compatibility['status'] != 'blocked' else 1,
                'stdout': json.dumps(
                    {
                        'report': str(project / '.zoo-agent' / 'architecture-compatibility-report.md'),
                        'status': compatibility['status'],
                        'issue_count': len(compatibility['issues']),
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
            }
        )
    if repair_result['returncode'] != 0:
        payload['status'] = 'failed'
    elif compatibility_status == 'blocked':
        payload['status'] = 'ready_with_architecture_blocks'
    elif compatibility_status == 'needs_review':
        payload['status'] = 'ready_needs_architecture_review'
    else:
        payload['status'] = 'ready'
    write_report(project, payload)
    print_json(payload)
    return repair_result['returncode']


if __name__ == '__main__':
    raise SystemExit(main())
