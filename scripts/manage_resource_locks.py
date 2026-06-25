#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime
import json
import os
import subprocess
import time
from pathlib import Path


def utc_now() -> str:
    return datetime.datetime.utcnow().replace(microsecond=0).isoformat() + 'Z'


def parse_utc(value: str) -> datetime.datetime | None:
    if not value:
        return None
    try:
        text = value[:-1] if value.endswith('Z') else value
        return datetime.datetime.fromisoformat(text)
    except ValueError:
        return None


def git_root(workspace: Path) -> Path:
    proc = subprocess.run(
        ['git', 'rev-parse', '--show-toplevel'],
        cwd=workspace,
        text=True,
        encoding='utf-8',
        errors='replace',
        capture_output=True,
    )
    if proc.returncode:
        raise SystemExit(proc.stderr.strip() or proc.stdout.strip() or 'workspace is not a git repository')
    return Path(proc.stdout.strip()).resolve()


def load_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')


class FileLock:
    def __init__(self, path: Path, timeout_seconds: float = 10.0) -> None:
        self.path = path
        self.timeout_seconds = timeout_seconds
        self.fd: int | None = None

    def __enter__(self) -> FileLock:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        deadline = time.monotonic() + self.timeout_seconds
        while True:
            try:
                self.fd = os.open(str(self.path), os.O_CREAT | os.O_EXCL | os.O_RDWR)
                os.write(self.fd, f'{os.getpid()} {utc_now()}'.encode())
                return self
            except FileExistsError:
                if time.monotonic() >= deadline:
                    raise SystemExit(f'resource lock file is busy: {self.path}')
                time.sleep(0.1)

    def __exit__(self, exc_type, exc, tb) -> None:
        if self.fd is not None:
            os.close(self.fd)
        try:
            self.path.unlink()
        except FileNotFoundError:
            pass


def empty_store() -> dict:
    return {
        'schema_version': '1.0',
        'generated_by': 'manage_resource_locks.py',
        'updated_at': utc_now(),
        'locks': [],
    }


def purge_expired(payload: dict, now_dt: datetime.datetime) -> list[dict]:
    active = []
    expired = []
    for lock in payload.get('locks') or []:
        if not isinstance(lock, dict):
            continue
        expires = parse_utc(str(lock.get('expires_at') or ''))
        if expires and expires <= now_dt:
            expired.append(lock)
        else:
            active.append(lock)
    payload['locks'] = active
    return expired


def acquire(payload: dict, owner: str, run_id: str, keys: list[str], ttl_seconds: int, force: bool) -> dict:
    now_dt = datetime.datetime.utcnow().replace(microsecond=0)
    expired = purge_expired(payload, now_dt)
    blockers = []
    existing = payload.get('locks') or []
    for key in keys:
        for lock in existing:
            if lock.get('conflict_key') != key:
                continue
            if lock.get('owner') == owner:
                continue
            if not force:
                blockers.append(
                    {
                        'id': 'resource_locked',
                        'conflict_key': key,
                        'owner': lock.get('owner', ''),
                        'run_id': lock.get('run_id', ''),
                        'expires_at': lock.get('expires_at', ''),
                    }
                )
    if blockers:
        return {'status': 'blocked', 'blockers': blockers, 'expired_locks_purged': expired}

    expires_at = (now_dt + datetime.timedelta(seconds=max(1, ttl_seconds))).isoformat() + 'Z'
    remaining = [lock for lock in existing if not (lock.get('owner') == owner and lock.get('conflict_key') in keys)]
    for key in keys:
        remaining.append(
            {
                'conflict_key': key,
                'owner': owner,
                'run_id': run_id,
                'acquired_at': now_dt.isoformat() + 'Z',
                'expires_at': expires_at,
            }
        )
    payload['locks'] = remaining
    return {'status': 'acquired', 'blockers': [], 'expired_locks_purged': expired}


def release(payload: dict, owner: str, keys: list[str], force: bool) -> dict:
    purge_expired(payload, datetime.datetime.utcnow().replace(microsecond=0))
    released = []
    kept = []
    key_set = set(keys)
    for lock in payload.get('locks') or []:
        if not isinstance(lock, dict):
            continue
        key_matches = not key_set or lock.get('conflict_key') in key_set
        owner_matches = lock.get('owner') == owner or force
        if key_matches and owner_matches:
            released.append(lock)
        else:
            kept.append(lock)
    payload['locks'] = kept
    return {'status': 'released', 'released': released}


def main() -> int:
    ap = argparse.ArgumentParser(description='Acquire, release, or inspect Zoo resource locks.')
    ap.add_argument('--workspace', required=True)
    ap.add_argument('--run-id', default='')
    ap.add_argument('--owner', default='')
    ap.add_argument('--conflict-key', action='append', default=[])
    ap.add_argument('--ttl-seconds', type=int, default=7200)
    ap.add_argument('--acquire', action='store_true')
    ap.add_argument('--release', action='store_true')
    ap.add_argument('--list', action='store_true')
    ap.add_argument('--force', action='store_true')
    args = ap.parse_args()

    actions = [args.acquire, args.release, args.list]
    if sum(1 for item in actions if item) != 1:
        raise SystemExit('Choose exactly one of --acquire, --release, or --list.')
    if (args.acquire or args.release) and not args.owner:
        raise SystemExit('--owner is required for --acquire and --release.')
    if args.acquire and not args.conflict_key:
        raise SystemExit('--conflict-key is required for --acquire.')

    repo_root = git_root(Path(args.workspace).resolve())
    lock_dir = repo_root / '.zoo-agent' / 'locks'
    lock_path = lock_dir / 'resource-locks.json'
    guard_path = lock_dir / 'resource-locks.lock'

    with FileLock(guard_path):
        payload = load_json(lock_path) or empty_store()
        payload.setdefault('schema_version', '1.0')
        payload.setdefault('generated_by', 'manage_resource_locks.py')
        payload.setdefault('locks', [])
        if args.acquire:
            result = acquire(payload, args.owner, args.run_id, args.conflict_key, args.ttl_seconds, args.force)
        elif args.release:
            result = release(payload, args.owner, args.conflict_key, args.force)
        else:
            expired = purge_expired(payload, datetime.datetime.utcnow().replace(microsecond=0))
            result = {'status': 'ok', 'expired_locks_purged': expired}
        payload['updated_at'] = utc_now()
        write_json(lock_path, payload)

    output = {
        'schema_version': '1.0',
        'generated_by': 'manage_resource_locks.py',
        'generated_at': utc_now(),
        'workspace': str(repo_root),
        'lock_path': str(lock_path),
        **result,
        'locks': payload.get('locks') or [],
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0 if output['status'] in {'ok', 'acquired', 'released'} else 20


if __name__ == '__main__':
    raise SystemExit(main())
