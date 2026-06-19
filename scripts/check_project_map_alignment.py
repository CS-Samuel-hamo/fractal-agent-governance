#!/usr/bin/env python3
from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from runtime_common import project_root, utc_now, write_json  # noqa: E402


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
SOURCE_ROOT_CANDIDATES = ['src', 'app', 'lib', 'packages', 'services', 'frontend/src', 'scripts']
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


def normalize(path: str) -> str:
    return path.replace('\\', '/').strip('/')


def matches_any(relative_path: str, patterns: list[str]) -> bool:
    value = normalize(relative_path)
    for pattern in patterns:
        pat = normalize(pattern)
        if fnmatch.fnmatch(value, pat) or fnmatch.fnmatch('/' + value, pat):
            return True
        if pat.endswith('/**') and (value == pat[:-3] or value.startswith(pat[:-2])):
            return True
    return False


def existing_paths(project: Path, candidates: list[str]) -> list[str]:
    return [item for item in candidates if (project / item).exists()]


def source_roots(project: Path) -> list[str]:
    profile = load_json(project / '.zoo-agent' / 'project-profile.json')
    roots = [normalize(str(item)) for item in profile.get('source_roots') or [] if str(item)]
    roots = [item for item in roots if (project / item).exists() and not matches_any(item, GENERATED_PATH_PATTERNS)]
    if roots:
        return sorted(set(roots))
    return existing_paths(project, SOURCE_ROOT_CANDIDATES)


def map_owned_paths(payload: dict[str, Any]) -> list[str]:
    owned: list[str] = []
    keys = [
        'source_roots',
        'test_roots',
        'api_entrypoints',
        'module_roots',
        'modules',
        'owners',
        'entrypoints',
    ]
    for key in keys:
        value = payload.get(key)
        if isinstance(value, list):
            for item in value:
                if isinstance(item, str):
                    owned.append(normalize(item))
                elif isinstance(item, dict):
                    for nested_key in ['path', 'root', 'entrypoint', 'source_root']:
                        nested = item.get(nested_key)
                        if isinstance(nested, str):
                            owned.append(normalize(nested))
        elif isinstance(value, dict):
            for nested in value.values():
                if isinstance(nested, str):
                    owned.append(normalize(nested))
                elif isinstance(nested, list):
                    owned.extend(normalize(str(item)) for item in nested if str(item))
    return sorted(set(item for item in owned if item))


