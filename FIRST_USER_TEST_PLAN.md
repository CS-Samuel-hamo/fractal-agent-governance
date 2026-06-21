# First User Test Plan

Goal: verify that a new user can understand and run the public alpha without internal knowledge.

## Test Path

1. Open `README.md`.
2. Follow `QUICKSTART.md`.
3. Run `agent --help`.
4. Run `agent "prepare this project for public release"`.
5. Run `agent`.
6. Run `agent cockpit`.
7. Run `agent continue` if the inbox suggests it.
8. Run `agent release`.
9. Run `agent pr`.
10. Open the Cockpit path.
11. File feedback using `FEEDBACK.md` or the GitHub issue templates.

## Pass Criteria

- No API key required.
- No network publish action.
- No push or merge.
- No GitHub API call.
- Cockpit is generated locally.
- Release / PR drafts are generated locally.
- User understands this is an AI Project Operator.
- User understands daily use is usually `agent "<goal>"` and `agent`.

## Notes For Testers

If an external worker is unavailable, the product should still explain what can be done with local scanner, preview, dry-run, or needs-attention fallback.
