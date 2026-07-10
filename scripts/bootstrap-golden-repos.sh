#!/usr/bin/env bash
# Bootstrap (or reset) the golden repositories that the stage 050
# golden-path templates copy from. Idempotent: re-running force-pushes the
# golden state, which is also the demo reset mechanism for the sources.
#
# Repositories managed (under github.com/${GITHUB_OWNER}):
#   parasol-insurance        — derived from redhat-ads-tech/parasol-insurance
#                              (Kafka/messaging stripped, devfile + Continue
#                              config overlaid from golden-repos/)
#   agentic-quarkus-scaffold — pushed verbatim from golden-repos/
#   migiq-spring-boot-sample — verified only (already golden, not touched)
#
# Requires: gh (authenticated with repo scope), git. No cluster access.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
GITHUB_OWNER="${GITHUB_OWNER:-adnan-drina}"
UPSTREAM_PARASOL="redhat-ads-tech/parasol-insurance"
UPSTREAM_REF="${UPSTREAM_REF:-main}"
WORKDIR="$(mktemp -d)"
trap 'rm -rf "$WORKDIR"' EXIT

log() { echo -e "\033[0;34m[golden-repos]\033[0m $*"; }
warn() { echo -e "\033[1;33m[golden-repos][WARN]\033[0m $*"; }

command -v gh >/dev/null || { echo "gh CLI is required"; exit 1; }
gh auth status >/dev/null || { echo "gh is not authenticated"; exit 1; }

ensure_repo() {
  local repo="$1" description="$2"
  if ! gh repo view "${GITHUB_OWNER}/${repo}" >/dev/null 2>&1; then
    log "Creating github.com/${GITHUB_OWNER}/${repo}"
    gh repo create "${GITHUB_OWNER}/${repo}" --public --description "${description}"
  fi
}

push_golden() {
  local dir="$1" repo="$2" message="$3"
  (
    cd "$dir"
    git init -q -b main
    git add -A
    git commit -q -m "$message"
    git remote add origin "https://github.com/${GITHUB_OWNER}/${repo}.git"
    # gh sets up credential helper for https pushes
    gh auth setup-git >/dev/null 2>&1 || true
    git push -q --force origin main
  )
  log "Pushed golden state to ${GITHUB_OWNER}/${repo}"
}

# --- 1. parasol-insurance (derived from upstream, stripped) ---
log "Deriving parasol-insurance from ${UPSTREAM_PARASOL}"
git clone -q --depth 1 --branch "$UPSTREAM_REF" "https://github.com/${UPSTREAM_PARASOL}.git" "$WORKDIR/parasol-insurance"
UPSTREAM_SHA="$(git -C "$WORKDIR/parasol-insurance" rev-parse HEAD)"
(
  cd "$WORKDIR/parasol-insurance"
  rm -rf .git

  # Strip Kafka/messaging components (tolerant: warn when absent so upstream
  # drift is visible instead of silently ignored).
  # InboxResource depends on EmailStore/Email, and inbox.html on the API —
  # the minimal golden main is Claims-only (email routing was deliberately
  # deferred; see the restructure plan).
  removed=0
  for f in $(find src -name "EmailRouter.java" -o -name "EmailGenerator.java" \
             -o -name "EmailStore.java" -o -name "Email.java" \
             -o -name "InboxResource.java" -o -name "inbox.html" 2>/dev/null); do
    rm -f "$f"; removed=$((removed+1)); echo "  removed $f"
  done
  [ "$removed" -gt 0 ] || warn "no Email*/Inbox files found — upstream layout may have changed"

  if grep -q "quarkus-messaging-kafka\|quarkus-smallrye-reactive-messaging-kafka" pom.xml; then
    python3 - <<'PY'
import re
with open("pom.xml") as f: pom = f.read()
for artifact in ("quarkus-messaging-kafka", "quarkus-smallrye-reactive-messaging-kafka", "quarkus-scheduler"):
    pom = re.sub(
        r"\s*<dependency>(?:(?!</dependency>).)*?<artifactId>%s</artifactId>.*?</dependency>" % artifact,
        "", pom, flags=re.DOTALL)
with open("pom.xml", "w") as f: f.write(pom)
PY
    echo "  stripped Kafka/scheduler dependencies from pom.xml"
  else
    warn "no Kafka dependencies found in pom.xml"
  fi

  for props in src/main/resources/application*.properties; do
    [ -f "$props" ] || continue
    sed -i.bak '/mp\.messaging\./d; /^kafka\./d; /%prod\.kafka\./d' "$props" && rm -f "${props}.bak"
  done

  # Provenance note (upstream carries no license file; keep attribution)
  cat >> README.md <<PROV

## Provenance

Golden repository for the rhoai3-coding-demo assisted golden path. Derived
from https://github.com/${UPSTREAM_PARASOL} (commit ${UPSTREAM_SHA}) with the
Kafka/email-routing path removed. Managed by
rhoai3-coding-demo/scripts/bootstrap-golden-repos.sh — do not commit demo
changes here; the portal template copies this repo per run.
PROV

  # Verify the stripped app still builds before publishing
  if command -v mvn >/dev/null || [ -x ./mvnw ]; then
    echo "  verifying stripped build (mvn -q -DskipTests package)..."
    MVN=./mvnw; [ -x "$MVN" ] || MVN=mvn
    "$MVN" -q -DskipTests package
    echo "  build OK"
  else
    warn "maven not available — skipping build verification"
  fi

  # Overlay platform assets (devfile + Continue config pointing at MaaS)
  cp "$REPO_ROOT/golden-repos/parasol-insurance-overlay/devfile.yaml" devfile.yaml
  mkdir -p .continue
  cp "$REPO_ROOT/golden-repos/parasol-insurance-overlay/.continue/config.yaml" .continue/config.yaml
)
ensure_repo "parasol-insurance" "Parasol Insurance golden repo (assisted golden path; derived from ${UPSTREAM_PARASOL})"
push_golden "$WORKDIR/parasol-insurance" "parasol-insurance" \
  "Golden state derived from ${UPSTREAM_PARASOL}@${UPSTREAM_SHA} (Kafka stripped, platform assets overlaid)"

# --- 2. agentic-quarkus-scaffold (authored in this repo) ---
log "Staging agentic-quarkus-scaffold"
cp -R "$REPO_ROOT/golden-repos/agentic-quarkus-scaffold" "$WORKDIR/agentic-quarkus-scaffold"
ensure_repo "agentic-quarkus-scaffold" "Corporate Quarkus scaffold golden repo (agentic golden path: AGENTS.md + skills + specs)"
push_golden "$WORKDIR/agentic-quarkus-scaffold" "agentic-quarkus-scaffold" \
  "Golden state from rhoai3-coding-demo/golden-repos/agentic-quarkus-scaffold"

# --- 3. migiq-spring-boot-sample (verify only) ---
if gh repo view "${GITHUB_OWNER}/migiq-spring-boot-sample" >/dev/null 2>&1; then
  log "migiq-spring-boot-sample exists (left untouched — already golden)"
else
  warn "migiq-spring-boot-sample not found under ${GITHUB_OWNER} — the autonomous-migration template needs it"
fi

log "Done. Reminders:"
echo "  - The GitHub App (webhook -> EventListener route) must be installed on"
echo "    'All repositories' so template-created repos trigger the pipeline."
echo "  - Re-running this script force-pushes golden state (demo reset)."
