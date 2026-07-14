#!/usr/bin/env bash
# Reset the coolstore-inventory-service demo to the pristine golden baseline.
#
# Every stage 060 demo run pushes real commits to main (required: pipeline
# triggers listen only on refs/heads/main). This script rewinds main to
# the golden branch via the GitHub API, optionally clears SonarQube history,
# and recreates the DevWorkspace so the next start clones pristine main.
#
# The force-push fires one expected app-push PipelineRun in coolstore-dev —
# it re-validates the chain and re-tags :latest (the dev deployment picks up
# the golden build).
#
# Prerequisites:
#   gh (authenticated with repo scope) OR GITHUB_TOKEN set
#   oc (logged in; required for workspace recreation and --fresh-sonar)
#
# Advancing the baseline:
#   When the demo app legitimately evolves, push the new baseline commit to
#   main, verify the pipeline is green, then update the golden branch:
#     gh api -X PATCH repos/$REPO_OWNER/$REPO_NAME/git/refs/heads/golden \
#       -f sha="$(gh api repos/$REPO_OWNER/$REPO_NAME/git/refs/heads/main --jq .object.sha)" \
#       -F force=true
#   Or: git push origin main:golden --force
#
# Usage:
#   ./scripts/reset-coolstore-demo.sh [--yes] [--fresh-sonar] [--skip-workspace] [--wait-pipeline]
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
source "$REPO_ROOT/scripts/lib.sh"

REPO_OWNER="${REPO_OWNER:-adnan-drina}"
REPO_NAME="${REPO_NAME:-coolstore-inventory-service}"
GOLDEN_BRANCH="${GOLDEN_BRANCH:-golden}"
WORKSPACE_NS="${WORKSPACE_NS:-wksp-ai-developer}"
WORKSPACE_NAME="${WORKSPACE_NAME:-agentic-coolstore}"
SONAR_PROJECT_KEY="${SONAR_PROJECT_KEY:-coolstore-inventory-service}"

FLAG_YES=false
FLAG_FRESH_SONAR=false
FLAG_SKIP_WORKSPACE=false
FLAG_WAIT_PIPELINE=false

for arg in "$@"; do
  case "$arg" in
    --yes)            FLAG_YES=true ;;
    --fresh-sonar)    FLAG_FRESH_SONAR=true ;;
    --skip-workspace) FLAG_SKIP_WORKSPACE=true ;;
    --wait-pipeline)  FLAG_WAIT_PIPELINE=true ;;
    *) log_error "Unknown flag: $arg"; exit 1 ;;
  esac
done

echo "╔══════════════════════════════════════════════════════════════════╗"
echo "║  Coolstore Demo Reset                                           ║"
echo "╚══════════════════════════════════════════════════════════════════╝"
echo ""

# --- 1. Preflight ---
log_step "Preflight checks"

if command -v gh >/dev/null 2>&1; then
  gh auth status >/dev/null 2>&1 || { log_error "gh is not authenticated. Run: gh auth login"; exit 1; }
  log_success "gh CLI authenticated"
elif [[ -n "${GITHUB_TOKEN:-}" ]]; then
  log_success "GITHUB_TOKEN is set (gh CLI not found; API calls will use the token)"
else
  log_error "Neither gh CLI (authenticated) nor GITHUB_TOKEN is available."
  log_error "Install gh and run 'gh auth login', or export GITHUB_TOKEN."
  exit 1
fi

NEEDS_CLUSTER=false
if [[ "$FLAG_SKIP_WORKSPACE" != "true" ]] || [[ "$FLAG_FRESH_SONAR" == "true" ]] || [[ "$FLAG_WAIT_PIPELINE" == "true" ]]; then
  NEEDS_CLUSTER=true
fi

if [[ "$NEEDS_CLUSTER" == "true" ]]; then
  load_env
  check_oc_logged_in
fi

GOLDEN_SHA=$(gh api "repos/${REPO_OWNER}/${REPO_NAME}/git/refs/heads/${GOLDEN_BRANCH}" --jq '.object.sha' 2>/dev/null || true)
if [[ -z "$GOLDEN_SHA" ]]; then
  log_error "Golden branch '${GOLDEN_BRANCH}' not found on ${REPO_OWNER}/${REPO_NAME}."
  log_error "Create it by pushing the pristine baseline commit:"
  log_error "  git push origin main:${GOLDEN_BRANCH}"
  exit 1
fi
log_success "Golden branch SHA: ${GOLDEN_SHA:0:12}"

MAIN_SHA=$(gh api "repos/${REPO_OWNER}/${REPO_NAME}/git/refs/heads/main" --jq '.object.sha' 2>/dev/null || true)
if [[ -z "$MAIN_SHA" ]]; then
  log_error "Could not resolve main branch SHA"
  exit 1
fi
log_success "Current main SHA:  ${MAIN_SHA:0:12}"

if [[ "$MAIN_SHA" == "$GOLDEN_SHA" ]]; then
  log_success "main is already at golden — skipping rewind"
  REWIND_SKIPPED=true
else
  REWIND_SKIPPED=false
fi

# --- 2. Confirmation ---
if [[ "$REWIND_SKIPPED" != "true" && "$FLAG_YES" != "true" ]]; then
  echo ""
  echo "This will force-push main to the golden baseline:"
  echo "  main   ${MAIN_SHA:0:12} -> golden ${GOLDEN_SHA:0:12}"
  echo "  repo   ${REPO_OWNER}/${REPO_NAME}"
  echo ""
  echo "This fires one expected pipeline run in coolstore-dev."
  echo ""
  read -r -p "Continue? [y/N] " confirm
  case "$confirm" in
    [yY]) ;;
    *) echo "Aborted."; exit 0 ;;
  esac
