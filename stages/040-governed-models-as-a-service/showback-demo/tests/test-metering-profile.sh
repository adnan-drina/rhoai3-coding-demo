#!/usr/bin/env bash
# Exercise the real activation helper with synthetic API responses; no cluster or inference transport.
# Usage: stages/040-governed-models-as-a-service/showback-demo/tests/test-metering-profile.sh
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../../.." && pwd)"
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
fail() { printf 'Metering profile test: %s\n' "$*" >&2; exit 1; }
cmp -s "$SCRIPT_DIR/../native/provider-pricing.json" \
    "$REPO_ROOT/gitops/stages/040-governed-models-as-a-service/040-showback-demo/metering/provider-pricing.json" ||
    fail 'Runtime and reviewed pricing catalogs differ'
source_profile="$REPO_ROOT/gitops/stages/040-governed-models-as-a-service/040-showback-demo/metering/profile.yaml"
ruby -ryaml -rjson -e 'puts JSON.generate(YAML.load_stream(STDIN.read).compact)' < "$source_profile" |
    jq -e '.[0].data as $d | ($d["baseline.json"]|fromjson) as $b | ($d["profile.json"]|fromjson) as $p |
      $d.enabled=="true" and $b.kind=="PayloadProcessorConfig" and $p.kind==$b.kind
      and $p.apiVersion==$b.apiVersion and ($p.profiles|length)==1
      and ($p.plugins|map(select(.type!="external-metering-streaming")))==$b.plugins
      and ($p.profiles[0].plugins.request|map(.pluginRef))==["maas-headers-guard","stream-usage-enforcer",
        "model-provider-resolver","external-metering-streaming","api-translation","apikey-injection"]
      and $p.profiles[0].plugins.response==[{pluginRef:"external-metering-streaming"}]
      and any($p.plugins[]; .type=="external-metering-streaming" and .name=="external-metering-streaming"
        and .parameters.source=="maas-default-gateway" and .parameters.failOpen==true
        and .parameters.meteringURL=="http://showback-external-metering.redhat-ods-monitoring.svc:8080")' >/dev/null ||
    fail 'Auth, routing or chunk response source contract differs'
mkdir -p "$work/bin"
export PROFILE_TEST_WORK="$work" PROFILE_TEST_STATE=healthy
export RHOAI_EXPECTED_API_SERVER=unit.invalid

# These are isolated fixture profiles, not a publishable activation configuration.
jq -n '{apiVersion:"llm-d.ai/v1alpha1",kind:"PayloadProcessorConfig",
  plugins:[{type:"maas-headers-guard",name:"maas-headers-guard"},{type:"stream-usage-enforcer"},
    {type:"model-provider-resolver"},{type:"api-translation"},{type:"apikey-injection"}],
  profiles:[{name:"default",plugins:{request:[{pluginRef:"maas-headers-guard"},
    {pluginRef:"stream-usage-enforcer"},{pluginRef:"model-provider-resolver"},
    {pluginRef:"api-translation"},{pluginRef:"apikey-injection"}],response:[]}}]}' > "$work/baseline.json"
jq '.plugins += [{type:"external-metering-streaming",name:"external-metering-streaming",
    parameters:{meteringURL:"http://metering.invalid",failOpen:true}}] |
  .profiles[0].plugins.request |= .[0:3]+[{pluginRef:"external-metering-streaming"}]+.[3:] |
  .profiles[0].plugins.response=[{pluginRef:"external-metering-streaming"}]' "$work/baseline.json" > "$work/candidate.json"
jq -n --rawfile baseline "$work/baseline.json" --rawfile candidate "$work/candidate.json" \
  '[{kind:"ConfigMap",metadata:{name:"showback-external-metering-profile"},
    data:{enabled:"true","baseline.json":$baseline,"profile.json":$candidate}}]' > "$work/source.json"
jq -n --rawfile baseline "$work/baseline.json" '{kind:"ConfigMap",
  metadata:{name:"payload-processing-plugins",namespace:"openshift-ingress",resourceVersion:"10",
    annotations:{"opendatahub.io/managed":"false",preserve:"annotation"},labels:{preserve:"label"},
    ownerReferences:[{apiVersion:"maas.opendatahub.io/v1alpha1",kind:"Config",name:"default",uid:"fixture-owner"}]},
  data:{"custom-ipp-config.yaml":$baseline,"custom-pre-processing-ipp-config.yaml":"preserve pre-profile bytes\n",
    unrelated:"preserve data bytes\n"}}' > "$work/original.json"

