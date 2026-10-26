# 停止 LiteLLM Proxy
# 用法: powershell -ExecutionPolicy Bypass -File scripts\stop.ps1
$ErrorActionPreference = "SilentlyContinue"
$root = Split-Path -Parent $PSScriptRoot
$pidFile = Join-Path $root "data\litellm.pid"

if (-not (Test-Path $pidFile)) { Write-Host "LiteLLM 未在运行（无 pid 文件）。"; exit 0 }

$oldPid = Get-Content $pidFile
$proc = Get-Process -Id $oldPid
if ($proc) {
    Stop-Process -Id $oldPid -Force
    Write-Host "LiteLLM (PID $oldPid) 已停止。"
} else {
    Write-Host "PID $oldPid 对应的进程不存在，清理 pid 文件。"
}
Remove-Item $pidFile -Force
