"""renpho-api-generic-logic: RENPHO認証情報の .env 形式読み書きと、クライアントの入口。

保存先は `$HOME/.claude-skills-env/renpho-api-generic-logic.env`(KEY=VALUE形式)。
トークンは導入先の環境なので、スキルの外に置く。別のファイルを一時的に使いたいときは、
環境変数 `RENPHO_ENV_FILE` にファイルの絶対パスを渡す。

**RENPHOはOAuthではなくメール+パスワード認証で、パスワード本体を保存する必要がある**
(references/credentials.md)。

**クライアントは `open_client()` から作る。** 保存済みtokenを渡すことと、ログインしたら
tokenを必ず保存することの両方を、ここで済ませる(references/session.md)。
呼び出し側が `RenphoClient` を直接組み立てると、どちらかを忘れたときに
スマホアプリが同期のたびに強制ログアウトされる。
"""
import os
import sys

from renpho_api import RenphoClient

DEFAULT_ENV_FILE = os.path.join(
    os.path.expanduser("~"), ".claude-skills-env", "renpho-api-generic-logic.env"
)

_KEYS = ("RENPHO_EMAIL", "RENPHO_PASSWORD", "RENPHO_USER_ID", "RENPHO_TOKEN")


def env_path(path=None):
    """使う環境ファイルのパス。引数 → 環境変数 `RENPHO_ENV_FILE` → 既定の順で決める。"""
    return path or os.environ.get("RENPHO_ENV_FILE") or DEFAULT_ENV_FILE


def load(path=None):
    """.envファイルを読み込み、スクリプト内部で使うキー名のdictを返す。"""
    path = env_path(path)
    values = {}
    if os.path.isfile(path):
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                key = key.strip()
                if key in _KEYS:
                    values[key] = value.strip()
    return {
        "email": values.get("RENPHO_EMAIL") or None,
        # パスワードは前後の引用符だけ剥がす(記号を含むパスワードを .env に入れる際、
        # 引用したくなる人が多いため)。中身は一切加工しない。
        "password": (values.get("RENPHO_PASSWORD") or "").strip('"').strip("'") or None,
        "user_id": values.get("RENPHO_USER_ID") or None,
        "token": values.get("RENPHO_TOKEN") or None,
    }


def save_session(token, user_id, path=None):
    """tokenとuser_idだけを更新する(メール・パスワードは読み書きせず現状のまま残す)。

    ログインのたびにRENPHOはアプリ側のセッションを無効化するため、取得したtokenは
    使い捨てにせず必ずここへ保存して次回以降使い回す(references/session.md)。
    """
    path = env_path(path)
    creds = load(path)
    creds["token"] = token
    creds["user_id"] = str(user_id) if user_id is not None else creds["user_id"]
    save(creds, path)


def save(creds, path=None):
    """dictを .env 形式で書き出す。既存ファイルは丸ごと置き換える。"""
    path = env_path(path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    lines = [
        "# renpho-api-generic-logic の認証情報",
        "# RENPHO Healthアプリにログインしているメールアドレスとパスワードを入れる。",
        "# RENPHO_USER_ID は空でよい(初回ログイン時に自動で判別できる)。",
        "# RENPHO_TOKEN も空でよい(初回ログイン時に自動で保存される)。",
        "# 有効期限は90日。手で消すと次回ログインが走り、アプリ側がログアウトされる。",
        f"RENPHO_EMAIL={creds.get('email') or ''}",
        f"RENPHO_PASSWORD={creds.get('password') or ''}",
        f"RENPHO_USER_ID={creds.get('user_id') or ''}",
        f"RENPHO_TOKEN={creds.get('token') or ''}",
    ]
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
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
