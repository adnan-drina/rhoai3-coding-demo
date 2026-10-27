#!/usr/bin/env bash
# Shared functions for the stage deploy.sh and validate.sh scripts: environment, cluster guard, logging, validation
# checks, and the read-only platform prerequisites several stages share (operator policy, node sizing, serving).
# Usage: REPO_ROOT=...; source "$REPO_ROOT/scripts/lib.sh"; load_env; check_oc_logged_in
set -euo pipefail
REPO_ROOT="${REPO_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"

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
yaml_json()   { ruby -ryaml -rjson -e 'puts JSON.generate(YAML.load_stream(STDIN.read).compact)'; }

# ── Environment ────────────────────────────────────────────────────────────────
# Source .env without clobbering values the caller already exported.
load_env() {
    local env_file="${REPO_ROOT:-.}/.env"
    if [[ -f "$env_file" ]]; then
        # Do not clobber already-exported vars.
        # `set -a; source .env` used to overwrite caller-explicit overrides
        # with stale pins. Snapshot pre-set keys, source, restore.
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

# ── Required .env values ─────────────────────────────────────────────────────
# Declare each mandatory value with require_env (naming how the stage uses it), then call assert_required_env before
# the first cluster mutation: a missing value otherwise yields a green deployment that fails hours later.
_REQUIRED_ENV_MISSING=()

# require_env VAR "what this value is and how this stage uses it"
require_env() {
    local var="$1" desc="$2"
    if [[ -z "${!var:-}" ]]; then
        _REQUIRED_ENV_MISSING+=("${var}"$'\t'"${desc}")
    fi
}

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

# ── Cluster guard: logged in, and to the cluster RHOAI_EXPECTED_API_SERVER names ──
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

# ── Validation checks ──────────────────────────────────────────────────────────
# Exit convention of validation_summary: 0 all passed, 1 a check failed, 2 warnings only.
VALIDATE_PASS=0
VALIDATE_WARN=0
VALIDATE_FAIL=0

# Match a pattern on a pipe without stopping early (grep -q makes the producer die of SIGPIPE under pipefail).
contains() { grep "$@" >/dev/null; }

# check LABEL COMMAND EXPECTED-SUBSTRING (check_warn reports a miss as a warning)
_check() {
    local level="$1" label="$2" cmd="$3" expected="$4" actual
    actual=$(eval "$cmd" 2>/dev/null) || actual="ERROR"
    if [[ "$actual" == *"$expected"* ]]; then
        echo -e "${GREEN}[PASS]${NC} $label"; VALIDATE_PASS=$((VALIDATE_PASS + 1))
    elif [[ "$level" == warn ]]; then
        echo -e "${YELLOW}[WARN]${NC} $label (expected: $expected, got: $actual)"; VALIDATE_WARN=$((VALIDATE_WARN + 1))
    else
        echo -e "${RED}[FAIL]${NC} $label (expected: $expected, got: $actual)"; VALIDATE_FAIL=$((VALIDATE_FAIL + 1))
    fi
}
check()      { _check fail "$@"; }
check_warn() { _check warn "$@"; }
# record LABEL RESULT: a check whose result was already computed ("pass" or "yes" passes; anything else is the reason).
# record_warn reports a miss as a warning (a missing persona session is not a platform fault).
_record() {
    if [[ "$3" == pass || "$3" == yes ]]; then
        echo -e "${GREEN}[PASS]${NC} $2"; VALIDATE_PASS=$((VALIDATE_PASS + 1))
    elif [[ "$1" == warn ]]; then
        echo -e "${YELLOW}[WARN]${NC} $2 ($3)"; VALIDATE_WARN=$((VALIDATE_WARN + 1))
    else
        echo -e "${RED}[FAIL]${NC} $2 ($3)"; VALIDATE_FAIL=$((VALIDATE_FAIL + 1))
    fi
}
record()      { _record fail "$@"; }
record_warn() { _record warn "$@"; }

# Every component Application of a stage (script-deployed ones too) Synced at one immutable revision, Healthy (or its
# declared accepted health) and last synced successfully; one line per component. An optional revision is required.
check_stage_applications() {
    local stage="$1" revision="${2:-}" output line rc=0 failed=0
    local args=(status "$stage")
    [[ -z "${GIT_REPO_URL:-}" ]] || args+=(--repo-url "$GIT_REPO_URL")
    [[ -z "$revision" ]] || args+=(--revision "$revision")
    output=$("$REPO_ROOT/scripts/stage-apps.sh" "${args[@]}" 2>&1) || rc=$?
    [[ -n "$output" ]] || output="ERROR no output from stage-apps status $stage"
    while IFS= read -r line; do
        case "$line" in
            "OK   "*) echo -e "${GREEN}[PASS]${NC} Argo CD ${line#OK   } reconciled"; VALIDATE_PASS=$((VALIDATE_PASS + 1)) ;;
            "FAIL "*) echo -e "${RED}[FAIL]${NC} Argo CD ${line#FAIL } not reconciled"; VALIDATE_FAIL=$((VALIDATE_FAIL + 1)); failed=1 ;;
            "ERROR"*) echo -e "${RED}[FAIL]${NC} Stage $stage Applications ($line)"; VALIDATE_FAIL=$((VALIDATE_FAIL + 1)); failed=1 ;;
            *) echo "    $line" ;;
        esac
    done <<< "$output"
    # A stage-wide problem (components at different revisions) fails status without marking one component FAIL.
    if [[ "$rc" -ne 0 && "$failed" -eq 0 ]]; then
        echo -e "${RED}[FAIL]${NC} Stage $stage Applications not reconciled at one revision (stage-apps status exit $rc)"
        VALIDATE_FAIL=$((VALIDATE_FAIL + 1))
    fi
}

