"""Token 中转控制台（多用户管理面板）服务。

只监听 127.0.0.1:5556，全部数据通过 5555（LiteLLM 管理 API + PostgreSQL）存取：
  GET  /                  -> monitor/dashboard.html
  POST /api/login         -> 登录（管理员 = .env 的 UI_USERNAME/UI_PASSWORD；
                             普通用户 = 5555 用户表 metadata.panel_password_hash）
  GET  /api/me            -> 当前登录状态与角色（admin / user）
  POST /api/logout        -> 退出登录
  GET  /api/usage         -> 用量记录（普通用户只返回自己 Key 的记录）
  GET  /api/prices        -> config.yaml 中各部署的显式单价（USD/1M token）
  POST /api/prices        -> 修改单价（写入 config.yaml，先备份为 config.yaml.bak）
  GET  /api/status        -> 代理运行状态、上游 Key 配置状态
  GET  /api/keys          -> Key 列表（管理员=全部；用户=只看自己的）
  POST /api/keys/create   -> 创建虚拟 Key（归属当前登录用户，明文只返回一次）
  POST /api/keys/delete   -> 吊销虚拟 Key
  POST /api/debug-chat    -> 调试页试聊（自动用当前用户名下的「面板调试」Key 调 5555）
  GET  /api/users         -> 用户列表（仅管理员）
  POST /api/users/create  -> 建用户（仅管理员，POST /user/new + 密码哈希入 metadata）
  POST /api/users/reset-password -> 重置用户密码（仅管理员，POST /user/update）
  POST /api/users/delete  -> 删除用户（仅管理员，POST /user/delete）
  POST /api/restart-proxy -> 通过 scripts/stop.ps1 + start.ps1 重启代理

  服务端持有 LITELLM_MASTER_KEY 调 5555 管理接口，浏览器端永远接触不到 master key；
  会话为内存态 HttpOnly cookie（SameSite=Strict），重启面板后需重新登录。

用法: .venv/Scripts/python.exe scripts/usage_server.py
"""
import hashlib
import json
import re
import secrets
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DASHBOARD = ROOT / "monitor" / "dashboard.html"
USAGE_FILE = ROOT / "data" / "usage.jsonl"
CONFIG_FILE = ROOT / "config" / "config.yaml"
ENV_FILE = ROOT / ".env"

# 面板登录会话（内存态，重启面板后需重新登录）
SESSIONS = {}  # sid -> {"user": str, "role": "admin" | "user"}


def load_usage():
    if not USAGE_FILE.exists():
        return []
    out = []
    for line in USAGE_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def read_prices():
    """解析 config.yaml：返回 [(model_name, upstream, input_per_m, output_per_m), ...]。

    单价缺失的部署以 null 表示（设置页会提示需补齐）。
    """
    text = CONFIG_FILE.read_text(encoding="ascii")
    prices = []
    cur = None
    for line in text.splitlines():
        m = re.match(r"\s*- model_name:\s*(\S+)", line)
        if m:
            cur = {"model": m.group(1), "upstream": None, "in": None, "out": None}
            prices.append(cur)
            continue
        if cur is None:
            continue
        m = re.match(r"\s*model:\s*(\S+)", line)
        if m and cur["upstream"] is None:
            cur["upstream"] = m.group(1)
        m = re.match(r"\s*input_cost_per_token:\s*([\d.eE+-]+)", line)
        if m:
            cur["in"] = round(float(m.group(1)) * 1e6, 6)
        m = re.match(r"\s*output_cost_per_token:\s*([\d.eE+-]+)", line)
        if m:
            cur["out"] = round(float(m.group(1)) * 1e6, 6)
    return prices


