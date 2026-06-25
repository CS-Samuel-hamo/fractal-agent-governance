from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from bounded_docs_writer import apply_docs_patch, is_safe_docs_target
from runtime_common import project_root, utc_now, write_json


def enabled() -> bool:
    value = os.environ.get('AGENT_ENABLE_REMOTE_AI_WORKER', '').strip().lower()
    return value in {'1', 'true', 'yes', 'on'}


def configured() -> bool:
    return bool(os.environ.get('OPENAI_API_KEY'))


def health(project: Path | None = None) -> dict[str, Any]:
    payload = {
        'schema_version': '1.0',
        'generated_by': 'remote_ai_worker_adapter.py',
        'generated_at': utc_now(),
        'worker_name': 'remote_openai_worker',
        'provider': 'openai_api',
        'available': bool(enabled() and configured()),
        'health': 'healthy' if enabled() and configured() else 'unavailable',
        'supports_actual_execution': bool(enabled() and configured()),
        'supports_preview': True,
        'reason': ''
        if enabled() and configured()
        else ('OPENAI_API_KEY not set' if enabled() else 'remote AI worker disabled'),
        'key_source': 'environment' if configured() else '',
        'key_value_stored': False,
        'model': os.environ.get('AGENT_OPENAI_MODEL', 'gpt-5.1'),
    }
    if project:
        write_json(project / '.zoo-agent' / 'workers' / 'remote_openai_worker_health.json', payload)
    return payload


def build_prompt(*, objective: str, target: str, current_text: str) -> str:
    return (
        'You are updating one documentation file for a local AI Project Operator.\n'
        'Return JSON only with keys "append_markdown" and "summary".\n'
        'Rules: do not invent citations, sources, empirical results, benchmarks, or completed work. '
        'Do not request secrets. Do not include raw API keys or paths. Append only; do not rewrite the full file.\n\n'
        f'Task: {objective}\n'
        f'Target file: {target}\n'
        'Current file excerpt:\n'
        f'{current_text[-4000:]}\n'
    )


def call_openai_responses(prompt: str) -> dict[str, Any]:
    key = os.environ.get('OPENAI_API_KEY', '')
    if not key:
        return {'status': 'skipped', 'reason': 'OPENAI_API_KEY not set'}
    data = {
        'model': os.environ.get('AGENT_OPENAI_MODEL', 'gpt-5.1'),
        'input': prompt,
    }
    request = urllib.request.Request(
        'https://api.openai.com/v1/responses',
        data=json.dumps(data).encode('utf-8'),
        headers={'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'},
        method='POST',
    )
    try:
        with urllib.request.urlopen(request, timeout=90) as response:
            payload = json.loads(response.read().decode('utf-8', errors='replace'))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        return {'status': 'failed', 'reason': type(exc).__name__}

    text = ''
    if isinstance(payload.get('output_text'), str):
        text = payload['output_text']
    else:
        for item in payload.get('output') or []:
            contents = item.get('content') if isinstance(item, dict) else []
            for content in contents or []:
                if isinstance(content, dict) and content.get('type') in {'output_text', 'text'}:
                    text += str(content.get('text') or '')
    try:
        parsed = json.loads(text)
    except Exception:
        parsed = {}
    return {
        'status': 'success' if parsed.get('append_markdown') else 'failed',
        'patch': parsed,
        'reason': '' if parsed else 'invalid_model_json',
    }


def execute_docs_patch(project: Path, *, objective: str, target_files: list[str]) -> dict[str, Any]:
    h = health(project)
    if not h.get('available'):
        return {'status': 'skipped', 'reason': h.get('reason') or 'remote worker unavailable', 'changed_files': []}
    safe_targets = [item for item in target_files if is_safe_docs_target(item)]
    if not safe_targets:
        return {'status': 'blocked', 'reason': 'no safe docs target', 'changed_files': []}

    changed: list[str] = []
    for target in safe_targets:
        path = project / target
        current = path.read_text(encoding='utf-8', errors='replace') if path.exists() else ''
        response = call_openai_responses(build_prompt(objective=objective, target=target, current_text=current))
        patch = response.get('patch') if isinstance(response.get('patch'), dict) else {}
        append = str(patch.get('append_markdown') or '').strip()
        if response.get('status') != 'success' or not append:
            continue
        if append in current:
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(current.rstrip() + '\n\n' + append + '\n', encoding='utf-8')
        changed.append(target)

    if not changed:
        # Keep the product path useful even when remote output is unavailable.
        return apply_docs_patch(project, objective=objective, target_files=safe_targets)
    payload = {
        'schema_version': '1.0',
        'generated_by': 'remote_ai_worker_adapter.py',
        'generated_at': utc_now(),
        'status': 'success',
        'changed_files': changed,
        'safe_for_user_output': True,
        'summary': 'Applied docs update with remote AI worker.',
        'key_value_stored': False,
    }
    write_json(project / '.zoo-agent' / 'workers' / 'remote_openai_worker_result.json', payload)
    return payload


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description='Optional remote AI worker adapter.')
    parser.add_argument('--workspace', default='.')
    parser.add_argument('--health', action='store_true')
    parser.add_argument('--objective', default='')
    parser.add_argument('--target-file', action='append', default=[])
    args = parser.parse_args()
    project = project_root(args.workspace)
    payload = (
        health(project)
        if args.health
        else execute_docs_patch(project, objective=args.objective, target_files=args.target_file)
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload.get('status') in {'success', 'skipped'} or payload.get('available') is not False else 1


if __name__ == '__main__':
    raise SystemExit(main())
