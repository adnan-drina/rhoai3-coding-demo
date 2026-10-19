#!/usr/bin/env bash
# Offline capture regression: genuine-owner flow, exactly two bounded calls, cleanup, and unknown failed usage.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROBE="$SCRIPT_DIR/../external-probe.sh"
work=$(mktemp -d /private/tmp/test-showback-external.XXXXXX)
trap 'rm -rf "$work"' EXIT
mkdir "$work/bin" "$work/repo" "$work/repo/scripts"
cat > "$work/repo/scripts/lib.sh" <<'LIB'
load_env() { :; }
check_oc_logged_in() { printf '%s\n' "${KUBECONFIG:-platform}" >> "$PROBE_TEST_STATE/guards"; }
LIB
cat > "$work/bin/oc" <<'OC'
#!/usr/bin/env bash
set -euo pipefail
case "$*" in
  *'get gateway '*) printf '%s\n' '{"spec":{"listeners":[{"name":"api","hostname":"gateway.example.invalid"}]}}' ;;
  *'get externalmodels '*) printf '%s\n' '{"items":[{"metadata":{"name":"nemotron-3-ultra-550b-a55b"},"spec":{"externalProviderRefs":[{"ref":{"name":"nvidia"},"targetModel":"nvidia/nemotron-3-ultra-550b-a55b"}]}}]}' ;;
  *'whoami -t'*) printf '%s\n' 'synthetic-owner-token' ;;
  *whoami*) printf '%s\n' 'ai-admin' ;;
  *) exit 1 ;;
esac
OC
cat > "$work/bin/curl" <<'CURL'
#!/usr/bin/env bash
set -euo pipefail
method=GET out='' headers='' body='' url=''
cat >/dev/null
while (($#)); do
  case "$1" in
    --request) method=$2; shift 2 ;;
    --output) out=$2; shift 2 ;;
    --dump-header) headers=$2; shift 2 ;;
    --data-binary) body=${2#@}; shift 2 ;;
    --config|--connect-timeout|--max-time|--max-filesize|--write-out|--proto|--header) shift 2 ;;
    --silent|--show-error|--insecure) shift ;;
    https:*) url=$1; shift ;;
    *) exit 1 ;;
  esac
done
printf 'HTTP/1.1 200 OK\r\n' > "$headers"
status=200
case "$method $url" in
  'GET '*/v1/subscriptions) printf '%s\n' '[{"subscription_id_header":"personal-ai-admin"}]' > "$out" ;;
  'GET '*/v1/models) printf '%s\n' '{"data":[{"id":"nemotron-3-ultra-550b-a55b","ready":true}]}' > "$out" ;;
  'POST '*/v1/api-keys) printf '%s\n' '{"id":"fixture-key-id","key":"synthetic-maas-key"}' > "$out"; status=201 ;;
  'GET '*/v1/api-keys/fixture-key-id) printf '%s\n' '{"username":"ai-admin","subscription":"personal-ai-admin","status":"active"}' > "$out" ;;
  'DELETE '*/v1/api-keys/fixture-key-id) printf '{}\n' > "$out"; touch "$PROBE_TEST_STATE/revoked" ;;
  'POST '*/v1/chat/completions)
    jq -e '.max_tokens==128 and .stream==false and .chat_template_kwargs.enable_thinking==false' "$body" >/dev/null
    count=0; [[ ! -f "$PROBE_TEST_STATE/count" ]] || count=$(cat "$PROBE_TEST_STATE/count")
    count=$((count+1)); printf '%s\n' "$count" > "$PROBE_TEST_STATE/count"
    ((count<=2)) || exit 1
    if [[ "${PROBE_TEST_FAIL_SECOND:-false}" == true && "$count" == 2 ]]; then
      printf '%s\n' '{"error":{"message":"synthetic unavailable"}}' > "$out"; status=503
    else
      jq -n --arg id "fixture-receipt-$count" '{id:$id,model:"nvidia/nemotron-3-ultra-550b-a55b",
        choices:[{message:{content:"OK"}}],usage:{prompt_tokens:21,completion_tokens:2,total_tokens:23}}' > "$out"
    fi ;;
  *) exit 1 ;;
esac
printf '%s' "$status"
CURL
chmod +x "$work/bin/oc" "$work/bin/curl"
: > "$work/persona"
chmod 600 "$work/persona"
export SHOWBACK_REPO_ROOT="$work/repo" PATH="$work/bin:$PATH"
bash "$PROBE" | jq -e '.network_requests==0 and .inference_requests==2' >/dev/null
for mode in success partial; do
  mkdir "$work/$mode-state"
  export PROBE_TEST_STATE="$work/$mode-state" PROBE_TEST_FAIL_SECOND=false
  [[ "$mode" != partial ]] || PROBE_TEST_FAIL_SECOND=true
  bash "$PROBE" --execute --persona "$work/persona" --output "$work/$mode" >/dev/null
  [[ $(cat "$PROBE_TEST_STATE/count") == 2 && -f "$PROBE_TEST_STATE/revoked" ]]
  [[ $(sed -n '1p' "$PROBE_TEST_STATE/guards") == platform && $(sed -n '2p' "$PROBE_TEST_STATE/guards") == "$work/persona" ]]
  jq -e '.revoked==true' "$work/$mode/key-revocation.json" >/dev/null
  if [[ "$mode" == success ]]; then
    jq -e '(.receipts|length)==2 and all(.receipts[];.usage.total_tokens==23)' "$work/$mode/probe.json" >/dev/null
  else
    jq -e '.receipts[0].usage.total_tokens==23 and .receipts[1].http_status=="503" and .receipts[1].usage==null' \
      "$work/$mode/probe.json" >/dev/null
  fi
done
printf 'PASS: bounded external capture and cleanup (offline stubs; no network)\n'
