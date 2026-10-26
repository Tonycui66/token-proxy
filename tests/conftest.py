"""测试公共工具：读取 .env、服务地址、鉴权头。"""
import os
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent

# trust_env=False：忽略系统代理（本机开启 Clash 类代理时，
# httpx 会把 127.0.0.1:5555 的请求也转给代理导致 502），测试必须直连本机。
CLIENT = httpx.Client(trust_env=False, timeout=60)


def load_env() -> dict:
    env = {}
    env_file = ROOT / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
    return env


ENV = load_env()
BASE_URL = f"http://{ENV.get('LITELLM_HOST', '127.0.0.1')}:{ENV.get('LITELLM_PORT', '5555')}"
MASTER_KEY = ENV.get("LITELLM_MASTER_KEY", "")
HEADERS = {"Authorization": f"Bearer {MASTER_KEY}"} if MASTER_KEY else {}

# 上游 Key 均未填写时，依赖真实上游的用例应跳过而不是失败
HAS_UPSTREAM_KEY = bool(ENV.get("OPENAI_API_KEY") or ENV.get("DEEPSEEK_API_KEY"))


def get(path: str, **kwargs) -> httpx.Response:
    return CLIENT.get(f"{BASE_URL}{path}", **kwargs)


def post(path: str, json: dict, headers: dict | None = None) -> httpx.Response:
    return CLIENT.post(f"{BASE_URL}{path}", json=json, headers=headers or HEADERS)
