param(
  [Parameter(Mandatory=$true)][string]$RunId,
  [Parameter(Mandatory=$true)][string]$TaskId,
  [Parameter(Mandatory=$true)][string]$Workspace,
  [Parameter(Mandatory=$true)][string]$Objective,
  [Parameter(Mandatory=$true)][string[]]$AllowedFile,
  [string[]]$DeniedFile = @(),
  [string[]]$TestCommand = @(),
  [int]$ChangedFileEstimate = 0,
  [string]$ForcePath = "",
  [int]$GovernanceLevel = -1,
  [string]$WorktreeRoot = "",
  [string]$StartPoint = "HEAD",
  [string]$Sandbox = "workspace-write",
  [string]$Profile = "",
  [string]$CodexHome = "",
  [int]$TimeoutSeconds = 360,
  [int]$TestTimeoutSeconds = 0,
  [int]$MaxRetries = 1,
  [switch]$AllowHardRisk,
  [switch]$FullPrompt,
  [switch]$DiscardFailedWorktree,
  [switch]$Ephemeral,
  [switch]$ExecutePlanned,
  [switch]$DryRun
)

$script = Join-Path $PSScriptRoot "..\scripts\run_ai_native_task.py"
$args = @(
  "--run-id", $RunId,
  "--task-id", $TaskId,
  "--workspace", $Workspace,
  "--objective", $Objective,
  "--changed-file-estimate", "$ChangedFileEstimate",
  "--sandbox", $Sandbox,
  "--timeout-seconds", "$TimeoutSeconds",
  "--test-timeout-seconds", "$TestTimeoutSeconds",
  "--max-retries", "$MaxRetries",
  "--start-point", $StartPoint
)
foreach ($item in $AllowedFile) { $args += @("--allowed-file", $item) }
foreach ($item in $DeniedFile) { $args += @("--denied-file", $item) }
foreach ($item in $TestCommand) { $args += @("--test-command", $item) }
if ($ForcePath -ne "") { $args += @("--force-path", $ForcePath) }
if ($GovernanceLevel -ge 0) { $args += @("--governance-level", "$GovernanceLevel") }
if ($WorktreeRoot -ne "") { $args += @("--worktree-root", $WorktreeRoot) }
if ($Profile -ne "") { $args += @("--profile", $Profile) }
if ($CodexHome -ne "") { $args += @("--codex-home", $CodexHome) }
if ($AllowHardRisk) { $args += "--allow-hard-risk" }
if ($FullPrompt) { $args += "--full-prompt" }
if ($DiscardFailedWorktree) { $args += "--discard-failed-worktree" }
if ($Ephemeral) { $args += "--ephemeral" }
if ($ExecutePlanned) { $args += "--execute-planned" }
if ($DryRun) { $args += "--dry-run" }
python $script @args

