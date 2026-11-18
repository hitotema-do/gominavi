"""品目ごとのページ（検索の入口）を、app/data/items.json から作る。

app/gomi/<よみ>.html を品目ごとに1枚、app/gomi/index.html に一覧を1枚作り、
app/sitemap.xml にも足す。内容はアプリと同じデータだけを使う（推測で書かない）。
build_data.py のあとに実行する。

    python scripts/build_item_pages.py
"""
import html
import json
import re
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "app"
OUT = APP / "gomi"
BASE = "https://hitotema-do.github.io/gominavi/"

# アプリの CATS と同じ考え方（index.html の「分別事典の分別区分」）
CATS = {
    "可燃ごみ": ("#C4421A", "可燃ごみ", None),
    "リサイクルプラ": ("#1F6FB2", "リサイクルプラ", None),
    "ペットボトル": ("#1F6FB2", "リサイクルプラ", "リサイクルプラと同じ日に、袋を分けて出してください。"),
    "その他プラ": ("#6B4FA8", "その他プラ", None),
    "資源ごみ": ("#2C7A3F", "資源ごみ", None),
    "有害ごみ": ("#2C7A3F", "資源ごみ", "資源ごみと同じ日に、袋を分けて「有害」と書いて出してください。"),
    "不燃ごみ": ("#4F5D6B", "不燃ごみ", None),
    "大型ごみ": ("#8A5A1E", "大型ごみ", None),
    "家電リサイクル": ("#A33A3A", None, None),
    "市では収集しない": ("#A33A3A", None, None),
}
BATTERY_TIP = "電池は、端子部分をテープで覆ってから出してください（ショートによる発火を防ぐため）。"
RESERVE = """<div class="box">
  <p><strong>大型ごみは予約が必要です（有料）。</strong></p>
  <p><a href="https://ogatagomi.city.hiroshima.lg.jp/eco/view/hiroshima/top.html" rel="noopener">インターネットで予約する（24時間）</a></p>
  <p>電話：0570-082530 または 082-544-5300（平日 9時〜18時）</p>
  <p>締め切り：インターネットは収集日の5日前、電話は3日前まで（土日祝を除いて数えます）</p>
</div>"""
KADEN = """<div class="box">
  <p><strong>家電リサイクル法の対象です。処分のしかたは3通りあります。</strong></p>
  <p>1. 買い替える店、または購入した店に引き取ってもらう</p>
  <p>2. 郵便局で家電リサイクル券を買ってリサイクル料金を払い、自分で指定の場所に持ち込む（予約不要）</p>
  <p>3. 市に収集を頼む（リサイクル料金のほかに、収集運搬手数料が1台3,000円。大型ごみ受付センター 0570-082530 に申し込み）</p>
</div>"""
KANA_ROWS = [("あ", "あいうえおぁぃぅぇぉ"), ("か", "かきくけこがぎぐげご"), ("さ", "さしすせそざじずぜぞ"),
             ("た", "たちつてとだぢづでどっ"), ("な", "なにぬねの"), ("は", "はひふへほばびぶべぼぱぴぷぺぽ"),
             ("ま", "まみむめも"), ("や", "やゆよゃゅょ"), ("ら", "らりるれろ"), ("わ", "わをんゎ")]
e = html.escape


def slug(y):
    s = re.sub(r"[()（）・/\\、,\s]+", "_", y).strip("_")
    return s


def base_name(n):
    return re.split(r"[(（]", n)[0]


def kana_row(y):
    for row, chars in KANA_ROWS:
        if y[:1] in chars:
            return row
    return "その他"

# ひとてま堂の数え係（案内ページ用）：このページを、この端末で1日1回だけ「+1」する。
# 送るのはアプリ名・ページ名・来たサイトの名前だけ（名前や端末を見分ける番号は送らない）。
# 作者の端末（アプリ側で「数えない」にしたもの）は数えない
COUNTER = r"""<script>
(function () {
  try {
    if (localStorage.getItem("hitotema.count.off")) return;
    var APP = "gominavi", KEY = "hitotema.page." + APP;
    var page = decodeURIComponent(location.pathname.split("/").pop().replace(/\.html$/, "")) || "index";
    var day = new Date(Date.now() + 9 * 3600e3).toISOString().slice(0, 10);
    var s = JSON.parse(localStorage.getItem(KEY) || "null");
    if (!s || s.d !== day) s = { d: day, p: [] };
    if (s.p.indexOf(page) >= 0) return;
    s.p.push(page);
    localStorage.setItem(KEY, JSON.stringify(s));
    var ref = ""; try { ref = new URL(document.referrer).hostname; if (ref === location.hostname) ref = "self"; } catch (e) {}
    navigator.sendBeacon("https://hitotema-count.hitotema-do.workers.dev/page",
      new Blob([JSON.stringify({ a: APP, p: page, r: ref })], { type: "text/plain" }));
  } catch (e) {}
})();
</script>"""

