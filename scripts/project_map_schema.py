#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
from typing import Any

from runtime_common import utc_now

MAP_SCHEMA_VERSION = '1.0'
SENSITIVE_PATTERNS = [
    '.env',
    '.env.*',
    'secrets/**',
    'credentials/**',
    '**/*.pem',
    '**/*.key',
    '.codex/**',
]


def map_dir(project: Path) -> Path:
    return project / '.zoo-agent' / 'map'


def default_project_map(project: Path, *, main_goal: str = '') -> dict[str, Any]:
    return {
        'schema_version': MAP_SCHEMA_VERSION,
        'generated_by': 'project_map_builder.py',
        'project_name': project.name,
        'project_type': 'unknown',
        'main_goal': main_goal,
        'modules': [],
        'capabilities': [],
        'risks': [],
        'next_actions': [],
        'last_updated': utc_now(),
    }


def default_project_state(project: Path, *, main_goal: str = '') -> dict[str, Any]:
    return {
        'schema_version': MAP_SCHEMA_VERSION,
        'generated_by': 'project_map_builder.py',
        'project_name': project.name,
        'main_goal': main_goal,
        'status': 'mapped',
        'progress': '0%',
        'last_action': '',
        'last_result': '',
        'last_updated': utc_now(),
    }


def evidence_item(kind: str, path: str, summary: str, *, confidence: float = 0.7) -> dict[str, Any]:
    return {
        'kind': kind,
        'path': path.replace('\\', '/'),
        'summary': summary,
        'confidence': round(max(0.0, min(1.0, float(confidence))), 3),
    }


def module_row(
    module_id: str,
    name: str,
    purpose: str,
    paths: list[str],
    evidence: list[dict[str, Any]],
    *,
    status: str = 'mapped',
    confidence: float = 0.6,
) -> dict[str, Any]:
    return {
        'module_id': module_id,
        'name': name,
        'purpose': purpose,
        'key_files': [item.replace('\\', '/') for item in paths],
        'status': status,
        'confidence': round(max(0.0, min(1.0, float(confidence))), 3),
        'evidence': evidence,
    }


def capability_row(
    capability_id: str, name: str, status: str, evidence: list[dict[str, Any]], related_modules: list[str]
) -> dict[str, Any]:
    return {
        'capability_id': capability_id,
        'name': name,
        'status': status,
        'evidence': evidence,
        'related_modules': related_modules,
    }


def risk_row(
    risk_id: str, description: str, severity: str, affected_files: list[str], evidence: list[dict[str, Any]]
) -> dict[str, Any]:
    return {
        'risk_id': risk_id,
        'description': description,
        'severity': severity,
        'affected_files': [item.replace('\\', '/') for item in affected_files],
        'evidence': evidence,
    }


def action_row(
    action_id: str,
    title: str,
    why_now: str,
    expected_impact: str,
    risk_level: str,
    target_files: list[str],
    evidence: list[dict[str, Any]],
    *,
    autopilot_eligible: bool = True,
) -> dict[str, Any]:
    return {
        'action_id': action_id,
        'title': title,
        'why_now': why_now,
        'expected_impact': expected_impact,
        'risk_level': risk_level,
        'target_files': [item.replace('\\', '/') for item in target_files],
        'autopilot_eligible': bool(autopilot_eligible),
        'evidence': evidence,
    }
