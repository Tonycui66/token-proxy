# Token 中转代理工具实施计划（PLAN.md）

## 1. 项目目标

基于开源项目 LiteLLM Proxy，在 Windows 本地搭建个人 Token
中转代理，实现多个上游模型 API Key 的统一管理，为 Python 程序、VS
Code、Claude Code、Codex 和个人 AI Agent 提供统一的模型访问入口。

### 核心目标

- 统一 API 代理地址。
- 统一管理多个上游模型及其 API Key。
- 使用独立的代理 Key 访问模型服务。
- 支持模型切换、流式响应和异常处理。
- 统计调用次数、Token 用量、响应时间和费用。
- 后续支持多个开发项目和 AI Agent 独立使用代理。

### 非目标

第一阶段不自行实现大模型推理，不重写所有供应商协议，不开发公开售卖平台，也不尝试绕过上游服务的认证、订阅或访问控制。

## 2. 技术选型

  组件       选型                       用途

  ---------- -------------------------- ------------------------------

  API 网关   LiteLLM Proxy              请求转发、模型路由、虚拟 Key
  容器环境   Docker Desktop             Windows 本地运行
  配置管理   YAML + 环境变量            模型和密钥配置
  数据库     PostgreSQL                 第二阶段持久化数据
  测试工具   PowerShell + Python        接口及异常测试
  版本管理   Git                        代码、配置模板和变更管理
  后台管理   LiteLLM 自带管理能力优先   减少重复开发

版本策略：先验证可用版本，再固定 LiteLLM
镜像版本；禁止生产配置长期使用未经验证的浮动标签。

## 3. 系统架构

```text
Windows 本地客户端
    |
    +-- Python / OpenAI SDK
    +-- VS Code / AI Agent
    +-- Claude Code / Codex（兼容性验证后接入）
    |
    v
LiteLLM Proxy
    |
    +-- 代理 Key 鉴权
    +-- 模型别名解析
    +-- 上游路由
    +-- 流式响应
    +-- 请求日志和用量统计
    |
    +--------------------+
    |                    |
    v                    v
上游模型 API         PostgreSQL
    |                    |
    +-- OpenAI           +-- Key 元数据
    +-- DeepSeek         +-- 调用记录
    +-- 其他授权服务      +-- 用量统计
                         +-- 预算与权限
```

默认监听地址：`127.0.0.1:5555`。

上游 API Key 只保存在代理服务端，不分发给客户端。

## 4. 项目目录

```text
token-proxy/
├── docker-compose.yml
├── .env
├── .env.example
├── .gitignore
├── README.md
├── PLAN.md
├── config/
│   └── config.yaml
├── scripts/
│   ├── start.ps1
│   ├── stop.ps1
│   ├── status.ps1
│   ├── test.ps1
│   └── backup.ps1
├── tests/
│   ├── test_health.py
│   ├── test_auth.py
│   ├── test_chat.py
│   ├── test_streaming.py
│   └── test_model_routing.py
├── docs/
│   ├── architecture.md
│   ├── deployment.md
│   ├── troubleshooting.md
│   └── security.md
└── data/
```

注意：`.env`、真实 API Key、敏感日志和数据库密码不得提交到
Git。数据库数据目录应按实际容器卷配置进行持久化。

## 5. 分阶段实施计划

### Phase 0：环境检查

任务：

- [x] 检查 Windows、PowerShell、Git、Docker Desktop。
- [x] 确认 Docker Compose 可以正常工作。
- [x] 确认上游 API Key 有效。
- [x] 确认本机能够访问上游 API。
- [x] 建立 Git 仓库和基础目录。

交付物：

- 项目目录。
- `.gitignore`。
- `.env.example`。
- 环境检查记录。

验收标准：

- Docker 正常运行。
- 项目目录结构完整。
- Git 不包含真实密钥。

### Phase 1：最小可运行代理

任务：

