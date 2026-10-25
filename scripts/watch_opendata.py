"""広島市オープンデータの見張り番。

ゴミナビが使っているデータ（data/opendata_state.json に記録）と、
オープンデータサイトの今の状態を比べ、新しいファイルや更新があれば知らせる。
GitHub Actions（.github/workflows/watch.yml）から毎日呼ばれる。

    python scripts/watch_opendata.py           # 見張る時期なら比べる
    python scripts/watch_opendata.py --force   # 時期に関係なく比べる
    python scripts/watch_opendata.py --record  # 今の状態を「使っているデータ」として記録する

--record は、新しいデータでゴミナビを更新し終えたあとに実行してコミットする。
"""
import argparse
import datetime
import html
import json
import os
import re
import sys
import time
import urllib.request
from pathlib import Path

DATASET_URL = "https://hiroshima-opendata.dataeye.jp/datasets/1338"
RESOURCE_URL = "https://hiroshima-opendata.dataeye.jp/resources/{id}"
STATE = Path(__file__).resolve().parent.parent / "data" / "opendata_state.json"
JST = datetime.timezone(datetime.timedelta(hours=9))

# 新年度のデータが出る時期は毎日、それ以外は毎月1日だけ見る
DAILY_FROM = (1, 15)
DAILY_UNTIL = (4, 10)


def fetch(url, tries=3):
    req = urllib.request.Request(url, headers={"User-Agent": "gominavi-watch (+https://hitotema-do.github.io/gominavi/)"})
    for i in range(tries):
        try:
            with urllib.request.urlopen(req, timeout=30) as res:
                return res.read().decode("utf-8")
        except OSError:  # 一時的なネットの不調は少し待ってやり直す
            if i == tries - 1:
                raise
            time.sleep(30)


def cell(page, label):
    m = re.search(r"<td>\s*" + label + r"\s*</td>\s*<td>(.*?)</td>", page, re.S)
    if not m:
        raise SystemExit(f"リソースのページから「{label}」が読み取れません（サイトの作りが変わった可能性）")
    return re.sub(r"<[^>]+>|\(単位:バイト\)", "", m.group(1)).split()[0]


def current_resources():
    page = fetch(DATASET_URL)
    found = re.findall(r'resources/(\d+)" class="is-resource">\s*<dl[^>]*>\s*<dt>(.*?)</dt>', page, re.S)
    if len(found) < 2:
        raise SystemExit("データセットのページからファイル一覧が読み取れません（サイトの作りが変わった可能性）")
    resources = {}
    for rid, name in found:
        page = fetch(RESOURCE_URL.format(id=rid))
        resources[rid] = {
            "name": html.unescape(name).strip(),
            "updated": cell(page, "最終更新日"),
            "size": cell(page, "ファイルサイズ"),
        }
    return resources


def in_watch_period(today):
    md = (today.month, today.day)
    return DAILY_FROM <= md <= DAILY_UNTIL or today.day == 1


def compare(old, new):
    changes = []
    for rid, r in new.items():
        before = old.get(rid)
        if before is None:
            changes.append(f"- **新しいファイル**：{r['name']}（最終更新日 {r['updated']}）\n  {RESOURCE_URL.format(id=rid)}")
        elif (before["updated"], before["size"]) != (r["updated"], r["size"]):
            changes.append(
                f"- **更新**：{r['name']}\n"
                f"  最終更新日 {before['updated']} → {r['updated']}、サイズ {before['size']} → {r['size']} バイト\n"
                f"  {RESOURCE_URL.format(id=rid)}"
            )
    return changes


def output(name, value):
    path = os.environ.get("GITHUB_OUTPUT")
    if path:
        with open(path, "a", encoding="utf-8") as f:
            f.write(f"{name}<<EOF\n{value}\nEOF\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--record", action="store_true")
    args = ap.parse_args()

    if args.record:
        STATE.write_text(json.dumps(current_resources(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"記録しました → {STATE}")
        return

    today = datetime.datetime.now(JST).date()
    if not (args.force or in_watch_period(today)):
        print(f"{today} は見張る日ではありません")
        output("changes", "")
        return

    changes = compare(json.loads(STATE.read_text(encoding="utf-8")), current_resources())
    report = "\n".join(changes)
    print(report or "変化なし")
    output("changes", report)


if __name__ == "__main__":
    sys.exit(main())
