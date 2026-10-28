"""renpho-api-generic-logic-skill: RENPHO認証情報の .env 形式読み書きと、クライアントの入口。

保存先は起動フォルダ(作業ディレクトリ)の `.env`(KEY=VALUE形式)。プロジェクトのスキルは
この1つを共有するので、書き込むときは RENPHO_* の行だけを書き換え、他の行はそのまま残す。
同じキーの環境変数があれば、読むときはそちらを優先する(references/credentials.md)。

**RENPHOはOAuthではなくメール+パスワード認証で、パスワード本体を保存する必要がある**
(references/credentials.md)。

**クライアントは `open_client()` から作る。** 保存済みtokenを渡すことと、ログインしたら
tokenを必ず保存することの両方を、ここで済ませる(references/session.md)。
呼び出し側が `RenphoClient` を直接組み立てると、どちらかを忘れたときに
スマホアプリが同期のたびに強制ログアウトされる。
importの仕方は SKILL.md の「手続きに使う道具」にある(ここには書かない)。

公開する関数:
  open_client(path=None, log=None, debug=False)   保存済みtokenを渡し、ログインしたらtokenを保存して log に出すクライアント。認証はまだ済ませない
  env_path(path=None)                             使う .env のパス
  read_file(path=None)                            .env の KEY=VALUE を dict で返す(環境変数は見ない)
  load(path=None)                                 .env を読み、同じキーの環境変数で上書きして dict で返す
  save_session(token, user_id, path=None)         token と user_id の行だけを書き換える
  write(updates, path=None)                       .env の updates のキーの行だけを書き換え、無いキーは末尾に足す
"""
import os
import sys

from renpho_api import RenphoClient

KEYS = ("RENPHO_EMAIL", "RENPHO_PASSWORD", "RENPHO_USER_ID", "RENPHO_TOKEN")

# 初めて RENPHO_* の行を足すときに、その上に置く説明。
_HEADER = (
    "# renpho-api-generic-logic-skill の認証情報",
    "# RENPHO Healthアプリにログインしているメールアドレスとパスワードを入れる。",
    "# RENPHO_USER_ID は空でよい(初回ログイン時に自動で判別できる)。",
    "# RENPHO_TOKEN も空でよい(初回ログイン時に自動で保存される)。",
    "# 有効期限は90日。手で消すと次回ログインが走り、アプリ側がログアウトされる。",
)


def env_path(path=None):
    """使う .env のパス。引数 → 起動フォルダの `.env` の順で決める。"""
    return path or os.path.join(os.getcwd(), ".env")


def read_file(path=None):
    """.env の KEY=VALUE を全部 dict で返す(環境変数は見ない)。無ければ空の dict。"""
    path = env_path(path)
    values = {}
    if os.path.isfile(path):
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                values[key.strip()] = value.strip()
    return values


def load(path=None):
    """.env を読み、同じキーの環境変数で上書きして、スクリプト内部で使うキー名のdictを返す。"""
    values = {k: v for k, v in read_file(path).items() if k in KEYS}
    values.update({k: os.environ[k] for k in KEYS if k in os.environ})
    return {
        "email": values.get("RENPHO_EMAIL") or None,
        # パスワードは前後の引用符だけ剥がす(記号を含むパスワードを .env に入れる際、
        # 引用したくなる人が多いため)。中身は一切加工しない。
        "password": (values.get("RENPHO_PASSWORD") or "").strip('"').strip("'") or None,
        "user_id": values.get("RENPHO_USER_ID") or None,
        "token": values.get("RENPHO_TOKEN") or None,
    }


def save_session(token, user_id, path=None):
    """tokenとuser_idの行だけを更新する(メール・パスワードは読み書きせず現状のまま残す)。

    ログインのたびにRENPHOはアプリ側のセッションを無効化するため、取得したtokenは
    使い捨てにせず必ずここへ保存して次回以降使い回す(references/session.md)。
    """
    updates = {"RENPHO_TOKEN": token or ""}
    if user_id is not None:
        updates["RENPHO_USER_ID"] = str(user_id)
    write(updates, path)


def write(updates, path=None):
    """`.env` のうち `updates` のキーの行だけを書き換え、無いキーは末尾に足す。

    `.env` は他のスキルの認証情報も持つので、他の行(値・コメント)は一切変えない。
    書きかけで落ちても元のファイルが壊れないよう、一時ファイルに書いてから置き換える。
    """
    path = env_path(path)
    lines = []
    if os.path.isfile(path):
        with open(path, "r", encoding="utf-8") as f:
            lines = f.read().splitlines()
    done = set()
    for i, line in enumerate(lines):
        s = line.strip()
        if s and not s.startswith("#") and "=" in s:
            key = s.split("=", 1)[0].strip()
            if key in updates:
                lines[i] = f"{key}={updates[key]}"
                done.add(key)
    rest = [f"{k}={v}" for k, v in updates.items() if k not in done]
    if rest:
        if lines and lines[-1].strip():
            lines.append("")
        if not any(k in done for k in KEYS):
            lines += _HEADER
        lines += rest
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines) + "\n")
    os.replace(tmp, path)
    # 認証情報ファイルなので、作成できる環境では所有者のみ読み書きに絞る
    # (Windowsでは無視されるが、macOS/Ubuntuで流用したときに効く)。
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def _stderr(msg):
    print(msg, file=sys.stderr, flush=True)


def open_client(path=None, log=None, debug=False):
    """保存済みtokenを使い、ログインしたら必ずtokenを保存するクライアントを返す。

    ログインは「スマホアプリが強制ログアウトされる」という副作用を伴うので、
    黙って起きたことにしない。ログインしたら `log`(既定は標準エラー)へ必ず出す。
    認証はまだ済ませていない。呼び出し側が `client.ensure_auth()` を呼ぶ。
    """
    path = env_path(path)
    creds = load(path)
    say = log or _stderr

    def _on_login(token, uid):
        save_session(token, uid, path)
        say("※ RENPHOにログインしました。スマホアプリ側のセッションはここで切れます")

    return RenphoClient(
        creds["email"], creds["password"], debug=debug,
        token=creds["token"], user_id=creds["user_id"] or None,
        on_login=_on_login,
    )