cat > "$work/bin/oc" <<'SH'
#!/usr/bin/env bash
set -euo pipefail
[[ ${1:-} != --request-timeout=* ]] || shift
printf '%s\n' "$*" >> "$PROFILE_TEST_WORK/calls"
case "$1" in
  whoami)
    [[ $PROFILE_TEST_STATE != guard-failure ]] || exit 1
    [[ ${2:-} != --show-server ]] || { echo https://api.unit.invalid:6443; exit 0; }
    echo fixture-user ;;
  kustomize)
    ruby -rjson -ryaml -e 'JSON.parse(File.read(ARGV[0])).each { |d| puts YAML.dump(d) }' "$PROFILE_TEST_WORK/source.json" ;;
  get)
    [[ $2 == configmap && $3 == payload-processing-plugins ]] || exit 97
    cat "$PROFILE_TEST_WORK/live.json" ;;
  patch)
    [[ $2 == configmap && $3 == payload-processing-plugins ]] || exit 97
    [[ " $* " == *' --type=json '* && " $* " == *' --patch-file=/dev/stdin '* ]] || exit 97
    cat > "$PROFILE_TEST_WORK/patch.json"
    [[ $PROFILE_TEST_STATE != conflict ]] || exit 1
    jq -e --slurpfile live "$PROFILE_TEST_WORK/live.json" '
      length==2 and .[0]=={op:"test",path:"/metadata/resourceVersion",value:$live[0].metadata.resourceVersion}
      and .[1].op=="replace" and .[1].path=="/data/custom-ipp-config.yaml"' "$PROFILE_TEST_WORK/patch.json" >/dev/null
    jq --slurpfile patch "$PROFILE_TEST_WORK/patch.json" \
      '.data["custom-ipp-config.yaml"]=$patch[0][1].value | .metadata.resourceVersion="11"' \
      "$PROFILE_TEST_WORK/live.json" > "$PROFILE_TEST_WORK/updated.json"
    if [[ $PROFILE_TEST_STATE == collateral-change ]]; then
      jq '.data["custom-pre-processing-ipp-config.yaml"]="unexpected edit"' \
        "$PROFILE_TEST_WORK/updated.json" > "$PROFILE_TEST_WORK/live.json"
    else cp "$PROFILE_TEST_WORK/updated.json" "$PROFILE_TEST_WORK/live.json"; fi ;;
  rollout)
    [[ $2 == status || ( $2 == restart && $3 == deployment/payload-processing ) ]] || exit 97
    [[ $PROFILE_TEST_STATE != restart-failure || $2 != restart ]] || exit 1
    [[ $PROFILE_TEST_STATE != backend-unready || $3 != deployment/showback-external-metering ]] || exit 1 ;;
  *) echo 'Unexpected synthetic oc call' >&2; exit 97 ;;
esac
SH
chmod +x "$work/bin/oc"
export PATH="$work/bin:$PATH"
{
    printf 'set -euo pipefail\nREPO_ROOT=%q\nsource %q\n' "$REPO_ROOT" "$REPO_ROOT/scripts/lib.sh"
    sed -n '/^showback_metering_profile()/,/^}/p' "$REPO_ROOT/stages/040-governed-models-as-a-service/deploy.sh"
    printf 'load_env\ncheck_oc_logged_in\nshowback_metering_profile "$1"\n'
} > "$work/run.sh"
grep -q '^showback_metering_profile()' "$work/run.sh" || fail 'Activation helper missing'
reset_case() {
    cp "$work/original.json" "$work/live.json"
    : > "$work/calls"
    export PROFILE_TEST_STATE=healthy
}
no_writes() { ! grep -Eq '^(patch|rollout restart) ' "$work/calls"; }
run() { bash "$work/run.sh" "$1" > "$work/run.log" 2>&1; }

