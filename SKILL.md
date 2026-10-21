---
name: renpho-api-generic-logic-skill
description: "文脈: RENPHO API。種類: 一般的な業務領域の判断。使う場面: この文脈の判断を直接聞かれたときに使う。この文脈の作業の前に読み、索引の「いつ聞くか」に当たる判断を聞く。"
metadata:
  version: "0.2.0"
  repository: "https://github.com/junyatakechi/renpho-api-generic-logic-skill"
---

# RENPHO Health APIの一般的な判断

## このスキルの役割

**RENPHO Health の非公式APIを扱うときの、一般的な判断を持つ generic-logic スキル。** RENPHOを使う人なら誰でも同じ答えになるが、AIの一般知識にはまだ無い判断を持つ。どれも、実機で確かめたか、実際に踏んで見つけたもの。

| | このスキル |
|---|---|
| 依存してよい環境 | 誰もが共有する環境だけ（RENPHO Health の非公式API `cloud.renpho.com`） |
| 持たないもの | 判断の対象（測定のレコード）と、導入先の環境。認証情報はプロジェクトのフォルダ直下の `.env` に置き、どこに記録するか・列名は呼び出し側が持つ |
| 持つ道具 | 手続きに使う道具だけ（APIとの通信と、値の変換）。判断に使う道具は持たない |
| 共有するとき | 混ぜて1つに育てる。新しく踏んだ落とし穴（別の機種の項目・プロトコルの変化）は、判断として足していく |

## 聞かれ方

他のスキルから聞かれるときは、ロジックスキル共通のやり取りで進める。

| 順 | 向き | 渡すもの |
|---|---|---|
| 1 | 呼び出し側 → このスキル | 聞きたい事・判断先（判断ファイルのパス）・欲しい答えの形 |
| 2 | このスキル → 呼び出し側 | 判断に要る材料の要求（各判断の「求める材料」） |
| 3 | 呼び出し側 → このスキル | 集めた材料 |
| 4 | このスキル → 呼び出し側 | 指定された形の答えと、その理由。手続きに関わる判断では、道具の使い方（どの道具を、どう呼び、何を守るか）も含める |

- 答えと理由を、組にして返す。
- 必須の材料が無ければ、答えずに足りない材料を返す。必須でない材料が無ければ、何が無かったために何を言えなかったかを添えて答える。
- 判断ファイルで答えられない聞きたい事には、一般論で答えず「判断が無い」と返す。新しい落とし穴を踏んだら、判断として足す。
- 判断のファイルに「未決」とある箇所に当たったら、未決であることを答えに含める。
- **このスキルの答えには、道具の使い方を含めることが多い。** 索引の「いつ聞くか」に当たったら、呼び出し側は聞きたい事・判断先・欲しい答えの形を伝えて聞き、返ってきた使い方に従って道具を自分で呼ぶ。
- **このスキルは判断して答えるだけで、手続きは代わりに行わない。** 手続きに使う道具は、呼び出し側が `scripts/` から自分で呼び、手続きの結果か例外を受け取る。
- 認証の設定・疎通の確認・項目の確認は、ユーザーから直接頼まれることもある（[認証情報の扱い](references/credentials.md)・[項目の意味と単位](references/field-units.md)）。

## 道具

道具は `scripts/` にある。どれも手続きに使う道具で、呼び出し側が手続きの中で使う。`renpho_api.py`・`renpho_env.py` はスキルの外を読み書きし（RENPHOとの通信・`.env`）、`renpho_records.py` は値の変換だけをする。**Pythonから使うなら常にimport、シェルからならスクリプトを起動する**（理由は [client-usage.md](references/client-usage.md)）。

- **呼び出し側は道具を写さず、自前の薄いラッパーも持たない。** クライアントの入口は `renpho_env.open_client()` に1つだけ置く。
- **道具で強制できる判断は、道具の中に実装してある。** 保存済みtokenの使い回し・ログインしたときのtokenの保存とログ・403のときの一度だけの再ログイン・新しい順への並べ替え・単位の確定・欠測の除外・IDの文字列化で、理由は判断ファイルに書いてある。強制できない判断（記録先が新しければ接続しない、など）は、このスキルが答えとして伝え、呼び出し側が守る。
- 失敗は例外で返す。続けるか止めるかは、呼び出し側が選ぶ。

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

