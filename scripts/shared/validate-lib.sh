#!/usr/bin/env bash
# Shared validation functions for RHOAI demo stage validation scripts
#
# Convention:
#   Exit 0 = all checks passed (PASS)
#   Exit 1 = at least one critical check failed (FAIL)
#   Exit 2 = warnings only, no critical failures (PARTIAL)
#
# Usage:
#   source "$REPO_ROOT/scripts/shared/validate-lib.sh"
#   check "Label" "oc get ..." "expected-substring"
#   check_warn "Label" "oc get ..." "expected-substring"
#   validation_summary

# Match a pattern on a pipe without stopping early. `grep -q` exits at the first
# match; the producer (oc, curl) then dies of SIGPIPE on a large document and
# pipefail turns the match into a miss. Use: `oc get ... | contains -E 'x' && echo present`.
contains() { grep "$@" >/dev/null; }

VALIDATE_PASS=0
VALIDATE_WARN=0
VALIDATE_FAIL=0

REPO_ROOT="${REPO_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
source "$REPO_ROOT/scripts/shared/lib.sh"
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

# Every component Application of a stage (including script-deployed ones) Synced at one immutable revision, Healthy
# (or its declared accepted health) and last synced successfully; one line per component. An optional revision
# requires that exact commit.
check_stage_applications() {
    local stage="$1" revision="${2:-}" output line
    local args=(status "$stage")
    [[ -z "${GIT_REPO_URL:-}" ]] || args+=(--repo-url "$GIT_REPO_URL")
    [[ -z "$revision" ]] || args+=(--revision "$revision")
    output=$(python3 "$REPO_ROOT/scripts/shared/stage_apps.py" "${args[@]}" 2>&1) || true
    [[ -n "$output" ]] || output="ERROR no output from stage_apps status $stage"
    while IFS= read -r line; do
        case "$line" in
            "OK   "*) echo -e "${GREEN}[PASS]${NC} Argo CD ${line#OK   } reconciled"; VALIDATE_PASS=$((VALIDATE_PASS + 1)) ;;
            "FAIL "*) echo -e "${RED}[FAIL]${NC} Argo CD ${line#FAIL } not reconciled"; VALIDATE_FAIL=$((VALIDATE_FAIL + 1)) ;;
            "ERROR"*) echo -e "${RED}[FAIL]${NC} Stage $stage Applications ($line)"; VALIDATE_FAIL=$((VALIDATE_FAIL + 1)) ;;
            *) echo "    $line" ;;
        esac
    done <<< "$output"
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
