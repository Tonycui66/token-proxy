# token-proxy —— 个人 Token 中转代理

基于 LiteLLM Proxy 的本地模型网关：统一管理多个上游 API Key，为 Python 程序、
VS Code、Claude Code、Codex 和个人 AI Agent 提供统一的模型访问入口。

实施计划见 [PLAN.md](PLAN.md)。

## 当前状态

- 运行方式：pip 原生运行（Docker Desktop 待安装，`docker-compose.yml` 已备好）。
- 已验证版本：litellm 1.106.4 / Python 3.14.7（2026-10-26）。
- 监听地址：`http://127.0.0.1:5555`（仅本机）。

## 快速开始

```powershell
# 1. 安装（离线可用，wheel 位于 D:\routine\offline-packages\wheels）
python -m venv .venv
.venv\Scripts\python.exe -m pip install --no-index --find-links ..\offline-packages\wheels "litellm[proxy]==1.106.4" pytest httpx

# 2. 配置：复制 .env.example 为 .env，填入 master key 与上游 Key
# 3. 启动
powershell -ExecutionPolicy Bypass -File scripts\start.ps1
# 4. 测试
powershell -ExecutionPolicy Bypass -File scripts\test.ps1
```

## 客户端接入

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://127.0.0.1:5555/v1",
    api_key="<代理 Key>",   # Phase 3 起为虚拟 Key；当前用 master key
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

- `.env` 含全部密钥，不提交 Git、不外发。
- master Key 只用于本机管理；客户端一律使用虚拟 Key（Phase 3 起）。
- 服务仅监听 127.0.0.1，勿改为 0.0.0.0 裸暴露。
