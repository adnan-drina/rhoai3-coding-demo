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
        # W4-121a / O-ENVNOCLOBBER: do not clobber already-exported vars.
        # `set -a; source .env` used to overwrite caller-explicit V10_WS_NAME
        # (and any other override) with stale pins — parity/idle then targeted
        # a Stopped workspace (W4-120a). Snapshot pre-set keys, source, restore.
        local _preserves=()
        local _line _key
        while IFS= read -r _line || [[ -n "$_line" ]]; do
            [[ "$_line" =~ ^[[:space:]]*# ]] && continue
            [[ "$_line" =~ ^[[:space:]]*$ ]] && continue
            _line="${_line#export }"
            _key="${_line%%=*}"
            _key="${_key#"${_key%%[![:space:]]*}"}"
            _key="${_key%"${_key##*[![:space:]]}"}"
            [[ -z "$_key" || "$_key" == *[!A-Za-z0-9_]* ]] && continue
            if [[ -n "${!_key+x}" ]]; then
                _preserves+=("$_key=${!_key}")
            fi
        done < "$env_file"
        set -a
        # shellcheck disable=SC1090
        source "$env_file"
        set +a
        # Bash 3.2 + set -u: empty "${arr[@]}" is unbound (W4-126a).
        local _p
        if ((${#_preserves[@]} > 0)); then
            for _p in "${_preserves[@]}"; do
                export "$_p"
            done
        fi
    fi
}

# ── Required .env pre-flight ───────────────────────────────────────────────────
# A stage that starts mutating the cluster with a mandatory .env value missing
# produces a broken-but-green deployment: Argo CD reports Synced/Healthy while a
# component silently fails hours later (an empty GITHUB_TOKEN crashes Developer
# Hub's scaffolder; a missing webhook secret means no pipeline ever triggers).
# It is on the deploy script — not the user — to catch this at the door. Declare
# each required value with require_env (naming what it is and how the stage uses
# it), then call assert_required_env before the first cluster mutation.
_REQUIRED_ENV_MISSING=()

# require_env VAR "what this value is and how this stage uses it"
require_env() {
    local var="$1" desc="$2"
    if [[ -z "${!var:-}" ]]; then
        _REQUIRED_ENV_MISSING+=("${var}"$'\t'"${desc}")
    fi
}

# assert_required_env — report every missing value at once (so it can be fixed in
# one pass) and stop before the stage changes anything.
assert_required_env() {
    [[ ${#_REQUIRED_ENV_MISSING[@]} -eq 0 ]] && return 0
    log_error "Cannot deploy ${STAGE_NAME:-this stage}: ${#_REQUIRED_ENV_MISSING[@]} required value(s) are not set in .env."
    log_error "The deployment needs these to configure the stage. Add them to ${REPO_ROOT:-.}/.env and re-run — nothing has been applied to the cluster yet:"
    echo "" >&2
    local entry var desc
    for entry in "${_REQUIRED_ENV_MISSING[@]}"; do
        var="${entry%%$'\t'*}"; desc="${entry#*$'\t'}"
        printf '  \033[1m%s\033[0m\n      %s\n\n' "$var" "$desc" >&2
    done
    _REQUIRED_ENV_MISSING=()
    exit 44
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
