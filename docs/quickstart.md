# Quickstart

Install or expose the `agent` wrapper from this repository on your PATH.

```powershell
agent --version
agent bootstrap
agent "fix typo in README"
```

Interactive mode:

```powershell
agent
```

Then type natural-language tasks:

```text
agent> fix typo in README
agent> /status --no-write
agent> /exit
```

If the project has not been bootstrapped, the first run asks:

```text
Project not bootstrapped. Bootstrap now? yes/no
```

Answering `yes` runs bootstrap. Answering `no` allows a one-off run with a warning.
