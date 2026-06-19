$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
& python (Join-Path $ScriptDir '..\scripts\agent.py') @args
