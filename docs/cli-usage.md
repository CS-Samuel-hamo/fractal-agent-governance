# CLI Usage

```powershell
agent --help
agent --version
agent bootstrap
agent status
agent status --no-write
agent run "<task>"
agent "<task>"
agent review --run-id <run-id>
agent rollback --run-id <run-id> --task-id <task-id> --dry-run
agent reroute --run-id <run-id> --task-id <task-id> --path governed
agent map check
agent standards check
```

## Interactive Commands

- `/status`
- `/review`
- `/rollback`
- `/reroute`
- `/help`
- `/exit`

Natural-language input is routed as `agent run "<input>"`.

## Windows Entry

Use `agent.cmd` from the repository root or add this repository directory to PATH. Do not overwrite existing PATH entries; append only after reviewing the change.
