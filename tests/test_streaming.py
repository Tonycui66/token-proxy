"""流式响应：SSE 分块返回且正常结束。需要真实上游 Key，未填写时跳过。"""
import sys
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).parent))
from conftest import BASE_URL, CLIENT, HAS_UPSTREAM_KEY, HEADERS  # noqa: E402

pytestmark = pytest.mark.skipif(
    not HAS_UPSTREAM_KEY, reason="未配置上游 API Key（.env 中 OPENAI_API_KEY / DEEPSEEK_API_KEY 为空）"
)


def test_streaming_ends_with_done():
    chunks = 0
    finished = False
    with CLIENT.stream(
        "POST",
        f"{BASE_URL}/v1/chat/completions",
        json={
            "model": "chat",
            "messages": [{"role": "user", "content": "从 1 数到 5"}],
            "max_tokens": 64,
            "stream": True,
        },
        headers=HEADERS,
    ) as resp:
        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers.get("content-type", "")
        for line in resp.iter_lines():
            if line.startswith("data: "):
                payload = line[6:]
                chunks += 1
                if payload.strip() == "[DONE]":
                    finished = True
    assert chunks > 1, "流式响应应包含多个分块"
    assert finished, "流式响应应以 [DONE] 结束"
