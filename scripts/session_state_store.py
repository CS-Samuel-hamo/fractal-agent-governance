#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import tempfile
import time
from pathlib import Path
from typing import Any

from runtime_common import load_json, project_root, utc_now, write_json


SESSION_SCHEMA_VERSION = '1.0'
LOCK_TTL_SECONDS = 30 * 60


def session_dir(project: Path) -> Path:
    return project / '.zoo-agent' / 'session'


def session_state_path(project: Path) -> Path:
    return session_dir(project) / 'session_state.json'


def session_history_path(project: Path) -> Path:
    return session_dir(project) / 'session_history.json'


def session_events_path(project: Path) -> Path:
    return session_dir(project) / 'session_events.jsonl'


def session_lock_path(project: Path) -> Path:
    return session_dir(project) / 'session_lock.json'


def session_digest_path(project: Path) -> Path:
    return session_dir(project) / 'session_digest.md'


def default_session_state(project: Path, *, goal: str = '', max_steps: int = 5) -> dict[str, Any]:
    now = utc_now()
    return {
        'schema_version': SESSION_SCHEMA_VERSION,
        'generated_by': 'session_state_store.py',
        'session_id': f'session-{int(time.time())}',
        'goal': goal,
        'status': 'not_started',
        'created_at': now,
        'updated_at': now,
        'current_step': 0,
        'max_steps': max_steps,
        'completed_steps': 0,
        'failed_steps': 0,
        'last_action_id': '',
        'current_action_id': '',
        'next_action_id': '',
        'pause_reason': '',
        'attention_required': False,
        'last_checkpoint_id': '',
        'resume_available': True,
        'cockpit_path': '.zoo-agent/cockpit/index.html',
    }


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=path.name + '.', suffix='.tmp', dir=str(path.parent))
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write('\n')
        Path(temp_name).replace(path)
    except Exception:
        try:
            Path(temp_name).unlink(missing_ok=True)
        except Exception:
            pass
        raise


def load_session_state(project: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    path = session_state_path(project)
    if not path.exists():
        return {}, {'status': 'missing', 'corrupted': False}
    try:
        data = json.loads(path.read_text(encoding='utf-8-sig'))
        if isinstance(data, dict):
            return data, {'status': 'ok', 'corrupted': False}
    except Exception as exc:
        return {}, {'status': 'corrupted', 'corrupted': True, 'error': str(exc)}
    return {}, {'status': 'invalid', 'corrupted': True, 'error': 'session_state_not_object'}


def save_session_state(project: Path, state: dict[str, Any]) -> dict[str, Any]:
    state = {**state, 'schema_version': SESSION_SCHEMA_VERSION, 'updated_at': utc_now()}
    atomic_write_json(session_state_path(project), state)
    mirror_autopilot_session(project, state)
    return state


def load_session_history(project: Path) -> dict[str, Any]:
    payload = load_json(session_history_path(project))
    if payload:
        return payload
    return {'schema_version': SESSION_SCHEMA_VERSION, 'generated_by': 'session_state_store.py', 'steps': []}


def append_session_history(project: Path, row: dict[str, Any]) -> dict[str, Any]:
    history = load_session_history(project)
    steps = [item for item in history.get('steps') or [] if isinstance(item, dict)]
    steps.append(row)
    history.update({'schema_version': SESSION_SCHEMA_VERSION, 'generated_by': 'session_state_store.py', 'updated_at': utc_now(), 'steps': steps})
    atomic_write_json(session_history_path(project), history)
    return history


def append_session_event(project: Path, event_type: str, payload: dict[str, Any] | None = None) -> None:
    path = session_events_path(project)
    path.parent.mkdir(parents=True, exist_ok=True)
    event = {'at': utc_now(), 'type': event_type, **(payload or {})}
    with path.open('a', encoding='utf-8') as handle:
        handle.write(json.dumps(event, ensure_ascii=False) + '\n')


def mirror_autopilot_session(project: Path, state: dict[str, Any]) -> None:
    mapped_status = state.get('status')
    if mapped_status == 'active':
        mapped_status = 'doing'
    payload = {
        'schema_version': '1.0',
        'generated_by': 'session_state_store.py',
        'session_id': state.get('session_id', ''),
        'goal': state.get('goal', ''),
        'status': mapped_status or 'not_started',
        'updated_at': state.get('updated_at') or utc_now(),
        'step_count': state.get('current_step', 0),
        'max_steps': state.get('max_steps', 0),
        'attention_reason': state.get('pause_reason', ''),
    }
    write_json(project / '.zoo-agent' / 'autopilot' / 'session.json', payload)


def lock_status(project: Path) -> dict[str, Any]:
    lock = load_json(session_lock_path(project))
    if not lock:
        return {'locked': False, 'stale': False}
    if lock.get('released'):
        return {'locked': False, 'stale': False, 'lock': lock}
    created = float(lock.get('created_monotonic') or 0.0)
    stale = bool(created and time.monotonic() - created > LOCK_TTL_SECONDS)
    return {'locked': True, 'stale': stale, 'lock': lock}


def acquire_session_lock(project: Path, *, session_id: str = '') -> dict[str, Any]:
    path = session_lock_path(project)
    status = lock_status(project)
    if status.get('locked') and not status.get('stale'):
        return {'acquired': False, 'stale_recovered': False, 'reason': 'session_already_locked'}
    payload = {
        'schema_version': SESSION_SCHEMA_VERSION,
        'generated_by': 'session_state_store.py',
        'session_id': session_id,
        'pid': os.getpid(),
        'created_at': utc_now(),
        'created_monotonic': time.monotonic(),
    }
    atomic_write_json(path, payload)
    return {'acquired': True, 'stale_recovered': bool(status.get('stale')), 'lock': payload}


def release_session_lock(project: Path) -> None:
    path = session_lock_path(project)
    if path.exists():
        atomic_write_json(path, {'schema_version': SESSION_SCHEMA_VERSION, 'generated_by': 'session_state_store.py', 'released_at': utc_now(), 'released': True})


def main() -> int:
    parser = argparse.ArgumentParser(description='Inspect long-running session state.')
    parser.add_argument('--workspace', default='.')
    args = parser.parse_args()
    project = project_root(args.workspace)
    state, meta = load_session_state(project)
    print(json.dumps({'state': state, 'meta': meta, 'lock': lock_status(project)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
