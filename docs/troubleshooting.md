# 故障排查

## 快速定位流程

```text
客户端报错
  |-- 无法连接 127.0.0.1:5555        -> 代理层（进程没起来 / 端口不对）
  |-- 401/403                        -> 鉴权层（Key 错误或被吊销）
  |-- 连接超时 / upstream connect    -> 上游层（网络、上游 Key、上游故障）
  `-- 500 且含 database              -> 数据库层（Phase 3 起）
```

## 1. 代理层

- 确认进程：`powershell -File scripts\status.ps1`。
- 查看日志：`data\logs\litellm-stderr.log`（启动失败基本都在这里）。
- 常见错误：
  - `No module named litellm` —— venv 未安装或损坏，重跑 docs/deployment.md 第 1 步。
  - `Address already in use` —— 端口被占用：`netstat -ano | findstr 5555`，或先 `scripts\stop.ps1`。
  - pid 文件存在但 status 显示进程不存在 —— 上次异常退出，直接 start 即可。

## 2. 鉴权层

- `Authorization: Bearer <key>` 格式是否正确（中间有空格）。
- 虚拟 Key 是否被吊销 / 过期 / 超预算（Phase 3 起可查 `/key/info`）。
- 区分：master Key 有管理权限，虚拟 Key 只有调用权限。

## 3. 上游层

- 检查 `.env` 对应供应商 Key 是否填写、是否有效（控制台手工试一次）。
- 常见上游错误码：
  - 401 —— 上游 Key 无效。
  - 429 —— 上游限流；LiteLLM 会自动重试（num_retries: 2）。
  - 5xx —— 上游故障，等恢复或依赖 fallback 切换到另一供应商。
- 本机网络代理：如需走代理访问 OpenAI/DeepSeek，在 `.env` 加 `HTTP_PROXY`/`HTTPS_PROXY`。

## 4. 数据库层（Phase 3 起）

- `DATABASE_URL` 与容器/服务状态。
- 连接失败时 LiteLLM 仍可代理请求，但虚拟 Key/用量功能不可用，日志会有 Prisma/psycopg 报错。

## 5. Windows 特有问题（本机已验证的坑）

| 问题 | 原因 | 解决 |
|------|------|------|
| `.ps1` 中文变乱码、字符串解析错乱 | PowerShell 5.1 对无 BOM 的 UTF-8 按 GBK 读 | 脚本保存为 UTF-8 **带 BOM**（scripts/ 下均已处理） |
| `.env` 报 UnicodeDecodeError | python-dotenv 按 UTF-8 读，文件是 GBK | `.env` 保存为 UTF-8，注释用 ASCII |
| config.yaml 报 GBK codec 错误 | litellm 读文件用系统默认编码 | config.yaml 注释保持 ASCII（已处理） |
| `litellm.exe` 无法启动（应用控制策略） | Smart App Control 拦截 pip 启动器 | 用 `scripts/run_proxy.py` + python.exe 启动（已内置） |
