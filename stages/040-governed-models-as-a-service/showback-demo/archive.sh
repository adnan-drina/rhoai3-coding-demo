#!/usr/bin/env bash
# Create/verify private immutable evidence bundles. Only explicit upload performs network writes.
# Upload uses the existing MLflow artifact proxy, then downloads and verifies every byte; no SDK/S3 keys.
# Usage: stages/040-governed-models-as-a-service/showback-demo/archive.sh pack --report FILE [--file FILE ...] --output DIR [--predecessor-manifest-sha256 HASH --correction-reason TEXT]
# Usage: stages/040-governed-models-as-a-service/showback-demo/archive.sh verify DIR
# Usage: stages/040-governed-models-as-a-service/showback-demo/archive.sh upload DIR
# REST contract: https://mlflow.org/docs/latest/api_reference/rest-api.html
# Workspace header: https://mlflow.org/docs/latest/self-hosting/workspaces/configuration/
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
source "$REPO_ROOT/scripts/lib.sh"
umask 077
for cmd in jq shasum curl; do command -v "$cmd" >/dev/null || { log_error "Missing command: $cmd"; exit 1; }; done
WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT
fail() { log_error "$*"; exit 1; }
digest() { shasum -a 256 "$1" | awk '{print $1}'; }
size() { wc -c < "$1" | tr -d '[:space:]'; }
safe_name() { [[ "$1" =~ ^[A-Za-z0-9][A-Za-z0-9._-]*$ && "$1" != manifest.json ]]; }