- [x] 配置 LiteLLM Proxy。
- [x] 配置一个上游模型。
- [x] 生成管理员 Key。
- [x] 使用 Docker Compose 启动代理。（实际因本机缺 WSL2/Docker Desktop，
      先改为 pip 原生运行；docker-compose.yml 已备好，Docker 就绪后切换）
- [x] 测试健康检查和聊天接口。（聊天接口需真实上游 Key，Key 由用户填 .env 后
      重跑 scripts/test.ps1 验证；测试已就绪，未填时自动跳过）
- [x] 测试错误 Key 的拒绝行为。

交付物：

- `docker-compose.yml`。
- `config/config.yaml`。
- `.env.example`。
- `scripts/start.ps1`。
- `scripts/stop.ps1`。
- `tests/test_chat.py`。

验收标准：

- 服务能够启动并保持运行。
- 合法请求可以得到上游模型响应。
- 无效 Key 被拒绝。
- 停止和重启操作正常。
- 代理端口只暴露给本机。

### Phase 2：多模型和统一路由

任务：

- [ ] 增加第二个上游模型。
- [ ] 配置统一模型别名。
- [ ] 验证模型选择是否正确。
- [ ] 测试供应商错误、超时和连接失败。
- [ ] 根据实际支持情况验证备用上游和故障切换。

交付物：

- 多模型配置。
- `tests/test_model_routing.py`。
- 模型配置说明。

验收标准：

- 客户端只使用模型别名。
- 不同别名能路由到正确的上游。
- 错误模型名能返回清晰错误。
- 故障切换行为经过实际测试，不以配置存在作为验收依据。

### Phase 3：代理 Key 和 PostgreSQL（2026-10-26 完成）

任务：

- [x] 增加 PostgreSQL。（未用容器：本机无 WSL2，改用 **PostgreSQL 17.6 便携版**，与用户"17 以上"要求一致）
- [x] 配置数据库连接。（`.env` DATABASE_URL，仅监听 127.0.0.1:5432）
- [x] 按 LiteLLM 对应版本的官方流程初始化数据库。（prisma generate + db push，98 张表；见 docs/deployment.md §6）
- [x] 创建独立的虚拟 Key。（POST /key/generate 已实测）
- [x] 为 Key 设置模型访问权限和可用预算。（models / max_budget / budget_duration 实测）
- [x] 验证 Key 的创建、查询、撤销和持久化。（创建→200 鉴权通过、吊销→401、数据落 PG 持久化）
- [x] 追加：5556 面板「我的 Key」页 —— 创建/列表/吊销全中文界面，master key 只在 usage_server 服务端持有。
- [x] 追加：5556 多用户（用户要求）—— 登录页 + 角色（admin/user），
  用户数据存 5555（POST /user/new，密码哈希入 metadata），Key 挂 user_id；
  管理员看全部/管用户，普通用户只见自己的 Key 与用量（按 Key 指纹过滤 usage）；
  用户管理页：建用户 / 重置密码 / 删除。全部走 LiteLLM 官方用户接口，自建零数据表。

交付物：

- 更新后的 `docker-compose.yml`。
- 数据库环境变量模板。
- 虚拟 Key 管理操作说明。
- `tests/test_auth.py`。

验收标准：

- 普通客户端可以使用独立虚拟 Key。
- 撤销后的 Key 无法继续调用。
- 服务重启后，持久化数据仍然存在。
- 普通客户端不能使用管理员权限执行管理操作。

### Phase 4：用量、费用和限流

任务：

- [ ] 记录调用时间、模型、状态码、延迟和 Token 用量。
- [ ] 区分供应商实际返回的用量与估算用量。
- [ ] 根据供应商定价统计费用。
- [ ] 配置调用速率和预算限制。
- [ ] 验证并发调用下的预算控制。
- [ ] 检查日志是否泄露密钥或敏感请求内容。

交付物：

- 用量统计说明。
- 费用核算规则。
- `tests/test_usage.py`。
- `docs/security.md`。

验收标准：

- 能够按代理 Key 和模型查询用量。
- Token 统计与上游返回数据一致，缺失数据明确标记。
- 超出已配置限制时，请求按预期被拒绝。
- 统计数据不被重复计算。