def write_prices(updates):
    """按 (model, upstream) 把新单价写回 config.yaml；缺失的行插到 model: 行之后。

    updates: [{"model":..., "upstream":..., "in_per_m":float, "out_per_m":float}, ...]
    返回 (成功数, 消息)。
    """
    wanted = {(u["model"], u["upstream"]): u for u in updates}
    lines = CONFIG_FILE.read_text(encoding="ascii").splitlines(keepends=True)
    out, cur, ok = [], None, 0
    for line in lines:
        m = re.match(r"(\s*)- model_name:\s*(\S+)", line)
        if m:
            cur = (m.group(2), None)
            out.append(line)
            continue
        if cur:
            m = re.match(r"(\s*)model:\s*(\S+)", line)
            if m and cur[1] is None:
                cur = (cur[0], m.group(2))
                out.append(line)
                u = wanted.get(cur)
                if u:
                    indent = m.group(1)
                    out.append(f"{indent}input_cost_per_token: {u['in_per_m'] * 1e-6:.8f}\n")
                    out.append(f"{indent}output_cost_per_token: {u['out_per_m'] * 1e-6:.8f}\n")
                    ok += 1
                continue
            # 已存在的单价行：若属于待更新部署则替换，否则原样保留
            if cur in wanted and re.match(r"\s*(input|output)_cost_per_token:", line):
                continue  # 已在插入时写好，跳过旧行
        out.append(line)
    if ok != len(wanted):
        return 0, f"仅匹配到 {ok}/{len(wanted)} 个部署，未做修改"
    backup = CONFIG_FILE.with_suffix(".yaml.bak")
    backup.write_text(CONFIG_FILE.read_text(encoding="ascii"), encoding="ascii")
    CONFIG_FILE.write_text("".join(out), encoding="ascii")
    return ok, f"已更新 {ok} 个部署的单价（备份: {backup.name}），需重启代理生效"


def read_env_status():
    st = {"openai_key": False, "deepseek_key": False}
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
            m = re.match(r"^(OPENAI_API_KEY|DEEPSEEK_API_KEY)=(\S*)", line.strip())
            if m:
                st["openai_key" if m.group(1) == "OPENAI_API_KEY" else "deepseek_key"] = bool(m.group(2))
    return st


def proxy_alive():
    """直连检查代理健康（绕过系统代理，避免被 Clash 拦截本地请求）。"""
    try:
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open("http://127.0.0.1:5555/health/liveliness", timeout=3) as r:
            return r.status == 200
    except Exception:
        return False


def master_key():
    """从 .env 读取 LITELLM_MASTER_KEY（只在服务端持有，浏览器端不可见）。"""
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
            m = re.match(r"^LITELLM_MASTER_KEY=(\S+)", line.strip())
            if m:
                return m.group(1)
    return None


def proxy_api(method, path, payload=None):
    """以 master key 调用 LiteLLM 管理接口（直连回环，绕过系统代理）。

    返回 (json 或 None, 错误消息或 None)。
    """
    mk = master_key()
    if not mk:
        return None, "未在 .env 中找到 LITELLM_MASTER_KEY"
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(
        "http://127.0.0.1:5555" + path, data=data, method=method,
        headers={"Authorization": "Bearer " + mk, "Content-Type": "application/json"},
    )
    try:
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(req, timeout=30) as r:
            return json.loads(r.read().decode("utf-8")), None
    except urllib.error.HTTPError as e:
        try:
            detail = json.loads(e.read().decode("utf-8"))
        except Exception:
            detail = {}
        msg = detail.get("error", {}).get("message") if isinstance(detail.get("error"), dict) else None
        return None, msg or detail.get("detail") or ("HTTP %d" % e.code)
    except Exception as e:
        return None, str(e)


