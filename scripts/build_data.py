"""広島市オープンデータ (data/raw/) から app/data/*.json を作る。

毎年4月に新年度の「家庭ごみ収集日程表」ZIP を展開して data/raw/r◯/ に置き、
YEAR_DIR を書き換えてこのスクリプトを実行する:
    python scripts/build_data.py

出力:
    app/data/items.json      品目（市内共通）
    app/data/wards.json      区・町名・グループの一覧（初回の地域選択用）
    app/data/<区コード>.json  その区の全グループの収集日
"""
import csv
import json
import re
import unicodedata
from pathlib import Path

YEAR_DIR = "r8"  # 令和8年度

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
OUT = ROOT / "app" / "data"

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
    s = unicodedata.normalize("NFKC", s or "")
    s = re.sub(r"\s*\n\s*", "", s).strip()
    return "" if s in ("―", "-") else s


# 50音事典に無いが、市HP「家庭ごみの正しい出し方」に記載がある品目
# https://www.city.hiroshima.lg.jp/living/gomi-kankyo/1021277/1003072/1026095/1026096/1003182.html
EXTRA_ITEMS = [
    {
        "n": "本",
        "c": "資源ごみ",
        "h": "ひもでしばってまとめて出す。",
        "note": "50音事典には未掲載。市HP「家庭ごみの正しい出し方」の資源ごみ（その他の紙類：本、雑誌、チラシなど）より",
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
        # URLに入れる町名のID（例：西白島町 → nishihakushimachou）
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


def main():
    OUT.mkdir(parents=True, exist_ok=True)

    def write(fname, obj):
        (OUT / fname).write_text(
            json.dumps(obj, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
        )

    items = build_items()
    write("items.json", items)

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
