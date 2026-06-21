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

## Verify Seed Prompt Bootstrap

For a new prompt-only project:

```powershell
mkdir paper-workflow-demo
cd paper-workflow-demo
notepad project_beginning_prompt.md
agent "read project_beginning_prompt.md"
agent
```

Expected result: the Job Inbox should show a clear `Reason`, `Evidence`,
`Suggested next action`, `Risk level`, and `How to continue`. It should not stop
with only a vague `blocked zone`.

## Upgrade

Pull or copy the repository update, then rerun:

```powershell
agent --version
agent "add a short README note"
```

The 1.0.5 patch is a repo update over the public alpha. It does not require a
new package manager install; refresh your clone or copy the updated files, then
rerun `agent --help`.
