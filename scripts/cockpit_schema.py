#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
from typing import Any

from runtime_common import utc_now


COCKPIT_SCHEMA_VERSION = '1.0'


def cockpit_dir(project: Path) -> Path:
    return project / '.zoo-agent' / 'cockpit'


def default_cockpit_data(project: Path) -> dict[str, Any]:
    return {
        'schema_version': COCKPIT_SCHEMA_VERSION,
        'generated_at': utc_now(),
        'project': {
            'name': project.name,
            'type': 'not available',
            'main_goal': 'not available',
            'state': 'unknown',
            'last_updated': '',
        },
        'session': {
            'active': False,
            'goal': '',
            'status': 'not_started',
            'current_action': '',
            'last_action': '',
            'next_action': '',
        },
        'map': {
            'modules': [],
            'capabilities': [],
            'risks': [],
            'next_actions': [],
        },
        'progress': {
            'completed_actions': [],
            'in_progress_actions': [],
            'blocked_actions': [],
            'recent_changes': [],
        },
        'attention': {
            'requires_attention': False,
            'items': [],
        },
        'safety': {
            'checkpoints_available': False,
            'undo_available': False,
            'last_checkpoint': '',
        },
        'readiness': {
            'for_094': 'not available',
            'map_quality_score': None,
            'evidence_coverage': None,
        },
    }