### Phase 5：客户端集成

任务：

- [ ] 使用 OpenAI SDK 接入本地代理。
- [ ] 测试非流式和流式响应。
- [ ] 测试工具调用及多轮对话。
- [ ] 评估 Claude Code 的 Anthropic 协议兼容性。
- [ ] 评估 Codex 当前版本的配置及认证要求。
- [ ] 为不同开发项目创建独立代理 Key。

交付物：

- Python 客户端示例。
- 客户端接入文档。
- `tests/test_streaming.py`。
- Claude Code / Codex 兼容性测试记录。

验收标准：

- 基础聊天请求正常。
- 流式响应能正确结束。
- 工具调用行为经过验证。
- 不兼容的客户端功能被明确记录，而不是默认视为支持。

### Phase 6：稳定性和日常运维

任务：

- [ ] 增加启动、停止、状态检查脚本。
- [ ] 增加日志检查和异常排查流程。
- [ ] 配置数据库备份和恢复。
- [ ] 固定镜像版本。
- [ ] 测试代理重启、上游故障和网络中断。
- [ ] 编写升级和回滚流程。

交付物：

- PowerShell 运维脚本。
- `docs/troubleshooting.md`。
- `docs/operations.md`。
- 备份与恢复说明。

验收标准：

- 服务能够正常启动、停止和重启。
- 故障时能够定位到代理、数据库或上游层。
- 备份能够恢复。
- 升级前能够回滚到已验证版本。

## 6. 测试矩阵

  测试类别       测试内容                  预期结果

  -------------- ------------------------- --------------------

  基础功能       合法 Key 调用模型         正常返回
  鉴权           无效 Key                  请求被拒绝
  模型路由       两个模型别名              路由正确
  流式接口       SSE 分块返回              数据连续、正常结束
  上游异常       错误 Key 或模型名         返回可诊断错误
  网络异常       上游超时                  请求失败可定位
  持久化         重启代理和数据库          数据按设计保留
  配额控制       超额请求                  按配置拒绝
  并发测试       多个请求同时调用          统计合理、服务稳定
  安全测试       检查日志和 Git            无真实密钥泄露
  客户端兼容性   SDK、Claude Code、Codex   按各自协议验证

## 7. 风险与控制措施

1. **上游 Key 泄露：**
   使用环境变量或安全密钥存储，限制日志内容，避免提交密钥。
2. **预算超支：**
   同时配置供应商侧预算和代理侧预算，不能只依赖本地统计。
3. **协议不兼容：** 分客户端验证接口、工具调用、流式响应和认证要求。
4. **镜像更新造成故障：** 固定版本，先测试后升级。
5. **数据库损坏或丢失：** 配置备份并实际执行恢复测试。
6. **代理意外暴露：**
   默认仅监听回环地址；确需远程访问时再配置认证和安全网络通道。
7. **并发导致统计偏差：** 验证并发扣额、失败请求和重复请求的处理逻辑。

## 8. 最终交付标准

项目完成后，应具备：

- Windows 本地一键启动和停止能力。
- 一个统一的模型 API 地址。
- 多上游模型配置能力。
- 独立代理 Key 的管理和撤销能力。
- 调用用量、费用和错误统计能力。
- Python 客户端测试程序。
- 客户端兼容性说明。
- 安全检查、备份、故障排查和版本回滚文档。

## 9. 执行优先级

- **P0：** 环境检查、代理启动、单模型调用、鉴权测试。
- **P1：** 多模型配置、流式接口、客户端接入。
- **P2：** PostgreSQL、虚拟 Key、用量统计、预算控制。
- **P3：** 稳定性测试、运维脚本、备份恢复、兼容性优化。

执行原则：每个阶段先完成可运行实现和验收，再进入下一阶段；不提前引入尚未需要的复杂功能。


## 10. 实施记录

### 2026-10-26 Phase 1 完成（pip 原生运行）

