"""Token 用量监控回调（LiteLLM CustomLogger）。

每次调用结束（成功或失败）向 data/usage.jsonl 追加一行 JSON：
时间、模型别名、实际上游模型、Key 指纹、token 数、费用(USD)、延迟、状态。
不记录消息内容与完整请求体，避免敏感信息落盘（见 docs/security.md）。

费用使用 config.yaml 中显式固定的单价（见 docs/cost-tracking.md）。
在 config.yaml 中通过 litellm_settings.callbacks: monitor.token_monitor.monitor_instance 注册。
"""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from litellm.integrations.custom_logger import CustomLogger

ROOT = Path(__file__).resolve().parent.parent
USAGE_FILE = ROOT / "data" / "usage.jsonl"


def _key_fingerprint(kwargs) -> str:
    """Key 只记 sha256 前 8 位指纹，绝不落盘明文。"""
    try:
        req = kwargs.get("litellm_params", {}).get("proxy_server_request") or {}
        auth = (req.get("headers") or {}).get("authorization", "") or ""
        token = auth.split(" ", 1)[-1].strip()
        if token:
            return hashlib.sha256(token.encode()).hexdigest()[:8]
    except Exception:
        pass
    return "unknown"


# litellm 对同一次调用可能同时触发 sync 和 async 回调，这里去重，保证统计不重复计
_seen: set[tuple[str, str]] = set()
_SEEN_MAX = 100000


def _dedupe_key(record: dict) -> tuple[str, str]:
    return (str(record.get("call_id")), str(record.get("status")))


def _base_record(kwargs, status: str) -> dict:
    slog = kwargs.get("standard_logging_object") or {}
    usage = (slog.get("response") or {}).get("usage") if isinstance(slog.get("response"), dict) else None
    prompt_t = slog.get("prompt_tokens")
    completion_t = slog.get("completion_tokens")
    return {
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "status": status,
        "model": slog.get("model_group") or kwargs.get("model"),
        "upstream_model": slog.get("model") or kwargs.get("litellm_params", {}).get("model"),
        "key_fp": (slog.get("metadata", {}).get("user_api_key_hash") or _key_fingerprint(kwargs))[:8],
        "prompt_tokens": prompt_t,
        "completion_tokens": completion_t,
        "total_tokens": slog.get("total_tokens"),
        # usage_source: upstream=供应商实际返回；missing=上游未返回用量（费用不可核算）
        "usage_source": "upstream" if prompt_t is not None else "missing",
        "cost_usd": slog.get("response_cost"),
        "latency_ms": int(
            (slog.get("end_time") - slog.get("start_time")).total_seconds() * 1000
        ) if slog.get("start_time") and slog.get("end_time") else None,
        "call_id": slog.get("id"),
    }


def _append(record: dict) -> None:
    dk = _dedupe_key(record)
    if dk in _seen:
        return
    _seen.add(dk)
    if len(_seen) > _SEEN_MAX:
        _seen.clear()
        _seen.add(dk)
    USAGE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with USAGE_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


class TokenMonitor(CustomLogger):
    def log_success_event(self, kwargs, response_obj, start_time, end_time):
        _append(_base_record(kwargs, "success"))

    async def async_log_success_event(self, kwargs, response_obj, start_time, end_time):
        _append(_base_record(kwargs, "success"))

    def log_failure_event(self, kwargs, response_obj, start_time, end_time):
        record = _base_record(kwargs, "failure")
        exc = kwargs.get("exception") or kwargs.get("orig_exception")
        record["error_type"] = type(exc).__name__ if exc else "unknown"
        _append(record)

    async def async_log_failure_event(self, kwargs, response_obj, start_time, end_time):
        record = _base_record(kwargs, "failure")
        exc = kwargs.get("exception") or kwargs.get("orig_exception")
        record["error_type"] = type(exc).__name__ if exc else "unknown"
        _append(record)


monitor_instance = TokenMonitor()
