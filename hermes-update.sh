#!/usr/bin/env bash
# One-shot update for Hermes Discord / cron. Builds RSS digest and deploys to GitHub Pages.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "$ROOT/scripts/deploy.sh"
