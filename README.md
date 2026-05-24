# AI News Digest

人工知能・生成AIの最新ニュースを RSS から集め、静的サイトとして公開するプロジェクトです。

**公開 URL:** https://casa2024takayama.github.io/ai-news/

## 仕組み

```text
RSS フィード → build.py → docs/index.html → GitHub Pages → Discord 通知
```

- 記事本文の全文転載はせず、**タイトル・要約・元記事リンク**のみ
- 夜間更新は **Hermes cron** から `scripts/deploy.sh` を実行

## 手動ビルド

```bash
cd ~/ai-news
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python build.py
open docs/index.html
```

## デプロイ

```bash
~/ai-news/scripts/deploy.sh
```

## Hermes cron（Discord 通知付き）

Discord DM で次を送って cron を作成:

```text
毎日午前6時に ~/ai-news/scripts/deploy.sh を実行して。
完了したら「AI News 更新」と https://casa2024takayama.github.io/ai-news/ をこのDMに送って。
```

※ Mac がスリープ中は cron は動きません。Gateway も起動しておいてください。

## 設定

- フィード一覧: `config/feeds.yaml`
- 記事キャッシュ: `data/articles.json`
- 生成物: `docs/`（GitHub Pages の公開元）

## ファイル構成

```text
ai-news/
  build.py              # RSS 取得 + HTML 生成
  config/feeds.yaml     # ニュースソース
  docs/                 # 公開サイト
  scripts/deploy.sh     # build + git push
  scripts/hermes-update.sh
```
