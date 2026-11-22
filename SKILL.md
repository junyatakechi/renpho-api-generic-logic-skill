---
name: renpho-api-generic-logic-skill
description: "文脈: RENPHO API。種類: 一般的な業務知識。使う場面: 名前で指名されたときだけ使い、会話の内容からは選ばない。"
metadata:
  skill-version: "0.2.8"
  design-name: "人の判断を切り出すAgent Skillsの設計"
  design-version: "6.0.1"
  design-url: "https://app.notion.com/p/3eaf2fd6925e8102b86fee3b6b3dd5a3"
---

# 索引

| 判断名 | 扱うこと | ファイル | 依存する判断 | 計算 |
|---|---|---|---|---|
| セッションとトークン | RENPHOに接続するコードを書く・同期を呼ぶ頻度を決めるとき、ログインでアプリが落ちるのをどう最小にするか | [session.md](references/session.md) | — | — |
| 認証情報の扱い | 認証情報を設定する・疎通を確かめるとき、パスワード本体を、どこに、誰が書くか | [credentials.md](references/credentials.md) | — | — |
| APIの呼び方 | RENPHOを読むコードを書くとき、どの入口から呼び、何を呼び出し側で書かないか | [client-usage.md](references/client-usage.md) | `session.md` | — |
| 測定時刻 | 測定の日付・時刻を記録する・期間で絞るとき、どの項目を測定時刻とするか | [measured-time.md](references/measured-time.md) | — | — |
| 測定がクラウドに上がる時期 | 新しい測定が取れないとき・同期の結果を読むとき、測定がいつRENPHOに上がり、取れないことをどう読むか | [upload-timing.md](references/upload-timing.md) | `measured-time.md`・`session.md` | — |
| 項目の意味と単位 | 項目を記録先の列に対応付ける・列を足すとき、どのキーが何で、単位は何か。どの項目に列を作るか | [field-units.md](references/field-units.md) | — | — |
| 1回の測定で残る複数のレコード | 測定を記録する・平均を取るとき、同じ測定の重複をどう畳むか | [session-collapse.md](references/session-collapse.md) | `measured-time.md` | — |
| 体組成が空のレコード | 測定を記録するとき、体組成が0で返る測定をどう記録するか | [missing-composition.md](references/missing-composition.md) | — | — |
| レコードIDの持ち方 | 記録先にIDの列を作る・差分を取る処理を書くとき、IDをどの型で持ち、何を一意キーにして重複を防ぐか | [record-id.md](references/record-id.md) | — | — |
| 非公式APIが壊れたとき | APIが失敗したとき・応答の形が変わったとき、失敗をどう見分け、どこを見て直すか | [unofficial-api.md](references/unofficial-api.md) | `credentials.md` | — |
| 設定の不足 | 道具が `RenphoAuthError` を返したとき、どの設定の不足によるものか | [missing-setup.md](references/missing-setup.md) | — | — |

# 手続きに使う道具

道具は `scripts/` にある。関数の一覧と引数は、各モジュールの冒頭の docstring が正。コードを書く前に読む。

| モジュール | 役割 |
|---|---|
| `renpho_api.py` | API通信。暗号化・ログイン・403のときの再ログイン・シャード・ページング・取得先の切り替え・新しい順への並べ替え・エラー |
| `renpho_env.py` | 認証情報の読み書きと、クライアントの入口 `open_client()`。tokenの発行時刻 |
| `renpho_records.py` | レコード → 意味と単位の確定した値。測定時刻・上がった時刻・同一測定の集約・欠測の除外・IDの文字列化（値の変換だけ） |

```python
import os, sys
sys.path.insert(0, os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "renpho-api-generic-logic-skill", "scripts")))
from renpho_api import RenphoError
from renpho_env import open_client
import renpho_records

client = open_client(log=print)
client.ensure_auth()
rows = [renpho_records.normalize(r) for r in renpho_records.collapse_sessions(client.get_measurements())]
```

`renpho_api.py` は暗号化に `pycryptodome` を使う。importして使うスクリプトは、先頭のインラインメタデータに `dependencies = ["pycryptodome>=3.15"]` を書き、`uv run` で起動する。このスキルのスクリプトは `pyproject.toml`・`uv.lock`・`.python-version` で固定してあるので、`uv run` で起動する（`python` で直接起動すると、環境に入っている版を拾い、固定が効かない）。

## 例外

| 例外 | 意味 |
|---|---|
| `RenphoError` | 基底。スクリプトはこれを捕まえる |
| `RenphoAuthError` | 認証情報が無い / ログインを拒否された |
| `RenphoAPIError` | APIがエラーを返した。`.code`・`.msg` |

## シェルから起動するスクリプト

プロジェクトのフォルダから `<skill-dir>/scripts/...` の形で起動し、スキルのフォルダへ cd しない。`RENPHO_*` は環境変数、無ければ起動フォルダの `.env` から読み、ログインしたら `.env` の `RENPHO_TOKEN`・`RENPHO_USER_ID` の行だけを書き換える。パスワードは引数で受け取らない。

| スクリプト | 中身 |
|---|---|
| `uv run <skill-dir>/scripts/renpho_auth.py init` | 起動フォルダの `.env` に `RENPHO_*` の空の行を足し、書き込む手順を案内する |
| `uv run <skill-dir>/scripts/renpho_auth.py check` | 疎通と取得件数を確かめる。保存済みtokenがあればログインしない |
| `uv run <skill-dir>/scripts/probe_fields.py [--limit 3] [--json 保存先]` | 実際に値が入っている項目と、常に空の項目を出す。どこにも書き込まない |

# このスキルの設計上の決まりごと

1. このスキルは判断を答えるだけで、判断の対象もデータも持たない。対象の値は、材料の写しとして受け取る。データを取りに行かず、保存もせず、IDも受け取らない。
2. 答える範囲は、聞きたい事を索引の「扱うこと」と照らして決める。索引の「依存する判断」にある判断を、先に出す。
3. 判断ファイルの「求める材料」がそろわなければ答えない。計算がある判断は、`uv run <skill-dir>/scripts/judge.py <判断> <材料.json>` で計算する。<判断> は `references/` のファイル名。依存する判断の材料も、一緒に渡す。
4. 答えは、指定された形にそろえ、理由と組にして返す。
5. 中核判断は、判断ファイルで答えられなければ、一般論で答えず「判断が無い」と返す。「未決」に当たったら、未決であることと、決めるまでの暫定の扱いを含める。一般的な業務知識は、判断ファイルに無いことを一般知識で補ってよい。
6. 読み込まれたら、索引の「扱うこと」に当たる作業で、その判断ファイルに従う。どの道具をどう呼ぶかは、判断ファイルの「道具」が示す。手続きは代わりに行わず、呼び出し側が道具を呼ぶ。操作する対象のIDは、材料ではなく、道具の引数で渡す。
