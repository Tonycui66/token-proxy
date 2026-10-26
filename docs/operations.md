# 日常运维手册

## 日常操作

```powershell
powershell -ExecutionPolicy Bypass -File scripts\start.ps1    # 启动
powershell -ExecutionPolicy Bypass -File scripts\status.ps1   # 状态
powershell -ExecutionPolicy Bypass -File scripts\test.ps1     # 接口测试
powershell -ExecutionPolicy Bypass -File scripts\backup.ps1   # 备份
powershell -ExecutionPolicy Bypass -File scripts\stop.ps1     # 停止
```

## 版本升级与回滚

1. 升级前备份：`scripts\backup.ps1`，并记录当前 litellm 版本（本文件第 5 节）。
2. 下载新版本 wheel 到离线库：
   `python -m pip download "litellm[proxy]==<新版本>" -d offline-packages\wheels`
3. 建临时 venv 安装并跑 `scripts\test.ps1` 全绿后，才切换正式 venv。
4. 回滚：重新安装旧版本 wheel（离线库中保留的即是），用 backup 恢复配置。
5. 已验证版本记录：
   - **litellm 1.106.4**（Python 3.14.7，2026-10-26 验证，当前使用）

## 故障演练（建议每季度一次）

- 重启代理：stop -> start，确认健康检查通过、测试全绿。
- 上游故障：临时把 `.env` 中某 Key 填错，确认 alias `chat` 仍可用另一上游（fallback）、
  错误模型名返回清晰错误；演练后恢复。
- 网络中断：断网状态下请求应快速失败并返回可诊断错误，而非无限挂起。

## 日志与清理

- `data/logs/litellm-*.log` 按需归档，不要外发（含请求元数据）。
- `data/backup/` 只保留最近若干份，含密钥，注意权限。

## Phase 3 起补充（PostgreSQL）

- 每日备份：`pg_dump litellm > backup\<日期>.sql`（届时在 backup.ps1 中自动化）。
- 恢复演练：恢复到临时库并跑 `scripts\test.ps1`，确认虚拟 Key 与用量数据完整。
