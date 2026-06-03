param(
  [Parameter(Mandatory=$true)][string]$TaskDir,
  [Parameter(Mandatory=$true)][string]$Workspace,
  [string]$Sandbox = "workspace-write",
  [string]$Profile = "",
  [string]$CodexHome = "D:\AI_DEV\codex_home",
  [int]$TimeoutSeconds = 360,
  [switch]$Ephemeral,
  [switch]$DryRun
)

$script = Join-Path $PSScriptRoot "..\scripts\run_codex_worker.py"
$args = @("--task-dir", $TaskDir, "--workspace", $Workspace, "--sandbox", $Sandbox)
if ($Profile -ne "") { $args += @("--profile", $Profile) }
if ($CodexHome -ne "") { $args += @("--codex-home", $CodexHome) }
if ($TimeoutSeconds -gt 0) { $args += @("--timeout-seconds", "$TimeoutSeconds") }
if ($Ephemeral) { $args += "--ephemeral" }
if ($DryRun) { $args += "--dry-run" }
python $script @args
