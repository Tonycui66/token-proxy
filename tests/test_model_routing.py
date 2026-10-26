"""模型路由：不同别名路由到正确上游。需要真实上游 Key，未填写时跳过。"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))
from conftest import ENV, HAS_UPSTREAM_KEY, post  # noqa: E402

pytestmark = pytest.mark.skipif(
    not HAS_UPSTREAM_KEY, reason="未配置上游 API Key（.env 中 OPENAI_API_KEY / DEEPSEEK_API_KEY 为空）"
)


def _provider_of(model: str) -> str | None:
    """从响应的 model 字段识别实际使用的上游。"""
    if "deepseek" in model.lower():
        return "deepseek"
    if "gpt" in model.lower():
        return "openai"
    return None


@pytest.mark.skipif(not ENV.get("OPENAI_API_KEY"), reason="OPENAI_API_KEY 未填写")
def test_route_openai_model():
    r = post(
        "/v1/chat/completions",
        {"model": "gpt-4o-mini", "messages": [{"role": "user", "content": "hi"}], "max_tokens": 8},
    )
    assert r.status_code == 200, r.text
    assert _provider_of(r.json()["model"]) == "openai"


@pytest.mark.skipif(not ENV.get("DEEPSEEK_API_KEY"), reason="DEEPSEEK_API_KEY 未填写")
def test_route_deepseek_model():
    r = post(
        "/v1/chat/completions",
        {"model": "deepseek-chat", "messages": [{"role": "user", "content": "hi"}], "max_tokens": 8},
    )
    assert r.status_code == 200, r.text
    assert _provider_of(r.json()["model"]) == "deepseek"


def test_route_alias_chat_responds():
    # 统一别名 chat：任一可用上游响应即通过（负载均衡目标不固定）
    r = post(
        "/v1/chat/completions",
        {"model": "chat", "messages": [{"role": "user", "content": "hi"}], "max_tokens": 8},
    )
    assert r.status_code == 200, r.text
    assert r.json()["choices"][0]["message"]["content"]
