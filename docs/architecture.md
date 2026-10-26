# 系统架构

## 当前形态（pip 原生运行）

因本机尚未安装 Docker Desktop（WSL2 缺失），Phase 1/2 采用 pip 原生方式运行 LiteLLM Proxy，
功能与容器形态一致，仅进程管理方式不同。

```text
Windows 本地客户端
    |
    +-- Python / OpenAI SDK
    +-- VS Code / AI Agent
    +-- Claude Code / Codex（兼容性验证后接入）
    |
    v
LiteLLM Proxy (python -m litellm, .venv 内)
    监听 127.0.0.1:5555 —— 仅回环地址
    |
    +-- 代理 Key 鉴权（master_key / 虚拟 Key）
    +-- 模型别名解析（config/config.yaml）
    +-- 上游路由与 fallback（同名多部署）
    +-- 流式响应（SSE）
    +-- 请求日志和用量/费用统计（显式单价，见 docs/cost-tracking.md）
    |
    +-- 上游模型 API：OpenAI / DeepSeek（Key 仅存于服务端 .env）
```

## 目录职责

- `config/config.yaml` —— 模型别名、上游路由、显式单价。
- `.env` —— 全部密钥（不提交 Git）；`.env.example` 为模板。
- `scripts/*.ps1` —— 启动 / 停止 / 状态 / 测试 / 备份。
- `tests/` —— 接口与鉴权测试（pytest，httpx）。
- `offline-packages/wheels/`（位于项目上级目录）—— 全量离线安装包。

## 演进计划

- Phase 3：加入 PostgreSQL 持久化（docker-compose.yml 已预留 db 服务定义）。
- Docker Desktop 就绪后：迁移到容器运行，镜像版本固定为已验证 tag，
  `scripts/start.ps1` 改为 `docker compose up -d` 封装。
