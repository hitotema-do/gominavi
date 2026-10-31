"""新しい年度のデータが出たら、ゴミナビを自動で作り直す（人の確認なしで公開まで進める）。

GitHub Actions（.github/workflows/watch.yml）から、見張り番が「新しいデータあり」と知らせたときに呼ばれる。

    1. 市のオープンデータから、いちばん新しい年度の収集日程表（ZIP）と分別50音事典（CSV）を取得
    2. data/raw/ に置き、build_data.py で app/data/*.json を作り直す
    3. build_holidays.py で、よくある質問の祝日の日付を作り直す
    4. app/sw.js のキャッシュ番号を1つ上げる
    5. 安全のための点検（去年と比べて極端に違わないか、など）。1つでも引っかかったら何も公開せず、失敗として終わる
    6. 見張り番の記録（data/opendata_state.json）を新しくする

失敗したときは、ファイルを書き換えたままになるので、呼び出し側（Actions）は変更をコミットしないこと。
"""
import datetime
import io
import json
import re
import subprocess
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import watch_opendata as wo  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
APP_DATA = ROOT / "app" / "data"
SW = ROOT / "app" / "sw.js"
DOWNLOAD = "https://hiroshima-opendata.dataeye.jp/resource_download/{id}"
WARDS = ["naka", "higashi", "minami", "nishi", "asaminami", "asakita", "aki", "saeki"]


def download(rid):
    import urllib.request

    req = urllib.request.Request(DOWNLOAD.format(id=rid), headers={"User-Agent": "gominavi-update (+https://hitotema-do.github.io/gominavi/)"})
    with urllib.request.urlopen(req, timeout=60) as res:
        return res.read()


def pick_resources(resources):
    """(収集日程表の令和◯年度, 日程表のリソースID, 事典のリソースID)"""
    sched = []
    for rid, r in resources.items():
        m = re.search(r"収集日程表.*?[（(]R(\d+)[）)]", r["name"])
        if m:
            sched.append((int(m.group(1)), rid))
    jiten = [rid for rid, r in resources.items() if "50音事典" in r["name"]]
    if not sched or len(jiten) != 1:
        raise SystemExit(f"データの一覧から日程表・事典を特定できません: {[r['name'] for r in resources.values()]}")
    year, rid = max(sched)
    return year, rid, jiten[0]


def extract_zip(data, dest):
    """市のZIPはファイル名が Shift_JIS のまま入っているので、読み替えて、フォルダを無視して dest に展開する"""
    dest.mkdir(parents=True, exist_ok=True)
    n = 0
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        for info in z.infolist():
            if info.is_dir():
                continue
            name = info.filename
            if not info.flag_bits & 0x800:  # UTF-8 フラグがなければ cp932
                name = name.encode("cp437").decode("cp932")
            name = name.replace("\\", "/").split("/")[-1]
            if not name.endswith(".csv") or name.startswith("."):
                continue
            (dest / name).write_bytes(z.read(info))
            n += 1
    return n


def load_all():
    """app/data の今の中身（点検で去年と比べるため、作り直す前に読んでおく）"""
    out = {}
    for name in ["items", "wards"] + WARDS:
        p = APP_DATA / f"{name}.json"
        out[name] = json.loads(p.read_text(encoding="utf-8")) if p.exists() else None
    return out


def kind_counts(ward_json):
    c = {}
    for g in ward_json["groups"].values():
        for ch in g["d"]:
            c[ch] = c.get(ch, 0) + 1
        c["o"] = c.get("o", 0) + len(g["o"])
    return c


