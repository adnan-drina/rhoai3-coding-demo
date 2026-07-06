#!/usr/bin/env bash
# Shared helper functions for RHOAI demo scripts

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info()    { echo -e "${BLUE}[INFO]${NC} $*"; }
log_success() { echo -e "${GREEN}[OK]${NC} $*"; }
log_warn()    { echo -e "${YELLOW}[WARN]${NC} $*"; }
log_error()   { echo -e "${RED}[ERROR]${NC} $*" >&2; }
log_step()    { echo -e "\n${BLUE}▶ $*${NC}"; }

load_env() {
    local env_file="${REPO_ROOT:-.}/.env"
    if [[ -f "$env_file" ]]; then
        set -a; source "$env_file"; set +a
    fi
}

check_oc_logged_in() {
    local request_timeout="${RHOAI_OC_REQUEST_TIMEOUT:-10s}"

    oc --request-timeout="$request_timeout" whoami &>/dev/null || {
        log_error "Not logged in or OpenShift API did not respond within ${request_timeout}."
        log_error "Run: oc login <cluster>"
        exit 1
    }

    local server expected
    server="$(oc --request-timeout="$request_timeout" whoami --show-server 2>/dev/null || true)"
    expected="${RHOAI_EXPECTED_API_SERVER:-${RHOAI_EXPECTED_CLUSTER:-}}"

    if [[ -z "$expected" && "${RHOAI_ALLOW_UNGUARDED_CLUSTER:-false}" != "true" ]]; then
        log_error "OpenShift API server guard is not configured"
        log_error "  Set RHOAI_EXPECTED_API_SERVER in .env to a unique target API-server substring."
        log_error "  Current API: ${server:-unknown}"
        log_error "  To bypass intentionally, set RHOAI_ALLOW_UNGUARDED_CLUSTER=true."
        exit 43
    fi

    if [[ -n "$expected" && "$server" != *"$expected"* ]]; then
        log_error "OpenShift API server guard failed"
        log_error "  expected: $expected"
        log_error "  actual:   $server"
        exit 42
    fi

    if [[ -n "$server" ]]; then
        log_info "OpenShift API: $server"
    fi
}

ensure_namespace() {
    local ns="$1"
    oc get namespace "$ns" &>/dev/null || oc create namespace "$ns"
}

# Apply the Argo CD Application for a stage.
apply_stage_app() {
    local stage="$1"
    oc apply -f "$REPO_ROOT/gitops/argocd/app-of-apps/${stage}.yaml"
    log_success "Argo CD Application '${stage}' applied"
}

ensure_secret_from_env() {
    local name="$1" ns="$2"; shift 2
    oc create secret generic "$name" -n "$ns" "${@/#/--from-literal=}" \
        --dry-run=client -o yaml | oc apply -f -
}

# Poll a command until it succeeds or the timeout (seconds) expires.
# Usage: wait_until "description" 300 oc get namespace foo
wait_until() {
    local desc="$1" timeout="$2" elapsed=0
    shift 2
    log_info "Waiting for ${desc} (timeout ${timeout}s)..."
    until "$@" &>/dev/null; do
        sleep 5
        elapsed=$((elapsed + 5))
        if [[ $elapsed -ge $timeout ]]; then
            log_error "Timeout waiting for ${desc} after ${timeout}s"
            return 1
        fi
    done
}