verify() {
    local directory="$1" name bytes sha member report_file
    [[ -d "$directory" && ! -L "$directory/manifest.json" && -f "$directory/manifest.json" ]] || fail 'Missing regular manifest'
    jq -se 'length == 1 and (.[0]|type) == "object"' "$directory/manifest.json" >/dev/null || fail 'Expected one manifest object'
    jq -e '.schema_version == 1 and (.files|type) == "array" and (.files|length) > 0
      and all([.report_id,.scope,.evidence_kind,.start,.end,.policy_version][];type == "string" and length > 0)
      and (.report_file|type) == "string" and .report_file != "manifest.json"
      and (.report_file as $report | any(.files[];.name == $report))
      and (if .predecessor_manifest_sha256 == null then .correction_reason == null
        else (.predecessor_manifest_sha256|test("^[a-f0-9]{64}$"))
          and (.correction_reason|type == "string" and length > 0) end)
      and ([.files[].name]|length) == ([.files[].name]|unique|length)
      and all(.files[]; (.name|test("^[A-Za-z0-9][A-Za-z0-9._-]*$")) and .name != "manifest.json"
        and (.bytes|type) == "number" and .bytes >= 0 and .bytes == (.bytes|floor)
        and (.sha256|test("^[a-f0-9]{64}$")))' "$directory/manifest.json" >/dev/null || fail 'Unsafe bundle manifest'
    while IFS=$'\t' read -r name bytes sha; do
        [[ -f "$directory/$name" && ! -L "$directory/$name" ]] || fail "Not a regular bundle member: $name"
        [[ $(size "$directory/$name") == "$bytes" && $(digest "$directory/$name") == "$sha" ]] || fail "Evidence hash/size mismatch: $name"
    done < <(jq -r '.files[]|[.name,.bytes,.sha256]|@tsv' "$directory/manifest.json")
    for member in "$directory"/* "$directory"/.[!.]* "$directory"/..?*; do
        [[ -e "$member" || -L "$member" ]] || continue
        name=$(basename "$member")
        [[ "$name" == manifest.json ]] && continue
        safe_name "$name" || fail 'Unsafe or hidden evidence member'
        jq -e --arg name "$name" 'any(.files[];.name == $name)' "$directory/manifest.json" >/dev/null || fail 'Unindexed evidence member'
    done
    report_file=$(jq -r '.report_file' "$directory/manifest.json")
    jq -e --slurpfile report "$directory/$report_file" '
      def identity: [.report_id,.scope,.evidence_kind,.start,.end,.policy_version];
      ($report|length) == 1 and (identity == ($report[0]|identity))' \
      "$directory/manifest.json" >/dev/null || fail 'Manifest identity differs from the archived report'
}

pack() {
    local report= output= predecessor= reason= source name sha bytes
    local files=()
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --report) report=${2:?}; shift 2 ;;
            --file) files+=("${2:?}"); shift 2 ;;
            --output) output=${2:?}; shift 2 ;;
            --predecessor-manifest-sha256) predecessor=${2:?}; shift 2 ;;
            --correction-reason) reason=${2:?}; shift 2 ;;
            *) fail 'Unknown pack argument' ;;
        esac
    done
    [[ -n "$report" && -n "$output" ]] || fail 'Report and output required'
    if [[ -n "$predecessor" || -n "$reason" ]]; then
        [[ "$predecessor" =~ ^[a-f0-9]{64}$ && -n "$reason" ]] || fail 'Correction requires predecessor SHA256 and reason'
    fi
    [[ ! -e "$output" && ! -L "$output" ]] || fail 'Evidence bundle already exists'
    if ((${#files[@]} > 0)); then files=("$report" "${files[@]}"); else files=("$report"); fi
    : > "$WORK/names"
    for source in "${files[@]}"; do
        name=$(basename "$source")
        safe_name "$name" || fail 'Unsafe or reserved evidence filename'
        [[ -f "$source" && ! -L "$source" ]] || fail 'Only explicit regular evidence files may be archived'
        case "$name" in *.json|*.jsonl|*.csv|*.prom) ;; *) fail 'Unsupported evidence file type' ;; esac
        printf '%s\n' "$name" >> "$WORK/names"
    done
    [[ $(sort "$WORK/names" | uniq | wc -l | tr -d ' ') == ${#files[@]} ]] || fail 'Duplicate evidence basenames'
    jq -se 'length == 1 and all(.[0]|[.report_id,.scope,.evidence_kind,.start,.end,.policy_version][];
      type == "string" and length > 0)' "$report" >/dev/null || fail 'Expected one report with complete identity'
    mkdir -p "$(dirname "$output")"
    mkdir -m 700 "$output"
    : > "$WORK/entries"
    for source in "${files[@]}"; do
        name=$(basename "$source")
        (set -o noclobber; cat "$source" > "$output/$name")
        sha=$(digest "$output/$name")
        bytes=$(size "$output/$name")
        jq -n --arg name "$name" --arg sha "$sha" --argjson bytes "$bytes" \
            '{name:$name,bytes:$bytes,sha256:$sha}' >> "$WORK/entries"
    done
    jq --slurpfile files "$WORK/entries" --arg report_file "$(basename "$report")" \
      --arg predecessor "$predecessor" --arg reason "$reason" '
      {schema_version:1,report_file:$report_file,report_id,scope,evidence_kind,start,end,policy_version,files:$files,
       retention_days_requested:400,retention_enforced:false,
       predecessor_manifest_sha256:(if $predecessor == "" then null else $predecessor end),
       correction_reason:(if $reason == "" then null else $reason end)}' "$output/$(basename "$report")" > "$output/manifest.json"
    verify "$output"
    echo 'Private evidence bundle created and verified.'
}

# AUTH_TOKEN remains in memory and reaches curl only through a private pipe.
# No redirects, provider URLs, direct S3 credentials, or automatic retries.
api() {
    local method="$1" path="$2" body="${3:-}" status
    local arguments=(--config - --silent --show-error --connect-timeout 10 --max-time 60
      --request "$method" --header 'X-MLFLOW-WORKSPACE: showback-reporting' --output "$WORK/api-body" --write-out '%{http_code}')
    [[ -z "${MLFLOW_CA_FILE:-}" ]] || arguments+=(--cacert "$MLFLOW_CA_FILE")
    [[ "${MLFLOW_INSECURE_SKIP_VERIFY:-false}" != true ]] || arguments+=(--insecure)
    if [[ -n "$body" ]]; then
        arguments+=(--data-binary "@$body")
        if [[ "$method" == PUT ]]; then arguments+=(--header 'Content-Type: application/octet-stream')
        else arguments+=(--header 'Content-Type: application/json'); fi
    fi
    status=$(printf 'header = "Authorization: Bearer %s"\n' "$AUTH_TOKEN" |
        curl "${arguments[@]}" "$TRACKING_BASE/api/$path") || fail 'MLflow transport failed'
    API_STATUS="$status"
}

upload() {
    local directory="$1" experiment run artifact name hash start
    verify "$directory"
    load_env
    check_oc_logged_in
    [[ "${MLFLOW_TRACKING_AUTH:-}" == kubernetes-namespaced && "${MLFLOW_WORKSPACE:-}" == showback-reporting ]] || fail 'Explicit namespaced MLflow workspace required'
    [[ "${MLFLOW_TRACKING_URI:-}" =~ ^https://[A-Za-z0-9.-]+(:[0-9]+)?(/[A-Za-z0-9._/-]*)?$ ]] || fail 'Explicit HTTPS MLflow tracking URI required'
    TRACKING_BASE=${MLFLOW_TRACKING_URI%/}
    [[ -n "${MLFLOW_TOKEN_PATH:-}" && -f "$MLFLOW_TOKEN_PATH" ]] || fail 'MLFLOW_TOKEN_PATH must name a private bearer-token file'
    AUTH_TOKEN=$(cat "$MLFLOW_TOKEN_PATH")
    [[ "$AUTH_TOKEN" =~ ^[A-Za-z0-9._~-]+$ ]] || fail 'Invalid bearer-token file'
    api GET '2.0/mlflow/experiments/get-by-name?experiment_name=showback-accounting'
    case "$API_STATUS" in
        200) experiment=$(jq -er '.experiment.experiment_id' "$WORK/api-body") ;;
        404)
            jq -e '.error_code == "RESOURCE_DOES_NOT_EXIST"' "$WORK/api-body" >/dev/null || fail 'Experiment lookup failed'
            jq -n '{name:"showback-accounting"}' > "$WORK/request.json"
            api POST 2.0/mlflow/experiments/create "$WORK/request.json"
            [[ "$API_STATUS" == 200 ]] || fail 'Experiment creation failed'
            experiment=$(jq -er '.experiment_id' "$WORK/api-body") ;;
        *) fail 'Experiment lookup failed' ;;
    esac
    [[ "$experiment" =~ ^[0-9]+$ ]] || fail 'Invalid experiment identity'
    hash=$(digest "$directory/manifest.json")
    start=$(($(date +%s) * 1000))
    jq --arg experiment "$experiment" --arg hash "$hash" --argjson start "$start" '
      {experiment_id:$experiment,start_time:$start,tags:[{key:"mlflow.runName",value:.report_id},
       {key:"showback.scope",value:.scope},{key:"showback.evidence_kind",value:.evidence_kind},
       {key:"showback.manifest_sha256",value:$hash},{key:"showback.policy_version",value:.policy_version}]}' \
      "$directory/manifest.json" > "$WORK/request.json"
    api POST 2.0/mlflow/runs/create "$WORK/request.json"
    [[ "$API_STATUS" == 200 ]] || fail 'Run creation failed; inspect MLflow before retrying'
    run=$(jq -er '.run.info.run_id' "$WORK/api-body")
    artifact=$(jq -er '.run.info.artifact_uri' "$WORK/api-body")
    [[ "$run" =~ ^[A-Za-z0-9_-]+$ ]] || fail 'Invalid run identity'
    [[ "$artifact" == mlflow-artifacts:/workspaces/showback-reporting/* ]] || fail 'Server did not return the expected proxied workspace artifact URI'
    artifact=${artifact#mlflow-artifacts:/}
    [[ "$artifact" =~ ^[A-Za-z0-9_./-]+$ ]] || fail 'Unsafe artifact URI'
    case "/$artifact/" in *'/../'*|*'/./'*|*'//'*) fail 'Unsafe artifact URI' ;; esac
    mkdir "$WORK/readback"
    jq -r '.files[].name' "$directory/manifest.json" > "$WORK/members"
    echo manifest.json >> "$WORK/members"
    while IFS= read -r name; do
        api PUT "2.0/mlflow-artifacts/artifacts/$artifact/evidence/$name" "$directory/$name"
        [[ "$API_STATUS" == 200 ]] || fail "Artifact upload failed for $name; run $run remains unfinished"
        api GET "2.0/mlflow-artifacts/artifacts/$artifact/evidence/$name"
        [[ "$API_STATUS" == 200 ]] || fail "Artifact readback failed for $name"
        cp "$WORK/api-body" "$WORK/readback/$name"
    done < "$WORK/members"
    bash "$SCRIPT_DIR/archive.sh" verify "$WORK/readback" >/dev/null
    [[ $(digest "$WORK/readback/manifest.json") == "$hash" ]] || fail 'Uploaded manifest differs on readback'
    jq -n --arg run "$run" --argjson end "$(($(date +%s) * 1000))" \
        '{run_id:$run,status:"FINISHED",end_time:$end}' > "$WORK/request.json"
    api POST 2.0/mlflow/runs/update "$WORK/request.json"
    [[ "$API_STATUS" == 200 ]] || fail "Readback passed but run $run was not marked FINISHED"
    unset AUTH_TOKEN
    printf 'MLflow run: %s (artifact readback verified; retention not automatically enforced)\n' "$run"
}

COMMAND=${1:-}
[[ $# -gt 0 ]] && shift
case "$COMMAND" in
    pack) pack "$@" ;;
    verify) [[ $# -eq 1 ]] || fail 'verify requires a directory'; verify "$1"; echo 'Evidence hashes verified.' ;;
    upload) [[ $# -eq 1 ]] || fail 'upload requires a directory'; upload "$1" ;;
    *) sed -n 's/^# Usage: //p' "$0" >&2; exit 1 ;;
esac
