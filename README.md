# 広島市ゴミナビ（仮称）

広島市の全8区に対応した、ごみ収集日・分別検索アプリ（非公式）。最初に区と町名を選ぶと、その地域の収集日を表示する。

- `app/` … アプリ本体（このフォルダをそのまま公開すれば動く。サーバー処理なし）
- `data/raw/` … 広島市オープンデータの元CSV（Shift_JIS）
- `scripts/build_data.py` … 元CSV → `app/data/*.json` を生成

## 毎年4月のデータ更新

1. [広島市オープンデータ](https://hiroshima-opendata.dataeye.jp/datasets/1338) から新年度の「家庭ごみ収集日程表」(ZIP) と「家庭ごみ分別50音事典」(CSV) を取得
2. ZIP を `data/raw/r◯/`（令和の年度）に展開し、事典を `data/raw/bunbetsu_jiten.csv` に置き換え
3. `scripts/build_data.py` の `YEAR_DIR` を書き換えて `python scripts/build_data.py`（読み仮名検索用に `pip install pykakasi` 推奨）
4. `app/sw.js` の `CACHE` の番号を1つ上げる

## 補足

- ペットボトルはリサイクルプラと同じ日、有害ごみは資源ごみと同じ日（収集日程表CSVには載っていないため、アプリ側で対応付けている）
- 選んだ地域は端末の localStorage にだけ保存する
- 英語表示：画面右上のボタンで切り替え（初回は端末の言語設定で自動選択）。訳語は `app/index.html` の `EN`・`TXT` にまとめてある。品目名・出し方・よくある質問の本文は日本語のまま
- LINEなどで送ったときのカード画像（app/og.png）は `python scripts/make_og_image.py` で作り直せる
- ローカル確認：`python -m http.server 8766 --directory app`
