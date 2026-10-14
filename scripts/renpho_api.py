"""renpho-api-generic-logic: Renpho Health API(非公式)のクライアント。

このモジュールは**他スキルから直接importして使う公開モジュール**(references/client-usage.md)。

RENPHOに公式APIは無い。ここで叩いているのはRENPHO Healthアプリが使う内部APIで、
仕様は公開されていない。**いつ壊れてもおかしくない前提**で扱うこと(references/unofficial-api.md)。

プロトコル:
  - ホスト: https://cloud.renpho.com
  - リクエスト/レスポンスのボディは全てAES-128-ECB + PKCS7 → base64 で暗号化し、
    `{"encryptData": "..."}` で包む。鍵はアプリに埋め込まれた固定値で、複数の
    リバースエンジニアリング実装が同じ値を公開している(秘匿されていない=難読化)。
  - 認証は email + password。応答の token を以降のヘッダに載せる。

ここにある定数(ホスト・鍵・エンドポイント・シャード数)は、どれもRENPHOという共有する環境の
仕様で、人が決めた値ではない。環境が変わったときに直す。

`requests`は使わず標準ライブラリのurllibで書いている(依存を増やさないため)。
AESだけは標準ライブラリに無いので pycryptodome を使う。
"""
import base64
import json
import urllib.error
import urllib.request

from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad

API_BASE_URL = "https://cloud.renpho.com"
ENCRYPTION_KEY = b"ed*wijdi$h6fe3ew"  # 16byte固定鍵(AES-128)
APP_VERSION = "6.6.0"
PLATFORM = "android"
SYSTEM_TYPE = "11"

ENDPOINTS = {
    "login": "renpho-aggregation/user/login",
    "device_info": "renpho-aggregation/device/count",
    "measurements": "RenphoHealth/scale/queryAllMeasureDataList",
    "body_composition": "RenphoHealth/scale/queryBodyCompositionMeasureData",
}

# 体組成計のデバイス種別。ログイン時に「どの機器の紐付けを返すか」の指定に使う。
BODY_WEIGHT_SCALE_TYPES = [f"{i:02X}" for i in range(1, 21)]  # "01"〜"14"

# 測定データは user_id % 24 で決まる24個のテーブルに分割保存されている。
MEASUREMENT_TABLE_SHARDS = 24

REQUEST_TIMEOUT_SEC = 60


class RenphoError(RuntimeError):
    """このモジュールが送出する例外の基底。スクリプトはこれを捕まえて exit する。"""


class RenphoAuthError(RenphoError):
    """認証情報が無い、またはRENPHOがログインを拒否した。"""


class RenphoAPIError(RenphoError):
    """APIがエラーコードを返した。"""

    def __init__(self, context, code, msg):
        super().__init__(f"{context} failed: code={code}, msg={msg}")
        self.code = code
        self.msg = msg


# ---------------------------------------------------------------- 暗号

def _encrypt(plaintext):
    cipher = AES.new(ENCRYPTION_KEY, AES.MODE_ECB)
    return base64.b64encode(cipher.encrypt(pad(plaintext.encode("utf-8"), AES.block_size))).decode()


def _decrypt(encrypted_b64):
    cipher = AES.new(ENCRYPTION_KEY, AES.MODE_ECB)
    raw = unpad(cipher.decrypt(base64.b64decode(encrypted_b64)), AES.block_size)
    return json.loads(raw.decode("utf-8"))


def _encrypt_body(obj):
    return {"encryptData": _encrypt(json.dumps(obj, separators=(",", ":")))}


# ---------------------------------------------------------------- クライアント

