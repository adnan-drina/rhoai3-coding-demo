#!/usr/bin/env bash
# Forbid Coolstore cart–specific hardcoding in harness "durable" paths.
# Package defaults that read migration.yaml may keep a fallback string; class
# names / cart URLs / repo ids must not drive harness logic.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
HARNESS="${ROOT}/stages/080-ai-autonomous-migration/scaffold-repo/quarkus-migration-scaffold/.hermes/harness"

# High-signal specimen identifiers — must not appear in harness core logic.
# O-ACCEPTGEN: catalog literals must come from migration.yaml acceptance.*,
# not hardcode products()/CatalogService in durable harness (tests exempt).
STRICT_PATTERNS=(
  'ShoppingCartServiceImpl'
  'coolstore-cart'
  '/services/carts'
  'CartResource\.java'
)

# Acceptance-proof tokens — forbidden in harness core unless parameterized
# (ALLOWED comment, acceptance_config, or fixture note).
ACCEPT_LITERAL_PATTERNS=(
  'CatalogService'
  'CATALOG_ENDPOINT'
  'MockCatalogService'
  'products\('
)

# Default legacy package string is OK only as migration.yaml fallback.
PKG_DEFAULT_ALLOW='plan-lint\.py|parse-roadmap\.py|harvest-fidelity\.py|sensors\.sh|outer-loop\.sh'

# Defaults / loaders that intentionally mention Coolstore-shaped tokens.
ACCEPT_LITERAL_ALLOW='acceptance_config\.py|acceptance-products\.py|sensors\.sh|supervisor\.sh|gen-contract-rules\.py'

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
  if ! echo "$base" | grep -qE "$ACCEPT_LITERAL_ALLOW"; then
    for pat in "${ACCEPT_LITERAL_PATTERNS[@]}"; do
      if grep -nE "$pat" "$f" 2>/dev/null | grep -vE 'ALLOWED:|specimen fixture|acceptance\.collection|from migration\.yaml|fallback|ACC_PROOF|ACC_COLLECTION|O-ACCEPTGEN'; then
        echo "COOLSTORE-LINT: $f hardcodes acceptance literal /$pat/ (use migration.yaml acceptance.*)" >&2
        FAIL=1
      fi
    done
  fi
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