fi

# --- 3. Rewind main ---
if [[ "$REWIND_SKIPPED" != "true" ]]; then
  log_step "Rewinding main to golden"
  gh api -X PATCH "repos/${REPO_OWNER}/${REPO_NAME}/git/refs/heads/main" \
    -f sha="$GOLDEN_SHA" -F force=true --silent
  log_success "main force-pushed to ${GOLDEN_SHA:0:12}"
  log_info "One app-push PipelineRun will fire in coolstore-dev (expected — re-validates and re-tags :latest)"
fi

# --- 4. Fresh SonarQube (optional) ---
if [[ "$FLAG_FRESH_SONAR" == "true" ]]; then
  log_step "Clearing SonarQube project history"
  # The gate is deterministic across resets even without this: new-code
  # violations are counted against the previous analysis. This is cosmetic
  # history cleanup.
  SONAR_USER=$(oc get secret sonarqube-admin -n sonarqube \
    -o jsonpath='{.data.username}' 2>/dev/null | base64 -d 2>/dev/null || true)
  SONAR_PASS=$(oc get secret sonarqube-admin -n sonarqube \
    -o jsonpath='{.data.password}' 2>/dev/null | base64 -d 2>/dev/null || true)
  if [[ -z "$SONAR_USER" || -z "$SONAR_PASS" ]]; then
    log_warn "sonarqube-admin Secret not found or empty — skipping SonarQube cleanup"
  else
    SONAR_HOST=$(oc get route sonarqube -n sonarqube \
      -o jsonpath='{.spec.host}' 2>/dev/null || true)
    if [[ -z "$SONAR_HOST" ]]; then
      log_warn "SonarQube Route not found — skipping cleanup"
    else
      HTTP_CODE=$(curl -sk -o /dev/null -w '%{http_code}' \
        -u "${SONAR_USER}:${SONAR_PASS}" \
        -X POST "https://${SONAR_HOST}/api/projects/delete?project=${SONAR_PROJECT_KEY}")
      case "$HTTP_CODE" in
        204) log_success "SonarQube project '${SONAR_PROJECT_KEY}' deleted" ;;
        404) log_success "SonarQube project '${SONAR_PROJECT_KEY}' already clean (404)" ;;
        *)   log_warn "SonarQube delete returned HTTP ${HTTP_CODE} — check manually" ;;
      esac
    fi
  fi
fi

# --- 5. Workspace recreation (unless --skip-workspace) ---
if [[ "$FLAG_SKIP_WORKSPACE" != "true" ]]; then
  log_step "Recreating DevWorkspace"
  oc delete devworkspace "$WORKSPACE_NAME" -n "$WORKSPACE_NS" --ignore-not-found
  log_info "Waiting for Argo CD self-heal to recreate ${WORKSPACE_NAME} (Stopped)..."
  for i in $(seq 1 30); do
    PHASE=$(oc get devworkspace "$WORKSPACE_NAME" -n "$WORKSPACE_NS" \
      -o jsonpath='{.status.phase}' 2>/dev/null || echo "")
    if [[ "$PHASE" == "Stopped" ]]; then
      log_success "DevWorkspace ${WORKSPACE_NAME} recreated (phase: Stopped)"
      break
    fi
    if [[ "$i" -eq 30 ]]; then
      log_warn "Timed out waiting for DevWorkspace recreation — check Argo CD sync"
    fi
    sleep 10
  done
fi

# --- 6. Wait for pipeline (optional) ---
if [[ "$FLAG_WAIT_PIPELINE" == "true" && "$REWIND_SKIPPED" != "true" ]]; then
  log_step "Waiting for reset PipelineRun to complete (max 15 min)"
  DEADLINE=$((SECONDS + 900))
  FINAL_STATUS=""
  while [[ $SECONDS -lt $DEADLINE ]]; do
    PR_STATUS=$(oc get pipelinerun -n coolstore-dev \
      --sort-by='.metadata.creationTimestamp' \
      -o jsonpath='{.items[-1:].status.conditions[?(@.type=="Succeeded")].status}' 2>/dev/null || echo "")
    case "$PR_STATUS" in
      True)
        FINAL_STATUS="Succeeded"
        break ;;
      False)
        FINAL_STATUS="Failed"
        break ;;
    esac
    sleep 15
  done
  case "$FINAL_STATUS" in
    Succeeded) log_success "Reset PipelineRun succeeded" ;;
    Failed)    log_warn "Reset PipelineRun failed — check coolstore-dev for details" ;;
    *)         log_warn "Timed out waiting for PipelineRun (15 min) — check coolstore-dev" ;;
  esac
fi

# --- 7. Summary ---
echo ""
echo "╔══════════════════════════════════════════════════════════════════╗"
echo "║  Reset Summary                                                  ║"
echo "╚══════════════════════════════════════════════════════════════════╝"
if [[ "$REWIND_SKIPPED" == "true" ]]; then
  echo "  Git:       main already at golden (${GOLDEN_SHA:0:12}) — no rewind needed"
else
  echo "  Git:       main rewound to golden (${GOLDEN_SHA:0:12})"
  echo "  Pipeline:  one app-push run fired in coolstore-dev"
fi
if [[ "$FLAG_FRESH_SONAR" == "true" ]]; then
  echo "  SonarQube: project history cleared"
fi
if [[ "$FLAG_SKIP_WORKSPACE" != "true" ]]; then
  echo "  Workspace: ${WORKSPACE_NAME} recreated (Stopped)"
else
  echo "  Workspace: skipped (--skip-workspace)"
fi
echo ""
echo "  Next: start the workspace from the Coolstore component page in RHDH."
echo ""
