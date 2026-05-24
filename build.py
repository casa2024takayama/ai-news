#!/usr/bin/env python3
"""Fetch AI news from RSS feeds and generate a static site in docs/."""

from __future__ import annotations

import html
import json
import re
import subprocess
import sys
import urllib.request
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any
try:
    import feedparser
    import yaml
except ImportError:
    print("Missing deps. Run: python3 -m venv .venv && .venv/bin/pip install -r requirements.txt", file=sys.stderr)
    sys.exit(1)

ROOT = Path(__file__).resolve().parent
from translate import translate_articles  # noqa: E402
CONFIG_PATH = ROOT / "config" / "feeds.yaml"
DATA_PATH = ROOT / "data" / "articles.json"
DOCS_DIR = ROOT / "docs"
ASSETS_DIR = DOCS_DIR / "assets"


def load_config() -> dict[str, Any]:
    with CONFIG_PATH.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def parse_date(entry: dict[str, Any]) -> datetime | None:
    for key in ("published_parsed", "updated_parsed"):
        parsed = entry.get(key)
        if parsed:
            try:
                return datetime(*parsed[:6], tzinfo=timezone.utc)
            except (TypeError, ValueError):
                pass
    for key in ("published", "updated"):
        raw = entry.get(key)
        if raw:
            try:
                dt = parsedate_to_datetime(raw)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt.astimezone(timezone.utc)
            except (TypeError, ValueError):
                pass
    return None


def clean_text(value: str | None) -> str:
    if not value:
        return ""
    text = re.sub(r"<[^>]+>", " ", value)
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def extract_summary(entry: dict[str, Any]) -> str:
    for key in ("summary", "description", "content"):
        value = entry.get(key)
        if isinstance(value, list) and value:
            value = value[0].get("value", "")
        text = clean_text(str(value) if value else "")
        if text:
            return text[:280] + ("…" if len(text) > 280 else "")
    return ""


def fetch_feed_payload(url: str) -> bytes:
    try:
        request = urllib.request.Request(
            url,
            headers={
                "User-Agent": "ai-news-digest/1.0 (+https://casa2024takayama.github.io/ai-news/)",
                "Accept": "application/rss+xml, application/xml, text/xml, */*",
            },
        )
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(request, timeout=30) as response:
            return response.read()
    except Exception:
        result = subprocess.run(
            ["curl", "-fsSL", "--max-time", "30", "-A", "ai-news-digest/1.0", url],
            check=True,
            capture_output=True,
        )
        return result.stdout


def fetch_feed(name: str, url: str, category: str) -> list[dict[str, Any]]:
    payload = fetch_feed_payload(url)
    parsed = feedparser.parse(payload)
    articles: list[dict[str, Any]] = []
    for entry in parsed.entries:
        link = entry.get("link") or entry.get("id")
        title = clean_text(entry.get("title"))
        if not link or not title:
            continue
        published = parse_date(entry)
        articles.append(
            {
                "id": link,
                "title": title,
                "url": link,
                "source": name,
                "category": category,
                "summary": extract_summary(entry),
                "published_at": published.isoformat() if published else None,
            }
        )
    return articles


