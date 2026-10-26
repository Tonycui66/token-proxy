"""LiteLLM Proxy 启动入口。

说明：不用 .venv\\Scripts\\litellm.exe（pip 生成的启动器会被 Windows
应用控制策略拦截），而是用 python.exe 直接调用 litellm:run_server。
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# 本地请求不走系统代理（否则 prisma 引擎/本地健康检查会被 Clash 拦截 502）
os.environ.setdefault("NO_PROXY", "localhost,127.0.0.1")
os.environ.setdefault("no_proxy", "localhost,127.0.0.1")

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")

from litellm import run_server  # noqa: E402

run_server(
    [
        "--config", str(ROOT / "config" / "config.yaml"),
        "--host", os.environ.get("LITELLM_HOST", "127.0.0.1"),
        "--port", str(os.environ.get("LITELLM_PORT", "5555")),
        # 关闭遥测上报
        "--telemetry", "False",
    ]
)
