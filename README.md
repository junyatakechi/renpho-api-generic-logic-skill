# renpho-api-generic-logic-skill

RENPHO Health（体組成計）の非公式APIを扱うときの、一般的な判断を持つロジックスキル。
スマホアプリを何度もログアウトさせる・単位を取り違える、といった落とし穴とその避け方を答え、RENPHO Health のAPIを呼ぶ道具を部品として渡す。

## 必要なもの

- [Claude Code](https://docs.claude.com/en/docs/claude-code/overview)
- Python 3.11以上と [uv](https://docs.astral.sh/uv/)
- RENPHOの体組成計と、RENPHO Healthアプリ（青いアイコン）のアカウント。旧Renphoアプリのアカウントでは動かない

## インストール

```bash
git clone https://github.com/junyatakechi/renpho-api-generic-logic-skill.git ~/.claude/skills/renpho-api-generic-logic-skill
```

特定のプロジェクトだけで使うなら、`<プロジェクト>/.claude/skills/` の中でクローンする。

## セットアップ

先に知っておくこと。

- **RENPHOに公式APIは無い。** このスキルが叩くのはRENPHO Healthアプリの内部APIで、予告なく壊れる。
- **RENPHOは、1つのアカウントに1つのセッションしか持てない。** 初めてログインしたとき（と、90日でtokenが切れたとき）に、スマホアプリがログアウトされる。以降は保存したtokenを使い回す。ただし、アプリでログインし直すとこちらのtokenが無効になり、次の接続で再ログインして、アプリがまたログアウトされる。
- **アプリがログアウトしている間の測定は、RENPHOに上がらない。** 体組成計がWi-Fiにつながっていても上がらない。スクリプトがログインしたあとは、スマホでアプリを開いてログインし直すと、溜まっていた測定がまとめて上がる。
- **`.env` には、RENPHOアカウントのパスワードそのものが入る。** 他のサービスと使い回していないパスワードにする。

手順。

1. 認証情報の雛形を作る。プロジェクトのフォルダ直下（Claude Code を起動するフォルダ）の `.env` に `RENPHO_*` の空の行が足される（`.env` が無ければ作られ、他のキーの行はそのまま残る）。以下のコマンドは、どれもプロジェクトのフォルダで実行する。

   ```bash
   cd <プロジェクトのフォルダ>
   uv run ~/.claude/skills/renpho-api-generic-logic-skill/scripts/renpho_auth.py init
   ```

2. `.env` をエディタで開き、自分で値を書き込む。**パスワードはClaudeに渡さない。** キーの中身は `.env.example` のコメントにある。

   ```
   RENPHO_EMAIL=<RENPHO Healthのメールアドレス>
   RENPHO_PASSWORD=<そのパスワード>
   RENPHO_USER_ID=
   RENPHO_TOKEN=
   ```

3. 疎通を確かめる。保存済みのtokenが無ければここで一度ログインし、スマホアプリがログアウトされる。

   ```bash
   uv run ~/.claude/skills/renpho-api-generic-logic-skill/scripts/renpho_auth.py check
   ```

## 使い方

主に、アプリケーションスキルから呼ばれる。
直接頼むときも、`/renpho-api-generic-logic-skill` で名前を指名する。指名しないと、このスキルは読み込まれない。

- 「/renpho-api-generic-logic-skill RENPHOに繋がるか確かめて」
- 「/renpho-api-generic-logic-skill RENPHOが返す項目を調べて」
- 「/renpho-api-generic-logic-skill RENPHOのAPIが壊れた」
