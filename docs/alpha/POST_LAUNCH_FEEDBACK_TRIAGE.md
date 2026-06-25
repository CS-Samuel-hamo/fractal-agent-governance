# Post-launch Feedback Triage

This alpha uses feedback to improve the AI Project Operator path, not to add broad feature creep.

Positioning to preserve:

- AI Project Operator
- Give it a project. It keeps moving it forward.
- Project-level Autopilot, not task-level coding agent.

## Feedback Categories

| Category | Use when | Destination |
| --- | --- | --- |
| install friction | user cannot install or run first command | 1.0.4 patch |
| first-run confusion | user cannot understand the first flow | 1.0.4 patch |
| positioning confusion | user thinks this is a Codex wrapper or GitHub bot | 1.0.4 patch or docs |
| project map quality | map is missing evidence or suggests weak next actions | 1.0.4 patch if blocking, otherwise 1.1 |
| autopilot next_action quality | next action is vague, risky, or not useful | 1.0.4 patch if repeated |
| session reliability | status, continue, stop, undo, or resume is unclear | 1.0.4 patch |
| cockpit clarity | user cannot understand project state in Cockpit | 1.0.4 patch or 1.1 |
| worker availability | worker doctor, local scanner, Codex availability, or dry-run fallback is unclear | 1.0.4 docs or 1.1 adapters |
| release/pr usefulness | release pack or PR draft is not useful | 1.0.4 wording or 1.1 workflow |
| privacy/safety concern | user worries about secrets, push, merge, or network calls | must fix now |
| docs gap | docs are missing or misleading | 1.0.4 patch |
| feature request | new capability request | 1.1 or later |
| bug | reproducible malfunction | patch if blocking |
| not now | cloud, marketplace, enterprise governance, or broad platform requests | later |

## Severity

- `critical`: privacy leak, destructive action, or unsafe remote behavior.
- `high`: blocks install, first run, or trust in the product.
- `medium`: weakens Project Map, Session, Cockpit, or release workflow value.
- `low`: wording polish or non-blocking request.

## Product Impact

Every item should answer one question:

- Does this stop first activation?
- Does this weaken AI Project Operator positioning?
- Does this reduce Project Map usefulness?
- Does this reduce Autopilot/session trust?
- Does this make Cockpit less explanatory?
- Does this reduce release/PR workflow value?

## Roadmap Destination

- `patch`: safe 1.0.4 fix, mostly docs, first-run friction, cockpit wording, branch publishing docs, install/debug hints.
- `roadmap`: 1.1+ product direction such as stronger Cockpit, optional GitHub integration, real worker adapters, installer.
- `later`: useful but not alpha-critical.
- `wont_fix`: conflicts with local-first safety or AI Project Operator positioning.

## Codex Wrapper Confusion

Mark feedback as positioning confusion when a user says or implies:

- "Is this just Codex with extra steps?"
- "Why not just use Codex?"
- "This is a coding agent wrapper."
- "Where is the project operator part?"

Recommended response:

- Clarify that Codex, Claude Code, local scanner, mock, and dry-run are workers.
- Re-emphasize Project Map, long-running session, Cockpit, local learning, and release/PR workflow.
- Improve README, FAQ, Community posts, and demo flow if confusion repeats.
