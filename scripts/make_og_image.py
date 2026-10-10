"""LINE や X でリンクを送ったときに出るカード画像（app/og.png, 1200x630）を作る。

    python scripts/make_og_image.py

文字は Windows の BIZ UDゴシック（アプリ本体と同じ書体）を使う。
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "app" / "og.png"
FONT_R = "C:/Windows/Fonts/BIZ-UDGothicR.ttc"
FONT_B = "C:/Windows/Fonts/BIZ-UDGothicB.ttc"

S = 2  # 2倍で描いて縮小（線をなめらかにするため）
W, H = 1200 * S, 630 * S

BG = "#F6F7F9"
INK = "#1C2128"
SUB = "#5F6B7A"
LINE = "#E2E6EB"
SOFT = "#EEF1F4"
ACCENT = "#0B6E6E"
KIND = {"可燃": "#C4421A", "リプラ": "#1F6FB2", "他プラ": "#6B4FA8", "資源": "#2C7A3F", "不燃": "#4F5D6B", "大型": "#8A5A1E"}


def font(path, size):
    return ImageFont.truetype(path, size * S)


def px(*v):
    return [x * S for x in v]


img = Image.new("RGB", (W, H), BG)
d = ImageDraw.Draw(img)

# ---- 左：アイコン・名前・説明 ----
# アイコン（app/icon.svg と同じごみ箱の線画）
ix, iy, isz = 80, 92, 112
d.rounded_rectangle(px(ix, iy, ix + isz, iy + isz), radius=26 * S, fill=ACCENT)
k = isz / 512
lw = round(28 * k * S)
for path in ([(150, 168), (362, 168)], [(216, 168), (216, 140), (296, 140), (296, 168)],
             [(172, 168), (190, 388), (322, 388), (340, 168)], [(232, 222), (232, 334)], [(280, 222), (280, 334)]):
    pts = [((ix + x * k) * S, (iy + y * k) * S) for x, y in path]
    d.line(pts, fill="white", width=lw, joint="curve")
    for x, y in pts:
        d.ellipse([x - lw / 2, y - lw / 2, x + lw / 2, y + lw / 2], fill="white")

d.text(px(80, 238), "広島市ゴミナビ", font=font(FONT_B, 72), fill=INK)
d.text(px(82, 336), "ごみの収集日と分け方が、", font=font(FONT_R, 38), fill=INK)
d.text(px(82, 386), "すぐわかる。", font=font(FONT_R, 38), fill=INK)

# 特徴のタグ
tx = 82
for label in ("全8区対応", "無料", "登録不要"):
    f = font(FONT_B, 24)
    w = d.textlength(label, font=f) / S
    d.rounded_rectangle(px(tx, 466, tx + w + 32, 512), radius=23 * S, fill="white", outline=LINE, width=2 * S)
    d.text(px(tx + 16, 476), label, font=f, fill=ACCENT)
    tx += w + 32 + 12

d.text(px(82, 556), "非公式アプリ ／ 広島市オープンデータを利用", font=font(FONT_R, 20), fill=SUB)

# ---- 右：アプリ画面の見本 ----
cx, cy, cw, ch = 690, 70, 440, 490
d.rounded_rectangle(px(cx, cy, cx + cw, cy + ch), radius=28 * S, fill="white", outline=LINE, width=2 * S)


def day_card(x, y, label, date, kind):
    w, h = 190, 150
    d.rounded_rectangle(px(x, y, x + w, y + h), radius=16 * S, fill=SOFT)
    d.rounded_rectangle(px(x, y, x + 9, y + h), radius=4 * S, fill=KIND[kind])
    d.text(px(x + 24, y + 18), label, font=font(FONT_B, 20), fill=SUB)
    d.text(px(x + 24, y + 48), date, font=font(FONT_R, 20), fill=INK)
    name = {"可燃": "可燃ごみ", "資源": "資源ごみ"}[kind]
    d.text(px(x + 24, y + 90), name, font=font(FONT_B, 32), fill=KIND[kind])


day_card(cx + 24, cy + 28, "明日", "10月15日（木）", "可燃")
day_card(cx + 226, cy + 28, "あさって", "10月16日（金）", "資源")

d.text(px(cx + 26, cy + 196), "収集日の朝 8:30 までに出してください。", font=font(FONT_R, 17), fill=SUB)

# 1週間
week = [("水", "14", "他プラ"), ("木", "15", "可燃"), ("金", "16", "資源"), ("土", "17", ""),
        ("日", "18", ""), ("月", "19", "不燃"), ("火", "20", "可燃")]
wx, wy, ww, wh, gap = cx + 24, cy + 236, 52, 86, 6
for i, (wd, n, kind) in enumerate(week):
    x = wx + i * (ww + gap)
    d.rounded_rectangle(px(x, wy, x + ww, wy + wh), radius=10 * S, fill=SOFT,
                        outline=ACCENT if i == 0 else None, width=3 * S if i == 0 else 0)
    wcol = KIND["可燃"] if wd == "日" else KIND["リプラ"] if wd == "土" else SUB
    f = font(FONT_R, 15)
    d.text(((x + ww / 2) * S, (wy + 18) * S), wd, font=f, fill=wcol, anchor="mm")
    d.text(((x + ww / 2) * S, (wy + 42) * S), n, font=font(FONT_B, 21), fill=INK, anchor="mm")
    d.text(((x + ww / 2) * S, (wy + 68) * S), kind or "－", font=font(FONT_B, 13),
           fill=KIND.get(kind, SUB), anchor="mm")

# 検索欄
sy = cy + 350
d.rounded_rectangle(px(cx + 24, sy, cx + cw - 24, sy + 58), radius=12 * S, fill="white", outline=LINE, width=3 * S)
d.text(px(cx + 44, sy + 17), "品目を入力（例：傘、電池）", font=font(FONT_R, 20), fill=SUB)
chip_x = cx + 24
for label in ("電池", "傘", "スプレー缶", "ふとん"):
    f = font(FONT_R, 17)
    w = d.textlength(label, font=f) / S
    d.rounded_rectangle(px(chip_x, sy + 74, chip_x + w + 26, sy + 108), radius=17 * S, fill="white", outline=LINE, width=2 * S)
    d.text(px(chip_x + 13, sy + 81), label, font=f, fill=INK)
    chip_x += w + 26 + 8

img.resize((1200, 630), Image.LANCZOS).save(OUT, optimize=True)
print(f"→ {OUT}")
