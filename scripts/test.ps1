# 运行全部接口测试
# 用法: powershell -ExecutionPolicy Bypass -File scripts\test.ps1
# 前提: 服务已启动 (scripts\start.ps1)；.env 中已填上游 Key 的用例才会真正执行
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
& (Join-Path $root ".venv\Scripts\python.exe") -m pytest tests -v --tb=short @args
