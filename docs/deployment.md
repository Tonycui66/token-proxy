# 部署指南（Windows，pip 原生运行）

## 0. 前提

- Windows 10/11，PowerShell 5.1+，Git，Python 3.14（其他 3.10+ 未验证）。
- 全部依赖 wheel 已保存在 `D:\routine\offline-packages\wheels\`（156MB+，118 个包），
  离线机器可直接安装。

## 1. 安装（离线 / 在线通用）

```powershell
# 在 D:\routine 下执行；--no-index 强制只用本地 wheel，验证离线可安装
python -m venv token-proxy\.venv
token-proxy\.venv\Scripts\python.exe -m pip install --no-index --find-links offline-packages\wheels "litellm[proxy]==1.106.4" pytest httpx
```

- 已验证版本：**litellm 1.106.4**（Python 3.14.7，2026-10-26）。升级前先在测试环境验证新版本。
- 重新联网下载最新版：`python -m pip download "litellm[proxy]" -d offline-packages\wheels`，
  然后把验证通过后的版本号固定到本文件和 scripts 里。

## 2. 配置

```powershell
cd token-proxy
copy .env.example .env   # 然后填入：LITELLM_MASTER_KEY（随机长字符串）、OPENAI_API_KEY、DEEPSEEK_API_KEY
```

要求：

- `LITELLM_MASTER_KEY` 使用随机值（可用 `python -c "import secrets;print('sk-master-'+secrets.token_urlsafe(32))"` 生成）。
- 上游 Key 只存在于 `.env`；`.env` 已被 `.gitignore` 排除，绝不提交。

## 3. 启动 / 停止 / 状态

```powershell
powershell -ExecutionPolicy Bypass -File scripts\start.ps1   # 启动并等待健康检查
powershell -ExecutionPolicy Bypass -File scripts\status.ps1  # 进程 + 健康状态
powershell -ExecutionPolicy Bypass -File scripts\stop.ps1    # 停止
```

服务地址：`http://127.0.0.1:5555`（仅本机回环）。

## 4. 验证

```powershell
powershell -ExecutionPolicy Bypass -File scripts\test.ps1
```

- 未填上游 Key 时：health / auth 用例执行，chat / streaming / routing 用例自动跳过（SKIP）。
- 填好上游 Key 后重跑：全部用例应 PASS。

## 5. 备份

```powershell
powershell -ExecutionPolicy Bypass -File scripts\backup.ps1
```

输出到 `data\backup\<时间戳>\`，包含 `.env`（含密钥），注意保管。

## 6. PostgreSQL（便携版，Phase 3）

- 版本：**PostgreSQL 17.6**，便携 zip 位于 `D:\routine\offline-packages\installers\postgresql-17.6-1-windows-x64-binaries.zip`，
  解压在 `offline-packages\installers\pgsql-tmp\pgsql\`（16 的备份在 `pgsql16/`）。
- 数据目录：`token-proxy\data\pgdata`（初始化：`initdb -U litellm -E UTF8 --locale=C --pwfile=...`）。
- 端口 5432，仅监听本机回环；超级用户 `litellm`，密码在 `data\.pg-pass`（勿提交）。
- 启停已集成进 `scripts\start.ps1` / `stop.ps1`（检测到 data\pgdata 自动管理）。
- 数据库连接：`.env` 中 `DATABASE_URL=postgresql://litellm:***@127.0.0.1:5432/litellm`。
- prisma 客户端生成（litellm 首次部署一次性步骤）：

  ```powershell
  $env:PYTHONUTF8=1
  token-proxy\.venv\Scripts\python.exe -m prisma generate --schema=token-proxy\.venv\Lib\site-packages\litellm_proxy_extras\schema.prisma
  # 需要把 token-proxy\.venv\Scripts 加进 PATH（prisma-client-py 生成器依赖）
  token-proxy\.venv\Scripts\python.exe -m prisma db push --schema=...
  ```

