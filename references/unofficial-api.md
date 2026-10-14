# 非公式APIが壊れたとき

## 求める材料

| 材料 | 種類 | 必須 | 形 | 無いとき |
|---|---|---|---|---|
| 起きたこと（例外の型・`code`・`msg`、HTTPステータス、復号の失敗） | 対象の記録 | ○ | エラーの文 | 判断できない |
| 使っているアプリとアカウントの種類（RENPHO Health か、旧Renpho か） | 導入先の環境 | — | アプリ名 | RENPHO Health として答える |

## 答え

1. **RENPHOに公式APIは無い。** 叩いているのはRENPHO Healthアプリの内部APIで、仕様は公開されておらず、予告なく壊れる。実際に一度壊れている。
2. **旧ホスト（`renpho.qnclouds.com`）には戻さない。** 旧Renphoアプリ専用で、RENPHO Healthのアカウントでは動かない。
3. **壊れたら、同じプロトコルを追っている次の実装との差分を見る。** どれも採用はしていない。仕様の参照先として使う。
   - `danvaneijck/renpho-api`（PyPI `renpho-api`）：最も追従が早い
   - `forkerer/RenphoGarminSync-CLI`：元のリバースエンジニアリング
   - `StartupBros-com/renpho-mcp-server`
4. **差分を取り込んだら、`renpho_api.py` の定数とこの判断を直す。** 呼び出し側には手を入れずに済むようにする。
5. **ログインの拒否と、プロトコルの破損を分ける。** `RenphoAuthError` で「ログインに失敗」と出たら、まず認証情報を疑う（[認証情報の扱い](credentials.md)）。正しい認証情報で復号の失敗や想定外の `code` が続くなら、プロトコルの破損を疑う。

## 道具

- `uv run scripts/renpho_auth.py check`：`debug=True` で、エンドポイントごとの `code` と `msg` を出す。
- `uv run scripts/probe_fields.py --json <保存先>`：応答の形が変わっていないかを、全件で確かめる。

## 理由

| 世代 | ホスト | 状態 |
|---|---|---|
| 旧 | `renpho.qnclouds.com`（sign_in → list_scale_user → measurements/list） | 旧Renphoアプリ専用。RENPHO Healthのアカウントでは動かない。参照実装（hass_renpho など）も更新停止。レート制限やIPの遮断の報告がある |
| 現行 | `cloud.renpho.com` | RENPHO Health（青いアイコン）のアカウント用。このスキルが使う |

## 却下した案

| 案 | 理由 |
|---|---|
| 参照実装（`renpho-api` など）をそのまま依存に入れる | 採用しなかった理由の記録は無い。仕様の参照先としてだけ使っている |

## 当てはまる範囲と限界

- RENPHOが公式APIを出したら、このスキルの道具ごと見直す。
