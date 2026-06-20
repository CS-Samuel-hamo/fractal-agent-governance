# Architecture

Agent Runtime presents one simple product flow:

```text
User -> Agent CLI -> Result
```

The default experience is:

```text
ask -> preview -> apply
```

## Product Surface

Users normally need only:

- `agent "<task>"`
- `agent "<task>" --apply`
- `agent status`
- `agent undo`

## Safety Model

- Preview is the default.
- Applying changes requires an explicit flag.
- Work is scoped to the current workspace.
- No automatic merge.
- No automatic push.
- No secret content reads.

Advanced diagnostics exist for maintainers, but they are hidden from the normal product path.
