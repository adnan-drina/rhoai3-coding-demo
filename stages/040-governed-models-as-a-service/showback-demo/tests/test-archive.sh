#!/usr/bin/env bash
# Offline hash/immutability checks and an intercepted curl/oc MLflow REST contract test; no network.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE="$(cd "$SCRIPT_DIR/.." && pwd)"
REPO_ROOT="$(cd "$BASE/../../.." && pwd)"
source "$REPO_ROOT/scripts/lib.sh"
WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT
fail() { log_error "$*"; exit 1; }
reject() { if "$@" >"$WORK/rejected.log" 2>&1; then fail 'Expected archive rejection'; fi; }
jq -n '{report_id:"synthetic-archive-test",scope:"demo",evidence_kind:"synthetic_fixture",
  start:"2026-10-16T00:00:00Z",end:"2026-10-16T00:04:00Z",policy_version:"v1"}' > "$WORK/report.json"
bash "$BASE/archive.sh" pack --report "$WORK/report.json" --output "$WORK/bundle"
bash "$BASE/archive.sh" verify "$WORK/bundle"
jq -e '.retention_days_requested==400 and .retention_enforced==false' "$WORK/bundle/manifest.json" >/dev/null
mode=$(stat -f %Lp "$WORK/bundle/report.json" 2>/dev/null || stat -c %a "$WORK/bundle/report.json")
[[ "$mode" == 600 ]] || fail 'Evidence permissions'
reject bash "$BASE/archive.sh" pack --report "$WORK/report.json" --output "$WORK/bundle"
reject bash "$BASE/archive.sh" pack --report "$WORK/report.json" --output "$WORK/correction" --correction-reason 'missing hash'
ln -s "$WORK/report.json" "$WORK/link.json"
reject bash "$BASE/archive.sh" pack --report "$WORK/report.json" --file "$WORK/link.json" --output "$WORK/symlink"
cp -R "$WORK/bundle" "$WORK/tampered"
printf '{}\n' > "$WORK/tampered/report.json"
reject bash "$BASE/archive.sh" verify "$WORK/tampered"
cp -R "$WORK/bundle" "$WORK/extra"
touch "$WORK/extra/.hidden"
reject bash "$BASE/archive.sh" verify "$WORK/extra"
cp -R "$WORK/bundle" "$WORK/mislabeled"
jq '.report_id="mislabeled-report"' "$WORK/mislabeled/manifest.json" > "$WORK/changed-manifest.json"
cp "$WORK/changed-manifest.json" "$WORK/mislabeled/manifest.json"
reject bash "$BASE/archive.sh" verify "$WORK/mislabeled"
cp -R "$WORK/bundle" "$WORK/invalid-correction"
jq '.correction_reason="missing predecessor"' "$WORK/invalid-correction/manifest.json" > "$WORK/changed-manifest.json"
cp "$WORK/changed-manifest.json" "$WORK/invalid-correction/manifest.json"
reject bash "$BASE/archive.sh" verify "$WORK/invalid-correction"
cat "$WORK/report.json" "$WORK/report.json" > "$WORK/multiple.json"
reject bash "$BASE/archive.sh" pack --report "$WORK/multiple.json" --output "$WORK/multiple-bundle"
hash=$(shasum -a 256 "$WORK/bundle/manifest.json" | awk '{print $1}')
bash "$BASE/archive.sh" pack --report "$WORK/report.json" --output "$WORK/correction" \
  --predecessor-manifest-sha256 "$hash" --correction-reason 'Corrected source evidence'
jq -e --arg hash "$hash" '.predecessor_manifest_sha256==$hash and .correction_reason=="Corrected source evidence"' \
  "$WORK/correction/manifest.json" >/dev/null

mkdir "$WORK/bin" "$WORK/mock"
cat > "$WORK/bin/oc" <<'SH'
#!/usr/bin/env bash
case "$*" in
  *whoami*--show-server*) echo https://api.archive-test.invalid:6443 ;;
  *whoami*) echo archive-test-user ;;
  *) echo 'Unexpected cluster operation' >&2; exit 1 ;;
esac
SH
cat > "$WORK/bin/curl" <<'SH'
#!/usr/bin/env bash
set -euo pipefail
method= output= body= url= config=
for argument in "$@"; do
    [[ "$argument" != *synthetic-bearer-secret* ]] || { echo 'Bearer leaked to argv' >&2; exit 90; }
