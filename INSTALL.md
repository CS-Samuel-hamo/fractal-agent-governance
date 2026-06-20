# Install

## Requirements

- Windows PowerShell or a compatible shell.
- Python 3.10+.
- Git.

## Local Install

```powershell
git clone <repo-url>
cd agent-runtime
.\bin\agent.cmd --version
```

## PATH Setup

Add the repository `bin` directory to your user `PATH`:

```powershell
$agentBin = "<REPO>\\bin"
[Environment]::SetEnvironmentVariable(
  "Path",
  [Environment]::GetEnvironmentVariable("Path", "User") + ";" + $agentBin,
  "User"
)
```

Restart PowerShell or VS Code after updating `PATH`.

## Verify

```powershell
agent --version
agent --help
agent "add a short README note"
agent status
```

## Upgrade

Pull or copy the repository update, then rerun:

```powershell
agent --version
agent "add a short README note"
```
