"""町名ごとのごみの日のページ（検索の入口）を、app/data/ の収集日データから作る。

app/machi/<区コード>-<町ID>.html を町ごとに1枚、app/machi/index.html に一覧を1枚作り、
app/sitemap.xml にも足す。内容はアプリと同じ収集日データだけを使う（推測で書かない）。
「毎週〇曜日」「月2回」などの言い方も、その年度のデータから数えて決める。
build_data.py のあとに実行する。

    python scripts/build_town_pages.py
"""
import datetime as dt
import json
import re
from collections import Counter
from pathlib import Path
from urllib.parse import quote

from build_item_pages import COUNTER, e, page

ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "app"
OUT = APP / "machi"
BASE = "https://hitotema-do.github.io/gominavi/"
WEEK = "月火水木金土日"  # date.weekday() の順
WARD_ORDER = ["naka", "higashi", "minami", "nishi", "asaminami", "asakita", "aki", "saeki"]

# アプリの KINDS と同じ（収集日データの1文字コード → 名前・短い名前・色）
KINDS = {
    "k": ("可燃ごみ", "可燃", "#C4421A"),
    "r": ("リサイクルプラ・ペットボトル", "リプラ", "#1F6FB2"),
    "p": ("その他プラ", "他プラ", "#6B4FA8"),
    "s": ("資源ごみ・有害ごみ", "資源", "#2C7A3F"),
    "f": ("不燃ごみ", "不燃", "#4F5D6B"),
    "o": ("大型ごみ（要予約）", "大型", "#8A5A1E"),
}
WEEKLY_MIN = 40  # 1年で40回以上ある曜日を「毎週」とみなす

# 数え係：ページ名はファイル名ではなく「町「〇〇」」で送る（ダッシュボードで読めるように）
COUNTER_PAGE = 'var page = decodeURIComponent(location.pathname.split("/").pop().replace(/\\.html$/, "")) || "index";'
assert COUNTER_PAGE in COUNTER

NEXT_JS = r"""<script>
(function () {
  var el = document.getElementById("next");
  if (!el) return;
  var K = { k: ["可燃ごみ", "#C4421A"], r: ["リサイクルプラ・ペットボトル", "#1F6FB2"], p: ["その他プラ", "#6B4FA8"],
            s: ["資源ごみ・有害ごみ", "#2C7A3F"], f: ["不燃ごみ", "#4F5D6B"], o: ["大型ごみ（要予約）", "#8A5A1E"] };
  var W = "日月火水木金土";
  var p = el.dataset.start.split("-"), start = new Date(+p[0], p[1] - 1, +p[2]);
  var d = el.dataset.d, o = el.dataset.o.split(",").map(Number);
  var now = new Date(), today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  var from = Math.round((today - start) / 864e5);
  if (now.getHours() * 60 + now.getMinutes() >= 8 * 60 + 30) from += 1; // 朝8時30分を過ぎたら今日は出せない
  if (from < 0 || from >= d.length) return;
  var rows = Object.keys(K).map(function (k) {
    for (var i = Math.max(from, 0); i < d.length; i++) {
      if ((k === "o" && o.indexOf(i) >= 0) || d.charAt(i) === k) {
        var x = new Date(start.getFullYear(), start.getMonth(), start.getDate() + i);
        var n = Math.round((x - today) / 864e5);
        var when = n === 0 ? "今日" : n === 1 ? "あす" : n + "日後";
        return '<tr><th style="color:' + K[k][1] + '">' + K[k][0] + "</th><td>" + (x.getMonth() + 1) + "月" + x.getDate() + "日（" + W[x.getDay()] + "）<span class=\"small\">　" + when + "</span></td></tr>";
      }
    }
    return "";
  }).join("");
  if (rows) el.innerHTML = "<h2>次の収集日</h2><table>" + rows + "</table>";
})();
</script>"""

STYLE = """<style>
.small { font-size: 13px; color: var(--sub); }
.crumb { font-size: 13px; color: var(--sub); }
.crumb a { color: var(--sub); }
.links { display: flex; flex-wrap: wrap; gap: 6px 14px; list-style: none; padding: 0; }
.sched th { width: auto; white-space: nowrap; }
.months { font-size: 14px; }
.months th, .months td { padding: 6px 6px 6px 0; }
.months th { width: 3em; }
#next th { width: 55%; }
</style>"""


def page_name(n):
    return "町「" + re.sub(r"[^\w\-]", "_", n) + "」"


