# 备份配置与敏感文件到 data\backup\（数据库备份在 Phase 3 接入 PostgreSQL 后扩展）
# 用法: powershell -ExecutionPolicy Bypass -File scripts\backup.ps1
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$dest = Join-Path $root "data\backup\$stamp"
New-Item -ItemType Directory -Force -Path $dest | Out-Null

Copy-Item (Join-Path $root "config\config.yaml") $dest
if (Test-Path (Join-Path $root ".env")) { Copy-Item (Join-Path $root ".env") $dest }
if (Test-Path (Join-Path $root "docker-compose.yml")) { Copy-Item (Join-Path $root "docker-compose.yml") $dest }

Write-Host "已备份到 $dest"
Write-Host "注意：备份目录包含 .env（含密钥），不要提交 Git 或外发。"