def validate(old, new, year):
    problems = []
    fy = 2018 + year
    for code in WARDS:
        o, n = old[code], new[code]
        if n is None:
            problems.append(f"{code}: データができていません")
            continue
        if n["start"] != f"{fy}-04-01" or n["end"] != f"{fy + 1}-03-31":
            problems.append(f"{code}: 期間が {n['start']}〜{n['end']}（{fy}-04-01〜{fy + 1}-03-31 のはず）")
        days = (datetime.date.fromisoformat(n["end"]) - datetime.date.fromisoformat(n["start"])).days + 1
        for g, s in n["groups"].items():
            if len(s["d"]) != days:
                problems.append(f"{code} グループ{g}: 日数 {len(s['d'])}（{days}日のはず）")
        if o is None:
            continue
        # 去年と比べて、グループ数・収集回数が極端に違っていないか
        if abs(len(n["groups"]) - len(o["groups"])) > max(1, len(o["groups"]) // 5):
            problems.append(f"{code}: グループ数 {len(o['groups'])} → {len(n['groups'])}")
        co, cn = kind_counts(o), kind_counts(n)
        # グループ数が違うこともあるので、1グループあたりで比べる
        for k in "krspf":
            a, b = co.get(k, 0) / len(o["groups"]), cn.get(k, 0) / len(n["groups"])
            if a and not (0.75 <= b / a <= 1.25):
                problems.append(f"{code}: 「{k}」の収集回数（1グループあたり）が {a:.0f} → {b:.0f}")
        if cn.get("o", 0) == 0:
            problems.append(f"{code}: 大型ごみの日がありません")
    # 町名
    if new["wards"] is None or old["wards"] is None:
        problems.append("wards.json がありません")
    else:
        for ow, nw in zip(old["wards"]["wards"], new["wards"]["wards"]):
            if ow["code"] != nw["code"] or not (0.9 <= len(nw["towns"]) / len(ow["towns"]) <= 1.1):
                problems.append(f"{nw['code']}: 町名 {len(ow['towns'])} → {len(nw['towns'])}")
    # 品目
    if old["items"] and new["items"]:
        a, b = len(old["items"]), len(new["items"])
        if not (0.8 <= b / a <= 1.5):
            problems.append(f"品目の数 {a} → {b}")
        known = {i.get("c") for i in old["items"]}
        unknown = {i.get("c") for i in new["items"]} - known
        if unknown:
            problems.append(f"知らない分別区分が出てきました: {sorted(x for x in unknown if x)}")
    return problems


def bump_sw():
    s = SW.read_text(encoding="utf-8")
    m = re.search(r'const CACHE = "gominavi-v(\d+)";', s)
    if not m:
        raise SystemExit("sw.js の CACHE の番号が見つかりません")
    SW.write_text(s.replace(m.group(0), f'const CACHE = "gominavi-v{int(m.group(1)) + 1}";'), encoding="utf-8", newline="")


def run(*args):
    subprocess.run([sys.executable, *args], check=True, cwd=ROOT)


def main():
    resources = wo.current_resources()
    state = json.loads(wo.STATE.read_text(encoding="utf-8"))
    if not wo.compare(state, resources):
        print("新しいデータはありません")
        return
    year, sched_id, jiten_id = pick_resources(resources)
    print(f"令和{year}年度（{2018 + year}年度）のデータで更新します")

    old = load_all()
    n = extract_zip(download(sched_id), RAW / f"r{year}")
    if n < 24:  # 家庭ごみ8＋大型ごみ8＋町名8
        raise SystemExit(f"ZIPから取り出せたCSVが {n} 個しかありません")
    jiten = download(jiten_id)
    jiten.decode("cp932")  # 文字化けしていないか（市のCSVは Shift_JIS）
    (RAW / "bunbetsu_jiten.csv").write_bytes(jiten)

    run("scripts/build_data.py")
    run("scripts/build_holidays.py")
    problems = validate(old, load_all(), year)
    if problems:
        raise SystemExit("点検で引っかかりました（公開しません）:\n- " + "\n- ".join(problems))
    bump_sw()
    run("scripts/watch_opendata.py", "--record")
    print("更新が終わりました")


if __name__ == "__main__":
    main()