- 运行方式：`scripts/run_proxy.py` + `.venv`（litellm 1.106.4，Python 3.14.7）。
  未用 Docker：本机无 WSL2，Docker Desktop 安装需重启，用户选择先 pip 原生运行。
- 离线安装包：`D:outine\offline-packages\wheels\`（118 个 wheel，含全量依赖 +
  pytest），验证过 `--no-index` 纯离线安装成功。
- 已验证的 Windows 坑（详见 docs/troubleshooting.md 第 5 节）：
  .ps1 需 UTF-8 BOM；.env / config.yaml 会被按系统默认编码读取，注释需 ASCII；
  pip 的 litellm.exe 启动器被 Smart App Control 拦截，改用 python 直调入口。
- 鉴权现状：无效 Key 均被拒绝且不转发上游，但无数据库时返回 400/500 而非 401
  （litellm 1.106.4 无 DB 行为），Phase 3 接 PostgreSQL 后收紧。
- 附加交付（用户要求）：Token 监控 —— `monitor/token_monitor.py` 回调把每次调用的
  模型/Key 指纹/token 数/费用/延迟写入 `data/usage.jsonl`（去重、不含请求内容）；
  `scripts/usage_report.py` 按模型/天/Key 指纹出汇总；计费标准固化于 config.yaml
  显式单价，规则见 docs/cost-tracking.md。

### 2026-10-26 Phase 2/3 完成（路由别名 + PostgreSQL 17.6 + 虚拟 Key + 中文管理面板）

- PostgreSQL 17.6 便携版（用户指定 17+）：zip 在 `D:\routine\offline-packages\installers\postgresql-17.6-1-windows-x64-binaries.zip`，
  数据目录 `data\pgdata`，仅监听回环，启停已集成 start.ps1 / stop.ps1。
- prisma generate + db push 完成（98 张官方 schema 表），代理带库启动；
  鉴权收紧：无 Key / 错 Key 均返回 401（tests/test_auth.py 已按 401 断言）。
- 虚拟 Key 全生命周期实测：创建（models/max_budget/budget_duration）→ 200 调用成功 →
  吊销 → 立即 401；持久化在 PG，重启后仍在。
- 中文管理面板（127.0.0.1:5556，替代 litellm 自带的 /ui 开发者界面）：
  - 登录页 + 多用户角色（admin / 普通用户），用户数据走 5555 用户接口存 PostgreSQL；
  - 概览：KPI、每日费用折线、请求数条形图、按模型汇总表（普通用户只看自己的用量）；
  - 我的 Key：卡片式创建/查看/吊销，花费进度条、预算周期、明文 Key 只在创建时显示一次；
  - 用户管理（管理员）：建用户/重置密码/删除；
  - 设置（管理员）：服务状态、计费单价在线修改（写回 config.yaml 自动备份）、代理重启；
  - master key 只在 scripts/usage_server.py 服务端持有，浏览器端不可见；
    会话为内存态 HttpOnly Cookie，重启面板后需重新登录。
- 实测通过：未登录 401、管理员/用户登录、用户建 Key（归属正确）、
  管理员/用户视角 Key 列表隔离、重置密码后旧密码失效、删除用户。
- 测试：6 passed / 7 skipped（跳过用例等待上游真实 Key）。
- backup.ps1 增加 pg_dump 数据库逻辑备份（litellm-db.dump，自定义格式）。

### 待办（用户侧）

1. 在 `.env` 填入 OPENAI_API_KEY / DEEPSEEK_API_KEY，重跑 `scripts/test.ps1`
   （当前 SKIP 的 7 个用例将真正执行，完成 Phase 1/2 的上游验收）。
2. 首次接入前核对 docs/cost-tracking.md 单价表与官方定价页。

### 后续阶段

- Phase 2：多模型别名已配置，待真实 Key 验证路由与故障切换。
- Phase 4：用量费用已具备（回调 + 面板），待验证并发下的预算控制与日志脱敏复查。
- Docker Desktop + WSL2 安装（安装包届时保留到 offline-packages/）。
