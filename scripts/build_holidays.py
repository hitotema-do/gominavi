"""よくある質問の「祝日もごみは収集される？」の日付を、収集日データから自動で作り直す。

内閣府の祝日一覧（syukujitsu.csv）と、app/data/*.json の収集日を突き合わせ、
可燃ごみ・リサイクルプラ（ペットボトル）が「収集する日」「収集しない日」を割り出して、
app/index.html の <!--hol-ja-->…<!--/hol-ja-->、<!--hol-en-->…<!--/hol-en--> の間を書き換える。
build_data.py のあとに実行する（scripts/auto_update.py が続けて呼ぶ）。

    python scripts/build_holidays.py
"""
import csv
import datetime
import io
import json
import re
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "app" / "data"
INDEX = ROOT / "app" / "index.html"
HOLIDAY_CSV = "https://www8.cao.go.jp/chosei/shukujitsu/syukujitsu.csv"
EXTRA = [(8, 6)]  # 広島市の平和記念日（国の祝日ではないが市のごみ収集はお休み・平日扱いが変わる）
YEAR_END = [(12, 29), (12, 30), (12, 31), (1, 1), (1, 2), (1, 3)]


def national_holidays():
    req = urllib.request.Request(HOLIDAY_CSV, headers={"User-Agent": "gominavi-update"})
    with urllib.request.urlopen(req, timeout=30) as res:
        text = res.read().decode("cp932")
    out = set()
    for row in list(csv.reader(io.StringIO(text)))[1:]:
        try:
            y, m, d = (int(x) for x in row[0].split("/"))
        except ValueError:
            continue
        out.add(datetime.date(y, m, d))
    return out


def compute():
    """(年度の西暦, 収集する日の一覧, 収集しない日の一覧) を返す。一覧は date のリスト"""
    wards = json.loads((DATA / "wards.json").read_text(encoding="utf-8"))
    sched = {}
    for w in wards["wards"]:
        j = json.loads((DATA / f"{w['code']}.json").read_text(encoding="utf-8"))
        start = datetime.date.fromisoformat(j["start"])
        sched[w["code"]] = (start, j)
    start = min(s for s, _ in sched.values())
    end = max(datetime.date.fromisoformat(j["end"]) for _, j in sched.values())
    hol = national_holidays()
    days = {d for d in hol if start <= d <= end}
    for y in (start.year, end.year):
        for m, d in EXTRA + YEAR_END:
            x = datetime.date(y, m, d)
            if start <= x <= end:
                days.add(x)
    collected = set()
    for st, j in sched.values():
        for g in j["groups"].values():
            for i, c in enumerate(g["d"]):
                if c in ("k", "r"):
                    collected.add(st + datetime.timedelta(days=i))
    # 土日は通常も収集しないので載せない（ただし年末年始の連続休みは、土日をはさんでも「1/1〜3」の形で載せる）
    year_end = {(m, d) for m, d in YEAR_END}
    days = sorted(d for d in days if d.weekday() < 5 or (d.month, d.day) in year_end)
    return start.year, [d for d in days if d in collected], [d for d in days if d not in collected]


def group_ja(days):
    """同じ月の日付を 5/4・5・6 の形にまとめる。1/1〜3 は年始の連続休み"""
    skip_new_year = [d for d in days if d.month == 1 and d.day <= 3]
    rest = [d for d in days if d not in skip_new_year or len(skip_new_year) < 3]
    parts = []
    by_month = {}
    for d in rest:
        by_month.setdefault((d.year, d.month), []).append(d.day)
    for (y, m), ds in sorted(by_month.items()):
        parts.append((y, m, f"{m}/" + "・".join(str(x) for x in ds)))
    if len(skip_new_year) >= 3:
        parts.append((skip_new_year[0].year, 1, "1/1〜3"))
    parts.sort(key=lambda p: (p[0], p[1], 0 if p[2] != "1/1〜3" else 1))
    return "、".join(p[2] for p in parts)


def group_en(days):
    skip_new_year = [d for d in days if d.month == 1 and d.day <= 3]
    items = []
    for d in days:
        if d in skip_new_year and len(skip_new_year) >= 3:
            if d.day == 1:
                items.append((d, "1/1–1/3"))
            continue
        items.append((d, f"{d.month}/{d.day}"))
    return ", ".join(t for _, t in items)


def build_blocks(year, yes, no):
    fy = year  # 年度の西暦（4月始まり）
    ja = (
        f"<p><strong>可燃ごみ・ペットボトル・リサイクルプラ</strong>は、祝日によって収集する日としない日があります（{fy}年度）。</p>\n"
        f"      <ul>\n        <li>収集する：{group_ja(yes)}</li>\n        <li>収集しない：{group_ja(no)}</li>\n      </ul>"
    )
    en = (
        f"<p><strong>Combustible waste, PET bottles and recyclable plastics</strong> are collected on some holidays and not on others (FY{fy}).</p>\n"
        f"      <ul>\n        <li>Collected: {group_en(yes)}</li>\n        <li>Not collected: {group_en(no)}</li>\n      </ul>"
    )
    return ja, en


def check_year_end(yes, no):
    """「年末年始の収集」の説明（12/29・30は収集、12/31〜1/3はお休み）が、今年度のデータと合っているか"""
    md_yes = {(d.month, d.day) for d in yes}
    weekdays = {(d.month, d.day) for d in yes + no if d.weekday() < 5}
    problems = []
    for md in ((12, 29), (12, 30)):
        if md in weekdays and md not in md_yes:
            problems.append(f"{md[0]}/{md[1]} が収集日になっていません（よくある質問の「年末年始」の説明と食い違います）")
    for md in ((12, 31), (1, 1), (1, 2), (1, 3)):
        if md in md_yes:
            problems.append(f"{md[0]}/{md[1]} が収集日になっています（「年末年始」の説明と食い違います）")
    return problems


def write_index(ja, en):
    s = INDEX.read_text(encoding="utf-8")
    for tag, block in (("ja", ja), ("en", en)):
        pat = re.compile(rf"(<!--hol-{tag}-->).*?(<!--/hol-{tag}-->)", re.S)
        if len(pat.findall(s)) != 1:
            raise SystemExit(f"index.html に hol-{tag} の印が1か所だけ見つかりません")
        s = pat.sub(lambda m: m.group(1) + block + m.group(2), s)
    INDEX.write_text(s, encoding="utf-8", newline="")


def main():
    year, yes, no = compute()
    problems = check_year_end(yes, no)
    if problems:
        raise SystemExit("祝日の確認で問題：\n" + "\n".join(problems))
    ja, en = build_blocks(year, yes, no)
    write_index(ja, en)
    print(f"よくある質問の祝日を更新（{year}年度）：収集 {len(yes)} 日、休み {len(no)} 日")


if __name__ == "__main__":
    main()
