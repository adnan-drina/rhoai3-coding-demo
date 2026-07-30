#!/usr/bin/env bash
# Forbid Coolstore cart–specific hardcoding in harness "durable" paths.
# Package defaults that read migration.yaml may keep a fallback string; class
# names / cart URLs / repo ids must not drive harness logic.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
HARNESS="${ROOT}/stages/080-ai-autonomous-migration/scaffold-repo/quarkus-migration-scaffold/.hermes/harness"

# High-signal specimen identifiers — must not appear in harness core logic.
STRICT_PATTERNS=(
  'ShoppingCartServiceImpl'
  'coolstore-cart'
  '/services/carts'
  'CartResource\.java'
)

# Default legacy package string is OK only as migration.yaml fallback.
PKG_DEFAULT_ALLOW='plan-lint\.py|parse-roadmap\.py|harvest-fidelity\.py|sensors\.sh|outer-loop\.sh'

FAIL=0
while IFS= read -r -d '' f; do
  case "$f" in
    */tests/*) continue ;;
  esac
  base=$(basename "$f")
  for pat in "${STRICT_PATTERNS[@]}"; do
    if grep -nE "$pat" "$f" 2>/dev/null | grep -vE 'ALLOWED:|specimen fixture'; then
      echo "COOLSTORE-LINT: $f matches /$pat/" >&2
      FAIL=1
    fi
  done
  if echo "$base" | grep -qE "$PKG_DEFAULT_ALLOW"; then
    continue
  fi
  if grep -nE 'com\.redhat\.coolstore' "$f" 2>/dev/null | grep -vE 'ALLOWED:|legacyPackage|from migration\.yaml|fallback'; then
    echo "COOLSTORE-LINT: $f hardcodes com.redhat.coolstore (use migration.yaml)" >&2
    FAIL=1
  fi
done < <(find "$HARNESS" \( -name '*.sh' -o -name '*.py' \) -print0 2>/dev/null)

if [ "$FAIL" = "1" ]; then
  echo "COOLSTORE-LINT RED — durable harness must be migration-general" >&2
  exit 1
fi
echo "COOLSTORE-LINT GREEN"
