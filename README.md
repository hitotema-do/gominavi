# 広島市ゴミナビ（仮称）

広島市の全8区に対応した、ごみ収集日・分別検索アプリ（非公式）。最初に区と町名を選ぶと、その地域の収集日を表示する。

- `app/` … アプリ本体（このフォルダをそのまま公開すれば動く。サーバー処理なし）
- `data/raw/` … 広島市オープンデータの元CSV（Shift_JIS）
- `scripts/build_data.py` … 元CSV → `app/data/*.json` を生成

## 毎年4月のデータ更新

見張り番（`.github/workflows/watch.yml` → `scripts/watch_opendata.py`）が、1/15〜4/10 は毎日、それ以外は毎月1日に市のオープンデータを確認する。`data/opendata_state.json` に記録した「使っているデータ」と違うものが出ると、「見張り番」ラベルの issue を作る（持ち主にメール通知）。届いたら以下を行う。

1. [広島市オープンデータ](https://hiroshima-opendata.dataeye.jp/datasets/1338) から新年度の「家庭ごみ収集日程表」(ZIP) と「家庭ごみ分別50音事典」(CSV) を取得
2. ZIP を `data/raw/r◯/`（令和の年度）に展開し、事典を `data/raw/bunbetsu_jiten.csv` に置き換え
3. `scripts/build_data.py` の `YEAR_DIR` を書き換えて `python scripts/build_data.py`（読み仮名検索用に `pip install pykakasi` 推奨）
4. `app/sw.js` の `CACHE` の番号を1つ上げる
5. よくある質問の祝日の日付を、日本語（HTML）と英語（`EN.html.faqBody`）の両方で更新する
6. 新しいCSVは機械的に変換せず、去年との違い（列・ファイル名・区分の名前）を見てから使い、いくつかの町を市のPDFカレンダーと突き合わせる
7. `python scripts/watch_opendata.py --record` で見張り番の記録を新しくしてコミットし、issue を閉じる

## 補足

- ペットボトルはリサイクルプラと同じ日、有害ごみは資源ごみと同じ日（収集日程表CSVには載っていないため、アプリ側で対応付けている）
- 選んだ地域は端末の localStorage にだけ保存する
- 英語表示：画面右上のボタンで切り替え（初回は端末の言語設定で自動選択）。画面の文言とよくある質問の英語版は `app/index.html` の `EN`・`TXT`
- 品目名・出し方・備考の英訳は `data/i18n/*_en.tsv`（日本語<TAB>英語）で管理し、`build_data.py` が `app/data/items_en.json` を作る。年度更新で英訳のない品目が出ると一覧表示されるので、tsv に追記して再実行する（訳がなければ画面では日本語で表示）
- LINEなどで送ったときのカード画像（app/og.png）は `python scripts/make_og_image.py` で作り直せる
- ローカル確認：`python -m http.server 8766 --directory app`
