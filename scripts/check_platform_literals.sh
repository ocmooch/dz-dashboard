#!/usr/bin/env bash
# Sleeper D1 guard (`01` §6, `03` §1): no comparisons (===, !==, ==, !=, case) against
# platform string literals in web/src, except in lib/platform.ts (the label helpers) and the
# generated client. Plain labels (e.g. an "NFL.com" id-source label) and test mock data are fine.
# Usage: check_platform_literals.sh [web/src root]. Exit 1 lists the offenders.
set -euo pipefail
root="${1:-$(cd "$(dirname "$0")/.." && pwd)/web/src}"
q="[\"'\`]"
lit="${q}(nfl_com|sleeper|NFL\\.com|Sleeper)${q}"
op="(===|!==|==|!=)"
pattern="${op}[[:space:]]*${lit}|${lit}[[:space:]]*${op}|case[[:space:]]+${lit}"
hits="$(grep -rnE "$pattern" "$root" --include='*.ts' --include='*.tsx' \
  | grep -vE '/lib/platform\.ts:|/lib/api/|\.test\.tsx?:' || true)"
if [ -n "$hits" ]; then
  echo "platform-literal comparisons outside lib/platform.ts (use lib/platform helpers):"
  echo "$hits"
  exit 1
fi
echo "platform literals: clean"
