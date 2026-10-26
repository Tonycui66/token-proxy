"""Token 用量/费用汇总报告。

用法:
  python scripts/usage_report.py                 # 全部汇总（按模型）
  python scripts/usage_report.py --by-day        # 按天汇总
  python scripts/usage_report.py --by-key        # 按 Key 指纹汇总
  python scripts/usage_report.py --last 7        # 只统计最近 7 天
数据源: data/usage.jsonl（由 monitor/token_monitor.py 写入）。
费用为代理侧核算口径，见 docs/cost-tracking.md。
"""
import argparse
import json
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
USAGE_FILE = ROOT / "data" / "usage.jsonl"


def load_records(days: int | None):
    if not USAGE_FILE.exists():
        return []
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)) if days else None
    records = []
    for line in USAGE_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        if cutoff and (r.get("ts", "") < cutoff.date().isoformat()):
            continue
        records.append(r)
    return records


def _fmt_cost(v):
    return f"${v:.6f}" if isinstance(v, (int, float)) else "$0.000000(usage缺失)"


def summarize(records, keyfunc, title):
    groups = defaultdict(lambda: {"reqs": 0, "fails": 0, "in": 0, "out": 0, "cost": 0.0, "missing": 0})
    for r in records:
        g = groups[keyfunc(r)]
        g["reqs"] += 1
        if r.get("status") != "success":
            g["fails"] += 1
        pt, ct = r.get("prompt_tokens"), r.get("completion_tokens")
        if pt is None or ct is None:
            g["missing"] += 1
        else:
            g["in"] += pt
            g["out"] += ct
        c = r.get("cost_usd")
        if isinstance(c, (int, float)):
            g["cost"] += c
    print(f"\n== {title} ==")
    if not groups:
        print("  （暂无数据）")
        return
    hdr = f"{'分组':<28}{'请求':>6}{'失败':>6}{'输入tok':>12}{'输出tok':>12}{'费用':>16}"
    print(hdr)
    print("-" * len(hdr))
    for k, g in sorted(groups.items()):
        print(f"{k:<28}{g['reqs']:>6}{g['fails']:>6}{g['in']:>12}{g['out']:>12}{_fmt_cost(g['cost']):>16}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--by-day", action="store_true", help="按天汇总")
    ap.add_argument("--by-key", action="store_true", help="按 Key 指纹汇总")
    ap.add_argument("--last", type=int, default=None, help="只统计最近 N 天")
    args = ap.parse_args()

    records = load_records(args.last)
    if not records:
        print(f"无记录（{USAGE_FILE} 不存在或为空）。调用一次模型后重试。")
        return 0

    summarize(records, lambda r: r.get("model", "?"), "按模型汇总")
    if args.by_day:
        summarize(records, lambda r: r.get("ts", "?")[:10], "按天汇总")
    if args.by_key:
        summarize(records, lambda r: r.get("key_fp", "?"), "按 Key 指纹汇总")
    return 0


if __name__ == "__main__":
    sys.exit(main())
