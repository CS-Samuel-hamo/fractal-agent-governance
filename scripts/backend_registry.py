#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections.abc import Callable
from pathlib import Path

from codex_backend_plugin import CodexExecutionBackend
from execution_interface import ExecutionBackend
from mock_backend_plugin import DryRunExecutionBackend, MockExecutionBackend

BackendFactory = Callable[[], ExecutionBackend]


class BackendRegistry:
    def __init__(self) -> None:
        self._factories: dict[str, BackendFactory] = {}

    def register(self, name: str, factory: BackendFactory) -> None:
        if not name:
            raise ValueError('backend name is required')
        self._factories[name] = factory

    def names(self) -> list[str]:
        return sorted(self._factories)

    def get(self, name: str) -> ExecutionBackend:
        key = name or 'codex'
        if key not in self._factories:
            raise KeyError(f'Unknown execution backend: {key}')
        return self._factories[key]()

    def health(self) -> dict[str, object]:
        return {name: self.get(name).health() for name in self.names()}


def default_registry() -> BackendRegistry:
    registry = BackendRegistry()
    registry.register('codex', CodexExecutionBackend)
    registry.register('mock', MockExecutionBackend)
    registry.register('dry_run', DryRunExecutionBackend)
    return registry


def write_backend_selection(workspace: Path, backend: str) -> Path:
    path = workspace / '.zoo-agent' / 'runtime' / 'backend-selection.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({'backend': backend}, ensure_ascii=False, indent=2), encoding='utf-8')
    return path


def read_backend_selection(workspace: Path, default: str = 'codex') -> str:
    path = workspace / '.zoo-agent' / 'runtime' / 'backend-selection.json'
    if not path.exists():
        return default
    try:
        payload = json.loads(path.read_text(encoding='utf-8-sig'))
        return str(payload.get('backend') or default)
    except Exception:
        return default


def main() -> int:
    parser = argparse.ArgumentParser(description='List, select, and health-check execution backend plugins.')
    parser.add_argument('--workspace', default='.')
    parser.add_argument('--list', action='store_true')
    parser.add_argument('--health', action='store_true')
    parser.add_argument('--select', default='')
    args = parser.parse_args()
    workspace = Path(args.workspace).resolve()
    registry = default_registry()
    if args.select:
        registry.get(args.select)
        path = write_backend_selection(workspace, args.select)
        print(json.dumps({'status': 'ok', 'backend': args.select, 'path': str(path)}, ensure_ascii=False, indent=2))
        return 0
    if args.health:
        print(json.dumps({'backends': registry.health()}, ensure_ascii=False, indent=2))
        return 0
    print(
        json.dumps(
            {'backends': registry.names(), 'selected': read_backend_selection(workspace)}, ensure_ascii=False, indent=2
        )
    )
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
