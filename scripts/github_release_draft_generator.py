#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from public_release_packager import VERSION, public_release_dir
from runtime_common import project_root, utc_now


def draft_text() -> str:
    return f"""# AI Project Operator v{VERSION}

Tag: `v{VERSION}`

## Summary

Project Map-backed Autopilot for AI-heavy developers.

Agent Runtime is a local-first AI Project Operator. Give it a project. It keeps moving it forward.

## What This Is

- Project-level Autopilot, not task-level coding agent.
- A local Project Map that tracks modules, capabilities, risks, and next actions.
- A long-running session runtime for project goals.
- A static local Cockpit for project progress.
- A worker-agnostic operator layer where coding tools are workers.
- Local release and PR draft generation.

## What This Is Not

- Not a Codex wrapper.
- Not a Claude Code replacement.
- Not a GitHub PR bot.
- Not a cloud service.
- Not an account system.
- Not a plugin marketplace.

## Core Capabilities

- Map a project locally.
- Start and continue a project session.
- Inspect project progress in Cockpit.
- Stop or inspect undo recovery points.
- Generate local release readiness reports.
- Generate local PR drafts, release notes drafts, and changelog drafts.

## Quickstart

```bash
agent cockpit
agent start "prepare this project for public release"
agent status
agent release
agent pr
```

## Demo Flow

```bash
cd examples/demo_project
agent cockpit
agent start "prepare this demo project for public release"
agent status
agent release
agent pr
```

## Privacy / Safety Guarantees

- No GitHub API calls.
- No automatic push or merge.
- No remote GitHub PR creation.
- No remote GitHub release creation.
- No cloud sync or telemetry.
- No `.env` content or API key reading.
- Release / PR workflow is local draft generation only.

## Known Limitations

- This release does not create remote GitHub PRs.
- It does not publish releases or upload artifacts.
- Claude/local actual execution is not claimed as fully supported unless a real local adapter is detected.
- Human review remains required before publishing, pushing, merging, or deploying.

## Roadmap

- 1.0 public alpha: stable local Project Operator path.
- 1.1: stronger session recovery and Cockpit clarity.
- 1.2: optional explicit GitHub integration with user confirmation.
- Later: team and enterprise workflows.

## Feedback Requested

- Does the Project Map help you understand project state?
- Does the session flow feel useful for real project progress?
- Does the Cockpit make next actions clear?
- Are release and PR drafts useful before manual publishing?
"""


def generate(project: Path) -> dict:
    text = draft_text()
    root_path = project / 'GITHUB_RELEASE_DRAFT.md'
    root_path.write_text(text, encoding='utf-8')
    out = public_release_dir(project)
    out.mkdir(parents=True, exist_ok=True)
    (out / 'github_release_draft.md').write_text(text, encoding='utf-8')
    payload = {
        'generated_at': utc_now(),
        'version': VERSION,
        'draft_path': 'GITHUB_RELEASE_DRAFT.md',
        'artifact_path': '.zoo-agent/public_release/github_release_draft.md',
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--workspace', default='.')
    args = parser.parse_args(argv)
    generate(project_root(args.workspace))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
