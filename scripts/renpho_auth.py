#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = ["pycryptodome>=3.15"]
# ///
"""renpho-api-generic-logic-skill: RENPHO認証情報のセットアップと疎通確認。

使い方:
  uv run scripts/renpho_auth.py init    # 起動フォルダの.envにRENPHO_*の空の行を足し、書き込み手順を案内する
  uv run scripts/renpho_auth.py check   # 疎通と取得件数を確認する(保存済みtokenがあればログインしない)

`init`はメールアドレス・パスワードを**受け取らない**。雛形を作るだけで、実際の値は
ユーザー自身がエディタで書き込む(Claudeにパスワードを渡さないため。references/credentials.md)。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from renpho_api import RenphoError  # noqa: E402
from renpho_env import KEYS, env_path, load, open_client, read_file, token_issued_at, write  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def cmd_init(path):
    creds = load(path)
    # .env は他のスキルと共有なので、無い RENPHO_* の行だけを空で足す。ある行は書き換えない。
    missing = [k for k in KEYS if k not in read_file(path)]
    if missing:
        write({k: "" for k in missing}, path)
        print(f"雛形の行を足しました: {path}({', '.join(missing)})")
    else:
        print(f"既にあります: {path}")
    print(f"  RENPHO_EMAIL    = {creds['email'] or '(未設定)'}")
    print(f"  RENPHO_PASSWORD = {'(設定済み)' if creds['password'] else '(未設定)'}")

    if not (creds["email"] and creds["password"]):
        print()
        print("次の手順で、ユーザー自身が値を書き込んでください(Claudeには渡さないこと)。")
        print()
        print(f"  vi {path}")
        print()
        print("  RENPHO_EMAIL=<RENPHO Healthアプリのメールアドレス>")
        print("  RENPHO_PASSWORD=<そのパスワード>")
        print()
        print("書き込んだら `uv run scripts/renpho_auth.py check` で疎通を確認します。")


def cmd_check(path):
    # 疎通確認のたびにログインするとスマホアプリがログアウトされるので、
    # 保存済みトークンがあればそれで確かめる(references/session.md)。
    client = open_client(path, log=lambda m: print(f"  {m}"), debug=True)
    print("保存済みトークンで確認中..." if client.token else "ログイン中...")
    client.ensure_auth()
    print(f"  OK  user_id={client.user_id}")
    print(f"      測定テーブル={client.measurement_table()}")
    issued = token_issued_at(client.token)
    print(f"      tokenの発行={issued.isoformat(timespec='minutes') if issued else '(読めない)'}"
          f"{'(この実行でログインした)' if client.logged_in else ''}")

    info = client.get_device_info()
    if info:
        scales = info.get("scale") or info.get("scales") or []
        print(f"  紐付いている体組成計: {len(scales)}件")

    print("測定データを取得中...")
    records = client.get_measurements()
    print(f"  取得件数: {len(records)}件")
    if records:
        latest = records[0]
        print(f"  最新レコードのフィールド数: {len(latest)}")
        print("  ※ 実際に入っている項目はcheckでは表示しない(probe_fields.pyで確認する)")


def main():
    path = env_path()
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "init":
        cmd_init(path)
    elif cmd == "check":
        cmd_check(path)
    else:
        sys.exit("Usage: renpho_auth.py {init|check}")


if __name__ == "__main__":
    try:
        main()
    except RenphoError as e:
        sys.exit(f"Error: {e}")
