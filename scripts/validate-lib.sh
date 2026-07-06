#!/usr/bin/env bash
# Shared validation functions for RHOAI demo stage validation scripts
#
# Convention:
#   Exit 0 = all checks passed (PASS)
#   Exit 1 = at least one critical check failed (FAIL)
#   Exit 2 = warnings only, no critical failures (PARTIAL)
#
# Usage:
#   source "$REPO_ROOT/scripts/validate-lib.sh"
#   check "Label" "oc get ..." "expected-substring"
#   check_warn "Label" "oc get ..." "expected-substring"
#   validation_summary

VALIDATE_PASS=0
VALIDATE_WARN=0
VALIDATE_FAIL=0

REPO_ROOT="${REPO_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
source "$REPO_ROOT/scripts/lib.sh"
load_env
check_oc_logged_in

check() {
    local label="$1" cmd="$2" expected="$3"
    local actual
    actual=$(eval "$cmd" 2>/dev/null) || actual="ERROR"
    if [[ "$actual" == *"$expected"* ]]; then
        echo -e "${GREEN}[PASS]${NC} $label"
        VALIDATE_PASS=$((VALIDATE_PASS + 1))
    else
        echo -e "${RED}[FAIL]${NC} $label (expected: $expected, got: $actual)"
        VALIDATE_FAIL=$((VALIDATE_FAIL + 1))
    fi
}

check_warn() {
    local label="$1" cmd="$2" expected="$3"
    local actual
    actual=$(eval "$cmd" 2>/dev/null) || actual="ERROR"
    if [[ "$actual" == *"$expected"* ]]; then
        echo -e "${GREEN}[PASS]${NC} $label"
        VALIDATE_PASS=$((VALIDATE_PASS + 1))
    else
        echo -e "${YELLOW}[WARN]${NC} $label (expected: $expected, got: $actual)"
        VALIDATE_WARN=$((VALIDATE_WARN + 1))
    fi
}

# Sync drift is a WARN because operator-managed resources routinely drift;
# health is the real signal: Progressing warns, anything else non-Healthy fails.
check_argocd_app() {
    local app_name="$1"
    local sync health
    sync=$(oc get application "$app_name" -n openshift-gitops -o jsonpath='{.status.sync.status}' 2>/dev/null || echo "NOT_FOUND")
    health=$(oc get application "$app_name" -n openshift-gitops -o jsonpath='{.status.health.status}' 2>/dev/null || echo "NOT_FOUND")

    if [[ "$sync" == "Synced" ]]; then
        echo -e "${GREEN}[PASS]${NC} Argo CD app '$app_name' sync: Synced"
        VALIDATE_PASS=$((VALIDATE_PASS + 1))
    else
        echo -e "${YELLOW}[WARN]${NC} Argo CD app '$app_name' sync: $sync (operator-managed resources may drift)"
        VALIDATE_WARN=$((VALIDATE_WARN + 1))
    fi

    if [[ "$health" == "Healthy" ]]; then
        echo -e "${GREEN}[PASS]${NC} Argo CD app '$app_name' health: Healthy"
        VALIDATE_PASS=$((VALIDATE_PASS + 1))
    elif [[ "$health" == "Progressing" ]]; then
        echo -e "${YELLOW}[WARN]${NC} Argo CD app '$app_name' health: Progressing (re-run validation once settled)"
        VALIDATE_WARN=$((VALIDATE_WARN + 1))
    else
        echo -e "${RED}[FAIL]${NC} Argo CD app '$app_name' health (expected: Healthy, got: $health)"
        VALIDATE_FAIL=$((VALIDATE_FAIL + 1))
    fi
}

# Counts pods whose Ready condition is True; a "0/1 Running" pod does not count.
check_pods_ready() {
    local ns="$1" selector="$2" min_count="${3:-1}"
    local ready_count
    ready_count=$(oc get pods -n "$ns" -l "$selector" \
        -o jsonpath='{range .items[*]}{.status.conditions[?(@.type=="Ready")].status}{"\n"}{end}' 2>/dev/null \
        | grep -c "True" || true)

    if [[ "$ready_count" -ge "$min_count" ]]; then
        echo -e "${GREEN}[PASS]${NC} Pods ready ($selector in $ns): $ready_count >= $min_count"
        VALIDATE_PASS=$((VALIDATE_PASS + 1))
    else
        echo -e "${RED}[FAIL]${NC} Pods ready ($selector in $ns): $ready_count < $min_count"
        VALIDATE_FAIL=$((VALIDATE_FAIL + 1))
    fi
}