done
while [[ $# -gt 0 ]]; do
    case "$1" in
      --request) method=$2; shift 2 ;;
      --output) output=$2; shift 2 ;;
      --data-binary) body=${2#@}; shift 2 ;;
      --config) [[ $2 == - ]] || exit 91; config=$(cat); shift 2 ;;
      --header|--connect-timeout|--max-time|--write-out|--cacert) shift 2 ;;
      --silent|--show-error|--insecure) shift ;;
      https://mlflow.archive-test.invalid/*) url=$1; shift ;;
      *) echo 'Unexpected curl contract' >&2; exit 92 ;;
    esac
done
[[ "$config" == 'header = "Authorization: Bearer synthetic-bearer-secret"' ]] || exit 93
printf '%s %s\n' "$method" "$url" >> "$MOCK_DIR/requests"
status=200
case "$method $url" in
  GET*experiments/get-by-name*) printf '{"experiment":{"experiment_id":"42"}}' > "$output" ;;
  POST*runs/create)
    jq -e '.experiment_id=="42" and any(.tags[];.key=="showback.manifest_sha256")' "$body" >/dev/null
    if [[ "${MOCK_MODE:-}" == foreign ]]; then
      printf '{"run":{"info":{"run_id":"run1","artifact_uri":"mlflow-artifacts://foreign.invalid/store"}}}' > "$output"
    elif [[ "${MOCK_MODE:-}" == traversal ]]; then
      printf '{"run":{"info":{"run_id":"run1","artifact_uri":"mlflow-artifacts:/workspaces/showback-reporting/.."}}}' > "$output"
    else
      printf '{"run":{"info":{"run_id":"run1","artifact_uri":"mlflow-artifacts:/workspaces/showback-reporting/42/run1/artifacts"}}}' > "$output"
    fi ;;
  PUT*mlflow-artifacts/artifacts/*)
    name=${url##*/}
    cp "$body" "$MOCK_DIR/$name"
    printf '{}' > "$output" ;;
  GET*mlflow-artifacts/artifacts/*)
    name=${url##*/}
    if [[ "${MOCK_MODE:-}" == corrupt && "$name" == report.json ]]; then printf '{}' > "$output"
    else cp "$MOCK_DIR/$name" "$output"; fi ;;
  POST*runs/update)
    jq -e '.run_id=="run1" and .status=="FINISHED"' "$body" >/dev/null
    touch "$MOCK_DIR/finished"
    printf '{}' > "$output" ;;
  *) exit 94 ;;
esac
printf '%s' "$status"
SH
chmod +x "$WORK/bin/oc" "$WORK/bin/curl"
printf 'synthetic-bearer-secret\n' > "$WORK/token"
export PATH="$WORK/bin:$PATH"
export MOCK_DIR="$WORK/mock"
export RHOAI_EXPECTED_API_SERVER=api.archive-test.invalid
export MLFLOW_TRACKING_AUTH=kubernetes-namespaced
export MLFLOW_WORKSPACE=showback-reporting
export MLFLOW_TRACKING_URI=https://mlflow.archive-test.invalid
export MLFLOW_TOKEN_PATH="$WORK/token"
bash "$BASE/archive.sh" upload "$WORK/bundle" > "$WORK/upload.log"
[[ -f "$MOCK_DIR/finished" ]] || fail 'Run not completed after readback'
cmp "$WORK/bundle/report.json" "$MOCK_DIR/report.json" || fail 'Uploaded bytes differ'
if grep -q synthetic-bearer-secret "$WORK/upload.log" "$MOCK_DIR/requests"; then fail 'Bearer exposed'; fi
rm "$MOCK_DIR/finished"
export MOCK_MODE=corrupt
reject bash "$BASE/archive.sh" upload "$WORK/bundle"
[[ ! -f "$MOCK_DIR/finished" ]] || fail 'Corrupt readback marked successful'
export MOCK_MODE=foreign
reject bash "$BASE/archive.sh" upload "$WORK/bundle"
[[ ! -f "$MOCK_DIR/finished" ]] || fail 'Foreign artifact destination accepted'
export MOCK_MODE=traversal
reject bash "$BASE/archive.sh" upload "$WORK/bundle"
[[ ! -f "$MOCK_DIR/finished" ]] || fail 'Parent-path artifact destination accepted'
echo 'PASS archive shell contracts (private hashes, immutability, correction, mocked upload/readback, secret handling)'
