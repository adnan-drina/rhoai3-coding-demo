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
    oc whoami &>/dev/null || { log_error "Not logged in. Run: oc login <cluster>"; exit 1; }
}

ensure_namespace() {
    local ns="$1"
    oc get namespace "$ns" &>/dev/null || oc create namespace "$ns"
}

ensure_secret_from_env() {
    local name="$1" ns="$2"; shift 2
    oc create secret generic "$name" -n "$ns" "${@/#/--from-literal=}" \
        --dry-run=client -o yaml | oc apply -f -
}

wait_for_crd() {
    local crd="$1" timeout="${2:-120}" elapsed=0
    log_info "Waiting for CRD $crd (timeout ${timeout}s)..."
    until oc get crd "$crd" &>/dev/null; do
        sleep 5
        elapsed=$((elapsed + 5))
        if [ $elapsed -ge $timeout ]; then
            log_error "Timeout waiting for CRD $crd after ${timeout}s"
            return 1
        fi
    done
}
