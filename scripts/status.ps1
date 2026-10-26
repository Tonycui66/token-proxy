# 查看 LiteLLM Proxy 状态
# 用法: powershell -ExecutionPolicy Bypass -File scripts\status.ps1
$root = Split-Path -Parent $PSScriptRoot
$pidFile = Join-Path $root "data\litellm.pid"

$envFile = Join-Path $root ".env"
$host_ = "127.0.0.1"; $port = "5555"
if (Test-Path $envFile) {
    Get-Content $envFile | ForEach-Object {
        if ($_ -match '^\s*(LITELLM_HOST|LITELLM_PORT)\s*=\s*(\S+)\s*$') {
            Set-Variable -Name $Matches[1].ToLower() -Value $Matches[2]
        }
    }
}

$running = $false
if (Test-Path $pidFile) {
    $oldPid = Get-Content $pidFile
    if ($oldPid -and (Get-Process -Id $oldPid -ErrorAction SilentlyContinue)) {
        $running = $true
        Write-Host "进程: 运行中 (PID $oldPid)"
    } else {
        Write-Host "进程: pid 文件存在但进程不存在（异常退出？）"
    }
} else {
    Write-Host "进程: 未启动"
}

$healthUrl = "http://${host_}:${port}/health/liveliness"
try {
    $r = Invoke-WebRequest -Uri $healthUrl -UseBasicParsing -TimeoutSec 3
    Write-Host "健康检查: $($r.StatusCode) $($r.Content)"
} catch {
    Write-Host "健康检查: 失败 ($healthUrl)"
}

if (-not $running) { exit 1 }
