# Demo

The public alpha includes a safe demo project at `examples/demo_project/`.

## Demo Story

You are preparing a small sample project for public release. Agent Runtime should:

1. map the project,
2. start a project session,
3. show progress in Cockpit,
4. generate release and PR drafts,
5. avoid network, tokens, push, merge, and deployment.

## Try It

The general pattern is `agent "<goal>"`, then `agent`.

```bash
cd examples/demo_project
agent "prepare this demo project for public release"
agent
agent cockpit
agent release
agent pr
```

## What To Expect

- A local Cockpit path.
- A session digest path.
- A release workflow report path.
- A PR draft path.

The demo does not require a real API key, network access, GitHub login, or remote repository.
