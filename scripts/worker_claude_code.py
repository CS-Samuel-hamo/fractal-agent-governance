"""Claude Code CLI Worker Adapter — structured protocol integration.

Uses the worker_protocol to inject project context and parse structured results.

Prerequisites: pip install anthropic (or use claude CLI directly)
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from runtime_common import project_root
from worker_protocol import (
    apply_worker_result,
    build_context_prompt,
    build_protocol_instruction,
    parse_worker_output,
)


def run_claude_code(
    project: Path,
    task: str,
    *,
    model: str = 'claude-sonnet-4-6',
    max_tokens: int = 8192,
) -> dict[str, Any]:
    """Run Claude Code CLI with structured protocol.

    Injects project context, executes the task, parses structured output,
    and applies results back to project state.

    Requires `claude` CLI installed and authenticated.
    """
    context = build_context_prompt(project)
    protocol_instr = build_protocol_instruction()
    full_prompt = f"""{context}

## Task

{task}

{protocol_instr}
"""
    cmd = [
        'claude',
        '--print',  # non-interactive, output to stdout
        '--model',
        model,
        '--max-tokens',
        str(max_tokens),
        full_prompt,
    ]

    try:
        proc = subprocess.run(
            cmd,
            cwd=project,
            text=True,
            encoding='utf-8',
            errors='replace',
            capture_output=True,
            timeout=300,  # 5 minute timeout
        )
    except FileNotFoundError:
        return {'status': 'error', 'error': 'claude CLI not found. Install: npm install -g @anthropic-ai/claude-code'}
    except subprocess.TimeoutExpired:
        return {'status': 'error', 'error': 'claude CLI timed out after 300s'}

    raw_output = proc.stdout or ''
    stderr = proc.stderr or ''

    # Parse structured result
    protocol_result = parse_worker_output(raw_output)

    # Apply results back to project state
    applied = apply_worker_result(project, protocol_result)

    return {
        'status': 'ok' if proc.returncode == 0 else 'error',
        'returncode': proc.returncode,
        'raw_output_preview': raw_output[:2000],
        'structured': protocol_result,
        'applied': applied,
        'stderr_preview': stderr[:500],
    }


def run_codex_cli(
    project: Path,
    task: str,
    *,
    model: str = '',
) -> dict[str, Any]:
    """Run OpenAI Codex CLI (OpenCode) with structured protocol.

    Codex CLI doesn't support structured output natively, so we
    inject the protocol instruction and parse the response.
    """
    from run_codex_worker import run_codex_task

    context = build_context_prompt(project)
    protocol_instr = build_protocol_instruction()
    full_prompt = f"""{context}

## Task

{task}

{protocol_instr}
"""
    # Use existing codex worker infrastructure
    result = run_codex_task(
        project=str(project),
        task=full_prompt,
        model=model or '',
    )

    raw_output = str(result.get('stdout', '') or '') + str(result.get('stderr', '') or '')
    protocol_result = parse_worker_output(raw_output)
    applied = apply_worker_result(project, protocol_result)

    return {
        'status': 'ok' if result.get('returncode') == 0 else 'error',
        'returncode': result.get('returncode'),
        'structured': protocol_result,
        'applied': applied,
    }


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Run a worker with structured protocol')
    parser.add_argument('--workspace', default='.')
    parser.add_argument('--worker', choices=['claude', 'codex'], default='claude')
    parser.add_argument('task', nargs='*')
    args = parser.parse_args()

    project = project_root(args.workspace)
    task = ' '.join(args.task).strip()

    if args.worker == 'claude':
        result = run_claude_code(project, task)
    else:
        result = run_codex_cli(project, task)

    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
