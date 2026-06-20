# Architecture

Agent Runtime is a CLI-first runtime engine with replaceable execution backends.

```text
User -> CLI -> Runtime -> Backend -> Result
```

## Product Surface

Users work through a small command set:

- `agent goal "<goal>"`
- `agent run "<task>"`
- `agent pipeline "<task>"`
- `agent status`
- `agent backend list`
- `agent backend switch <backend>`

The runtime hides implementation details and returns concise results by default.

## Safety Model

The runtime is conservative by default:

- dry-run is supported everywhere
- actual execution should be scoped
- no automatic merge
- no automatic push
- no secret content reads
- rollback defaults to dry-run
