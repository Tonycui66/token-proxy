# token-proxy —— 个人 Token 中转代理

基于 LiteLLM Proxy 的本地模型网关：统一管理多个上游 API Key，为 Python 程序、
VS Code、Claude Code、Codex 和个人 AI Agent 提供统一的模型访问入口。

实施计划见 [PLAN.md](PLAN.md)。

## 当前状态

- 运行方式：pip 原生运行（Docker Desktop 待安装，`docker-compose.yml` 已备好）。
- 已验证版本：litellm 1.106.4 / Python 3.14.7 / PostgreSQL 17.6（便携版，2026-10-26）。
- 代理监听：`http://127.0.0.1:5555`（仅本机）；数据库 5432（仅本机回环）。
- 中文管理面板：`http://127.0.0.1:5556`（仅本机）。

## 快速开始

```powershell
# 1. 安装（离线可用，wheel 位于 D:\routine\offline-packages\wheels）
python -m venv .venv
.venv\Scripts\python.exe -m pip install --no-index --find-links ..\offline-packages\wheels "litellm[proxy]==1.106.4" pytest httpx

# 2. 配置：复制 .env.example 为 .env，填入 master key 与上游 Key
# 3. 启动（自动管理便携版 PostgreSQL）
powershell -ExecutionPolicy Bypass -File scripts\start.ps1
# 4. 测试
powershell -ExecutionPolicy Bypass -File scripts\test.ps1
# 5. 打开中文管理面板（用量监控 + Key 管理 + 计费单价设置）
powershell -ExecutionPolicy Bypass -File scripts\dashboard.ps1
```

## 管理面板（5556）

面向日常使用，全中文，litellm 自带的 /ui（5555）仅作备用。**多用户**：
管理员在面板建用户（用户数据全部存在 5555 的 PostgreSQL 里，走 LiteLLM 官方
`/user/new` 等接口）；每个用户登录后只能看到和创建自己的 Key，用量也只统计
自己名下的调用。管理员账号即 `.env` 中的 `UI_USERNAME` / `UI_PASSWORD`。

- **概览**：请求总数、成功率、Token 与费用 KPI，每日费用折线图、按模型汇总
  （管理员看全部，普通用户只看自己的）。
- **我的 Key**：卡片式创建 / 查看 / 吊销虚拟 Key；可设花费上限与重置周期，
  超出上限自动停用；明文 Key 只在创建时显示一次。
- **用户管理**（仅管理员）：建用户（用户名 / 初始密码 / 总花费上限）、
  重置密码、删除用户。
- **设置**（仅管理员）：服务状态、计费单价在线修改（写回 config.yaml，
  自动备份）、一键重启代理。

## 客户端接入

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://127.0.0.1:5555/v1",
    api_key="<虚拟 Key>",   # 在面板「我的 Key」页创建
)
resp = client.chat.completions.create(
    model="chat",            # 统一别名；也可用 gpt-4o-mini / deepseek-chat 等
    messages=[{"role": "user", "content": "你好"}],
)
```

## 模型别名

| 别名 | 实际上游 | 说明 |
|------|----------|------|
| `chat` | gpt-4o-mini ↔ deepseek-chat | 统一入口，双上游负载均衡 + 故障切换 |
| `gpt-4o-mini` / `gpt-4o` | OpenAI | 直连指定模型 |
| `deepseek-chat` / `deepseek-reasoner` | DeepSeek | 直连指定模型 |

计费标准见 [docs/cost-tracking.md](docs/cost-tracking.md)（每个模型单价显式固定于 config.yaml）。

## 文档

- [docs/architecture.md](docs/architecture.md) —— 架构与演进
- [docs/deployment.md](docs/deployment.md) —— 安装部署
- [docs/cost-tracking.md](docs/cost-tracking.md) —— 计费标准与费用核算
- [docs/security.md](docs/security.md) —— 安全基线
- [docs/troubleshooting.md](docs/troubleshooting.md) —— 故障排查
- [docs/operations.md](docs/operations.md) —— 日常运维、升级回滚

## 安全须知

- `.env` 含全部密钥（含数据库密码），不提交 Git、不外发。
- master Key 只在服务端用于管理（面板后端 / 本机命令行）；客户端一律使用虚拟 Key。
- 面板登录会话为内存态 HttpOnly Cookie；用户密码只存 SHA-256 哈希（个人本机使用场景，
  如需更高强度可接 OAuth/SSO）。
- 服务与数据库均仅监听 127.0.0.1，勿改为 0.0.0.0 裸暴露。
