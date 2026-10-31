# 広島市ゴミナビ（仮称）

広島市の全8区に対応した、ごみ収集日・分別検索アプリ（非公式）。最初に区と町名を選ぶと、その地域の収集日を表示する。

- `app/` … アプリ本体（このフォルダをそのまま公開すれば動く。サーバー処理なし）
- `data/raw/` … 広島市オープンデータの元CSV（Shift_JIS）
- `scripts/build_data.py` … 元CSV → `app/data/*.json` を生成

## 年度更新（自動）

見張り番（`.github/workflows/watch.yml` → `scripts/watch_opendata.py`）が、1/15〜4/10 は毎日、それ以外は毎月1日に市のオープンデータを確認する。`data/opendata_state.json` に記録した「使っているデータ」と違うものが出ると、`scripts/auto_update.py` が次をすべて自動で行い、公開までする。

1. [広島市オープンデータ](https://hiroshima-opendata.dataeye.jp/datasets/1338) から、いちばん新しい年度の「家庭ごみ収集日程表」(ZIP) と「家庭ごみ分別50音事典」(CSV) を取得し、`data/raw/r◯/`（令和の年度）と `data/raw/bunbetsu_jiten.csv` に置く
2. `scripts/build_data.py`（いちばん新しい `r◯` フォルダを自動で使う）で `app/data/*.json` を作り直す
3. `scripts/build_holidays.py` が、内閣府の祝日一覧と収集日データから、よくある質問の祝日の日付（日本語・英語）を作り直す
4. `app/sw.js` の `CACHE` の番号を1つ上げる
5. 点検：期間・日数、去年と比べた収集回数・グループ数・町名数・品目数、知らない分別区分、年末年始の説明との食い違い。1つでも引っかかると**何も公開せず**、「自動更新は止まりました」という issue（「見張り番」ラベル）で知らせる
6. 点検に通ったら、コミットして公開し、「自動で更新しました」という issue を作って閉じる（持ち主にメールが届く）
7. `watch_opendata.py --record` で見張り番の記録を新しくする

issue で「止まりました」と届いたら、Claude に「ゴミナビ更新して」と伝える（手で直すときは `python scripts/auto_update.py` を手元で動かすと、止まる理由が見える）。

## 補足

- ペットボトルはリサイクルプラと同じ日、有害ごみは資源ごみと同じ日（収集日程表CSVには載っていないため、アプリ側で対応付けている）
- 選んだ地域は端末の localStorage にだけ保存する
- 英語表示：画面右上のボタンで切り替え（初回は端末の言語設定で自動選択）。画面の文言とよくある質問の英語版は `app/index.html` の `EN`・`TXT`
- 品目名・出し方・備考の英訳は `data/i18n/*_en.tsv`（日本語<TAB>英語）で管理し、`build_data.py` が `app/data/items_en.json` を作る。自動更新で英訳のない品目が出ても、画面では日本語のまま表示される。気づいたときに tsv に追記して `build_data.py` を再実行する
- LINEなどで送ったときのカード画像（app/og.png）は `python scripts/make_og_image.py` で作り直せる
- ローカル確認：`python -m http.server 8766 --directory app`