def file_inventory(project: Path, roots: list[str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for root in roots:
        base = project / root
        if not base.exists():
            continue
        if base.is_file():
            candidates = [base]
        else:
            candidates = [path for path in base.rglob('*') if path.is_file()]
        for path in candidates:
            rel = normalize(str(path.relative_to(project)))
            if matches_any(rel, GENERATED_PATH_PATTERNS):
                continue
            try:
                stat = path.stat()
            except OSError:
                continue
            rows.append({'path': rel, 'size': stat.st_size, 'mtime_ns': stat.st_mtime_ns})
    return sorted(rows, key=lambda item: item['path'])


def inventory_digest(rows: list[dict[str, Any]]) -> str:
    h = hashlib.sha256()
    for row in rows:
        h.update(f"{row['path']}\0{row['size']}\0{row['mtime_ns']}\n".encode('utf-8'))
    return h.hexdigest()


def build_project_map(project: Path) -> tuple[dict[str, Any], str]:
    roots = source_roots(project)
    tests = existing_paths(project, TEST_ROOT_CANDIDATES)
    manifests = existing_paths(project, MANIFEST_CANDIDATES)
    inventory = file_inventory(project, roots + tests + manifests)
    digest = inventory_digest(inventory)
    payload = {
        'schema_version': '1.0',
        'generated_by': 'check_project_map_alignment.py',
        'generated_at': utc_now(),
        'workspace': str(project),
        'source_roots': roots,
        'test_roots': tests,
        'manifests': manifests,
        'exclude_patterns': GENERATED_PATH_PATTERNS,
        'filesystem_digest': digest,
        'inventory_file_count': len(inventory),
        'sample_files': [item['path'] for item in inventory[:100]],
    }
    lines = [
        '# Project Map',
        '',
        f"- generated_at: {payload['generated_at']}",
        f"- filesystem_digest: {digest}",
        f"- inventory_file_count: {len(inventory)}",
        '',
        '## Source Roots',
        '',
    ]
    lines.extend([f'- {item}' for item in roots] or ['- none detected'])
    lines.extend(['', '## Test Roots', ''])
    lines.extend([f'- {item}' for item in tests] or ['- none detected'])
    lines.extend(['', '## Manifests', ''])
    lines.extend([f'- {item}' for item in manifests] or ['- none detected'])
    lines.extend(['', '## Sample Files', ''])
    lines.extend([f"- {item['path']}" for item in inventory[:100]] or ['- none detected'])
    lines.append('')
    return payload, '\n'.join(lines)


def check_alignment(project: Path) -> dict[str, Any]:
    active_json = project / '.zoo-agent' / 'project-map.json'
    active_md = project / '.zoo-agent' / 'project-map.md'
    active = load_json(active_json)
    current_map, _ = build_project_map(project)
    blockers: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []

    if not active:
        blockers.append({'id': 'project_map_missing', 'message': 'Missing active .zoo-agent/project-map.json.'})
    else:
        owned = map_owned_paths(active)
        contaminated = [item for item in owned if matches_any(item, GENERATED_PATH_PATTERNS)]
        if contaminated:
            blockers.append(
                {
                    'id': 'project_map_generated_path_contamination',
                    'message': 'Project map contains generated/runtime paths.',
                    'paths': contaminated[:50],
                }
            )

        missing_roots = [item for item in active.get('source_roots') or [] if not (project / normalize(str(item))).exists()]
        if missing_roots:
            blockers.append({'id': 'project_map_missing_source_roots', 'message': 'Project map source roots do not exist.', 'paths': missing_roots})

        active_digest = str(active.get('filesystem_digest') or '')
        current_digest = current_map.get('filesystem_digest')
        if not active_digest:
            warnings.append({'id': 'project_map_digest_missing', 'message': 'Active project map has no filesystem_digest; refresh is recommended.'})
        elif active_digest != current_digest:
            warnings.append(
                {
                    'id': 'project_map_stale',
                    'message': 'Active project map digest does not match current filesystem inventory.',
                    'active_digest': active_digest,
                    'current_digest': current_digest,
                }
            )

    status = 'blocked' if blockers else ('needs_refresh' if warnings else 'pass')
    return {
        'schema_version': '1.0',
        'generated_by': 'check_project_map_alignment.py',
        'generated_at': utc_now(),
        'workspace': str(project),
        'status': status,
        'active_project_map': str(active_json),
        'current_digest': current_map.get('filesystem_digest', ''),
        'active_digest': str(active.get('filesystem_digest') or ''),
        'blockers': blockers,
        'warnings': warnings,
        'current_project_map': current_map,
    }


def promote(project: Path, *, dry_run: bool) -> dict[str, Any]:
    proposal_json = project / '.zoo-agent' / 'project-map.json.new'
    proposal_md = project / '.zoo-agent' / 'project-map.md.new'
    active_json = project / '.zoo-agent' / 'project-map.json'
    active_md = project / '.zoo-agent' / 'project-map.md'
    proposal = load_json(proposal_json)
    blockers: list[dict[str, Any]] = []
    if not proposal:
        blockers.append({'id': 'missing_project_map_proposal', 'message': 'Missing .zoo-agent/project-map.json.new.'})
    contaminated = [item for item in map_owned_paths(proposal) if matches_any(item, GENERATED_PATH_PATTERNS)]
    if contaminated:
        blockers.append({'id': 'proposal_generated_path_contamination', 'message': 'Project map proposal contains generated/runtime paths.', 'paths': contaminated})

    actions: list[dict[str, str]] = []
    if not blockers:
        actions.append({'action': 'promote', 'from': str(proposal_json), 'to': str(active_json)})
        if proposal_md.exists():
            actions.append({'action': 'promote', 'from': str(proposal_md), 'to': str(active_md)})
        if not dry_run:
            write_json(active_json, proposal)
            if proposal_md.exists():
                active_md.write_text(proposal_md.read_text(encoding='utf-8'), encoding='utf-8')
            proposal_json.unlink(missing_ok=True)
            proposal_md.unlink(missing_ok=True)

    report = check_alignment(project) if not blockers and not dry_run else {
        'schema_version': '1.0',
        'generated_by': 'check_project_map_alignment.py',
        'generated_at': utc_now(),
        'workspace': str(project),
        'status': 'blocked' if blockers else 'dry_run',
        'blockers': blockers,
        'warnings': [],
    }
    report['promotion'] = {'dry_run': dry_run, 'actions': actions, 'blockers': blockers}
    if not dry_run:
        write_json(project / '.zoo-agent' / 'project-map-alignment.json', report)
    return report


def refresh(project: Path, *, promote_if_missing: bool, dry_run: bool) -> dict[str, Any]:
    payload, markdown = build_project_map(project)
    active_missing = not (project / '.zoo-agent' / 'project-map.json').exists()
    if active_missing and promote_if_missing:
        json_path = project / '.zoo-agent' / 'project-map.json'
        md_path = project / '.zoo-agent' / 'project-map.md'
        action = 'write_active_missing_map'
    else:
        json_path = project / '.zoo-agent' / 'project-map.json.new'
        md_path = project / '.zoo-agent' / 'project-map.md.new'
        action = 'write_project_map_proposal'

    report = {
        'schema_version': '1.0',
        'generated_by': 'check_project_map_alignment.py',
        'generated_at': utc_now(),
        'workspace': str(project),
        'status': 'dry_run' if dry_run else 'refreshed',
        'action': action,
        'project_map_json': str(json_path),
        'project_map_md': str(md_path),
        'project_map': payload,
    }
    if not dry_run:
        write_json(json_path, payload)
        md_path.parent.mkdir(parents=True, exist_ok=True)
        md_path.write_text(markdown, encoding='utf-8')
        alignment = check_alignment(project)
        alignment['refresh'] = report
        write_json(project / '.zoo-agent' / 'project-map-alignment.json', alignment)
        return alignment
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description='Check, refresh, or promote project-map alignment.')
    parser.add_argument('--workspace', default='.')
    parser.add_argument('--refresh', action='store_true')
    parser.add_argument('--promote', action='store_true')
    parser.add_argument('--promote-if-missing', action='store_true')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()

    if args.refresh and args.promote:
        raise SystemExit('Choose only one of --refresh or --promote.')

    project = project_root(args.workspace)
    if args.promote:
        report = promote(project, dry_run=args.dry_run)
    elif args.refresh:
        report = refresh(project, promote_if_missing=args.promote_if_missing, dry_run=args.dry_run)
    else:
        report = check_alignment(project)
        if not args.dry_run:
            write_json(project / '.zoo-agent' / 'project-map-alignment.json', report)

    print(json.dumps(report, ensure_ascii=False, indent=2))
    status = str(report.get('status') or '')
    if status == 'pass' or status in {'refreshed', 'dry_run'}:
        return 0
    if status == 'needs_refresh':
        return 10
    return 20


if __name__ == '__main__':
    raise SystemExit(main())
