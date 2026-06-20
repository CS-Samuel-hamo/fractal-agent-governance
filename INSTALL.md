# Install

## Requirements

- Windows PowerShell or a compatible shell.
- Python 3.10+.
- Git.
- Optional: a real execution backend such as Codex CLI.

## Local Install

```powershell
git clone <repo-url>
cd agent-runtime
python scripts\validate_starter_pack.py
.\bin\agent.cmd --version
```

## PATH Setup

Add the repository `bin` directory to your user `PATH`:

```powershell
$agentBin = "<repo>\\bin"
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
agent backend list
python scripts\test_product_alpha.py
```

## Upgrade

Pull or copy the repository update, then rerun:

```powershell
python scripts\validate_starter_pack.py
python scripts\test_product_alpha.py
```
