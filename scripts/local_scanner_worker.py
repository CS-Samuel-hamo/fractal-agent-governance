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
from worker_adapter_contract import worker_contract
from worker_interface import worker_result

SKIP_DIRS = {'.git', '.zoo-agent', '.tmp', '__pycache__', '.pytest_cache', 'node_modules', '.venv', 'venv'}
SECRET_MARKERS = (
    '.env',
    'secret',
    'secrets',
    'credential',
    'credentials',
    'token',
    'apikey',
    'api_key',
    '.pem',
    '.key',
)
MANIFEST_NAMES = {'package.json', 'pyproject.toml', 'requirements.txt', 'setup.py', 'Cargo.toml', 'go.mod', 'pom.xml'}
DOC_SUFFIXES = {'.md', '.mdx', '.rst'}
TEST_MARKERS = ('test', 'tests', '_test.', '.test.', '.spec.')
SCRIPT_SUFFIXES = {'.py', '.ps1', '.sh', '.js', '.ts'}
CODE_SUFFIXES = {'.py', '.js', '.ts', '.tsx', '.jsx', '.go', '.rs', '.java', '.cs'}


def local_scanner_contract(project: Path | None = None) -> dict[str, Any]:
    payload = worker_contract(
        'local_scanner_worker',
        supports_preview=True,
        supports_actual_execution=False,
        supports_repo_scan=True,
        requires_external_binary=False,
        requires_network=False,
        reads_secrets=False,
        modifies_files=False,
        can_run_commands=False,
        safe_default_mode='preview',
    )
    if project:
        write_json(project / '.zoo-agent' / 'workers' / 'local_scanner_contract.json', payload)
    return payload


def is_secret_like(path: Path) -> bool:
    surface = '/'.join(path.parts).lower()
    return any(marker in surface for marker in SECRET_MARKERS)


def rel(project: Path, path: Path) -> str:
    return path.relative_to(project).as_posix()


def detect_project_type(manifests: list[str], files: list[str]) -> str:
    if 'package.json' in manifests:
        return 'javascript'
    if any(item in manifests for item in ['pyproject.toml', 'requirements.txt', 'setup.py']):
        return 'python'
    if 'Cargo.toml' in manifests:
        return 'rust'
    if 'go.mod' in manifests:
        return 'go'
    if any(path.endswith('.md') for path in files):
        return 'docs'
    return 'unknown'


def scan_repo(project: Path, *, max_files: int = 2000) -> dict[str, Any]:
    files_scanned = 0
    skipped: list[dict[str, str]] = []
    seen_files: list[str] = []
    manifests: list[str] = []
    docs: list[str] = []
    tests: list[str] = []
    scripts: list[str] = []
    module_counts: dict[str, int] = {}

    for path in sorted(project.rglob('*')):
        if files_scanned >= max_files:
            skipped.append({'path': '<limit>', 'reason': 'scan limit reached'})
            break
        if any(part in SKIP_DIRS for part in path.relative_to(project).parts):
            continue
        if path.is_dir():
            continue
        relative = rel(project, path)
        if is_secret_like(path):
            skipped.append({'path': relative, 'reason': 'restricted name skipped; content not read'})
            continue
        seen_files.append(relative)
        files_scanned += 1
        if path.name in MANIFEST_NAMES:
            manifests.append(relative)
        if path.suffix in DOC_SUFFIXES or relative.lower().startswith('docs/'):
            docs.append(relative)
        if any(marker in relative.lower() for marker in TEST_MARKERS):
            tests.append(relative)
        if path.suffix in SCRIPT_SUFFIXES and (relative.startswith('scripts/') or path.suffix in {'.ps1', '.sh'}):
            scripts.append(relative)
        if path.suffix in CODE_SUFFIXES:
            module = relative.split('/')[0] if '/' in relative else path.stem
            module_counts[module] = module_counts.get(module, 0) + 1

    candidate_modules = [
        {'name': name, 'file_count': count, 'evidence': [f'{name}/']}
        for name, count in sorted(module_counts.items(), key=lambda item: (-item[1], item[0]))[:12]
    ]
    capabilities = []
    if docs:
        capabilities.append({'name': 'Documentation', 'status': 'partial', 'evidence': docs[:5]})
    if tests:
        capabilities.append({'name': 'Tests', 'status': 'partial', 'evidence': tests[:5]})
    if manifests:
        capabilities.append({'name': 'Project manifest', 'status': 'implemented', 'evidence': manifests[:5]})

    risks = []
    if skipped:
        risks.append(
            {
                'description': 'Restricted files were detected and skipped.',
                'severity': 'medium',
                'affected_files': [item['path'] for item in skipped[:8]],
                'evidence': ['metadata only'],
            }
        )

    payload = {
        'schema_version': '1.0',
        'generated_by': 'local_scanner_worker.py',
        'generated_at': utc_now(),
        'project_root': '<PROJECT_ROOT>',
        'files_scanned': files_scanned,
        'files_skipped': skipped,
        'detected_project_type': detect_project_type([Path(item).name for item in manifests], seen_files),
        'detected_manifests': manifests[:30],
        'detected_docs': docs[:50],
        'detected_tests': tests[:50],
        'detected_scripts': scripts[:50],
        'candidate_modules': candidate_modules,
        'map_support': {
            'suggested_modules': candidate_modules,
            'suggested_capabilities': capabilities,
            'suggested_risks': risks,
            'evidence': [{'path': item, 'kind': 'file_metadata'} for item in (manifests[:10] + docs[:10] + tests[:10])],
        },
    }
    write_json(project / '.zoo-agent' / 'workers' / 'local_scanner_report.json', payload)
    return payload


def execute(project: Path, task: dict[str, Any] | None = None, context: dict[str, Any] | None = None) -> dict[str, Any]:
    _ = task, context
    report = scan_repo(project)
    result = worker_result(
        worker_name='local_scanner_worker',
        worker_type='analysis',
        provider='local_scanner',
        status='success',
        changed_files=[],
        summary=f'Scanned {report.get("files_scanned", 0)} files for project map support.',
        confidence=0.95,
        raw_log_path='.zoo-agent/workers/local_scanner_report.json',
        safe_for_user_output=True,
    )
    write_json(project / '.zoo-agent' / 'workers' / 'worker_execution_result.json', result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description='Run a safe local repository metadata scan.')
    parser.add_argument('--workspace', default='.')
    args = parser.parse_args()
    project = project_root(args.workspace)
    payload = scan_repo(project)
    print(
        json.dumps(
            {
                'status': 'ok',
                'report': '.zoo-agent/workers/local_scanner_report.json',
                'files_scanned': payload.get('files_scanned', 0),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
