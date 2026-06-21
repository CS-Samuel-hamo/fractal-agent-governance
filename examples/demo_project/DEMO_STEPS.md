# Demo Steps

Run these commands from `examples/demo_project/`:

```bash
agent cockpit
agent start "prepare this demo project for public release"
agent status
agent release
agent pr
```

Expected result:

- a local Cockpit file path
- a session status summary
- a local release workflow report
- a local PR draft

No network, push, merge, remote PR, deployment, token, or secret is required.
