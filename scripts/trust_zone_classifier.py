#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from runtime_common import project_root, utc_now, write_json


BLOCKED_TERMS = ['secret', '.env', 'auth', 'payment', 'billing', 'production deploy', 'deploy production', 'database migration', 'migration', 'auto push', 'auto merge', 'delete files', 'destructive']
GUARDED_TERMS = ['public api', 'api response', 'schema', 'dependency', 'package.json', 'pyproject.toml', '.github/workflows', 'ci pipeline', 'config', 'cross-module', 'core runtime']
TRUSTED_PREFIXES = ['docs/', 'examples/', 'tests/', 'test/']
TRUSTED_FILES = {'README.md', 'QUICKSTART.md', 'INSTALL.md', 'EXAMPLES.md', 'CONTRIBUTING.md'}


def classify_trust_zone(*, title: str = '', target_files: list[str] | None = None, risk_level: str = 'low') -> dict[str, Any]:
    files = [str(item).replace('\\', '/') for item in target_files or []]
    surface = ' '.join([title, risk_level, *files]).lower()
    reasons: list[str] = []
    if any(term in surface for term in BLOCKED_TERMS) or any(path.lower().startswith(('.env', 'secrets/', 'credentials/')) for path in files):
        zone = 'blocked'
        reasons.append('blocked_sensitive_or_destructive_surface')
    elif risk_level in {'high', 'critical'}:
        zone = 'blocked'
        reasons.append('high_risk_action')
    elif any(term in surface for term in GUARDED_TERMS):
        zone = 'guarded'
        reasons.append('guarded_api_config_dependency_or_cross_module_surface')
    elif files and all(path in TRUSTED_FILES or any(path.startswith(prefix) for prefix in TRUSTED_PREFIXES) or path.startswith('scripts/') for path in files):
        zone = 'trusted'
        reasons.append('trusted_documentation_test_example_or_local_script_surface')
    elif len(files) == 1 and str(risk_level) == 'low':
        zone = 'trusted'
        reasons.append('small_isolated_low_risk_file_edit')
    else:
        zone = 'guarded'
        reasons.append('unknown_or_broad_surface')

    return {
        'schema_version': '1.0',
        'generated_by': 'trust_zone_classifier.py',
        'generated_at': utc_now(),
        'zone': zone,
        'risk_level': 'high' if zone == 'blocked' else str(risk_level or 'unknown'),
        'target_files': files,
        'reasons': reasons,
        'standard_mode': 'auto' if zone == 'trusted' else ('needs_attention' if zone == 'blocked' else 'preview'),
        'autopilot_mode': 'auto' if zone in {'trusted', 'guarded'} else 'needs_attention',
        'requires_checkpoint': zone in {'trusted', 'guarded'},
        'requires_tests': zone == 'guarded',
        'requires_explanation': zone in {'trusted', 'guarded'},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description='Classify an action into trusted, guarded, or blocked zone.')
    parser.add_argument('--workspace', default='.')
    parser.add_argument('--title', default='')
    parser.add_argument('--target-file', action='append', default=[])
    parser.add_argument('--risk-level', default='low')
    parser.add_argument('--output', default='')
    args = parser.parse_args()
    project = project_root(args.workspace)
    payload = classify_trust_zone(title=args.title, target_files=args.target_file, risk_level=args.risk_level)
    if args.output:
        write_json(Path(args.output).resolve(), payload)
    else:
        write_json(project / '.zoo-agent' / 'autopilot' / 'trust_zone.json', payload)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