class RenphoClient:
    """RENPHOのAPIクライアント。

    **tokenは使い捨てにしないこと。** RENPHOはアカウントに対して1セッションしか保持せず、
    ログインするたびに直前のtokenを無効化する(実測で確認済み。references/session.md)。
    つまり同期のたびにログインすると、そのたびにユーザーのスマホアプリが強制ログアウトされる。
    保存済みtokenを`token=`で渡し、`on_login`で新しいtokenを永続化すること。
    呼び出し側は直接組み立てず、`renpho_env.open_client()` を使う(両方を済ませた状態で返る)。
    """

    def __init__(self, email, password, debug=False, token=None, user_id=None, on_login=None):
        self.email = email
        self.password = password
        self.debug = debug
        self.token = token
        self.user_id = user_id
        self.user_info = None
        # 新しいtokenを取得したときに呼ばれる。保存先を知っているのは呼び出し側なので、
        # ここでは「保存して」と伝えるだけにする。
        self.on_login = on_login

    def _post(self, endpoint, body, auth=True, _allow_relogin=True):
        url = f"{API_BASE_URL}/{endpoint}"
        data = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(url, data=data, method="POST")
        req.add_header("Content-Type", "application/json")
        if auth and self.token:
            req.add_header("token", self.token)
            req.add_header("userId", str(self.user_id))
            req.add_header("appVersion", APP_VERSION)
            req.add_header("platform", PLATFORM)
        try:
            with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT_SEC) as resp:
                result = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", errors="replace")
            raise RenphoAPIError(endpoint, e.code, detail) from None
        if self.debug:
            print(f"  POST {endpoint} -> code={result.get('code')} msg={result.get('msg')}")

        # 保存済みtokenが無効化されていた場合だけ、ここで一度だけログインし直す。
        # アプリ側が後からログインすると、こちらのtokenは403になる(単一セッション制約)。
        if auth and _allow_relogin and self._is_token_rejected(result) and self.email:
            if self.debug:
                print("  token が無効化されていました。再ログインします。")
            self.login()
            return self._post(endpoint, body, auth=auth, _allow_relogin=False)
        return result

    @staticmethod
    def _is_token_rejected(result):
        """tokenが無効(403)かどうか。RENPHOは本文のcodeで返し、HTTPは200のまま。"""
        return str(result.get("code")) == "403"

    @staticmethod
    def _check(result, context):
        code = result.get("code")
        msg = str(result.get("msg", ""))
        # 成功時のcodeは実装によって0/200/"0"のゆらぎがあるため、msgも見る。
        if msg.lower() == "success" or code in (0, 200, "0", "200"):
            return
        raise RenphoAPIError(context, code, msg)

    def login(self):
        """ログインしてtokenとuser_idを保持する。戻り値は復号済みのログイン応答。"""
        if not self.email or not self.password:
            raise RenphoAuthError(
                "RENPHO_EMAIL / RENPHO_PASSWORD が設定されていません。"
                "renpho-api-generic-logic の README「セットアップ」に従ってください。"
            )
        payload = {
            "questionnaire": {},
            "login": {
                "email": self.email,
                "password": self.password,
                "areaCode": "US",
                "appRevision": APP_VERSION,
                "cellphoneType": "PythonScript",
                "systemType": SYSTEM_TYPE,
                "platform": PLATFORM,
            },
            "bindingList": {"deviceTypes": BODY_WEIGHT_SCALE_TYPES},
        }
        result = self._post(ENDPOINTS["login"], _encrypt_body(payload), auth=False)
        try:
            self._check(result, "Login")
        except RenphoAPIError as e:
            # 資格情報の誤りは運用で最も多い失敗なので、型を分けて案内しやすくする。
            raise RenphoAuthError(
                f"RENPHOへのログインに失敗しました({e.msg})。"
                "メールアドレス・パスワードがRENPHO Healthアプリのものと一致しているか確認してください。"
            ) from None
        data = _decrypt(result["data"])
        login_info = data.get("login", {})
        self.token = login_info.get("token")
        self.user_id = login_info.get("id")
        self.user_info = login_info
        if not self.token:
            raise RenphoAuthError("ログイン応答にtokenが含まれていませんでした。")
        # ここで保存しないと次回もログインが走り、そのたびにアプリがログアウトされる。
        if self.on_login:
            self.on_login(self.token, self.user_id)
        return data

    def ensure_auth(self):
        """認証済みの状態にする。保存済みtokenがあればログインしない。

        tokenが無効化されていた場合は`_post`側が一度だけ再ログインするので、
        ここでは「tokenもパスワードも無い」ケースだけを弾く。
        """
        if self.token and self.user_id:
            return
        self.login()

    def measurement_table(self, user_id=None):
        """測定データが入っているシャードテーブル名。user_id % 24 で決まる。"""
        uid = user_id if user_id is not None else self.user_id
        return f"measurements_info_{int(uid) % MEASUREMENT_TABLE_SHARDS}"

    def get_device_info(self):
        """紐付いている機器の情報。取得できなければNoneを返す(必須ではないため)。"""
        result = self._post(ENDPOINTS["device_info"], _encrypt_body({}))
        try:
            self._check(result, "GetDeviceInfo")
        except RenphoAPIError:
            return None
        return _decrypt(result["data"]) if result.get("data") else None

    def get_measurements(self, user_id=None, page_size=50, max_pages=200):
        """体組成の測定データを新しい順に全件取得する。

        体組成計(インピーダンス測定あり)は queryBodyCompositionMeasureData に入る。
        機種によってはこちらが空で、旧来の queryAllMeasureDataList にしか無いことが
        あるため、空だった場合は自動でフォールバックする。
        """
        uid = user_id if user_id is not None else self.user_id
        table = self.measurement_table(uid)
        records = self._paginate(ENDPOINTS["body_composition"], table, uid, page_size, max_pages)
        if not records:
            if self.debug:
                print("  体組成エンドポイントが空。従来エンドポイントにフォールバックします。")
            records = self._paginate(ENDPOINTS["measurements"], table, uid, page_size, max_pages)
        # APIは古い順で返す。呼び出し側が「最新」を取り違えないよう、ここで新しい順に統一する
        # (実機確認: records[0]が最古、records[-1]が最新の測定だった)。
        records.sort(key=lambda r: r.get("timeStamp") or 0, reverse=True)
        return records

    def _paginate(self, endpoint, table, uid, page_size, max_pages):
        out = []
        for page in range(1, max_pages + 1):
            body = _encrypt_body({
                "pageNum": page,
                "pageSize": page_size,
                "userIds": [str(uid)],
                "tableName": table,
            })
            result = self._post(endpoint, body)
            self._check(result, f"{endpoint} page {page}")
            if not result.get("data"):
                break
            records = _extract_records(_decrypt(result["data"]))
            if not records:
                break
            out.extend(records)
            # 総件数はサーバー側が0を返すことがあり当てにならないので、
            # 「1ページ埋まらなかったら最後」だけを終了条件にする。
            if len(records) < page_size:
                break
        return out


def _extract_records(page_data):
    """復号結果からレコード配列を取り出す。応答の包み方に揺れがあるため吸収する。"""
    if isinstance(page_data, list):
        return page_data
    if isinstance(page_data, dict):
        for key in ("list", "records", "data", "measurements"):
            value = page_data.get(key)
            if isinstance(value, list):
                return value
    return []
