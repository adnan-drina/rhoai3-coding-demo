#!/usr/bin/env bash
# Shared validation functions for RHOAI demo step validation scripts
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

check_argocd_app() {
    local app_name="$1"
    local sync health
    sync=$(oc get application "$app_name" -n openshift-gitops -o jsonpath='{.status.sync.status}' 2>/dev/null || echo "NOT_FOUND")
    health=$(oc get application "$app_name" -n openshift-gitops -o jsonpath='{.status.health.status}' 2>/dev/null || echo "NOT_FOUND")

    if [[ "$sync" == "Synced" ]]; then
        echo -e "${GREEN}[PASS]${NC} Argo CD app '$app_name' sync: Synced"
        VALIDATE_PASS=$((VALIDATE_PASS + 1))
    else
        echo -e "${RED}[FAIL]${NC} Argo CD app '$app_name' sync (expected: Synced, got: $sync)"
        VALIDATE_FAIL=$((VALIDATE_FAIL + 1))
    fi

    if [[ "$health" == "Healthy" ]]; then
        echo -e "${GREEN}[PASS]${NC} Argo CD app '$app_name' health: Healthy"
        VALIDATE_PASS=$((VALIDATE_PASS + 1))
    else
        echo -e "${YELLOW}[WARN]${NC} Argo CD app '$app_name' health (expected: Healthy, got: $health)"
        VALIDATE_WARN=$((VALIDATE_WARN + 1))
    fi
}

check_pods_ready() {
    local ns="$1" selector="$2" min_count="${3:-1}"
    local ready_count
    ready_count=$(oc get pods -n "$ns" -l "$selector" --no-headers 2>/dev/null \
        | grep -c "Running" || echo "0")

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
