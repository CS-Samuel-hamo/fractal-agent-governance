param(
  [Parameter(ValueFromRemainingArguments=$true)]
  [string[]]$AgentArgs
)

$script = Join-Path $PSScriptRoot "..\scripts\agent.py"
python $script @AgentArgs

