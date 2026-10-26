# 费用核算规则（计费标准）

> 本文档是计费标准的唯一权威来源。修改 `config/config.yaml` 中的单价时，
> 必须同步更新本文档，并在 Git 提交说明中注明"调价"。

## 1. 计费公式

每次调用的费用：

```text
费用(USD) = 输入 token 数 × input_cost_per_token
          + 输出 token 数 × output_cost_per_token
          + 缓存命中输入 token 数 × 缓存单价（如供应商支持）
```

- token 数取上游 API 实际返回的 `usage.prompt_tokens` / `usage.completion_tokens`，
  不使用本地估算值。
- 上游未返回 `usage` 的响应，费用记为 0 并标记 `usage_missing=true`，
  不会用估算值冒充实际值。

## 2. 单价表（固定于 config.yaml，单位 USD / 1M tokens）

| 模型别名            | 上游模型               | 输入单价 | 输出单价 | 单价来源与确认日期 |
|---------------------|------------------------|----------|----------|--------------------|
| gpt-4o-mini         | openai/gpt-4o-mini     | $0.15    | $0.60    | OpenAI 定价页，2026-10-26 填入 |
| gpt-4o              | openai/gpt-4o          | $2.50    | $10.00   | OpenAI 定价页，2026-10-26 填入 |
| deepseek-chat       | deepseek/deepseek-chat | $0.28    | $0.42    | DeepSeek 定价页（缓存未命中价），2026-10-26 填入 |
| deepseek-reasoner   | deepseek/deepseek-reasoner | $0.28 | $0.42   | DeepSeek 定价页，2026-10-26 填入 |
| chat（统一别名）    | 由路由决定             | 按实际命中的上游部署单价计 | 同左 | — |

⚠️ 单价必须以官方定价页为准，本表填写时的价格不代表后续不变：

- OpenAI: https://openai.com/api/pricing/
- DeepSeek: https://api-docs.deepseek.com/quick_start/pricing

**首次接入真实 Key 前，应人工核对上表与官方页面是否一致。**

## 3. 单价如何生效

`config/config.yaml` 每个 `litellm_params` 中显式声明：

```yaml
input_cost_per_token: 0.00000028   # $0.28 / 1M 输入
output_cost_per_token: 0.00000042  # $0.42 / 1M 输出
```

显式声明的原因：

1. LiteLLM 内置价目表随版本变化，依赖它会让费用统计不可复现。
2. 本项目要求"统计数据不被重复计算、来源可追溯"，显式单价 + Git 版本管理即可追溯任一天使用的单价。

## 4. 查询口径

- 按代理 Key 查询：`GET /key/info`（带该 Key）或管理端 `/spend`。
- 按模型查询：`GET /v1/models` 与 `/spend` 输出按 model 分组。
- Phase 3 接入 PostgreSQL 后，所有调用明细（时间、Key、模型、状态码、
  延迟、token 数、费用）持久化，可按日/Key/模型出报表。

## 5. 与上游账单的关系

- 本地费用统计是**代理侧核算**，用于预算控制和用量分析。
- 上游账单由供应商侧实际扣费为准；两者可能因缓存计价、批量折扣等存在差异。
- 控制超支风险必须同时依赖：代理侧预算限制（Phase 4）+ 供应商侧消费限额。
