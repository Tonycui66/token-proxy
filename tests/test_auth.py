"""鉴权：无 Key / 错误 Key 必须被拒绝。

当前（未接 PostgreSQL）litellm 1.106.4 行为：
- 无 Key           -> 500（litellm 抛裸 Exception）
- 错误 Key         -> 400 {"No connected db."}
两者都不会把请求转发到上游，即"被拒绝"成立；
Phase 3 接入数据库后应收紧为 401/403，届时更新本文件。
"""
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from conftest import post  # noqa: E402

BODY = {"model": "chat", "messages": [{"role": "user", "content": "hi"}]}


def _assert_rejected(r):
    assert r.status_code >= 400, f"应被拒绝，实际 {r.status_code}: {r.text[:200]}"
    assert r.status_code != 200
    # 拒绝响应必须可诊断（包含错误结构），而不是静默或空响应
    assert "error" in r.text.lower() or "internal server error" in r.text.lower()


def test_missing_key_rejected():
    r = post("/v1/chat/completions", BODY, headers={})
    _assert_rejected(r)


def test_wrong_key_rejected():
    r = post(
        "/v1/chat/completions",
        BODY,
        headers={"Authorization": f"Bearer sk-fake-{uuid.uuid4().hex}"},
    )
    _assert_rejected(r)


def test_wrong_key_message_diagnosable():
    r = post(
        "/v1/chat/completions",
        BODY,
        headers={"Authorization": "Bearer sk-fake-diagnostic-check"},
    )
    _assert_rejected(r)
    assert "error" in r.text.lower()