def analyze(start, sched):
    """種類ごとに、収集日（date の一覧）と、言い方（毎週〇曜日／月〇回）を返す。"""
    days = {}
    for i, c in enumerate(sched["d"]):
        if c != "-":
            days.setdefault(c, []).append(start + dt.timedelta(i))
    days["o"] = [start + dt.timedelta(i) for i in sched["o"]]
    out = {}
    for k in KINDS:
        ds = days.get(k, [])
        if not ds:
            continue
        wk = Counter(x.weekday() for x in ds)
        weekly = sorted(w for w, c in wk.items() if c >= WEEKLY_MIN)
        if weekly:
            # 毎週の曜日なのに収集しない日（祝日・年末年始など）。データから数えるだけ
            off = []
            x = start
            have = set(ds)
            end = start + dt.timedelta(len(sched["d"]) - 1)
            while x <= end:
                if x.weekday() in weekly and x not in have:
                    off.append(x)
                x += dt.timedelta(1)
            other = [x for x in ds if x.weekday() not in weekly]
            out[k] = {"weekly": weekly, "off": off, "other": other, "dates": ds}
        else:
            main = wk.most_common(1)[0][0]
            per_month = round(len(ds) / 12)
            out[k] = {"monthly": per_month, "main": main, "mixed": len(wk) > 1, "dates": ds}
    return out


def say(info):
    if "weekly" in info:
        return "毎週" + "・".join(WEEK[w] for w in info["weekly"]) + "曜日"
    s = f"月{info['monthly']}回（{WEEK[info['main']]}曜日）"
    return s + "　※曜日がずれる日あり" if info["mixed"] else s


def md(x):
    return f"{x.month}/{x.day}（{WEEK[x.weekday()]}）"


def build_town(ward, town, data, start, same, fy):
    sched = data["groups"][str(town["g"])]
    info = analyze(start, sched)
    n, wn = town["n"], ward["name"]
    fname = f"{ward['code']}-{town['id']}"
    url = f"{BASE}machi/{fname}.html"
    weekly = [f"{KINDS[k][0]}は{say(v)}" for k, v in info.items() if "weekly" in v]
    monthly = [KINDS[k][0].replace("（要予約）", "") for k, v in info.items() if "monthly" in v]
    title = f"{n}（{wn}）のごみの日・収集日｜広島市ゴミナビ"
    desc = (f"広島市{wn}{n}のごみの日。" + "、".join(weekly) + "。"
            + ("・".join(monthly) + "は月2回。" if monthly else "")
            + "祝日・年末年始のお休みや、次の収集日も分かります（非公式）。")

    parts = [f'  <p class="crumb"><a href="../">広島市ゴミナビ</a> ＞ <a href="./">町名から探す</a> ＞ <a href="./#w-{ward["code"]}">{e(wn)}</a></p>',
             f"  <h1>{e(n)}（広島市{e(wn)}）のごみの日</h1>",
             '  <table class="sched">']
    for k, v in info.items():
        parts.append(f'    <tr><th style="color:{KINDS[k][2]}">{e(KINDS[k][0])}</th><td>{e(say(v))}</td></tr>')
    parts.append("  </table>")
    parts.append("  <p>収集日の朝8時30分までに出してください。</p>")
    d_attr = sched["d"]
    o_attr = ",".join(map(str, sched["o"]))
    parts.append(f'  <div id="next" data-start="{data["start"]}" data-d="{d_attr}" data-o="{o_attr}"></div>')
    parts.append(f'  <p><a class="btn" href="../?from=town&amp;area={ward["code"]}-{town["id"]}">{e(n)}のカレンダーをゴミナビで見る</a></p>')
    parts.append('  <p class="small">ゴミナビでは、町を選んでおくと、次に出せる日と品目の分け方をすぐに調べられます（無料・登録不要）。</p>')

    # 月2回のもの：月ごとの日付
    mk = [k for k, v in info.items() if "monthly" in v]
    if mk:
        parts.append(f"  <h2>月2回のごみの収集日（{fy}）</h2>")
        parts.append('  <table class="months"><tr><th>月</th>' + "".join(
            f'<th style="color:{KINDS[k][2]}">{KINDS[k][1]}</th>' for k in mk) + "</tr>")
        months = []
        x = start.replace(day=1)
        while len(months) < 12:
            months.append((x.year, x.month))
            x = (x + dt.timedelta(32)).replace(day=1)
        for y, m in months:
            cells = []
            for k in mk:
                ds = [z for z in info[k]["dates"] if (z.year, z.month) == (y, m)]
                cells.append("・".join(f"{z.day}日" + ("" if z.weekday() == info[k]["main"] else f"（{WEEK[z.weekday()]}）") for z in ds) or "－")
            parts.append(f"    <tr><th>{m}月</th>" + "".join(f"<td>{c}</td>" for c in cells) + "</tr>")
        parts.append("  </table>")
        parts.append(f'  <p class="small">表の見出し：{e("、".join(KINDS[k][1] + "＝" + KINDS[k][0] for k in mk))}。大型ごみは予約が必要です（有料）。</p>')

    # 毎週のもの：お休みの日
    wk = [(k, v) for k, v in info.items() if "weekly" in v]
    if any(v["off"] or v["other"] for _, v in wk):
        parts.append(f"  <h2>祝日・年末年始のお休み（{fy}）</h2>")
        for k, v in wk:
            if v["off"]:
                parts.append(f'  <p><strong style="color:{KINDS[k][2]}">{e(KINDS[k][0])}</strong>がお休みの日：{"、".join(md(z) for z in v["off"])}</p>')
            if v["other"]:
                parts.append(f'  <p><strong style="color:{KINDS[k][2]}">{e(KINDS[k][0])}</strong>がいつもと違う曜日にある日：{"、".join(md(z) for z in v["other"])}</p>')
        parts.append("  <p>12月31日〜1月3日は、すべてのごみの収集がお休みです。</p>")

    if same:
        parts.append(f"  <h2>{e(wn)}で同じ収集日の町</h2>")
        parts.append('  <ul class="links">' + "".join(
            f'<li><a href="{ward["code"]}-{t["id"]}.html">{e(t["n"])}</a></li>' for t in same) + "</ul>")
    parts.append("  <h2>ほかの町・品目を調べる</h2>")
    parts.append('  <ul class="links"><li><a href="./">町名の一覧</a></li><li><a href="../gomi/">品目の分け方の一覧</a></li></ul>')

    body = "\n".join(parts) + "\n" + NEXT_JS
    html = page(title, desc, url, body)
    html = html.replace(COUNTER_PAGE, f'var page = "{page_name(n)}";', 1)
    html = html.replace("<link rel=\"stylesheet\" href=\"../pages.css\">", "<link rel=\"stylesheet\" href=\"../pages.css\">\n" + STYLE, 1)
    (OUT / f"{fname}.html").write_text(html, encoding="utf-8")
    return f"{BASE}machi/{fname}.html"


