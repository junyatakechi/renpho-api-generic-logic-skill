"""renpho-api-generic-logic-skill: RENPHOのレコードを、意味と単位の確定した値へ変換する(値の変換だけ)。

通信はしない。`renpho_api.RenphoClient.get_measurements()` が返したレコードを受け取り、
RENPHO側の事情(測定時刻・単位・欠測・同一測定の重複・IDの桁)を吸収した値を返す。
**どの列に書くかは持たない。** キーはRENPHOのキーのまま返すので、列名への対応付けは
呼び出し側(導入先の環境)が持つ。

ここにある判断と、その理由:
  - 測定時刻は `timeStamp` だけが正しい            → references/measured-time.md
  - 項目の意味と単位(恒等式で確定)                → references/field-units.md
  - 1回の測定で複数レコードが残る                   → references/session-collapse.md
  - 体組成が空のレコード                            → references/missing-composition.md
  - レコードIDはテキストで持つ                      → references/record-id.md

作成者が決めた値(`SESSION_WINDOW_MIN`・丸めの桁)は、判断ファイルの表ではなくここに定数で置く。
このモジュールは他スキルが読み込むたびにimportするので、表の書き損じ1つで
使うすべてのスキルが止まるのを避けるため。決めた理由は判断ファイルにある。
importの仕方は SKILL.md の「手続きに使う道具」にある(ここには書かない)。

公開する関数と定数:
  normalize(record)                                       {"id", "measured_at", "has_body_composition", "values"}。values はRENPHOのキー → 丸めた値で、有効な値だけ
  collapse_sessions(records, window_minutes=SESSION_WINDOW_MIN)   同じ測定の連続したレコードを、最後の1件に集約する
  measured_at(record)                                     測定時刻(JST)
  uploaded_at(record)                                     RENPHOに上がった時刻(JST)。createdAt を UTC+8 として読む。読めなければ None
  has_body_composition(record)                           体組成があるか
  record_id(record)                                       レコードID(文字列)
  FIELDS / FIELD_KEYS                                     RENPHOのキー・意味・単位・丸めの桁
  SESSION_WINDOW_MIN                                      同じ測定とみなす間隔(分)
"""
from datetime import datetime, timedelta, timezone

JST = timezone(timedelta(hours=9))

# (RENPHOのキー, 意味, 単位, 丸めの桁。0なら整数)
# 単位はAPIが返さないので、実データの恒等式で確定させた(references/field-units.md)。
FIELDS = [
    ("weight",        "体重",               "kg",     1),
    ("bmi",           "BMI",                "",       1),
    ("bodyfat",       "体脂肪率",           "%",      1),
    ("water",         "体水分率",           "%",      1),
    ("muscle",        "骨格筋量",           "kg",     1),
    ("sinew",         "筋肉量",             "kg",     1),
    ("bone",          "骨量",               "kg",     2),
    ("bmr",           "基礎代謝",           "kcal/日", 0),
    ("visfat",        "内臓脂肪レベル",     "レベル", 0),
    ("subfat",        "皮下脂肪率",         "%",      1),
    ("protein",       "タンパク質率",       "%",      1),
    ("bodyage",       "体年齢",             "歳",     0),
    ("fatFreeWeight", "除脂肪体重",         "kg",     1),
    ("TW",            "標準体重",           "kg",     1),
    ("WC",            "体重コントロール",   "kg",     1),
    ("resistance",    "生体インピーダンス", "Ω",      0),
    ("bodytype",      "体型分類",           "コード", 0),
]
FIELD_KEYS = tuple(k for k, *_ in FIELDS)

# 体組成が測れなかった測定(インピーダンスが取れず0で返る)でも体重とBMIは有効。
# それ以外の項目は0を「未測定」として扱い、値を返さない(references/missing-composition.md)。
ALWAYS_VALID = {"weight", "bmi"}

# 同一セッションとみなす間隔(分)。作成者が決めた値(references/session-collapse.md)。
SESSION_WINDOW_MIN = 5


def measured_at(record):
    """測定時刻(JST)。timeStampだけが信頼できる(references/measured-time.md)。"""
    return datetime.fromtimestamp(record["timeStamp"], JST)


# createdAt はタイムゾーンの無い文字列で、UTC+8 の時刻で入っている(references/measured-time.md)。
CREATED_AT_TZ = timezone(timedelta(hours=8))


def uploaded_at(record):
    """RENPHOに上がった時刻(JST)。測定時刻には使わない(references/measured-time.md)。"""
    try:
        at = datetime.strptime(record["createdAt"], "%Y-%m-%d %H:%M:%S")
    except (KeyError, TypeError, ValueError):
        return None
    return at.replace(tzinfo=CREATED_AT_TZ).astimezone(JST)


def has_body_composition(record):
    return (record.get("bodyfat") or 0) > 0


def collapse_sessions(records, window_minutes=SESSION_WINDOW_MIN):
    """同一セッションの連続測定を最後の1件に集約する。

    体重計は1回乗るあいだに複数レコードを残す(実測で、1分違いの2件が同じ体重だった)。
    そのまま入れると同じ測定が二重に並び、週次平均が乗り直した日だけ重く出る。
    新しい順で受け取り、新しい順で返す。`window_minutes` が0なら集約しない。
    """
    if not records:
        return []
    ordered = sorted(records, key=lambda r: r["timeStamp"], reverse=True)
    if not window_minutes:
        return ordered
    window = window_minutes * 60
    kept = [ordered[0]]  # 各セッションで最も新しい1件を残す
    for rec in ordered[1:]:
        if kept[-1]["timeStamp"] - rec["timeStamp"] > window:
            kept.append(rec)
    return kept


def record_id(record):
    """RENPHOのレコードID。2^53を超えるので必ず文字列で返す(references/record-id.md)。"""
    return str(record["id"])


def normalize(record):
    """1レコードを、意味と単位の確定した素の値へ変換する。

    戻り値:
      {"id": str, "measured_at": datetime(JST), "has_body_composition": bool,
       "values": {RENPHOのキー: 丸めた値}}

    `values` に入るのは `FIELDS` のキーのうち、有効な値があるものだけ。
    体組成が空の測定は体重とBMIだけになる。0を「値」として返さない。
    """
    has_comp = has_body_composition(record)
    values = {}
    for key, _meaning, _unit, digits in FIELDS:
        value = record.get(key)
        if value is None:
            continue
        if key not in ALWAYS_VALID and (not has_comp or value == 0):
            continue
        values[key] = round(float(value), digits) if digits else int(value)
    return {
        "id": record_id(record),
        "measured_at": measured_at(record),
        "has_body_composition": has_comp,
        "values": values,
    }
