#!/usr/bin/env bash
# Build site, commit, and push to GitHub Pages.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

SITE_URL="https://casa2024takayama.github.io/ai-news/"

if [[ ! -d .venv ]]; then
  python3 -m venv .venv
  .venv/bin/pip install -q -r requirements.txt
fi

.venv/bin/python build.py

git add docs/ data/articles.json
if git diff --cached --quiet; then
  echo "No changes to deploy."
  echo "SITE_URL=$SITE_URL"
  exit 0
fi

git commit -m "$(cat <<EOF
Update AI news digest

Automated RSS build.
EOF
)"

git push origin main 2>&1 || {
  echo "git push failed. Run: gh auth status && git remote -v" >&2
  exit 1
}
echo "✓ Deployed: $SITE_URL"
echo "SITE_URL=$SITE_URL"