def merge_articles(existing: list[dict[str, Any]], fresh: list[dict[str, Any]], retention_days: int, max_articles: int) -> list[dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {a["id"]: a for a in existing if a.get("id")}
    for article in fresh:
        prev = by_id.get(article["id"])
        if prev:
            for key in ("title_ja", "summary_ja", "_translate_source"):
                if key in prev and article.get("title") == prev.get("title") and article.get("summary") == prev.get("summary"):
                    article[key] = prev[key]
        by_id[article["id"]] = article

    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
    merged: list[dict[str, Any]] = []
    for article in by_id.values():
        ts = article.get("published_at")
        if ts:
            try:
                dt = datetime.fromisoformat(ts)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                if dt < cutoff:
                    continue
            except ValueError:
                pass
        merged.append(article)

    def sort_key(item: dict[str, Any]) -> datetime:
        ts = item.get("published_at")
        if not ts:
            return datetime.min.replace(tzinfo=timezone.utc)
        try:
            dt = datetime.fromisoformat(ts)
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except ValueError:
            return datetime.min.replace(tzinfo=timezone.utc)

    merged.sort(key=sort_key, reverse=True)
    return merged[:max_articles]


def format_jst(iso_ts: str | None) -> str:
    if not iso_ts:
        return "日時不明"
    try:
        dt = datetime.fromisoformat(iso_ts)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        jst = dt.astimezone(timezone(timedelta(hours=9)))
        return jst.strftime("%Y-%m-%d %H:%M JST")
    except ValueError:
        return iso_ts


def write_css() -> None:
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    css = """
:root {
  color-scheme: light dark;
  --bg: #0b1020;
  --panel: #121933;
  --text: #e8ecff;
  --muted: #9aa7d7;
  --accent: #6ea8fe;
  --border: #243056;
  --chip: #1a2444;
}
* { box-sizing: border-box; }
body {
  margin: 0;
  font-family: "Hiragino Sans", "Yu Gothic UI", system-ui, sans-serif;
  background: linear-gradient(180deg, #070b16 0%, #0b1020 100%);
  color: var(--text);
  line-height: 1.6;
}
.wrap { max-width: 920px; margin: 0 auto; padding: 24px 16px 64px; }
header { margin-bottom: 28px; }
.badge {
  display: inline-block;
  padding: 4px 10px;
  border-radius: 999px;
  background: var(--chip);
  color: var(--accent);
  font-size: 12px;
  letter-spacing: .04em;
}
h1 { margin: 10px 0 6px; font-size: 2rem; }
.subtitle { color: var(--muted); margin: 0; }
.meta {
  margin-top: 14px;
  color: var(--muted);
  font-size: 14px;
}
.stats {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  margin: 18px 0 24px;
}
.stat {
  background: var(--panel);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 12px 14px;
  min-width: 140px;
}
.stat strong { display: block; font-size: 1.2rem; }
.grid { display: grid; gap: 14px; }
.card {
  background: var(--panel);
  border: 1px solid var(--border);
  border-radius: 16px;
  padding: 18px 18px 16px;
}
.card h2 {
  margin: 0 0 8px;
  font-size: 1.08rem;
  line-height: 1.45;
}
.card h2 a {
  color: var(--text);
  text-decoration: none;
}
.card h2 a:hover { color: var(--accent); }
.card .original {
  color: var(--muted);
  font-size: 12px;
  margin: 0 0 6px;
}
.row {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  align-items: center;
  font-size: 12px;
  color: var(--muted);
}
.chip {
  background: var(--chip);
  border: 1px solid var(--border);
  border-radius: 999px;
  padding: 2px 8px;
}
footer {
  margin-top: 36px;
  color: var(--muted);
  font-size: 13px;
  border-top: 1px solid var(--border);
  padding-top: 16px;
}
@media (max-width: 640px) {
  h1 { font-size: 1.55rem; }
}
""".strip()
    (ASSETS_DIR / "style.css").write_text(css + "\n", encoding="utf-8")


def render_html(config: dict[str, Any], articles: list[dict[str, Any]]) -> str:
    site = config.get("site", {})
    title = site.get("title", "AI News Digest")
    subtitle = site.get("subtitle", "")
    built_at = datetime.now(timezone(timedelta(hours=9))).strftime("%Y-%m-%d %H:%M JST")
    categories = sorted({a.get("category", "その他") for a in articles})

    cards = []
    for article in articles:
        title_ja = article.get("title_ja") or article.get("title") or ""
        summary_ja = article.get("summary_ja") or article.get("summary") or "（要約なし）"
        title_en = article.get("title") or ""
        show_original = bool(article.get("title_ja")) and title_en and title_en != title_ja
        original_html = (
            f'<p class="original">{html.escape(title_en)}</p>' if show_original else ""
        )
        cards.append(
            f"""
            <article class="card">
              <h2><a href="{html.escape(article['url'])}" target="_blank" rel="noopener noreferrer">{html.escape(title_ja)}</a></h2>
              {original_html}
              <p class="summary">{html.escape(summary_ja)}</p>
              <div class="row">
                <span class="chip">{html.escape(article.get('category') or 'その他')}</span>
                <span>{html.escape(article.get('source') or '')}</span>
                <span>{html.escape(format_jst(article.get('published_at')))}</span>
              </div>
            </article>
            """.strip()
        )

    cards_html = "\n".join(cards) if cards else '<article class="card"><p class="summary">記事がまだありません。しばらくしてから再ビルドしてください。</p></article>'

    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(title)}</title>
  <meta name="description" content="{html.escape(subtitle)}">
  <link rel="stylesheet" href="assets/style.css">
</head>
<body>
  <main class="wrap">
    <header>
      <span class="badge">AUTO UPDATED</span>
      <h1>{html.escape(title)}</h1>
      <p class="subtitle">{html.escape(subtitle)}</p>
      <p class="meta">最終更新: {built_at} ・ RSS + Grok 翻訳</p>
    </header>
    <section class="stats">
      <div class="stat"><strong>{len(articles)}</strong>件の記事</div>
      <div class="stat"><strong>{len(categories)}</strong>カテゴリ</div>
      <div class="stat"><strong>Grok</strong>日本語翻訳</div>
    </section>
    <section class="grid">
      {cards_html}
    </section>
    <footer>
      各記事の著作権は原媒体に帰属します。本サイトは要約とリンク集です。
    </footer>
  </main>
</body>
</html>
"""


def main() -> int:
    config = load_config()
    site = config.get("site", {})
    retention_days = int(site.get("retention_days", 7))
    max_articles = int(site.get("max_articles", 60))

    existing: list[dict[str, Any]] = []
    if DATA_PATH.exists():
        existing = json.loads(DATA_PATH.read_text(encoding="utf-8"))

    fresh: list[dict[str, Any]] = []
    for feed in config.get("feeds", []):
        name = feed.get("name", "Unknown")
        url = feed.get("url")
        category = feed.get("category", "その他")
        if not url:
            continue
        try:
            fetched = fetch_feed(name, url, category)
            fresh.extend(fetched)
            print(f"✓ {name}: {len(fetched)} articles")
        except Exception as exc:
            print(f"✗ {name}: {exc}", file=sys.stderr)

    articles = merge_articles(existing, fresh, retention_days, max_articles)
    articles = translate_articles(articles, config)
    DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    DATA_PATH.write_text(json.dumps(articles, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    write_css()
    (DOCS_DIR / "index.html").write_text(render_html(config, articles), encoding="utf-8")
    print(f"✓ Built {len(articles)} articles -> {DOCS_DIR / 'index.html'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