def list_keys():
    """聚合 /key/list + /key/info，返回面板需要的精简字段（管理员视角，全部 Key）。"""
    lst, err = proxy_api("GET", "/key/list")
    if err:
        return None, err
    keys = []
    for h in lst.get("keys", []):
        info, err = proxy_api("GET", "/key/info?key=" + h)
        if err:
            keys.append({"hash": h, "error": err})
            continue
        d = info.get("info", {})
        keys.append({
            "hash": h,
            "alias": d.get("key_alias") or "(未命名)",
            "mask": d.get("key_name"),
            "user_id": d.get("user_id"),
            "models": d.get("models") or [],
            "spend": d.get("spend") or 0.0,
            "max_budget": d.get("max_budget"),
            "budget_duration": d.get("budget_duration"),
            "budget_reset_at": d.get("budget_reset_at"),
            "status": d.get("status") or "active",
            "blocked": d.get("blocked"),
            "expires": d.get("expires"),
            "created_at": d.get("created_at"),
            "last_active": d.get("last_active"),
        })
    return keys, None


def _key_brief(d):
    """从 /key/info 或 /user/info 的 key 条目提取面板字段。"""
    return {
        "hash": d.get("token"),
        "alias": d.get("key_alias") or "(未命名)",
        "mask": d.get("key_name"),
        "user_id": d.get("user_id"),
        "models": d.get("models") or [],
        "spend": d.get("spend") or 0.0,
        "max_budget": d.get("max_budget"),
        "budget_duration": d.get("budget_duration"),
        "budget_reset_at": d.get("budget_reset_at"),
        "status": d.get("status") or "active",
        "blocked": d.get("blocked"),
        "expires": d.get("expires"),
        "created_at": d.get("created_at"),
        "last_active": d.get("last_active"),
    }


def list_user_keys(username):
    """普通用户视角：只返回自己名下的 Key（GET /user/info 自带 keys）。"""
    info, err = proxy_api("GET", "/user/info?user_id=" + urllib.parse.quote(username))
    if err:
        return None, err
    return [_key_brief(k) for k in (info.get("keys") or [])], None


def create_key(body, owner):
    """POST /key/generate。Key 归属到当前登录用户；明文 sk- 只在创建响应返回一次。"""
    payload = {"user_id": owner}
    if body.get("alias"):
        payload["key_alias"] = str(body["alias"])
    models = body.get("models") or []
    if models:
        payload["models"] = models
    if body.get("max_budget") is not None and body.get("max_budget") != "":
        try:
            payload["max_budget"] = float(body["max_budget"])
        except ValueError:
            return None, "预算必须是数字"
    if body.get("budget_duration"):
        payload["budget_duration"] = body["budget_duration"]
    if body.get("expires"):
        payload["expires"] = body["expires"]
    resp, err = proxy_api("POST", "/key/generate", payload)
    if err:
        return None, err
    return {"key": resp.get("key"), "mask": resp.get("key_name"), "alias": payload.get("key_alias")}, None


def delete_key(hash_):
    if not hash_ or not re.fullmatch(r"[0-9a-f]{16,}", hash_):
        return False, "无效的 Key 标识"
    resp, err = proxy_api("POST", "/key/delete", {"keys": [hash_]})
    if err:
        return False, err
    deleted = (resp or {}).get("deleted_keys") or []
    return hash_ in deleted, "已吊销" if hash_ in deleted else "代理未确认删除，请刷新列表核实"


def _env_cred(name):
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
            m = re.match(r"^%s=(\S*)" % name, line.strip())
            if m and m.group(1):
                return m.group(1)
    return None


def verify_login(username, password):
    """管理员：.env 的 UI_USERNAME/UI_PASSWORD；普通用户：5555 用户表的
    metadata.panel_password_hash（管理员在面板建用户时写入）。"""
    admin_user = _env_cred("UI_USERNAME") or "admin"
    admin_pw = _env_cred("UI_PASSWORD")
    if admin_pw and username == admin_user and password == admin_pw:
        return {"user": username, "role": "admin"}
    info, err = proxy_api("GET", "/user/info?user_id=" + urllib.parse.quote(username))
    if err or not isinstance(info, dict):
        return None
    ui = info.get("user_info") or {}
    stored = (ui.get("metadata") or {}).get("panel_password_hash")
    if stored and stored == hashlib.sha256(password.encode("utf-8")).hexdigest():
        role = "admin" if ui.get("user_role") == "proxy_admin" else "user"
        return {"user": username, "role": role}
    return None


