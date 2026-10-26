"""聊天接口：需要真实上游 Key，未填写时跳过。"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))
from conftest import HAS_UPSTREAM_KEY, post  # noqa: E402

pytestmark = pytest.mark.skipif(
    not HAS_UPSTREAM_KEY, reason="未配置上游 API Key（.env 中 OPENAI_API_KEY / DEEPSEEK_API_KEY 为空）"
)


def test_chat_basic():
    r = post(
        "/v1/chat/completions",
        {
            "model": "chat",
            "messages": [{"role": "user", "content": "回复两个字：成功"}],
            "max_tokens": 16,
        },
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["choices"][0]["message"]["content"]
    # 用量统计存在（Phase 4 会进一步核对来源）
    assert "usage" in data


def test_chat_wrong_model_name_clear_error():
    r = post(
        "/v1/chat/completions",
        {
            "model": "no-such-model-xyz",
            "messages": [{"role": "user", "content": "hi"}],
            "max_tokens": 8,
        },
    )
    assert r.status_code in (400, 404)
    # 错误信息应可诊断：包含模型名
    assert "no-such-model-xyz" in r.text
