# Agent Runtime

AI Project Operator for safe local project progress.

Status: `0.9.3-alpha`. The product surface is intentionally small:

```text
goal -> progress -> result
```

## Three-Minute Start

```powershell
git clone <repo-url>
cd agent-runtime
.\bin\agent.cmd --version
agent "fix README typo"
```

By default, `agent "<task>"` runs in preview mode. It shows what would happen without applying changes.

Apply is explicit:

```powershell
agent "fix README typo" -f README.md --apply
```

For project-level progress, start with a goal:

```powershell
agent start "improve project readiness"
agent status
agent continue
```

## Everyday Commands

```powershell
agent "add a short README note"
agent "add a short README note" --preview
agent "fix README typo" -f README.md --apply
agent start "improve project readiness"
agent continue
agent stop
agent status
agent cockpit
agent undo
```

The default output is concise:

```json
{
  "task": "fix README typo",
  "mode": "preview",
  "result": "PREVIEW_READY"
}
```

## Project Cockpit

Generate a local, offline project cockpit:

```powershell
agent cockpit
```

Open `.zoo-agent/cockpit/index.html` in your browser to see project status, recent progress, next actions, attention items, and undo availability.

## Safety

- Preview is the default.
- Single task file changes require `--apply`.
- Project mode can advance low-impact, reversible work and pauses when attention is needed.
- No automatic merge.
- No automatic push.
- No deployment or production migration.
- No secret, API key, token, or `.env` content reading.
- Local runtime metadata is ignored by Git by default.

## Learn More

- [INSTALL.md](INSTALL.md)
- [QUICKSTART.md](QUICKSTART.md)
- [EXAMPLES.md](EXAMPLES.md)
- [CLI_REFERENCE.md](CLI_REFERENCE.md)
- [ARCHITECTURE.md](ARCHITECTURE.md)
- [docs/product-mind-model.md](docs/product-mind-model.md)