reset_case
run preflight || { cat "$work/run.log" >&2; fail 'Baseline preflight rejected'; }
no_writes || fail 'Preflight wrote or restarted'
run activate || { cat "$work/run.log" >&2; fail 'Reviewed activation rejected'; }
[[ $(grep -c '^patch ' "$work/calls") == 1 ]] || fail 'Activation did not patch exactly once'
[[ $(grep -c '^rollout restart deployment/payload-processing ' "$work/calls") == 1 ]] || fail 'Wrong restart scope'
jq -e --slurpfile before "$work/original.json" --slurpfile target "$work/candidate.json" '
  (.data["custom-ipp-config.yaml"]|fromjson)==$target[0] and
  del(.data["custom-ipp-config.yaml"],.metadata.resourceVersion)==
    ($before[0]|del(.data["custom-ipp-config.yaml"],.metadata.resourceVersion))' "$work/live.json" >/dev/null ||
  fail 'Metadata, pre-profile or unrelated data changed'
: > "$work/calls"
run activate || fail 'Idempotent activation rejected'
no_writes || fail 'Already-active profile patched or restarted'

for mutation in \
  '.metadata.annotations["opendatahub.io/managed"]="true"' \
  '.metadata.ownerReferences=[]' \
  '.data["custom-pre-processing-ipp-config.yaml"]=""' \
  '.data["custom-ipp-config.yaml"]="{unreviewed: true}"'; do
    reset_case
    jq "$mutation" "$work/original.json" > "$work/live.json"
    if run preflight; then fail "Preflight accepted $mutation"; fi
    no_writes || fail 'Rejected preflight allowed writes'
done
for state in guard-failure backend-unready conflict collateral-change; do
    reset_case
    export PROFILE_TEST_STATE=$state
    if run activate; then fail "Activation accepted $state"; fi
    ! grep -q '^rollout restart ' "$work/calls" || fail "$state restarted processing"
    if [[ $state == guard-failure || $state == backend-unready ]]; then
        no_writes || fail "$state allowed a patch"
    fi
done
cp "$work/source.json" "$work/reviewed-source.json"
for mutation in '.[0].data.enabled="unspecified"' '.[0].data["profile.json"]="invalid JSON"'; do
    reset_case
    jq "$mutation" "$work/reviewed-source.json" > "$work/source.json"
    if run preflight; then fail 'Preflight accepted invalid source activation data'; fi
    no_writes || fail 'Invalid source allowed writes'
done
cp "$work/reviewed-source.json" "$work/source.json"

# A patch followed by restart failure is reported as failure. The known profile
# remains persisted; an explicit operator restart is the documented recovery.
reset_case
export PROFILE_TEST_STATE=restart-failure
if run activate; then fail 'Activation hid a restart failure'; fi
jq -e --slurpfile expected "$work/candidate.json" \
    '(.data["custom-ipp-config.yaml"]|fromjson)==$expected[0]' "$work/live.json" >/dev/null ||
    fail 'Restart failure did not retain the known candidate'
export PROFILE_TEST_STATE=healthy
oc rollout restart deployment/payload-processing -n openshift-ingress > /dev/null
: > "$work/calls"
run activate || fail 'Readiness check after explicit restart recovery failed'
no_writes || fail 'Recovered matching profile restarted again'

# Reviewed disable restores only the previous default response profile.
reset_case
jq --rawfile candidate "$work/candidate.json" '.data["custom-ipp-config.yaml"]=$candidate' \
  "$work/original.json" > "$work/live.json"
jq '.[0].data.enabled="false"' "$work/source.json" > "$work/disabled.json"
cp "$work/disabled.json" "$work/source.json"
run activate || fail 'Reviewed disable rejected'
jq -e --slurpfile expected "$work/baseline.json" \
  '(.data["custom-ipp-config.yaml"]|fromjson)==$expected[0]' "$work/live.json" >/dev/null || fail 'Disable did not restore baseline'
: > "$work/calls"
run activate || fail 'Idempotent disable rejected'
no_writes || fail 'Already-disabled profile restarted'

reset_case
printf '[]\n' > "$work/source.json"
run activate || fail 'Legacy bundle without metering rejected'
no_writes || fail 'Legacy bundle activated metering'
printf '%s\n' 'PASS Metering profile: guarded preflight, exact delegated profile, preservation, atomic conflict, failure rejection and idempotent scoped restart.'
