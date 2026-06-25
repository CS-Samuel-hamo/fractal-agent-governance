# Product Iteration Plan

Feedback maps into product decisions through these buckets.

| Bucket | Meaning | Examples |
| --- | --- | --- |
| patch | safe alpha fix | docs clarity, first-run friction, cockpit wording |
| UX improvement | improves existing user path | clearer status, better report wording |
| docs improvement | no runtime behavior change | README, FAQ, launch docs |
| product direction | informs 1.1+ | stronger Cockpit, optional GitHub integration |
| backlog | valid but not urgent | advanced worker configuration |
| not now | conflicts with scope | cloud sync, marketplace, enterprise governance |

## Decision Rules

- Privacy/security goes first.
- First-run blockers outrank feature requests.
- Positioning confusion gets a docs patch before new features.
- Feature requests do not enter 1.0.4 unless they unblock core alpha usage.
- Keep the public path: task, start, status, continue, stop, undo, cockpit, release, pr.