def page(title, desc, url, body):
    return f"""<!doctype html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>{e(title)}</title>
<meta name="description" content="{e(desc)}">
<link rel="canonical" href="{url}">
<meta property="og:type" content="article">
<meta property="og:locale" content="ja_JP">
<meta property="og:site_name" content="広島市ゴミナビ">
<meta property="og:title" content="{e(title)}">
<meta property="og:description" content="{e(desc)}">
<meta property="og:url" content="{url}">
<meta property="og:image" content="{BASE}og.png">
<meta name="twitter:card" content="summary_large_image">
<link rel="icon" href="../icon.svg" type="image/svg+xml">
<link href="https://fonts.googleapis.com/css2?family=BIZ+UDPGothic:wght@400;700&display=swap" rel="stylesheet">
<link rel="stylesheet" href="../pages.css">
<style>
.cat {{ display: inline-block; color: #fff; font-weight: 700; padding: 4px 14px; border-radius: 999px; font-size: 18px; }}
.ans {{ background: var(--card); border: 1px solid var(--line); border-radius: 12px; padding: 16px; margin: 0 0 16px; }}
.ans .how {{ font-size: 17px; margin: 12px 0 0; }}
.box {{ background: var(--card); border: 1px solid var(--line); border-radius: 10px; padding: 12px 16px; margin: 0 0 16px; }}
.box p {{ margin: 0 0 6px; }}
.small {{ font-size: 13px; color: var(--sub); }}
.links {{ display: flex; flex-wrap: wrap; gap: 6px 14px; list-style: none; padding: 0; }}
.crumb {{ font-size: 13px; color: var(--sub); }}
.crumb a {{ color: var(--sub); }}
</style>
{COUNTER}
</head>
<body>
<div class="wrap">
{body}
  <div class="foot">
    <nav aria-label="運営情報">
      <a href="../about.html">このアプリについて</a>
      <a href="../privacy.html">プライバシーポリシー</a>
      <a href="../contact.html">お問い合わせ</a>
      <a href="../hitotema.html">ひとてま堂について</a>
    </nav>
    <p>広島市の公開データ（家庭ごみの分別事典など）をもとに、ひとてま堂が作っています。広島市の公式サービスではありません。最新の情報や判断に迷うときは、広島市のホームページや各区の環境事業所で確かめてください。</p>
  </div>
</div>
</body>
</html>
"""