`renpho_api.py` は暗号化に `pycryptodome` を使う。`uv run` で起動するスクリプトは、先頭のインラインメタデータに `dependencies = ["pycryptodome>=3.15"]` を書く。このスキルのスクリプトは `pyproject.toml` + `uv.lock` + `.python-version` で固定してあるので、`uv run` で起動する（`python` で直接叩くと、環境に入っている版を拾い、固定が効かない）。

| モジュール | 役割 |
|---|---|
| `renpho_api.py` | API通信。暗号化・ログイン・403のときの再ログイン・シャード・ページング・取得先の切り替え・新しい順への並べ替え・エラー |
| `renpho_env.py` | 認証情報の読み書きと、クライアントの入口 `open_client()` |
| `renpho_records.py` | レコード → 意味と単位の確定した値。測定時刻・同一測定の集約・欠測の除外・IDの文字列化 |

### `renpho_api.py`・`renpho_env.py` の関数

| 関数 | 中身 |
|---|---|
| `open_client(path=None, log=None, debug=False)` | 保存済みtokenを渡し、ログインしたらtokenを保存して `log` に出すクライアントを返す。認証はまだ済ませない |
| `client.ensure_auth()` | 保存済みtokenがあればログインしない。無ければ一度ログインする |
| `client.get_measurements(user_id=None)` | 測定を全件、新しい順で返す |
| `client.get_device_info()` | 紐付いている機器の情報。取れなければ `None` |
| `client.measurement_table()` | 測定が入っているシャードのテーブル名 |

`client.login()` は呼ばない（[セッションとトークン](references/session.md)）。

### `renpho_records.py` の関数

| 関数・定数 | 中身 |
|---|---|
| `normalize(record)` | `{"id", "measured_at", "has_body_composition", "values"}` を返す。`values` はRENPHOのキー → 丸めた値で、有効な値だけ |
| `collapse_sessions(records, window_minutes=SESSION_WINDOW_MIN)` | 同じ測定の連続したレコードを、最後の1件に集約する |
| `measured_at(record)` | 測定時刻（JST） |
| `record_id(record)` | レコードID（文字列） |
| `FIELDS` / `FIELD_KEYS` | RENPHOのキー・意味・単位・丸めの桁 |

| 例外 | 意味 |
|---|---|
| `RenphoError` | 基底。スクリプトはこれを捕まえる |
| `RenphoAuthError` | 認証情報が無い / ログインを拒否された |
| `RenphoAPIError` | APIがエラーを返した。`.code`・`.msg` |

### シェルから起動するスクリプト

いずれも環境変数、無ければ起動フォルダ（プロジェクトのフォルダ直下）の `.env` から `RENPHO_*` を読み、ログインしたら `.env` の `RENPHO_TOKEN`・`RENPHO_USER_ID` の行だけを書き換える。プロジェクトのフォルダから `<skill-dir>/scripts/...` の形で起動し、スキルのフォルダへ cd しない。

| スクリプト | 中身 |
|---|---|
| `uv run <skill-dir>/scripts/renpho_auth.py init` | 起動フォルダの `.env` に `RENPHO_*` の空の行を足し、書き込む手順を案内する。パスワードは受け取らない |
| `uv run <skill-dir>/scripts/renpho_auth.py check` | 疎通と取得件数を確かめる。保存済みtokenがあればログインしない |
| `uv run <skill-dir>/scripts/probe_fields.py [--limit 3] [--json 保存先]` | 実際に値が入っている項目と、常に空の項目を出す。どこにも書き込まない |

## 索引

