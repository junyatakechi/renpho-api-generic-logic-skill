# renpho-api-generic-logic-skill

RENPHO Health（体組成計）の非公式APIをClaudeから扱うための、generic-logic スキル。
Claudeに頼むと、スマホアプリを何度もログアウトさせたり、単位を取り違えたりする落とし穴を避けながら、体組成計の測定を取得する。

中身は、RENPHOを使う人なら誰でも同じ答えになる一般的な判断（落とし穴とその避け方）と、RENPHO Health のAPIを呼ぶ道具。取った測定をどこに記録するかは決めない。
他のスキルがRENPHOの測定を取るときに、判断を聞き、道具を部品として使える。

- [SKILL.md](SKILL.md): 役割・判断の索引・道具の一覧・判断ファイルの形
- [references/](references/): 1判断1ファイル。どれも「求める材料・答え・値・道具・理由・却下した案・当てはまる範囲と限界」の形で書いてある
- [scripts/](scripts/): RENPHO Health のAPIを呼ぶ道具

## 先に知っておくこと

- **RENPHOに公式APIは無い。** このスキルが叩くのはRENPHO Healthアプリの内部APIで、予告なく壊れる。
- **RENPHOは、1つのアカウントに1つのセッションしか持てない。** 初めてログインしたとき（と、90日でtokenが切れたとき）に、スマホアプリがログアウトされる。以降は保存したtokenを使い回すので、ログインは起きない。
- **`.env` には、RENPHOアカウントのパスワードそのものが入る。** 他のサービスと使い回していないパスワードにする。
- RENPHO Health（青いアイコン）のアカウントで使う。旧Renphoアプリのアカウントでは動かない。

## 必要なもの

- [Claude Code](https://docs.claude.com/en/docs/claude-code/overview)
- RENPHOの体組成計と、RENPHO Healthアプリのアカウント
- Python 3.11以上と [uv](https://docs.astral.sh/uv/)

## インストール

スキルのフォルダでクローンする。フォルダ名はリポジトリ名のままでよい。

```bash
git clone https://github.com/junyatakechi/renpho-api-generic-logic-skill.git ~/.claude/skills/renpho-api-generic-logic-skill
```

特定のプロジェクトだけで使うなら、`<プロジェクト>/.claude/skills/` の中でクローンする。

## セットアップ

1. 認証情報の雛形を作る。プロジェクトのフォルダ直下（Claude Code を起動するフォルダ）の `.env` に `RENPHO_*` の空の行が足される（`.env` が無ければ作られ、他のキーの行はそのまま残る）。以下のコマンドは、どれもプロジェクトのフォルダで実行する。

   ```bash
   cd <プロジェクトのフォルダ>
   uv run ~/.claude/skills/renpho-api-generic-logic-skill/scripts/renpho_auth.py init
   ```

2. `.env` をエディタで開き、自分で値を書き込む。**パスワードはClaudeに渡さない。** キーの名前は同梱の `.env.example` と同じ。

   ```
   RENPHO_EMAIL=<RENPHO Healthのメールアドレス>
   RENPHO_PASSWORD=<そのパスワード>
   RENPHO_USER_ID=
   RENPHO_TOKEN=
   ```

   `RENPHO_USER_ID` と `RENPHO_TOKEN` は空でよい。初めてログインしたときに自動で保存される。`RENPHO_USER_ID` は、1つのメールアドレスに複数のアカウントが紐付いているときだけ指定する。

3. 疎通を確かめる。保存済みのtokenが無ければここで一度ログインし、スマホアプリがログアウトされる。

   ```bash
   uv run ~/.claude/skills/renpho-api-generic-logic-skill/scripts/renpho_auth.py check
   ```

## 使い方

Claudeに普段の言葉で頼むと、Claudeがこのスキルを読み込んで作業する。

| 頼み方 | Claudeがすること |
|---|---|
| 「RENPHOの認証を設定して」 | 雛形を作り、書き込む手順を案内する。パスワードは受け取らない |
| 「RENPHOに繋がるか確かめて」 | 保存済みのtokenで疎通と取得件数を確かめる |
| 「RENPHOが返す項目を調べて」 | 実際に値が入っている項目と、常に空の項目を出す |
| 「RENPHOのAPIが壊れた」 | 認証の失敗かプロトコルの破損かを見分け、どこを見て直すかを答える |

取った測定をNotionに記録するのは、アプリケーションスキル（renpho-collection-app-skill など）の担当。

## 他のスキルから使う

RENPHOの測定を取るスキルを作るときは、このスキルのモジュールを部品として使える。

```python
import os, sys
sys.path.insert(0, os.path.expanduser("~/.claude/skills/renpho-api-generic-logic-skill/scripts"))
from renpho_api import RenphoError
from renpho_env import open_client
import renpho_records

client = open_client(log=print)   # 保存済みtokenを使い、ログインしたら保存する
client.ensure_auth()
records = renpho_records.collapse_sessions(client.get_measurements())
rows = [renpho_records.normalize(r) for r in records]
```

| モジュール | 役割 |
|---|---|
| `renpho_api.py` | API通信。暗号化・ログイン・ページング・エラー |
| `renpho_env.py` | 認証情報の読み書きと、クライアントの入口 `open_client()` |
| `renpho_records.py` | レコード → 意味と単位の確定した値（測定時刻・同一測定の集約・欠測の除外） |

- `client.login()` を直接呼ばない。呼ぶたびにスマホアプリがログアウトされる。
- `normalize()` が返すキーはRENPHOのキー（`weight`・`bodyfat` など）のまま。どの列に書くかは呼び出し側が決める。
- 起動するスクリプトの先頭に、`dependencies = ["pycryptodome>=3.15"]` のインラインメタデータを書いて `uv run` で起動する。

## ライセンス

[MIT License](LICENSE)
