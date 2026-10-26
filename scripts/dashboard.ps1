# 启动 Token 监控面板（浏览器自动打开 http://127.0.0.1:5556）
# 用法: powershell -ExecutionPolicy Bypass -File scripts\dashboard.ps1
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot

$pidFile = Join-Path $root "data\usage-server.pid"
if (Test-Path $pidFile) {
    $oldPid = Get-Content $pidFile -ErrorAction SilentlyContinue
    if ($oldPid -and (Get-Process -Id $oldPid -ErrorAction SilentlyContinue)) {
        Write-Host "面板已在运行 (PID $oldPid)，直接打开浏览器。"
        Start-Process "http://127.0.0.1:5556"
        exit 0
    }
}

$venvPython = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) { Write-Error "虚拟环境不存在，请先运行安装步骤（README.md）。" }

$logDir = Join-Path $root "data\logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null

$proc = Start-Process -FilePath $venvPython -ArgumentList @(
    (Join-Path $root "scripts\usage_server.py")
) -WorkingDirectory $root -WindowStyle Hidden -PassThru `
  -RedirectStandardOutput (Join-Path $logDir "usage-server-stdout.log") `
  -RedirectStandardError  (Join-Path $logDir "usage-server-stderr.log")

Set-Content -Path $pidFile -Value $proc.Id
Start-Sleep -Seconds 2
Start-Process "http://127.0.0.1:5556"
Write-Host "Token 监控面板已启动 (PID $($proc.Id))：http://127.0.0.1:5556"
Write-Host "停止：Stop-Process -Id $($proc.Id)"