check_csv_succeeded() {
    local ns="$1" pattern="$2" phase
    phase=$(oc get csv -n "$ns" -o jsonpath="{.items[?(@.spec.displayName==\"$pattern\")].status.phase}" 2>/dev/null || echo "")
    [[ -n "$phase" ]] || phase=$(oc get csv -n "$ns" --no-headers 2>/dev/null | grep -i "$pattern" | awk '{print $NF}' || echo "NOT_FOUND")
    if [[ "$phase" == *"Succeeded"* ]]; then
        echo -e "${GREEN}[PASS]${NC} CSV succeeded: $pattern (in $ns)"; VALIDATE_PASS=$((VALIDATE_PASS + 1))
    else
        echo -e "${RED}[FAIL]${NC} CSV not succeeded: $pattern (in $ns, phase: $phase)"; VALIDATE_FAIL=$((VALIDATE_FAIL + 1))
    fi
}

# PASS when the URL answers with one of the comma-separated HTTP codes; WARN otherwise (auth redirects vary).
check_http_code() {
    local label="$1" url="$2" expected="${3:-200}" code
    code=$(curl -sk -o /dev/null -w "%{http_code}" --max-time 20 "$url" 2>/dev/null || echo "000")
    if [[ ",${expected}," == *",${code},"* ]]; then
        echo -e "${GREEN}[PASS]${NC} $label (HTTP ${code})"; VALIDATE_PASS=$((VALIDATE_PASS + 1))
    else
        echo -e "${YELLOW}[WARN]${NC} $label (HTTP ${code})"; VALIDATE_WARN=$((VALIDATE_WARN + 1))
    fi
}

validation_summary() {
    echo ""
    echo "VALIDATION: $VALIDATE_PASS passed, $VALIDATE_WARN warnings, $VALIDATE_FAIL failed (total: $((VALIDATE_PASS + VALIDATE_WARN + VALIDATE_FAIL)))"
    if [[ $VALIDATE_FAIL -gt 0 ]]; then return 1; elif [[ $VALIDATE_WARN -gt 0 ]]; then return 2; fi
    return 0
}

