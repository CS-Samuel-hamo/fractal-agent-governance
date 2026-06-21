#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from cross_project_privacy_filter import filter_artifact, write_privacy_report  # noqa: E402
from cross_project_store import append_project_index, initialize_store, store_dir  # noqa: E402
from project_fingerprint import build_fingerprint  # noqa: E402
from runtime_common import project_root, utc_now, write_json  # noqa: E402


ARTIFACTS = [
    '.zoo-agent/map/project_map.json',
    '.zoo-agent/map/map_evidence.json',
    '.zoo-agent/session/session_history.json',
    '.zoo-agent/session/session_digest.md',
    '.zoo-agent/session_dogfood/session_dogfood_trace.json',
    '.zoo-agent/worker_dogfood/worker_router_dogfood_trace.json',
    '.zoo-agent/real_worker_dogfood/real_worker_dogfood_trace.json',
    '.zoo-agent/workers/local_scanner_report.json',
]


def safe_project_id(fingerprint_hash: str, source_label: str) -> str:
    return 'project-' + hashlib.sha256(f'{fingerprint_hash}:{source_label}'.encode('utf-8')).hexdigest()[:12]


def read_artifact(path: Path) -> Any:
    if path.suffix.lower() == '.md':
        return {'kind': 'markdown_summary', 'content': path.read_text(encoding='utf-8', errors='replace')[:4000]}
    try:
        return json.loads(path.read_text(encoding='utf-8-sig'))
    except Exception:
        return {}


def import_project_artifacts(target_project: Path, source_project: Path, *, source_kind: str = 'local_artifact') -> dict[str, Any]:
    initialize_store(target_project)
    imported: list[dict[str, Any]] = []
    skipped: list[dict[str, str]] = []
    sanitized_payloads: dict[str, Any] = {}
    for relative in ARTIFACTS:
        path = source_project / relative
        if not path.exists():
            skipped.append({'artifact': relative, 'reason': 'missing'})
            continue
        report = filter_artifact(path, read_artifact(path))
        write_privacy_report(target_project, report)
        if not report.get('safe_to_store'):
            skipped.append({'artifact': relative, 'reason': report.get('rejection_reason', 'privacy_rejected')})
            continue
        key = relative.replace('.zoo-agent/', '').replace('/', '__')
        sanitized_payloads[key] = report.get('sanitized')
        imported.append({'artifact': relative, 'privacy_status': report.get('privacy_status'), 'redactions': report.get('redactions') or []})

    fingerprint = build_fingerprint(source_project)
    project_id = safe_project_id(fingerprint.get('fingerprint_hash', ''), source_project.name)
    bundle = {
        'schema_version': '1.0',
        'generated_by': 'learning_artifact_importer.py',
        'project_id': project_id,
        'source': source_kind,
        'imported_at': utc_now(),
        'fingerprint': fingerprint,
        'artifacts': sanitized_payloads,
        'imported': imported,
        'skipped': skipped,
    }
    bundle_path = store_dir(target_project) / 'imported_projects' / f'{project_id}.json'
    write_json(bundle_path, bundle)
    append_project_index(
        target_project,
        {
            'project_id': project_id,
            'project_type': fingerprint.get('project_type', 'unknown'),
            'fingerprint': fingerprint.get('fingerprint_hash', ''),
            'source': source_kind,
            'imported_at': bundle['imported_at'],
            'privacy_status': 'sanitized' if any(item.get('redactions') for item in imported) else 'sanitized',
            'evidence_count': sum(1 for item in imported if item.get('artifact')),
        },
    )
    report = {'schema_version': '1.0', 'generated_by': 'learning_artifact_importer.py', 'project_id': project_id, 'imported': imported, 'skipped': skipped, 'bundle': f'.zoo-agent/learning/cross_project/imported_projects/{project_id}.json'}
    write_json(store_dir(target_project) / 'import_report.json', report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description='Import sanitized local artifacts into cross-project learning store.')
    parser.add_argument('--workspace', default='.')
    parser.add_argument('--source', default='')
    args = parser.parse_args()
    target = project_root(args.workspace)
    source = project_root(args.source) if args.source else target
    payload = import_project_artifacts(target, source)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
