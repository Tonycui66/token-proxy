# 备份配置与敏感文件到 data\backup\
# 用法: powershell -ExecutionPolicy Bypass -File scripts\backup.ps1
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$dest = Join-Path $root "data\backup\$stamp"
New-Item -ItemType Directory -Force -Path $dest | Out-Null

Copy-Item (Join-Path $root "config\config.yaml") $dest
if (Test-Path (Join-Path $root ".env")) { Copy-Item (Join-Path $root ".env") $dest }
if (Test-Path (Join-Path $root "docker-compose.yml")) { Copy-Item (Join-Path $root "docker-compose.yml") $dest }

# PostgreSQL 逻辑备份（便携版 pg_dump）
$envFile = Join-Path $root ".env"
$pgPassFile = Join-Path $root "data\.pg-pass"
$pgBin = Join-Path $root "..\offline-packages\installers\pgsql-tmp\pgsql\bin"
if ((Test-Path $pgPassFile) -and (Test-Path (Join-Path $pgBin "pg_dump.exe"))) {
  $dbUrl = (Select-String -Path $envFile -Pattern "^DATABASE_URL=(.+)$").Matches[0].Groups[1].Value
  $env:PGPASSWORD = (Get-Content $pgPassFile -Raw).Trim()
  & (Join-Path $pgBin "pg_dump.exe") --no-owner --no-privileges -Fc -d $dbUrl -f (Join-Path $dest "litellm-db.dump") 2>$null
  if ($LASTEXITCODE -eq 0) { Write-Host "数据库已备份: litellm-db.dump" }
  else { Write-Warning "pg_dump 失败（数据库可能未启动），其余文件已备份" }
  Remove-Item Env:PGPASSWORD
}

Write-Host "已备份到 $dest"
Write-Host "注意：备份目录包含 .env（含密钥），不要提交 Git 或外发。"
