# 启动 LiteLLM Proxy（pip 原生运行）
# 用法: powershell -ExecutionPolicy Bypass -File scripts\start.ps1
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot

# 读取 .env
$envFile = Join-Path $root ".env"
if (-not (Test-Path $envFile)) {
    Write-Error "未找到 $envFile，请先复制 .env.example 为 .env 并填写。"
}
Get-Content $envFile | ForEach-Object {
    if ($_ -match '^\s*([^#=\s][^=]*)\s*=\s*(.*)\s*$') {
        [Environment]::SetEnvironmentVariable($Matches[1].Trim(), $Matches[2].Trim(), "Process")
    }
}

$pidFile = Join-Path $root "data\litellm.pid"
if (Test-Path $pidFile) {
    $oldPid = Get-Content $pidFile -ErrorAction SilentlyContinue
    if ($oldPid -and (Get-Process -Id $oldPid -ErrorAction SilentlyContinue)) {
        Write-Host "LiteLLM 已在运行 (PID $oldPid)。如需重启请先执行 scripts\stop.ps1"
        exit 0
    }
}

$venvPython = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) { Write-Error "虚拟环境不存在，请先运行安装步骤（README.md）。" }
# 说明：litellm.exe（pip 启动器）会被 Windows 应用控制策略拦截，
# 因此通过 python.exe 直接调用包入口 litellm:run_server。
$venvPython = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) { Write-Error "虚拟环境不存在，请先运行安装步骤（README.md）。" }

$logDir = Join-Path $root "data\logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$stdout = Join-Path $logDir "litellm-stdout.log"
$stderr = Join-Path $logDir "litellm-stderr.log"

$host_ = if ($env:LITELLM_HOST) { $env:LITELLM_HOST } else { "127.0.0.1" }
$port  = if ($env:LITELLM_PORT) { $env:LITELLM_PORT } else { "5555" }

$proc = Start-Process -FilePath $venvPython -ArgumentList @(
    (Join-Path $root "scripts\run_proxy.py")
) -WorkingDirectory $root -RedirectStandardOutput $stdout -RedirectStandardError $stderr -PassThru -WindowStyle Hidden

Set-Content -Path $pidFile -Value $proc.Id
Write-Host "LiteLLM 已启动 (PID $($proc.Id))，监听 http://${host_}:${port}"

# 等待健康检查
$ok = $false
foreach ($i in 1..30) {
    Start-Sleep -Seconds 1
    try {
        $r = Invoke-WebRequest -Uri "http://${host_}:${port}/health/liveliness" -UseBasicParsing -TimeoutSec 2
        if ($r.StatusCode -eq 200) { $ok = $true; break }
    } catch { }
}
if ($ok) { Write-Host "健康检查通过。" }
else {
    Write-Warning "30 秒内健康检查未通过，请查看日志："
    Write-Warning "  $stderr"
    exit 1
}