def main():
    items = json.loads((APP / "data" / "items.json").read_text(encoding="utf-8"))
    real = [it for it in items if it.get("c")]
    by_name = {it["n"]: it for it in real}
    aliases = {}
    for it in items:
        if it.get("ref") and it["ref"] in by_name:
            aliases.setdefault(it["ref"], []).append(it["n"])
    real.sort(key=lambda it: it["y"])
    slugs = {}
    for it in real:
        s = slug(it["y"])
        while s in slugs.values():
            s += "_"
        slugs[it["n"]] = s

    OUT.mkdir(exist_ok=True)
    for old in OUT.glob("*.html"):
        old.unlink()

    for i, it in enumerate(real):
        n, c = it["n"], it["c"]
        color, kind, tip = CATS.get(c, ("#4F5D6B", None, None))
        url = f"{BASE}gomi/{slugs[n]}.html"
        al = aliases.get(n, [])
        title = f"{n}は何ごみ？捨て方・出し方｜広島市ゴミナビ"
        desc = f"広島市で{n}を捨てるときは「{c}」です。{it['h']}" + (f"（{'・'.join(al)}も同じ）" if al else "")
        parts = [f'  <p class="crumb"><a href="../">広島市ゴミナビ</a> ＞ <a href="./">品目から探す</a></p>',
                 f"  <h1>{e(n)}の捨て方（広島市）</h1>",
                 f'  <div class="ans"><span class="cat" style="background:{color}">{e(c)}</span>',
                 f'  <p class="how">{e(it["h"])}</p></div>']
        if tip and not ("有害" in it["h"] or "袋を分けて" in it["h"]):
            parts.append(f"  <p>{e(tip)}</p>")
        if re.search(r"電池|バッテリー", n) and c == "有害ごみ" and "テープ" not in it["h"]:
            parts.append(f"  <p>{e(BATTERY_TIP)}</p>")
        if c == "大型ごみ":
            parts.append(RESERVE)
        if c == "家電リサイクル":
            parts.append(KADEN)
        if it.get("note"):
            parts.append(f'  <p class="small">補足：{e(it["note"])}</p>')
        if al:
            parts.append(f'  <p class="small">別の呼び方：{e("、".join(al))}</p>')
        if kind:
            parts.append(f"  <h2>{e(kind)}の収集日</h2>")
            parts.append(f"  <p>{e(kind)}の収集日は、町によって違います。ゴミナビで町名を選ぶと、次に出せる日がすぐ分かります。</p>")
        else:
            parts.append("  <h2>ほかの品目も調べる</h2>")
        q = quote(n)
        label = f"{n}を次に出せる日を見る" if kind else "ゴミナビで調べる"
        parts.append(f'  <p><a class="btn" href="../?from=item&amp;q={q}">{e(label)}</a></p>')
        if kind:
            parts.append('  <p class="small">初めての方は、区と町を選ぶと表示されます（無料・登録不要）。</p>')
        # 関連：名前が似ているもの → 同じ区分で50音が近いもの
        b = base_name(n)
        tail = b[-2:] if len(b) >= 3 and re.fullmatch(r"[\u4e00-\u9fff]{2}", b[-2:]) else None
        rel = [x for x in real if x["n"] != n and len(b) >= 2 and (base_name(x["n"]) == b or b in x["n"])]
        rel += [x for x in real if x["n"] != n and tail and tail in x["n"] and x not in rel]
        same = sorted((x for j, x in enumerate(real) if x["n"] != n and x["c"] == c and x not in rel),
                      key=lambda x: abs(real.index(x) - i))
        rel = (rel[:5] + same)[:8]
        if rel:
            parts.append("  <h2>関連する品目</h2>")
            parts.append('  <ul class="links">' + "".join(
                f'<li><a href="{slugs[x["n"]]}.html">{e(x["n"])}</a></li>' for x in rel) + "</ul>")
        (OUT / f"{slugs[n]}.html").write_text(page(title, desc, url, "\n".join(parts)), encoding="utf-8")

    # 一覧ページ
    groups = {}
    for it in real:
        groups.setdefault(kana_row(it["y"]), []).append(it)
    order = [r for r, _ in KANA_ROWS] + ["その他"]
    body = ['  <p class="crumb"><a href="../">広島市ゴミナビ</a> ＞ 品目から探す</p>',
            "  <h1>広島市のごみの分け方　品目一覧</h1>",
            f"  <p>{len(real)}品目の分け方を、50音順にまとめました。品目名を押すと、分け方と出し方が分かります。</p>",
            '  <p><a class="btn" href="../?from=itemlist">ゴミナビで品目名を入れて調べる</a></p>',
            '  <p class="links">' + " ".join(f'<a href="#k-{r}">{r}行</a>' for r in order if r in groups) + "</p>"]
    for r in order:
        if r not in groups:
            continue
        body.append(f'  <h2 id="k-{r}">{r}行</h2>')
        body.append('  <ul class="links">' + "".join(
            f'<li><a href="{slugs[x["n"]]}.html">{e(x["n"])}</a></li>' for x in groups[r]) + "</ul>")
    (OUT / "index.html").write_text(page(
        "広島市のごみの分け方 品目一覧（50音順）｜広島市ゴミナビ",
        f"広島市の家庭ごみ{len(real)}品目の分け方を50音順にまとめた一覧。品目ごとに、何ごみか・出し方・大型ごみの予約などが分かります（非公式）。",
        f"{BASE}gomi/", "\n".join(body)), encoding="utf-8")

    # サイトマップ（品目ページ以外の行は残す）
    sm = APP / "sitemap.xml"
    keep = [u for u in re.findall(r"<loc>(.*?)</loc>", sm.read_text(encoding="utf-8")) if "/gomi/" not in u]
    urls = keep + [f"{BASE}gomi/"] + [f"{BASE}gomi/{slugs[it['n']]}.html" for it in real]
    sm.write_text('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
                  + "".join(f"  <url>\n    <loc>{quote(u, safe=':/')}</loc>\n  </url>\n" for u in urls)
                  + "</urlset>\n", encoding="utf-8")
    print(f"品目ページ {len(real)} 枚、一覧 1 枚を作りました（{OUT}）")


if __name__ == "__main__":
    main()