def list_users():
    """管理员视角：用户列表（GET /user/list）。"""
    resp, err = proxy_api("GET", "/user/list?role=internal_user")
    if err:
        return None, err
    users = []
    for u in resp.get("users", []):
        users.append({
            "user_id": u.get("user_id"),
            "email": u.get("user_email"),
            "spend": u.get("spend") or 0.0,
            "max_budget": u.get("max_budget"),
            "role": u.get("user_role"),
            "created_at": u.get("created_at"),
        })
    return users, None


def create_user(body):
    """建用户（POST /user/new），密码哈希写进 metadata 供面板登录校验。"""
    uid = str(body.get("user_id") or "").strip()
    password = str(body.get("password") or "")
    if not re.fullmatch(r"[A-Za-z0-9_\-.]{2,32}", uid):
        return False, "用户名只能用 2-32 位字母/数字/._-"
    if len(password) < 6:
        return False, "初始密码至少 6 位"
    payload = {
        "user_id": uid,
        "user_email": uid + "@panel.local",
        "user_role": "internal_user",
        "metadata": {"panel_password_hash": hashlib.sha256(password.encode("utf-8")).hexdigest()},
    }
    if body.get("max_budget") not in (None, ""):
        try:
            payload["max_budget"] = float(body["max_budget"])
        except ValueError:
            return False, "预算必须是数字"
    _, err = proxy_api("POST", "/user/new", payload)
    if err:
        return False, err
    return True, "用户 %s 已创建" % uid


def reset_user_password(user_id, new_password):
    if len(new_password) < 6:
        return False, "新密码至少 6 位"
    _, err = proxy_api("POST", "/user/update", {
        "user_id": user_id,
        "metadata": {"panel_password_hash": hashlib.sha256(new_password.encode("utf-8")).hexdigest()},
    })
    if err:
        return False, err
    return True, "密码已重置"


def delete_user(user_id):
    if user_id == (_env_cred("UI_USERNAME") or "admin"):
        return False, "不能删除管理员账号"
    resp, err = proxy_api("POST", "/user/delete", {"user_ids": [user_id]})
    if err:
        return False, err
    # litellm 的 /user/delete 返回删除数量（int）或 {"deleted": [...]}，两种都兼容
    n = resp if isinstance(resp, int) else len((resp or {}).get("deleted") or (resp or {}).get("user_ids") or [])
    return n > 0, ("用户 %s 已删除" % user_id if n > 0 else "代理未确认删除，请刷新核实")


DEBUG_KEYS = {}  # user -> 「面板调试」Key 明文（内存态；面板重启后会重建一把）


def get_debug_key(user):
    """为调试页取当前用户的专属 Key：首次使用自动创建（花费归属该用户、受预算控制）。"""
    if user in DEBUG_KEYS:
        return DEBUG_KEYS[user], None
    resp, err = proxy_api("POST", "/key/generate", {"user_id": user, "key_alias": "面板调试"})
    if err:
        return None, err
    key = resp.get("key")
    DEBUG_KEYS[user] = key
    return key, None