check_crd_exists() {
    local crd="$1"
    if oc get crd "$crd" &>/dev/null; then
        echo -e "${GREEN}[PASS]${NC} CRD exists: $crd"
        VALIDATE_PASS=$((VALIDATE_PASS + 1))
    else
        echo -e "${RED}[FAIL]${NC} CRD missing: $crd"
        VALIDATE_FAIL=$((VALIDATE_FAIL + 1))
    fi
}

check_csv_succeeded() {
    local ns="$1" pattern="$2"
    local phase
    phase=$(oc get csv -n "$ns" -o jsonpath="{.items[?(@.spec.displayName==\"$pattern\")].status.phase}" 2>/dev/null || echo "")
    if [[ -z "$phase" ]]; then
        phase=$(oc get csv -n "$ns" --no-headers 2>/dev/null | grep -i "$pattern" | awk '{print $NF}' || echo "NOT_FOUND")
    fi

    if [[ "$phase" == *"Succeeded"* ]]; then
        echo -e "${GREEN}[PASS]${NC} CSV succeeded: $pattern (in $ns)"
        VALIDATE_PASS=$((VALIDATE_PASS + 1))
    else
        echo -e "${RED}[FAIL]${NC} CSV not succeeded: $pattern (in $ns, phase: $phase)"
        VALIDATE_FAIL=$((VALIDATE_FAIL + 1))
    fi
}

# PASS when the secret key exists and is not a placeholder (case-insensitive
# "placeholder"/"replace"). Bad-case severity is "fail" (default) or "warn".
check_secret_value() {
    local label="$1" ns="$2" secret="$3" key="$4" severity="${5:-fail}"
    local value value_lc
    value=$(oc get secret "$secret" -n "$ns" -o jsonpath="{.data.${key}}" 2>/dev/null | base64 -d 2>/dev/null || echo "")
    value_lc=$(printf '%s' "$value" | tr '[:upper:]' '[:lower:]')
    if [[ -n "$value" && "$value_lc" != *placeholder* && "$value_lc" != *replace* ]]; then
        echo -e "${GREEN}[PASS]${NC} $label: set"
        VALIDATE_PASS=$((VALIDATE_PASS + 1))
    elif [[ "$severity" == "warn" ]]; then
        echo -e "${YELLOW}[WARN]${NC} $label is placeholder or missing"
        VALIDATE_WARN=$((VALIDATE_WARN + 1))
    else
        echo -e "${RED}[FAIL]${NC} $label is placeholder or missing"
        VALIDATE_FAIL=$((VALIDATE_FAIL + 1))
    fi
}

# PASS when the URL answers with one of the expected comma-separated HTTP
# codes; WARN otherwise (endpoints behind auth redirects vary per cluster).
check_http_code() {
    local label="$1" url="$2" expected="${3:-200}"
    local code
    code=$(curl -sk -o /dev/null -w "%{http_code}" --max-time 20 "$url" 2>/dev/null || echo "000")
    if [[ ",${expected}," == *",${code},"* ]]; then
        echo -e "${GREEN}[PASS]${NC} $label (HTTP ${code})"
        VALIDATE_PASS=$((VALIDATE_PASS + 1))
    else
        echo -e "${YELLOW}[WARN]${NC} $label (HTTP ${code})"
        VALIDATE_WARN=$((VALIDATE_WARN + 1))
    fi
}

validation_summary() {
    local total=$((VALIDATE_PASS + VALIDATE_WARN + VALIDATE_FAIL))
    echo ""
    echo "VALIDATION: $VALIDATE_PASS passed, $VALIDATE_WARN warnings, $VALIDATE_FAIL failed (total: $total)"

    if [[ $VALIDATE_FAIL -gt 0 ]]; then
        return 1
    elif [[ $VALIDATE_WARN -gt 0 ]]; then
        return 2
    else
        return 0
    fi
}
