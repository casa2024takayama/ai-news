"""Translate article titles/summaries to Japanese via xAI (Grok)."""

from __future__ import annotations

import json
import os
import re
import subprocess
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

HERMES_AUTH = Path.home() / ".hermes" / "auth.json"
XAI_CHAT_URL = "https://api.x.ai/v1/chat/completions"
DEFAULT_MODEL = "grok-4-1-fast-non-reasoning"
BATCH_SIZE = 8


def _load_xai_token() -> str | None:
    if token := os.getenv("XAI_API_KEY"):
        return token.strip()
    if not HERMES_AUTH.exists():
        return None
    try:
        data = json.loads(HERMES_AUTH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    providers = data.get("providers") or {}
    xai = providers.get("xai-oauth") or {}
    tokens = xai.get("tokens") or {}
    token = tokens.get("access_token")
    if token:
        return str(token)
    pool = (data.get("credential_pool") or {}).get("xai-oauth") or []
    if pool and pool[0].get("access_token"):
        return str(pool[0]["access_token"])
    return None


def _looks_japanese(text: str) -> bool:
    if not text:
        return False
    ja = len(re.findall(r"[\u3040-\u30ff\u4e00-\u9fff]", text))
    latin = len(re.findall(r"[A-Za-z]", text))
    return ja >= 4 and ja >= latin


def _needs_translation(article: dict[str, Any]) -> bool:
    title = article.get("title") or ""
    summary = article.get("summary") or ""
    if _looks_japanese(title) and _looks_japanese(summary):
        return False
    source_key = f"{title}\n{summary}"
    if article.get("title_ja") and article.get("summary_ja"):
        if article.get("_translate_source") == source_key:
            return False
    return True


def _chat_json(token: str, model: str, prompt: str) -> Any:
    body = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": "You translate tech news into natural Japanese. Respond with valid JSON only.",
            },
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.2,
    }
    raw = json.dumps(body).encode("utf-8")
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "User-Agent": "ai-news-digest/1.0",
    }
    try:
        request = urllib.request.Request(XAI_CHAT_URL, data=raw, headers=headers, method="POST")
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(request, timeout=120) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception:
        result = subprocess.run(
            [
                "curl",
                "-fsSL",
                "--max-time",
                "120",
                "-X",
                "POST",
                XAI_CHAT_URL,
                "-H",
                f"Authorization: Bearer {token}",
                "-H",
                "Content-Type: application/json",
                "-d",
                json.dumps(body, ensure_ascii=False),
            ],
            check=True,
            capture_output=True,
        )
        payload = json.loads(result.stdout.decode("utf-8"))
    content = payload["choices"][0]["message"]["content"]
    content = content.strip()
    if content.startswith("```"):
        content = re.sub(r"^```(?:json)?\s*", "", content)
        content = re.sub(r"\s*```$", "", content)
    return json.loads(content)


def _translate_batch(token: str, model: str, batch: list[dict[str, Any]]) -> dict[str, dict[str, str]]:
    items = []
    for article in batch:
        items.append(
            {
                "id": article["id"],
                "title": article.get("title") or "",
                "summary": article.get("summary") or "",
            }
        )
    prompt = (
        "Translate each item's title and summary into natural Japanese for a news digest site.\n"
        "Rules:\n"
        "- Keep proper nouns (OpenAI, Google, GPT, etc.) readable in Japanese context\n"
        "- summary_ja: max 180 Japanese characters\n"
        "- title_ja: concise headline style\n"
        "- Return JSON object: {\"items\": [{\"id\": \"...\", \"title_ja\": \"...\", \"summary_ja\": \"...\"}, ...]}\n\n"
        f"INPUT:\n{json.dumps(items, ensure_ascii=False)}"
    )
    parsed = _chat_json(token, model, prompt)
    rows = parsed.get("items") if isinstance(parsed, dict) else parsed
    if not isinstance(rows, list):
        raise ValueError("Unexpected translation response shape")
    out: dict[str, dict[str, str]] = {}
    for row in rows:
        if not isinstance(row, dict) or not row.get("id"):
            continue
        out[str(row["id"])] = {
            "title_ja": str(row.get("title_ja") or "").strip(),
            "summary_ja": str(row.get("summary_ja") or "").strip(),
        }
    return out


def translate_articles(articles: list[dict[str, Any]], config: dict[str, Any]) -> list[dict[str, Any]]:
    site = config.get("site") or {}
    if not site.get("translate", True):
        return articles

    token = _load_xai_token()
    if not token:
        print("⚠ Translation skipped: no XAI_API_KEY or ~/.hermes/auth.json xai-oauth token")
        return articles

    model = site.get("translate_model") or DEFAULT_MODEL
    batch_size = int(site.get("translate_batch_size") or BATCH_SIZE)
    pending = [a for a in articles if _needs_translation(a)]
    if not pending:
        print("✓ Translation: all articles already localized")
        return articles

    print(f"→ Translating {len(pending)} article(s) via {model}...")
    by_id = {a["id"]: a for a in articles}

    for i in range(0, len(pending), batch_size):
        batch = pending[i : i + batch_size]
        try:
            translated = _translate_batch(token, model, batch)
        except urllib.error.HTTPError as exc:
            print(f"✗ Translation batch failed: HTTP {exc.code}")
            break
        except subprocess.CalledProcessError:
            print("✗ Translation batch failed: API request error")
            break
        except Exception as exc:
            print(f"✗ Translation batch failed: {exc.__class__.__name__}")
            break
        for article in batch:
            row = translated.get(article["id"])
            if not row:
                continue
            target = by_id[article["id"]]
            target["title_ja"] = row.get("title_ja") or target.get("title_ja")
            target["summary_ja"] = row.get("summary_ja") or target.get("summary_ja")
            target["_translate_source"] = f"{target.get('title') or ''}\n{target.get('summary') or ''}"
        print(f"  ✓ batch {i // batch_size + 1}: {len(translated)} translated")

    return list(by_id.values())
