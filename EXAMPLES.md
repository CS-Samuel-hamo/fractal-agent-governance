# Examples

## Preview A Small Task

```bash
agent "fix README typo"
```

## Apply A Scoped Task

```bash
agent "fix README typo" -f README.md --apply
```

## Start A Release Readiness Session

```bash
agent start "prepare this project for public release"
agent status
agent continue
```

## Open The Cockpit

```bash
agent cockpit
```

Open the printed local HTML file.

## Generate Release Artifacts

```bash
agent release
```

Outputs are local drafts and reports.

## Generate A PR Draft

```bash
agent pr
```

The command creates a local PR draft. It does not create a remote PR.

## Demo Project

```bash
cd examples/demo_project
agent cockpit
agent start "prepare this demo project for public release"
agent release
agent pr
```
