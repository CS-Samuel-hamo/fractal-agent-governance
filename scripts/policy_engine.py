#!/usr/bin/env python3
"""Policy engine — .zoarc file loading and enforcement.

.zoarc is a YAML-based policy file that controls:
  - Worker routing (which worker handles which task)
  - Security boundaries (block/warn on dangerous actions)
  - Cost controls (max spend, preferred worker)

Policy file location (checked in order):
  1. .zoarc in project root
  2. .zoo-agent/policies/*.yaml (multi-file)
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from runtime_common import load_json

# ── Default policies (used when no .zoarc file exists) ──────────────────────

DEFAULT_POLICIES: dict[str, Any] = {
    'routing': [
        {'match': {'risk': 'high'}, 'require_worker': 'claude_worker_stub', 'human_review': True},
        {'match': {'risk': 'critical'}, 'block': True, 'message': 'Critical risk tasks require manual approval.'},
        {'match': {'type': 'docs'}, 'preferred': 'bounded_docs_writer'},
        {'match': {'type': 'test'}, 'preferred': 'codex_worker_existing_adapter'},
        {'match': {'type': 'code'}, 'preferred': 'codex_worker_existing_adapter'},
        {'match': {'type': 'review'}, 'preferred': 'claude_worker_stub'},
    ],
    'security': [
        {'deny': {'action': 'delete_file'}},
        {'deny': {'action': 'modify_env'}},
        {'deny': {'pattern': '.env*'}},
        {'warn': {'action': 'modify_config'}},
    ],
    'cost': {
        'max_daily_calls': 50,
        'max_daily_cost': 10.0,
        'preferred_worker': 'codex_worker_existing_adapter',
    },
}


# ── Policy loading ──────────────────────────────────────────────────────────


def _find_policy_file(project: Path) -> Path | None:
    """Find the first available policy file."""
    candidates = [
        project / '.zoarc',
    ]
    policies_dir = project / '.zoo-agent' / 'policies'
    if policies_dir.exists():
        candidates.extend(sorted(policies_dir.glob('*.yaml')))
    for path in candidates:
        if path.exists():
            return path
    return None


def _parse_zoarc(text: str) -> dict[str, Any]:
    """Parse a .zoarc file (simple YAML-like format).

    Supports a simplified YAML subset:
      - comments (#)
      - key: value
      - key:\n  - list items\n  - list items
      - nested dicts with indentation

    Falls back to JSON if parsing fails.
    """
    # Try parsing as JSON first
    text_stripped = text.strip()
    if text_stripped.startswith('{'):
        try:
            return json.loads(text_stripped)
        except json.JSONDecodeError:
            pass

    # Simple YAML-like parser
    lines = text.split('\n')
    result: dict[str, Any] = {}
    stack: list[tuple[int, str, Any]] = [(-1, 'root', result)]

    for line in lines:
        stripped = line.rstrip()
        if not stripped or stripped.strip().startswith('#'):
            continue
        indent = len(line) - len(line.lstrip())
        content = stripped.strip()

        if content.endswith(':'):
            key = content[:-1].strip()
            new_container: list[Any] | dict[str, Any] = []
            parent = stack[-1][2]
            if isinstance(parent, dict):
                parent[key] = new_container
            stack.append((indent, key, new_container))

        elif content.startswith('- '):
            item_text = content[2:].strip()
            if ':' in item_text:
                k, v = item_text.split(':', 1)
                item_dict: dict[str, Any] = {k.strip(): _parse_value(v.strip())}
                # Pop back to correct parent
                while stack[-1][0] >= indent:
                    stack.pop()
                parent = stack[-1][2]
                if isinstance(parent, list):
                    parent.append(item_dict)
                stack.append((indent, '', item_dict))
            else:
                parent = stack[-1][2]
                if isinstance(parent, list):
                    parent.append(_parse_value(item_text))

        else:
            if ': ' in content:
                key, value = content.split(': ', 1)
                key = key.strip()
                value = _parse_value(value.strip())
                # Pop back to correct indent level
                while stack and stack[-1][0] >= indent:
                    stack.pop()
                if stack:
                    parent = stack[-1][2]
                    while stack and stack[-1][0] >= indent:
                        stack.pop()
                    # Re-find parent after popping
                    idx = len(stack) - 1
                    while idx >= 0 and stack[idx][0] >= indent:
                        idx -= 1
                    if idx >= 0:
                        parent = stack[idx][2]
                    if isinstance(parent, dict):
                        parent[key] = value
                    elif isinstance(parent, list):
                        parent.append({key: value})
                    stack.append((indent, key, value))

    return result.get('policies', result) if 'policies' in result else result


def _parse_value(value: str) -> Any:
    """Parse a YAML value."""
    if value.lower() == 'true':
        return True
    if value.lower() == 'false':
        return False
    if value.lower() == 'null' or value.lower() == '~':
        return None
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        pass
    if value.startswith('[') and value.endswith(']'):
        return [v.strip().strip('"\'') for v in value[1:-1].split(',') if v.strip()]
    return value.strip('"\'')


def load_policies(project: Path) -> dict[str, Any]:
    """Load policies from .zoarc file, falling back to defaults."""
    policy_file = _find_policy_file(project)
    if policy_file:
        try:
            text = policy_file.read_text(encoding='utf-8')
            custom = _parse_zoarc(text)
            # Deep merge with defaults
            merged = {}
            for section in ['routing', 'security', 'cost']:
                merged[section] = custom.get(section, DEFAULT_POLICIES.get(section, {}))
            if isinstance(merged.get('routing'), list) and isinstance(DEFAULT_POLICIES.get('routing'), list):
                merged['routing'] = custom['routing'] + DEFAULT_POLICIES['routing']
            return merged
        except Exception:
            pass
    return dict(DEFAULT_POLICIES)


# ── Policy evaluation ──────────────────────────────────────────────────────


def evaluate_routing(
    policies: dict[str, Any],
    *,
    task_type: str = '',
    risk_level: str = 'low',
    file_patterns: list[str] | None = None,
) -> dict[str, Any]:
    """Evaluate routing policies for a task.

    Returns the first matching policy rule, or a default allow-all rule.
    """
    rules = policies.get('routing', [])
    file_patterns = file_patterns or []

    for rule in rules:
        match = rule.get('match', {})
        # Check risk level
        if match.get('risk') and match['risk'] != risk_level:
            continue
        # Check task type
        if match.get('type') and match['type'] != task_type:
            continue
        # Check file pattern
        if match.get('pattern') and not any(re.search(match['pattern'].replace('*', '.*'), fp) for fp in file_patterns):
            continue
        return rule

    return {'preferred': 'auto'}


def check_security(policies: dict[str, Any], *, action: str = '', filepath: str = '') -> dict[str, Any]:
    """Check security policies for an action.

    Returns {'decision': 'allow'} or {'decision': 'deny', 'reason': '...'}.
    """
    rules = policies.get('security', [])
    surface = f'{action} {filepath}'.lower()
    for rule in rules:
        if 'deny' in rule:
            deny = rule['deny']
            if deny.get('action') and deny['action'] in surface:
                return {'decision': 'deny', 'reason': f'policy blocks: {deny["action"]}', 'rule': rule}
            if deny.get('pattern') and re.search(deny['pattern'].replace('*', '.*'), surface):
                return {'decision': 'deny', 'reason': f'policy blocks pattern: {deny["pattern"]}', 'rule': rule}
        if 'warn' in rule:
            warn = rule['warn']
            if warn.get('action') and warn['action'] in surface:
                return {'decision': 'warn', 'reason': f'policy warns: {warn["action"]}', 'rule': rule}
    return {'decision': 'allow'}


def check_cost_limit(policies: dict[str, Any], project: Path) -> dict[str, Any]:
    """Check if cost limits have been reached."""
    cost_config = policies.get('cost', {})
    max_calls = cost_config.get('max_daily_calls', 0)
    max_cost = cost_config.get('max_daily_cost', 0)
    if not max_calls and not max_cost:
        return {'within_limit': True}

    # Read current usage
    usage_path = project / '.zoo-agent' / 'cost' / 'daily_usage.json'
    usage = load_json(usage_path) if usage_path.exists() else {}

    today = __import__('datetime').date.today().isoformat()
    today_usage = usage.get(today, {'calls': 0, 'cost': 0.0})

    result: dict[str, Any] = {
        'within_limit': True,
        'today_calls': today_usage['calls'],
        'today_cost': today_usage['cost'],
    }
    if max_calls and today_usage['calls'] >= max_calls:
        result['within_limit'] = False
        result['reason'] = f'daily call limit reached ({today_usage["calls"]}/{max_calls})'
    if max_cost and today_usage['cost'] >= max_cost:
        result['within_limit'] = False
        result['reason'] = f'daily cost limit reached (${today_usage["cost"]:.2f}/${max_cost:.2f})'
    return result


# ── CLI ─────────────────────────────────────────────────────────────────────


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description='Policy engine — evaluate routing and security policies.')
    parser.add_argument('--workspace', default='.')
    parser.add_argument('--check', choices=['routing', 'security', 'cost'], default='routing', help='What to check')
    parser.add_argument('--task-type', default='')
    parser.add_argument('--risk', default='low')
    parser.add_argument('--action', default='')
    parser.add_argument('--file', default='')
    parser.add_argument('--show', action='store_true', help='Show loaded policies')
    args = parser.parse_args()

    from runtime_common import project_root

    project = project_root(args.workspace)
    policies = load_policies(project)

    if args.show:
        print(json.dumps(policies, ensure_ascii=False, indent=2))
        return 0

    if args.check == 'routing':
        result = evaluate_routing(policies, task_type=args.task_type, risk_level=args.risk)
    elif args.check == 'security':
        result = check_security(policies, action=args.action, filepath=args.file)
    elif args.check == 'cost':
        result = check_cost_limit(policies, project)

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
