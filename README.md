# Agent Runtime

Natural-language CLI for safe local AI tasks.

Status: `0.9.2-alpha`. The product surface is intentionally small:

```text
ask -> preview -> apply
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

## Everyday Commands

```powershell
agent "add a short README note"
agent "add a short README note" --preview
agent "fix README typo" -f README.md --apply
agent status
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

## Safety

- Preview is the default.
- File changes require `--apply`.
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