def main():
    W = json.loads((APP / "data" / "wards.json").read_text(encoding="utf-8"))
    wards = sorted(W["wards"], key=lambda w: WARD_ORDER.index(w["code"]) if w["code"] in WARD_ORDER else 99)
    OUT.mkdir(exist_ok=True)
    for old in OUT.glob("*.html"):
        old.unlink()

    urls, count, fy = [], 0, ""
    for w in wards:
        data = json.loads((APP / "data" / f"{w['code']}.json").read_text(encoding="utf-8"))
        start = dt.date.fromisoformat(data["start"])
        fy = f"{start.year}年度"
        towns = sorted(w["towns"], key=lambda t: t["y"])
        for t in towns:
            same = [x for x in towns if x["g"] == t["g"] and x["id"] != t["id"]]
            urls.append(build_town(w, t, data, start, same, fy))
            count += 1

    # 一覧ページ
    body = ['  <p class="crumb"><a href="../">広島市ゴミナビ</a> ＞ 町名から探す</p>',
            "  <h1>広島市のごみの日　町名から探す</h1>",
            f"  <p>広島市の{count}の町の、ごみの収集日（{fy}）をまとめました。町名を押すと、ごみの種類ごとの曜日と、祝日・年末年始のお休みが分かります。</p>",
            '  <p><a class="btn" href="../?from=townlist">ゴミナビで町を選んで、次に出せる日を見る</a></p>',
            '  <p class="links">' + " ".join(f'<a href="#w-{w["code"]}">{e(w["name"])}</a>' for w in wards) + "</p>"]
    for w in wards:
        body.append(f'  <h2 id="w-{w["code"]}">{e(w["name"])}</h2>')
        body.append('  <ul class="links">' + "".join(
            f'<li><a href="{w["code"]}-{t["id"]}.html">{e(t["n"])}</a></li>' for t in sorted(w["towns"], key=lambda t: t["y"])) + "</ul>")
    html = page("広島市のごみの日 町名から探す（収集日・曜日）｜広島市ゴミナビ",
                f"広島市の{count}の町の、可燃ごみ・リサイクルプラ・資源ごみ・不燃ごみ・大型ごみの収集日を町名から探せます（{fy}・非公式）。",
                f"{BASE}machi/", "\n".join(body))
    html = html.replace(COUNTER_PAGE, 'var page = "町の一覧";', 1)
    html = html.replace("<link rel=\"stylesheet\" href=\"../pages.css\">", "<link rel=\"stylesheet\" href=\"../pages.css\">\n" + STYLE, 1)
    (OUT / "index.html").write_text(html, encoding="utf-8")

    # サイトマップ（町のページ以外の行は残す）
    sm = APP / "sitemap.xml"
    keep = [u for u in re.findall(r"<loc>(.*?)</loc>", sm.read_text(encoding="utf-8")) if "/machi/" not in u]
    urls = keep + [f"{BASE}machi/"] + urls
    sm.write_text('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
                  + "".join(f"  <url>\n    <loc>{quote(u, safe=':/%')}</loc>\n  </url>\n" for u in urls)
                  + "</urlset>\n", encoding="utf-8")
    print(f"町のページ {count} 枚、一覧 1 枚を作りました（{OUT}）")


if __name__ == "__main__":
    main()
