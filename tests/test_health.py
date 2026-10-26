"""健康检查：服务存活、模型列表可访问。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from conftest import BASE_URL, HEADERS, get  # noqa: E402


def test_liveliness():
    r = get("/health/liveliness")
    assert r.status_code == 200
    assert r.json() == "I'm alive!"


def test_models_list_requires_auth():
    # 未带 Key 不应看到模型列表（无 DB 阶段返回 500 纯文本，Phase 3 接库后收紧为 401 JSON）
    r = get("/v1/models")
    assert r.status_code >= 400
    assert '"data"' not in r.text


def test_models_list_with_master_key():
    r = get("/v1/models", headers=HEADERS)
    assert r.status_code == 200
    names = {m["id"] for m in r.json()["data"]}
    # 配置中的别名都应出现
    for expected in ("gpt-4o-mini", "deepseek-chat", "chat"):
        assert expected in names, f"缺少模型别名 {expected}，实际: {names}"
