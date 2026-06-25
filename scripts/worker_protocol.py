"""Structured Worker Protocol — bidirectional context exchange.

Enables the project operator to:
  1. Inject project map context into worker prompts
  2. Parse structured results from worker responses
  3. Auto-update project state based on worker output

Supported workers: Claude Code CLI, Codex CLI, OpenCode.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

# ── Protocol Schema ──────────────────────────────────────────────────────────
# The worker is instructed to return a structured block at the end of its output.
# This block is parsed by the project operator to update project state.

PROTOCOL_MARKER_START = '<!-- ZOO-AGENT-PROTOCOL -->'
PROTOCOL_MARKER_END = '<!-- /ZOO-AGENT-PROTOCOL -->'


def build_context_prompt(project: Path) -> str:
    """Build the project context section injected into every worker prompt.

    Reads project map, risks, and next actions and formats them as a
    structured context block that the worker can use.
    """
    from runtime_common import load_json

    map_path = project / '.zoo-agent' / 'map' / 'project_map.json'
    session_path = project / '.zoo-agent' / 'session' / 'session_state.json'

    context_parts = ['<project-context>']

    # Project map
    project_map = load_json(map_path) if map_path.exists() else {}
    if project_map.get('modules'):
        context_parts.append('<modules>')
        for m in (project_map.get('modules') or [])[:10]:
            name = m.get('name', '?')
            status = m.get('status', 'unknown')
            context_parts.append(f'  <module name="{name}" status="{status}"/>')
        context_parts.append('</modules>')

    # Risks
    all_risks = project_map.get('risks') or []
    if all_risks:
        context_parts.append('<risks>')
        for r in all_risks[:5]:
            desc = r.get('description', r.get('type', '?'))
            severity = r.get('severity', 'unknown')
            context_parts.append(f'  <risk severity="{severity}">{desc}</risk>')
        context_parts.append('</risks>')

    # Session
    session = load_json(session_path) if session_path.exists() else {}
    if session.get('goal'):
        context_parts.append(f'<goal>{session["goal"]}</goal>')

    context_parts.append('</project-context>')

    return '\n'.join(context_parts)


def build_protocol_instruction(expect_changes: bool = True) -> str:
    """Build the instruction telling the worker how to return structured data."""
    instruction = f"""

{PROTOCOL_MARKER_START}
IMPORTANT: After completing the task, output a structured result block:

```json
{{
  "protocol_version": "1.0",
  "summary": "Brief summary of what was done",
  "changed_files": ["path/to/file1", "path/to/file2"],
  "new_risks": [
    {{"description": "Risk description", "severity": "low|medium|high"}}
  ],
  "modules_affected": ["module-name"],
  "suggested_next": "Suggested next action for the project",
  "blockers": ["Any blockers encountered"]
}}
```
{PROTOCOL_MARKER_END}
"""
    return instruction


def parse_worker_output(output: str) -> dict[str, Any]:
    """Parse structured protocol data from worker output.

    Looks for the protocol marker block and extracts JSON.
    Returns empty dict if no structured data is found.
    """
    # Try marker-based extraction first
    start = output.find(PROTOCOL_MARKER_START)
    end = output.find(PROTOCOL_MARKER_END)

    if start >= 0 and end > start:
        block = output[start + len(PROTOCOL_MARKER_START) : end]
        # Extract JSON from code block
        json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', block, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass
        # Fallback: try to parse the whole block as JSON
        try:
            return json.loads(block.strip())
        except json.JSONDecodeError:
            pass

    # Fallback: try to find any JSON block in the output
    json_blocks = re.findall(r'```(?:json)?\s*(\{.*?\})\s*```', output, re.DOTALL)
    for block in json_blocks:
        try:
            data = json.loads(block)
            if data.get('protocol_version'):
                return data
        except json.JSONDecodeError:
            continue

    return {}


def apply_worker_result(project: Path, result: dict[str, Any]) -> dict[str, Any]:
    """Apply structured worker result back to project state.

    Updates the project map (versioned), session state, and next actions.
    Uses project_map_updater for versioned map updates.
    """
    from project_map_updater import update_project_map
    from runtime_common import load_json, utc_now, write_json

    actions = []
    changed = result.get('changed_files') or []
    new_risks = result.get('new_risks') or []

    # Update project map via the versioned updater
    update_project_map(
        project,
        run_id='protocol-' + utc_now(),
        action={'title': result.get('summary', 'worker task')},
        execution_result={'leaf_results': [{'changed_files': changed}]},
        final_result={'final_verdict': 'COMPLETED'},
    )
    actions.extend(
        a
        for a in [
            f'updated project map: {len(changed)} file(s)' if changed else '',
            f'added {len(new_risks)} risk(s)' if new_risks else '',
        ]
        if a
    )

    # Record new risks directly (update_project_map doesn't handle risks)
    if new_risks:
        map_path = project / '.zoo-agent' / 'map' / 'project_map.json'
        project_map = load_json(map_path) if map_path.exists() else {}
        existing_risks = project_map.get('risks', [])
        project_map['risks'] = existing_risks + new_risks
        write_json(map_path, project_map)
        actions.append(f'added {len(new_risks)} risk(s)')

    # Update suggested next action
    suggested = result.get('suggested_next')
    if suggested:
        next_path = project / '.zoo-agent' / 'autopilot' / 'selected_next_action.json'
        next_action = load_json(next_path) if next_path.exists() else {}
        next_action['title'] = suggested
        next_action['source'] = 'worker_protocol'
        write_json(next_path, next_action)
        actions.append(f'suggested next: {suggested[:60]}')

    return {
        'actions_applied': [a for a in actions if a],
        'changed_files': changed,
        'new_risks': len(new_risks),
        'map_version': (load_json(project / '.zoo-agent' / 'map' / 'project_map.json') or {}).get('_version'),
    }
