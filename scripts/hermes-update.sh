#!/usr/bin/env bash
# Build + deploy + print URL for Hermes cron / Discord notification.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUTPUT="$("$ROOT/scripts/deploy.sh" 2>&1 | tee /dev/stderr)"
SITE_URL="$(echo "$OUTPUT" | sed -n 's/^SITE_URL=//p' | tail -1)"

if [[ -z "$SITE_URL" ]]; then
  SITE_URL="https://casa2024takayama.github.io/ai-news/"
fi

echo ""
echo "Discord notification text:"
echo "AI News 更新完了"
echo "$SITE_URL"
