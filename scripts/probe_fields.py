#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = ["pycryptodome>=3.15"]
# ///
"""renpho-api-generic-logic-skill: RENPHOが実際に返してくる項目を調べる(読むだけ)。

使い方:
  uv run scripts/probe_fields.py [--limit 3] [--json out.json]

記録先の列の設計を、想像ではなく**実データ**から決めるためのスクリプト。
機種によって返す項目が違う(心拍・心臓指数は心拍センサ搭載機のみ等)ため、
記録先に列を足す前に必ずこれで確認する(references/field-units.md)。どこにも書き込まない。

保存済みtokenがあればログインしない(references/session.md)。
"""
import argparse
import json
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from renpho_api import RenphoError  # noqa: E402
from renpho_env import open_client  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=3, help="内容を表示するレコード数(既定3)")
    ap.add_argument("--json", help="全レコードをこのパスにJSONで保存する")
    args = ap.parse_args()

    client = open_client()
    client.ensure_auth()
    records = client.get_measurements()

    print(f"user_id={client.user_id} / テーブル={client.measurement_table()}")
    print(f"取得件数: {len(records)}件")
    if not records:
        print("レコードが0件です。RENPHO Healthアプリ側に測定履歴があるか確認してください。")
        return

    # 全レコードを走査し、「実際に値が入っている項目」だけを拾う。
    # 1件目だけを見ると、その日たまたま欠測だった項目を見落とす。
    present = Counter()
    for r in records:
        for k, v in r.items():
            if v not in (None, "", 0, "0"):
                present[k] += 1

    print(f"\n=== 値が入っている項目({len(present)}種) ===")
    print(f"{'項目':<28}{'件数':>6}  {'最新値'}")
    latest = records[0]
    for key, count in present.most_common():
        print(f"{key:<28}{count:>6}  {str(latest.get(key))[:40]}")

    always_empty = sorted(set().union(*(r.keys() for r in records)) - set(present))
    if always_empty:
        print(f"\n=== 常に空の項目({len(always_empty)}種・記録先に列を作らない) ===")
        print("  " + ", ".join(always_empty))

    print(f"\n=== 最新{args.limit}件 ===")
    for r in records[: args.limit]:
        print(json.dumps({k: v for k, v in r.items() if k in present},
                         ensure_ascii=False, indent=2))

    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(records, f, ensure_ascii=False, indent=2)
        print(f"\n全{len(records)}件を保存しました: {args.json}")


if __name__ == "__main__":
    try:
        main()
    except RenphoError as e:
        sys.exit(f"Error: {e}")