# ── Node sizing ────────────────────────────────────────────────────────────────
# The full stack overloads small control planes: on 2026-07-20 m6a.xlarge (4 vCPU / 16 GiB) masters failed one after
# another until etcd quorum was at risk. Control-plane and CPU workers need >= 16 vCPU / 60 GiB (m6a.4xlarge-class);
# GPU nodes are sized by accelerator and exempt. Each deploy.sh calls this before its first change.
require_node_sizing() {
    local vcpu="${REQUIRED_NODE_VCPU:-16}" mem="${REQUIRED_NODE_MEM_GIB:-60}" undersized
    if ! undersized=$(oc --request-timeout="${RHOAI_OC_REQUEST_TIMEOUT:-10s}" get nodes -o json 2>/dev/null |
        jq -er --argjson cpu "$vcpu" --argjson mem "$mem" '
            def pad($n): tostring | if length < $n then . + (" " * ($n - length)) else . end;
            if (.items | type) != "array" or (.items | length) == 0 then error("empty node inventory") else . end
            | [.items[] | .metadata.labels as $l | ($l["node.kubernetes.io/instance-type"] // "?") as $type
                | select(($l["nvidia.com/gpu.present"] or $l["cluster-api/accelerator"] or $l["node-role.kubernetes.io/gpu"]
                    or ($type | test("^[gp]"))) | not)
                | (if $l["node-role.kubernetes.io/control-plane"] != null or $l["node-role.kubernetes.io/master"] != null
                    then "control-plane" else "worker" end) as $role
                | ((.status.capacity.cpu // "0") | tonumber? // 0) as $c
                | (.status.capacity.memory // "0") as $m
                | (($m | gsub("[^0-9]"; "")) | if . == "" then 0 else tonumber end) as $num
                | (if ($m | gsub("[0-9]"; "")) == "Ki" then $num / 1048576 else $num / 1073741824 end) as $gib
                | select($c < $cpu or $gib < $mem)
                | "\($role | pad(14)) \(.metadata.name | pad(45)) \($type | pad(14)) \($c) vCPU / \($gib | floor) GiB"] | join("\n")'); then
        log_error "Unable to verify node sizing; stopping before changes."
        exit 46
    fi
    if [[ -n "$undersized" ]]; then
        log_error "Cluster nodes are too small to run the demo; stopping before any changes."
        echo "  Required: >= ${vcpu} vCPU / >= ${mem} GiB (m6a.4xlarge-class) for control-plane and CPU worker nodes." >&2
        echo "  Undersized nodes (reprovision with m6a.4xlarge or larger control-plane AND worker nodes):" >&2
        sed 's/^/    /' <<<"$undersized" >&2
        exit 45
    fi
    log_success "Node sizing meets the demo minimum (>= ${vcpu} vCPU / ${mem} GiB; GPU nodes exempt)."
}

# ── Operator policy ────────────────────────────────────────────────────────────
# Qualified channel and minimum version (same major.minor family) of each Automatic Subscription the demo selects.
# Rolling channels update within the family; this check refuses a family the demo has not qualified.
OPERATOR_POLICY='{
  "rhods-operator": ["stable-3.5", "3.5.1"], "openshift-gitops-operator": ["gitops-1.21", "1.21.5"],
  "odf-operator": ["stable-4.22", "4.22.5"], "cluster-observability-operator": ["stable", "1.5.3"],
  "opentelemetry-product": ["stable", "0.158.0-2"], "tempo-product": ["stable", "0.22.0-2"], "nfd": ["stable", "4.22.0"],
  "gpu-operator-certified": ["v26.7", "26.7.1"], "kueue-operator": ["stable-v1.4", "1.4.2"],
  "leader-worker-set": ["stable-v1.0", "1.0.1"], "rhcl-operator": ["stable", "1.4.3"], "authorino-operator": ["stable", "1.4.3"],
  "dns-operator": ["stable", "1.4.2"], "limitador-operator": ["stable", "1.4.2"], "servicemeshoperator3": ["stable-3.4", "3.4.3"],
  "agent-sandbox-operator": ["preview-0.9", "0.9.0"], "devspaces": ["stable", "3.31.0"]}'
POLICY_JQ='def ver: [capture("^(?<a>[0-9]+)\\.(?<b>[0-9]+)\\.(?<c>[0-9]+)(-(?<d>[0-9]+)|-rhodf)?$")]
        | if length == 0 then error("Unsupported operator version shape") else .[0] | [.a, .b, .c, (.d // "0")] | map(tonumber) end;
    def compatible($p; $pkg; $v): if $p[$pkg] == null then error("Operator baseline is deferred/unqualified: \($pkg)")
        else ($v | ver) as $a | ($p[$pkg][1] | ver) as $b
        | if $a[:2] == $b[:2] and $a >= $b then true else error("Unavailable/incompatible operator release: \($pkg) \($v)") end end;'

# check_operator_policy MANIFEST [--wait SECONDS | --verify]
# Default (before install): the catalog offers each selected Subscription's reviewed channel at a qualified version
# and nothing already installed conflicts. --wait/--verify: each installed CSV is qualified and Succeeded.
check_operator_policy() {
    local manifest="$1" mode="${2:-}" wait="${3:-0}" selected work sub ns name deadline live csv installed
    work=$(mktemp -d)
    if [[ -d "$manifest" ]]; then oc kustomize "$manifest" >"$work/raw"; else cat "$manifest" >"$work/raw"; fi
    yaml_json <"$work/raw" | jq -c '[.[] | select(.kind == "Subscription")]' >"$work/selected.json"
    selected=$(cat "$work/selected.json")
    [[ $(jq length <<<"$selected") -gt 0 ]] || { rm -rf "$work"; log_error "No selected Subscriptions in $manifest"; return 1; }
    jq -e --argjson p "$OPERATOR_POLICY" 'all(.[]; .spec.installPlanApproval == "Automatic" and .spec.channel == $p[.spec.name][0])' \
        <<<"$selected" >/dev/null || { rm -rf "$work"; log_error "Unreviewed Subscription approval or channel in $manifest"; return 1; }
    if [[ -z "$mode" ]]; then
        if [[ "$(oc --request-timeout=15s get cloudcredential cluster -o jsonpath='{.spec.credentialsMode}')" == Manual ||
              -n "$(oc --request-timeout=15s get authentication cluster -o jsonpath='{.spec.serviceAccountIssuer}')" ]]; then
            rm -rf "$work"; log_error "Automatic demo install excludes cloud workload-token/Manual credential mode"; return 1
        fi
        # The effective credential mode is not inferred from Secrets; the provisioner states the standard contract.
        [[ "${RHOAI_OPERATOR_CREDENTIAL_MODE:-}" == standard ]] ||
            { rm -rf "$work"; log_error "Unknown/nonstandard cloud identity contract (RHOAI_OPERATOR_CREDENTIAL_MODE); Automatic installation refused"; return 1; }
        oc --request-timeout=60s get packagemanifest -n openshift-marketplace -o json >"$work/catalog.json"
        while IFS= read -r sub; do
            ns=$(jq -r '.metadata.namespace' <<<"$sub")
            oc --request-timeout=15s get subscription -n "$ns" -o json >"$work/existing.json"
            jq -n -e --argjson s "$sub" --argjson p "$OPERATOR_POLICY" --argjson selected "$selected" \
                --slurpfile catalog "$work/catalog.json" --slurpfile existing "$work/existing.json" "$POLICY_JQ"'
                $s.spec as $x
                | [$catalog[0].items[] | select(.metadata.name == $x.name and .status.catalogSource == $x.source
                    and .status.catalogSourceNamespace == $x.sourceNamespace)]
                | if length != 1 then error("Catalog package/source is missing or ambiguous: \($x.name)") else .[0] end
                | [.status.channels[] | select(.name == $x.channel)]
                | if length != 1 then error("Selected channel unavailable: \($x.name) \($x.channel)") else .[0] end
                | compatible($p; $x.name; .currentCSVDesc.version)
                | [$existing[0].items[] | select(.metadata.name == $s.metadata.name)
                    | select([.spec.name, .spec.channel, .spec.source, .spec.sourceNamespace] != [$x.name, $x.channel, $x.source, $x.sourceNamespace])]
                | if length > 0 then error("Existing selected operator has incompatible source/channel scope: \($x.name)") else . end
                | ([$selected[] | "\(.metadata.namespace)/\(.metadata.name)"]) as $owned
                | [$existing[0].items[] | select(.spec.installPlanApproval == "Manual" and ("\(.metadata.namespace)/\(.metadata.name)" | IN($owned[]) | not))]
                | if length > 0 then error("Foreign Manual subscription blocks namespace Automatic resolution in \($s.metadata.namespace)") else true end' \
                >/dev/null || { rm -rf "$work"; return 1; }
        done < <(jq -c '.[]' <<<"$selected")
        rm -rf "$work"
        echo "PASS Offered catalog/source/channel compatibility; future rolling updates are not frozen"
        return 0
    fi
    [[ "$mode" == --wait ]] || wait=0
    deadline=$((SECONDS + wait))
    while IFS= read -r sub; do
        ns=$(jq -r '.metadata.namespace' <<<"$sub"); name=$(jq -r '.metadata.name' <<<"$sub")
        while true; do
            live=$(oc --request-timeout=15s get subscription "$name" -n "$ns" --ignore-not-found -o json)
            if [[ -n "$live" ]]; then
                jq -e --argjson s "$sub" '[.spec.name, .spec.channel, .spec.source, .spec.sourceNamespace, .spec.installPlanApproval]
                    == [$s.spec.name, $s.spec.channel, $s.spec.source, $s.spec.sourceNamespace, $s.spec.installPlanApproval]' <<<"$live" >/dev/null ||
                    { rm -rf "$work"; log_error "Native Subscription policy differs from source: $name"; return 1; }
                installed=$(jq -r '.status.installedCSV // ""' <<<"$live")
                if [[ -n "$installed" ]]; then
                    csv=$(oc --request-timeout=15s get csv "$installed" -n "$ns" --ignore-not-found -o json)
                    if [[ -n "$csv" ]]; then
                        jq -n -e --argjson p "$OPERATOR_POLICY" --argjson csv "$csv" --argjson live "$live" "$POLICY_JQ"'
                            compatible($p; $live.spec.name; $csv.spec.version)' >/dev/null || { rm -rf "$work"; return 1; }
                        jq -e --argjson csv "$csv" '$csv.status.phase == "Succeeded" and .status.currentCSV == .status.installedCSV' \
                            <<<"$live" >/dev/null && break
                    fi
                fi
            fi
            if (( wait == 0 || SECONDS >= deadline )); then
                rm -rf "$work"; log_error "Automatic operator readiness pending: $name (inspect the native OLM conditions)"; return 1
            fi
            sleep 5
        done
        echo "PASS Automatic current CSV Succeeded: $(jq -r '.spec.name' <<<"$live")"
    done < <(jq -c '.[]' <<<"$selected")
    rm -rf "$work"
}

# ── Serving prerequisites (Stages 030 and 040 updates) ─────────────────────────
# An installed serving stage is updated only when its components are reconciled and the native serving platform is
# ready. Parked GPU capacity is not a prerequisite; broken scheduled GPU workloads are.
check_serving_prerequisites() {
    local stage="$1" policy subscription installed ds
    "$REPO_ROOT/scripts/stage-apps.sh" status "$stage" --repo-url "$GIT_REPO_URL" >/dev/null ||
        { log_error "Existing Stage $stage source must be reconciled before update"; return 1; }
    oc --request-timeout=10s get datasciencecluster default-dsc -o json | jq -e '.spec.components.kserve.managementState == "Managed"
        and any(.status.conditions[]?; .type == "KserveReady" and .status == "True")' >/dev/null ||
        { log_error "Native KServe is not ready"; return 1; }
    policy=$(oc --request-timeout=10s get clusterpolicy gpu-cluster-policy -o json)
    jq -e '.status.state == "ready"' <<<"$policy" >/dev/null || { log_error "Native GPU ClusterPolicy is not ready"; return 1; }
    # The Subscription updates within the reviewed v26.7 channel, so read the installed CSV from it.
    subscription=$(oc --request-timeout=10s get subscription gpu-operator-certified -n nvidia-gpu-operator -o json)
    installed=$(jq -r '.status.installedCSV // ""' <<<"$subscription")
    jq -e --arg i "$installed" '.spec.channel == "v26.7" and ($i | startswith("gpu-operator-certified.v26.7."))' <<<"$subscription" >/dev/null &&
        [[ $(oc --request-timeout=10s get csv "$installed" -n nvidia-gpu-operator -o jsonpath='{.status.phase}') == Succeeded ]] ||
        { log_error "Reviewed GPU operator channel/version is not installed"; return 1; }
    for ds in nvidia-operator-validator nvidia-dcgm-exporter; do
        oc --request-timeout=10s get daemonset "$ds" -n nvidia-gpu-operator -o json | jq -e --arg uid "$(jq -r '.metadata.uid' <<<"$policy")" '
            .status as $s | ($s.desiredNumberScheduled // 0) as $n
            | any(.metadata.ownerReferences[]?; .uid == $uid and .controller)
            and $s.observedGeneration == .metadata.generation and ($s.numberReady // 0) == $n and ($s.updatedNumberScheduled // 0) == $n' \
            >/dev/null || { log_error "Scheduled native GPU workload $ds is not current/ready or has another owner"; return 1; }
    done
    echo "PASS Existing native serving/GPU installation and scheduled workloads; parked capacity is not an update prerequisite"
}
