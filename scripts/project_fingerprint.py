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

from runtime_common import load_json, project_root, write_json  # noqa: E402


def infer_type(scanner: dict[str, Any], project_map: dict[str, Any]) -> str:
    detected = str(scanner.get('detected_project_type') or '').lower()
    if detected == 'python':
        if any('cli' in str(item).lower() for item in project_map.get('capabilities') or []):
            return 'python_cli'
        return 'python_library'
    if detected == 'javascript':
        return 'node_app'
    if detected == 'docs':
        return 'docs_site'
    if project_map.get('project_type'):
        return str(project_map.get('project_type'))
    return 'unknown'


def readiness_stage(project_map: dict[str, Any], scanner: dict[str, Any]) -> str:
    capabilities = {str(item.get('status') or '').lower() for item in project_map.get('capabilities') or [] if isinstance(item, dict)}
    if 'verified' in capabilities and scanner.get('detected_tests'):
        return 'release_candidate'
    if project_map.get('modules') and (scanner.get('detected_docs') or scanner.get('detected_tests')):
        return 'mid'
    if project_map or scanner.get('files_scanned'):
        return 'early'
    return 'unknown'


def build_fingerprint(project: Path) -> dict[str, Any]:
    project_map = load_json(project / '.zoo-agent' / 'map' / 'project_map.json')
    scanner = load_json(project / '.zoo-agent' / 'workers' / 'local_scanner_report.json')
    structure = [
        f"modules:{len(project_map.get('modules') or [])}",
        f"manifests:{len(scanner.get('detected_manifests') or [])}",
        f"docs:{len(scanner.get('detected_docs') or [])}",
        f"tests:{len(scanner.get('detected_tests') or [])}",
        f"scripts:{len(scanner.get('detected_scripts') or [])}",
    ]
    capability_features = sorted({str(item.get('status') or 'unknown') for item in project_map.get('capabilities') or [] if isinstance(item, dict)})
    risk_profile = sorted({str(item.get('severity') or 'unknown') for item in project_map.get('risks') or [] if isinstance(item, dict)})
    project_type = infer_type(scanner, project_map)
    stage = readiness_stage(project_map, scanner)
    material = json.dumps({'project_type': project_type, 'structure': structure, 'capabilities': capability_features, 'stage': stage, 'risks': risk_profile}, sort_keys=True)
    return {
        'schema_version': '1.0',
        'generated_by': 'project_fingerprint.py',
        'project_type': project_type,
        'structure_features': structure,
        'capability_features': capability_features,
        'readiness_stage': stage,
        'risk_profile': risk_profile,
        'fingerprint_hash': hashlib.sha256(material.encode('utf-8')).hexdigest()[:16],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description='Build privacy-preserving project fingerprint.')
    parser.add_argument('--workspace', default='.')
    parser.add_argument('--output', default='')
    args = parser.parse_args()
    project = project_root(args.workspace)
    payload = build_fingerprint(project)
    output = Path(args.output).resolve() if args.output else project / '.zoo-agent' / 'learning' / 'cross_project' / 'project_fingerprint.json'
    write_json(output, payload)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