def debug_chat(user, body):
    """以当前用户的调试 Key 调 5555 /v1/chat/completions，返回回复与用量。"""
    key, err = get_debug_key(user)
    if err:
        return None, err
    model = str(body.get("model") or "chat")
    payload = {
        "model": model,
        "messages": body.get("messages") or [{"role": "user", "content": "hi"}],
        "temperature": body.get("temperature", 0.7),
        "max_tokens": body.get("max_tokens", 1024),
    }
    req = urllib.request.Request(
        "http://127.0.0.1:5555/v1/chat/completions",
        data=json.dumps(payload).encode("utf-8"), method="POST",
        headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"},
    )
    started = time.monotonic()
    try:
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(req, timeout=120) as r:
            resp = json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            detail = json.loads(e.read().decode("utf-8"))
            msg = detail.get("error", {})
            msg = msg.get("message") if isinstance(msg, dict) else msg
        except Exception:
            msg = "HTTP %d" % e.code
        return None, str(msg)
    except Exception as e:
        return None, str(e)
    latency_ms = int((time.monotonic() - started) * 1000)
    choices = resp.get("choices") or []
    usage = resp.get("usage") or {}
    out = {
        "content": (choices[0].get("message") or {}).get("content") if choices else None,
        "model": resp.get("model"),
        "latency_ms": latency_ms,
        "prompt_tokens": usage.get("prompt_tokens"),
        "completion_tokens": usage.get("completion_tokens"),
    }
    # 用 config.yaml 显式单价核算该次费用（与 docs/cost-tracking.md 同一口径）
    for p in read_prices():
        if p["model"] == model and p["in"] is not None and p["out"] is not None:
            out["cost_usd"] = round(
                usage.get("prompt_tokens", 0) * p["in"] * 1e-6
                + usage.get("completion_tokens", 0) * p["out"] * 1e-6, 8)
            break
    return out, None


def filter_usage_for_user(rows, username):
    """普通用户只能看到自己名下 Key 的用量（按 Key 指纹 = token 哈希前 8 位过滤）。"""
    keys, err = list_user_keys(username)
    if err or keys is None:
        return []
    fps = {(k.get("hash") or "")[:8] for k in keys}
    return [r for r in rows if (r.get("key_fp") or "") in fps]