| 判断 | ファイル | 扱うこと | 依存する判断 | いつ聞くか |
|---|---|---|---|---|
| セッションとトークン | [session.md](references/session.md) | ログインでアプリが落ちるのを、どう最小にするか | — | RENPHOに接続するコードを書く前・同期を呼ぶ頻度を決めるとき |
| 認証情報の扱い | [credentials.md](references/credentials.md) | パスワード本体を、どこに、誰が書くか | — | 認証情報を設定する前・疎通を確かめるとき |
| APIの呼び方 | [client-usage.md](references/client-usage.md) | どの入口から呼び、何を呼び出し側で書かないか | セッションとトークン | RENPHOを読むコードを書く前 |
| 測定時刻 | [measured-time.md](references/measured-time.md) | どの項目を測定時刻とするか | — | 測定の日付・時刻を記録する前・期間で絞る前 |
| 項目の意味と単位 | [field-units.md](references/field-units.md) | どのキーが何で、単位は何か。どの項目に列を作るか | — | 項目を記録先の列に対応付ける前・列を足す前 |
| 1回の測定で残る複数のレコード | [session-collapse.md](references/session-collapse.md) | 同じ測定の重複をどう畳むか | 測定時刻 | 測定を記録する前・平均を取る前 |
| 体組成が空のレコード | [missing-composition.md](references/missing-composition.md) | 体組成が0で返る測定をどう記録するか | — | 測定を記録する前 |
| レコードIDの持ち方 | [record-id.md](references/record-id.md) | IDの型と、重複を防ぐ一意キー | — | 記録先にIDの列を作る前・差分を取る処理を書く前 |
| 非公式APIが壊れたとき | [unofficial-api.md](references/unofficial-api.md) | 失敗の見分け方と、どこを見て直すか | 認証情報の扱い | APIが失敗したとき・応答の形が変わったとき |

## 依存の順

答えを別の判断の材料にする依存は無い。どの判断から聞いてもよい。索引の「依存する判断」は、あわせて読むと答えの前提が分かる判断で、各ファイルの本文からリンクしている。

## 判断ファイルの形

判断を足すとき・直すときは、この形を守る。

| 項目 | 書くこと |
|---|---|
| 求める材料 | 呼び出し側に求めるもの。列は「材料・種類・必須・形・無いとき」。判断の対象は、RENPHOでする作業。種類は `対象の属性`（作業の中身）/ `対象の記録` / `別の判断` / `導入先の環境`（判断が環境に依るときだけ。機種・記録先の型など） |
| 答え | 判断そのもの |
| 値 | 作成者が決めた値だけを、`| 名前 | 値 | 単位 |` の表で書く。無ければ省く |
| 道具 | 道具の使い方。どの道具を、どう呼び、何を守るか |
| 理由 | なぜそう判断するか。実際に確かめた日付と、起きたことを残す |
| 却下した案 | 選ばなかった案と、その理由。記録が無ければ「記録なし」と書く |
| 当てはまる範囲と限界 | どこまで使えるか |

- **導入先の環境は書かない。** 認証情報・どこに記録するか・列名は、呼び出し側か `.env` が持つ。
- **環境の仕様に合わせた値は、道具のコードの定数が正。** ホスト・鍵・エンドポイント・シャード数のような値は、人が決めるものではないので判断ファイルに値の表として置かない。判断の本文から「`renpho_api.py` の定数が正」と指す。
- **道具は値の表を読まない。** 多くのスキルが読み込むたびにimportするので、表の書き損じ1つで、使うすべてのスキルが止まるため。作成者が決めた値（同じ測定とみなす間隔・丸めの桁）は `renpho_records.py` に定数として置き、表は写しとして残し、決めた理由を判断ファイルに書く。

## 設定が無いとき → README の「セットアップ」

認証情報は導入先の環境なので、スキルの外に置く。`.env` への雛形の追加とパスワードの書き込みは人の手作業で、手順は README の「セットアップ」だけが持つ。次の合図が出たら先へ進まず、README の「セットアップ」をユーザーに案内する。**パスワードをチャットで受け取らない。**

| 合図 | 足りないもの |
|---|---|
| `RenphoAuthError`（`RENPHO_EMAIL / RENPHO_PASSWORD が設定されていません。`） | 起動フォルダの `.env`、またはその中の `RENPHO_EMAIL`・`RENPHO_PASSWORD` |
| `RenphoAuthError`（`RENPHOへのログインに失敗しました`） | 正しいメールアドレス・パスワード。RENPHO Health（青いアイコン）のアカウントであること |

## 未決

- 同じ測定とみなす間隔（5分）と、最後の1件を残すこと（[1回の測定で残る複数のレコード](references/session-collapse.md)）を決めた理由の記録が無い。
- 丸めの桁（[項目の意味と単位](references/field-units.md)）を決めた理由の記録が無い。
- Elis Aspire 以外の機種で、項目の意味と単位の恒等式が成り立つかは確かめていない。
