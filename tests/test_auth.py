"""鉴权：无 Key / 错误 Key 必须被 401 拒绝（PostgreSQL 已接入，虚拟 Key 生效）。"""
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from conftest import post  # noqa: E402

BODY = {"model": "chat", "messages": [{"role": "user", "content": "hi"}]}


def test_missing_key_rejected():
    r = post("/v1/chat/completions", BODY, headers={})
    assert r.status_code == 401, f"应 401，实际 {r.status_code}: {r.text[:200]}"


def test_wrong_key_rejected():
    r = post(
        "/v1/chat/completions",
        BODY,
        headers={"Authorization": f"Bearer sk-fake-{uuid.uuid4().hex}"},
    )
    assert r.status_code == 401, f"应 401，实际 {r.status_code}: {r.text[:200]}"


def test_wrong_key_message_diagnosable():
    r = post(
        "/v1/chat/completions",
        BODY,
        headers={"Authorization": "Bearer sk-fake-diagnostic-check"},
    )
    assert r.status_code == 401
    assert "error" in r.text.lower()
