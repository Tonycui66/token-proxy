"""用量统计：调用后 usage.jsonl 应产生记录，费用与 token 字段齐备。

依赖真实上游 Key；未填写时跳过。费用口径见 docs/cost-tracking.md。
"""
import json
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))
from conftest import HAS_UPSTREAM_KEY, post  # noqa: E402

USAGE_FILE = Path(__file__).resolve().parent.parent / "data" / "usage.jsonl"

pytestmark = pytest.mark.skipif(
    not HAS_UPSTREAM_KEY, reason="未配置上游 API Key（.env 中 OPENAI_API_KEY / DEEPSEEK_API_KEY 为空）"
)


def test_usage_recorded_after_call():
    r = post(
        "/v1/chat/completions",
        {
            "model": "chat",
            "messages": [{"role": "user", "content": "hi"}],
            "max_tokens": 8,
        },
    )
    assert r.status_code == 200, r.text
    data = r.json()
    usage = data.get("usage") or {}
    if not usage.get("prompt_tokens"):
        pytest.skip("上游未返回 usage，无法核对统计（应标记 usage_source=missing）")

    time.sleep(2)  # 回调异步落盘
    assert USAGE_FILE.exists(), "usage.jsonl 未生成"
    call_id = data.get("id")
    lines = [json.loads(x) for x in USAGE_FILE.read_text(encoding="utf-8").splitlines() if x.strip()]
    mine = [x for x in lines if x.get("call_id") == call_id]
    assert mine, f"未找到本次调用({call_id})的记录"
    rec = mine[-1]
    # 统计不重复：同一 call_id 只记一次成功
    assert sum(1 for x in mine if x["status"] == "success") == 1
    # token 数与上游一致
    assert rec["prompt_tokens"] == usage["prompt_tokens"]
    assert rec["completion_tokens"] == usage["completion_tokens"]
    assert rec["usage_source"] == "upstream"
    # 费用按固定单价可核算
    assert isinstance(rec["cost_usd"], (int, float)) and rec["cost_usd"] >= 0
