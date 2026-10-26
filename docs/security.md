# 安全基线

## 密钥管理

1. 上游 API Key（OPENAI_API_KEY / DEEPSEEK_API_KEY）只保存在服务端 `.env`，
   不进入 Git、不写进日志、不分发给任何客户端。
2. `LITELLM_MASTER_KEY` 是管理员 Key：只用于本机管理和创建虚拟 Key，
   绝不配置到日常客户端。
3. 客户端只使用虚拟 Key（Phase 3 起支持按 Key 授权、限模型、限预算）。
4. `.gitignore` 已排除 `.env`、`data/`（pid、日志、备份）。提交前执行
   `git grep -iE "sk-[a-zA-Z0-9]{20,}"` 确认无真实密钥。

## 网络暴露

1. 服务只监听 `127.0.0.1`，端口 5555 仅本机可访问。
2. 需要局域网/远程访问时，必须经过认证代理或 VPN，不直接改监听地址裸奔。

## 日志

1. 生产运行保持 `set_verbose: false`（config.yaml 已默认），
   避免请求体和密钥进入日志。
2. `data/logs/` 下的运行日志包含请求元数据，不得外发；如需排查可临时开 DEBUG，排查后关闭。
3. 备份目录 `data/backup/` 含 `.env`（密钥），与密钥同等对待。

## 上游风险控制

1. 供应商控制台开启消费限额（OpenAI: usage limits；DeepSeek: 余额上限），
   不能只依赖代理侧预算。
2. 代理侧预算（Phase 4）：虚拟 Key 设置 `max_budget`，超限自动拒绝请求。

## 泄露应急

- 上游 Key 疑似泄露：立即在供应商控制台吊销 → 更新 `.env` → `scripts/stop.ps1 && scripts/start.ps1`。
- master Key 泄露：重新生成 `.env` 中 `LITELLM_MASTER_KEY` 并重启，同时吊销全部虚拟 Key（Phase 3 起记录 Key 清单）。