def restart_proxy():
    for script, timeout in (("stop.ps1", 60), ("start.ps1", 240)):
        try:
            r = subprocess.run(
                ["powershell", "-ExecutionPolicy", "Bypass", "-File", str(ROOT / "scripts" / script)],
                capture_output=True, text=True, timeout=timeout, cwd=str(ROOT),
            )
        except subprocess.TimeoutExpired:
            return False, f"{script} 超时（{timeout}s），请到 data/logs 排查"
        if r.returncode != 0:
            return False, f"{script} 失败: {(r.stderr or r.stdout)[-200:]}"
    return (proxy_alive(), "代理已重启" if proxy_alive() else "重启命令已执行，但健康检查未通过，请查看 data/logs")


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body: bytes, ctype: str, extra_headers=None):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for k, v in (extra_headers or []):
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _json(self, code, obj, extra_headers=None):
        self._send(code, json.dumps(obj, ensure_ascii=False).encode("utf-8"),
                   "application/json; charset=utf-8", extra_headers)

    def _session(self):
        for part in (self.headers.get("Cookie") or "").split(";"):
            part = part.strip()
            if part.startswith("panel_sid="):
                return SESSIONS.get(part.split("=", 1)[1])
        return None

    def _deny(self):
        self._json(401, {"ok": False, "message": "请先登录"})

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            self._send(200, DASHBOARD.read_bytes(), "text/html; charset=utf-8")
            return
        if self.path == "/api/me":
            s = self._session()
            self._json(200, {"logged_in": bool(s), "user": s and s["user"], "role": s and s["role"]})
            return
        s = self._session()
        if not s:
            self._deny()
            return
        if self.path == "/api/usage":
            rows = load_usage()
            if s["role"] != "admin":
                rows = filter_usage_for_user(rows, s["user"])
            self._json(200, rows)
        elif self.path == "/api/prices":
            self._json(200, read_prices())
        elif self.path == "/api/status":
            st = read_env_status()
            st["proxy_running"] = proxy_alive()
            self._json(200, st)
        elif self.path == "/api/keys":
            if s["role"] == "admin":
                keys, err = list_keys()
            else:
                keys, err = list_user_keys(s["user"])
            self._json(200 if keys is not None else 502,
                       keys if keys is not None else {"ok": False, "message": err})
        elif self.path == "/api/users" and s["role"] == "admin":
            users, err = list_users()
            self._json(200 if users is not None else 502,
                       users if users is not None else {"ok": False, "message": err})
        else:
            self._send(404, b"not found", "text/plain; charset=utf-8")

    def do_POST(self):
        if self.path == "/api/login":
            try:
                length = int(self.headers.get("Content-Length", 0))
                payload = json.loads(self.rfile.read(length) or b"{}")
            except Exception:
                self._json(400, {"ok": False, "message": "invalid JSON"})
                return
            sess = verify_login(str(payload.get("username", "")), str(payload.get("password", "")))
            if not sess:
                self._json(401, {"ok": False, "message": "用户名或密码不对"})
                return
            sid = secrets.token_urlsafe(24)
            SESSIONS[sid] = sess
            cookie = "panel_sid=%s; Path=/; HttpOnly; SameSite=Strict" % sid
            self._json(200, {"ok": True, "user": sess["user"], "role": sess["role"]},
                       [("Set-Cookie", cookie)])
            return
        if self.path == "/api/logout":
            for part in (self.headers.get("Cookie") or "").split(";"):
                part = part.strip()
                if part.startswith("panel_sid="):
                    SESSIONS.pop(part.split("=", 1)[1], None)
            self._json(200, {"ok": True})
            return
        s = self._session()
        if not s:
            self._deny()
            return
        try:
            length = int(self.headers.get("Content-Length", 0))
            payload = json.loads(self.rfile.read(length) or b"{}")
        except Exception:
            self._json(400, {"ok": False, "message": "invalid JSON"})
            return
        if self.path == "/api/prices":
            ok, msg = write_prices(payload.get("prices", []))
            self._json(200 if ok else 400, {"ok": bool(ok), "message": msg})
        elif self.path == "/api/keys/create":
            resp, err = create_key(payload, s["user"])
            self._json(200 if resp is not None else 400,
                       {"ok": resp is not None, "key": (resp or {}).get("key"),
                        "mask": (resp or {}).get("mask"), "message": err or "创建成功"})
        elif self.path == "/api/keys/delete":
            ok, msg = delete_key(str(payload.get("hash", "")))
            self._json(200 if ok else 400, {"ok": ok, "message": msg})
        elif self.path == "/api/debug-chat":
            out, err = debug_chat(s["user"], payload)
            self._json(200 if out is not None else 400,
                       dict(out or {}, ok=out is not None, message=err or ""))
        elif self.path == "/api/users/create" and s["role"] == "admin":
            ok, msg = create_user(payload)
            self._json(200 if ok else 400, {"ok": ok, "message": msg})
        elif self.path == "/api/users/reset-password" and s["role"] == "admin":
            ok, msg = reset_user_password(str(payload.get("user_id", "")), str(payload.get("password", "")))
            self._json(200 if ok else 400, {"ok": ok, "message": msg})
        elif self.path == "/api/users/delete" and s["role"] == "admin":
            ok, msg = delete_user(str(payload.get("user_id", "")))
            self._json(200 if ok else 400, {"ok": ok, "message": msg})
        elif self.path == "/api/restart-proxy":
            ok, msg = restart_proxy()
            self._json(200 if ok else 500, {"ok": ok, "message": msg})
        else:
            self._send(404, b"not found", "text/plain; charset=utf-8")

    def log_message(self, fmt, *args):
        sys.stderr.write("[usage-server] %s\n" % (fmt % args))


if __name__ == "__main__":
    host, port = "127.0.0.1", 5556
    print(f"Token 监控面板: http://{host}:{port}  (Ctrl+C 退出)")
    ThreadingHTTPServer((host, port), Handler).serve_forever()
