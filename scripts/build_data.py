"""広島市オープンデータ (data/raw/) から app/data/*.json を作る。

新年度の「家庭ごみ収集日程表」ZIP を展開して data/raw/r◯/（令和の年度）に置くと、
いちばん新しい年度のフォルダを使ってこのスクリプトが変換する（scripts/auto_update.py が自動で行う）:
    python scripts/build_data.py

出力:
    app/data/items.json      品目（市内共通）
    app/data/wards.json      区・町名・グループの一覧（初回の地域選択用）
    app/data/<区コード>.json  その区の全グループの収集日
    app/data/items_en.json   品目名・出し方・備考の英訳（英語表示用）

英訳は data/i18n/*_en.tsv（日本語<TAB>英語）で管理する。年度更新で新しい品目や
文言が増えると、英訳のないものを一覧表示するので、tsv に追記して再実行する。
"""
import csv
import json
import re
import unicodedata
from pathlib import Path

WARDS = [  # (ファイル番号, 区名, コード)
    (1, "中区", "naka"),
    (2, "東区", "higashi"),
    (3, "南区", "minami"),
    (4, "西区", "nishi"),
    (5, "安佐南区", "asaminami"),
    (6, "安佐北区", "asakita"),
    (7, "安芸区", "aki"),
    (8, "佐伯区", "saeki"),
]

# 収集日程表の略称 → 1文字コード（JSONを小さくするため）
KINDS = {"可燃": "k", "リプラ": "r", "他プラ": "p", "不燃": "f", "資源": "s", "大型": "o"}

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
I18N = ROOT / "data" / "i18n"
OUT = ROOT / "app" / "data"

# いちばん新しい年度のフォルダ（例：r8 = 令和8年度）
YEAR_DIR = max((p.name for p in RAW.glob("r[0-9]*") if p.is_dir()), key=lambda n: int(n[1:]))

try:
    import pykakasi

    _kks = pykakasi.kakasi()

    def reading(text):
        return "".join(w["hira"] for w in _kks.convert(text))

    def romaji(text):
        return "".join(w["hepburn"] for w in _kks.convert(text))
except ImportError:  # 読みが無くても漢字・カナ検索は動く
    def reading(text):
        return ""

    def romaji(text):
        raise SystemExit("町名のURL用IDを作るには pykakasi が必要です: pip install pykakasi")


def read_csv(path):
    with open(path, encoding="cp932", newline="") as f:
        return list(csv.reader(f))


def clean(s):
    # ①②③ は NFKC で 1 2 3 になり文と区別できなくなるので、先に（1）（2）（3）にしておく
    s = re.sub(r"[①-⑳]", lambda m: f"（{ord(m.group()) - 0x245F}）", s or "")
    s = unicodedata.normalize("NFKC", s)
    s = re.sub(r"\s*\n\s*", "", s).strip()
    return "" if s in ("―", "-") else s


# 50音事典に無いが、市HPに記載がある品目
# 「家庭ごみの正しい出し方」
#   https://www.city.hiroshima.lg.jp/living/gomi-kankyo/1021277/1003072/1026095/1026096/1003182.html
# 「よくある質問と回答（分別・出し方）」
#   https://www.city.hiroshima.lg.jp/faq/gomi-kankyo/1001569/index.html
SRC_DASHIKATA = "市HP「家庭ごみの正しい出し方」より"
SRC_FAQ = "市HP「よくある質問と回答」より"
EXTRA_ITEMS = [
    {
        "n": "本",
        "c": "資源ごみ",
        "h": "ひもでしばってまとめて出す。",
        "note": "50音事典には未掲載。市HP「家庭ごみの正しい出し方」の資源ごみ（その他の紙類：本、雑誌、チラシなど）より",
    },
    {
        "n": "モバイルバッテリー",
        "c": "有害ごみ",
        "h": "端子部分をテープで覆い、資源ごみとは袋を分けて、ポリ袋に入れて「有害」と書いて出す。(収集日は「資源ごみ」と同じ日)",
        "note": "破損・膨張したものも収集します。破損・膨張していないものは、区役所の充電式電池回収ボックスも利用できます。" + SRC_DASHIKATA,
    },
    {
        "n": "ペットボトルのキャップ・ラベル",
        "c": "リサイクルプラ",
        "h": "ペットボトルからはずして、リサイクルプラとして出す。",
        "note": "紙のラベルは可燃ごみ。ボトルの口に残るリング状の部分は、はずさなくてかまいません。" + SRC_FAQ,
    },
    {
        "n": "生ごみ(台所ごみ)",
        "c": "可燃ごみ",
        "h": "よく水を切って新聞紙などに包み、じょうぶな紙袋またはポリ袋(土のう袋を除く)に入れて出す。",
        "note": SRC_FAQ,
    },
    {
        "n": "脱酸素剤",
        "c": "可燃ごみ",
        "h": "じょうぶな紙袋またはポリ袋(土のう袋を除く)に入れて出す。",
        "note": SRC_FAQ,
    },
    {
        "n": "ハンディファン",
        "c": "不燃ごみ",
        "h": "電池を取り外して(電池は「有害ごみ」)、透明または半透明のじょうぶなポリ袋に入れて出す。",
        "note": "充電式電池を取り外せないものは、他の不燃ごみと袋を分け、袋に「危険」と書いて出してください。" + SRC_FAQ,
    },
    {
        "n": "灯油・ガソリン(石油類)",
        "c": "市では収集しない",
        "h": "引火性があるため、市では収集できません。販売店にご相談ください。",
        "note": SRC_FAQ,
    },
    {
        "n": "耕運機(農業用)",
        "c": "市では収集しない",
        "h": "販売店または製造元にご相談ください。",
        "note": SRC_FAQ,
    },
    {
        "n": "引っ越しなどで一度に出る大量のごみ(一時多量ごみ)",
        "c": "市では収集しない",
        "h": "引っ越し、庭木の刈り込み、模様替えなどで一度に大量に出るごみは収集しません。自分で市の処理施設に持ち込むか、市の許可業者に依頼してください。",
        "note": SRC_FAQ,
    },
]


