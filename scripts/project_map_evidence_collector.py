#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from project_map_schema import SENSITIVE_PATTERNS, evidence_item, map_dir
from runtime_common import project_root, utc_now, write_json
from seed_prompt_discovery import discover_seed_prompt, seed_evidence_item

SAFE_DOC_NAMES = ['README.md', 'QUICKSTART.md', 'INSTALL.md', 'EXAMPLES.md', 'CONTRIBUTING.md']
COMMON_DIRS = ['src', 'app', 'lib', 'scripts', 'tests', 'test', 'docs', 'examples', 'frontend', 'backend', 'packages']
MANIFESTS = ['package.json', 'pyproject.toml', 'requirements.txt', 'go.mod', 'Cargo.toml', 'pom.xml']


def _rel(project: Path, path: Path) -> str:
    return path.relative_to(project).as_posix()


def is_sensitive_path(rel_path: str) -> bool:
    normalized = rel_path.replace('\\', '/').lower()
    if normalized in {'.env', '.env.local'} or normalized.startswith('.env.'):
        return True
    blocked_prefixes = ['secrets/', 'credentials/', '.codex/']
    if any(normalized.startswith(prefix) for prefix in blocked_prefixes):
        return True
    return normalized.endswith(('.pem', '.key'))


def safe_read_excerpt(path: Path, *, limit: int = 240) -> str:
    try:
        text = path.read_text(encoding='utf-8', errors='replace')
    except Exception:
        return ''
    cleaned = ' '.join(line.strip() for line in text.splitlines()[:8] if line.strip())
    return cleaned[:limit]


def collect_evidence(project: Path, *, main_goal: str = '') -> dict[str, Any]:
    evidence: list[dict[str, Any]] = []
    skipped_sensitive: list[str] = []
    seed_report = discover_seed_prompt(project, goal=main_goal)
    selected_seed = seed_report.get('selected') if isinstance(seed_report.get('selected'), dict) else None
    if selected_seed:
        evidence.append(seed_evidence_item(selected_seed))
    for name in SAFE_DOC_NAMES:
        path = project / name
        if path.exists() and path.is_file():
            evidence.append(
                evidence_item(
                    'documentation_surface', name, safe_read_excerpt(path) or f'{name} exists.', confidence=0.8
                )
            )
    docs_dir = project / 'docs'
    if docs_dir.exists() and docs_dir.is_dir():
        for path in sorted(docs_dir.glob('*.md'))[:8]:
            rel = _rel(project, path)
            if not is_sensitive_path(rel):
                evidence.append(
                    evidence_item(
                        'documentation_surface', rel, safe_read_excerpt(path) or f'{rel} exists.', confidence=0.72
                    )
                )

    for name in COMMON_DIRS:
        path = project / name
        if path.exists() and path.is_dir():
            sample_files = []
            for child in sorted(path.rglob('*')):
                if len(sample_files) >= 12:
                    break
                if child.is_file():
                    rel = _rel(project, child)
                    if is_sensitive_path(rel):
                        skipped_sensitive.append(rel)
                        continue
                    sample_files.append(rel)
            evidence.append(
                evidence_item(
                    'directory', name, f'{name}/ exists with {len(sample_files)} sampled files.', confidence=0.65
                )
            )

    for name in MANIFESTS:
        path = project / name
        if path.exists() and path.is_file():
            evidence.append(evidence_item('manifest', name, f'{name} exists.', confidence=0.75))

    for child in sorted(project.iterdir()):
        rel = child.name
        if is_sensitive_path(rel):
            skipped_sensitive.append(rel)

    return {
        'schema_version': '1.0',
        'generated_by': 'project_map_evidence_collector.py',
        'generated_at': utc_now(),
        'workspace': str(project),
        'evidence': evidence,
        'seed_prompt': seed_report,
        'sensitive_content_read': False,
        'sensitive_patterns': SENSITIVE_PATTERNS,
        'skipped_sensitive_paths': sorted(set(skipped_sensitive)),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description='Collect safe, evidence-backed project map inputs.')
    parser.add_argument('--workspace', default='.')
    parser.add_argument('--output', default='')
    args = parser.parse_args()
    project = project_root(args.workspace)
    payload = collect_evidence(project)
    output = Path(args.output).resolve() if args.output else map_dir(project) / 'map_evidence.json'
    write_json(output, payload)
    print(json.dumps({'status': 'ok', 'map_evidence': str(output)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