def build_items():
    items = [dict(it, y=reading(it["n"])) for it in EXTRA_ITEMS]
    for row in read_csv(RAW / "bunbetsu_jiten.csv")[1:]:
        name, cat, how, note = (clean(x) for x in row[1:5])
        if not name:
            continue
        item = {"n": name, "y": reading(name)}
        ref = re.search(r"品目「(.+?)」に掲載", cat)
        if ref:
            item["ref"] = ref.group(1)
        else:
            if "家電リサイクル法" in cat:
                cat = "家電リサイクル"
            elif not cat:
                cat = "市では収集しない"
            item["c"] = cat
            item["h"] = how
            if note:
                item["note"] = note
        items.append(item)
    return items


def build_towns(no, name):
    towns = []
    for row in read_csv(RAW / YEAR_DIR / f"3-{no}{name}町名.csv")[1:]:
        # 「１丁目」と「一丁目」が混在しているので漢数字にそろえる
        n = re.sub(r"(\d)丁目", lambda m: "〇一二三四五六七八九"[int(m.group(1))] + "丁目", clean(row[0]))
        y = clean(row[1])
        # URLに入れる町名のID（例：紙屋町一丁目 → kamiyachou1choume）
        tid = re.sub(r"[^a-z0-9]+", "-", romaji(y).lower()).strip("-")
        towns.append({"id": tid, "n": n, "y": y, "g": int(row[2])})
    ids = [t["id"] for t in towns]
    dup = {i for i in ids if ids.count(i) > 1}
    assert not dup, f"{name}: URL用IDが重複 {dup}"
    return towns


def build_schedule(no, name, groups):
    """グループごとに、年度の初日からの日数で引ける文字列を作る。

    1日1文字（家庭ごみ）＋大型ごみの日の一覧。空き日は "-"。
    """
    days = None
    sched = {}
    for kind_file in ("家庭ごみ", "大型ごみ"):
        rows = read_csv(RAW / YEAR_DIR / f"1-{no}{kind_file}収集日（{name}）.csv")
        header = rows[0]
        body = rows[1:]
        dates = [r[0].strip("#") for r in body]
        if days is None:
            days = dates
        assert dates == days, f"{name} {kind_file} の日付が家庭ごみと一致しない"
        for g in groups:
            col = header.index(str(g))
            cells = [r[col].strip() for r in body]
            for c in cells:
                assert not c or c in KINDS, f"{name} グループ{g}: 未知の区分 {c!r}"
            if kind_file == "家庭ごみ":
                sched[g] = {"d": "".join(KINDS[c] if c else "-" for c in cells)}
            else:
                sched[g]["o"] = [i for i, c in enumerate(cells) if c]
    return days, sched


def build_items_en(items):
    """英訳の対訳表から、今年度の品目で使う分だけを取り出す。訳のないものは画面では日本語で表示される"""
    def table(name):
        rows = (line.rstrip("\n").split("\t") for line in (I18N / f"{name}_en.tsv").read_text(encoding="utf-8").splitlines() if line)
        return dict(rows)

    out = {}
    for key, field in (("names", "n"), ("how", "h"), ("notes", "note")):
        tsv = table(key)
        used = list(dict.fromkeys(it[field] for it in items if it.get(field)))
        out[key] = {ja: tsv[ja] for ja in used if ja in tsv}
        missing = [ja for ja in used if ja not in tsv]
        if missing:
            print(f"英訳なし（data/i18n/{key}_en.tsv に追記）: {len(missing)} 件")
            for ja in missing:
                print(f"  {ja}")
    return out


def main():
    OUT.mkdir(parents=True, exist_ok=True)

    def write(fname, obj):
        (OUT / fname).write_text(
            json.dumps(obj, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
        )

    items = build_items()
    write("items.json", items)
    write("items_en.json", build_items_en(items))

    index = []
    for no, name, code in WARDS:
        towns = build_towns(no, name)
        groups = sorted({t["g"] for t in towns})
        days, sched = build_schedule(no, name, groups)
        write(f"{code}.json", {"ward": name, "start": days[0], "end": days[-1], "groups": sched})
        index.append({"code": code, "name": name, "towns": towns})
        print(f"{name}: 町名 {len(towns)}, グループ {len(groups)}, {days[0]}〜{days[-1]}")
    write("wards.json", {"year": YEAR_DIR, "wards": index})
    print(f"品目 {len(items)} 件 → {OUT}")


if __name__ == "__main__":
    main()
