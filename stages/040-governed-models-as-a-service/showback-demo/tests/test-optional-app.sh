#!/usr/bin/env bash
# Offline regression for optional component selection and status. All cluster responses/writes are synthetic.
# Usage: stages/040-governed-models-as-a-service/showback-demo/tests/test-optional-app.sh
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../../.." && pwd)"
ENGINE="$REPO_ROOT/scripts/stage-apps.sh"
source "$REPO_ROOT/scripts/lib.sh"
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
fail() { echo "Optional Application test: $*" >&2; exit 1; }
reject() { if "$@" >"$work/rejected.log" 2>&1; then fail "Expected rejection: $*"; fi; }
mkdir -p "$work/repo/gitops/applications" "$work/bin"
for name in 040-maas-platform 040-showback-demo; do
    cp "$REPO_ROOT/gitops/applications/$name.yaml" "$work/repo/gitops/applications/"
done
export SHOWBACK_ENGINE_FIXTURE="$work/repo"
export SHOWBACK_ENGINE_CALLS="$work/calls.jsonl"
export SHOWBACK_ENGINE_REVISION=1111111111111111111111111111111111111111
export SHOWBACK_ENGINE_STATE=absent

# No invocation reaches oc. Only the exact synthetic API shapes this test needs are accepted.
cat >"$work/bin/oc" <<'SH'
#!/usr/bin/env bash
set -euo pipefail
[[ "${1:-}" == --request-timeout=* ]] && shift
case "${1:-}" in
    get)
        [[ $# == 8 && "$2" == applications.argoproj.io && "$4" == -n && "$5" == openshift-gitops \
            && "$6" == --ignore-not-found && "$7" == -o && "$8" == json ]] || exit 97
        name=$3
        [[ "$name" != 040-showback-demo || "$SHOWBACK_ENGINE_STATE" != discovery-failure ]] || exit 29
        [[ "$name" != 040-showback-demo || "$SHOWBACK_ENGINE_STATE" != absent ]] || exit 0
        ruby -ryaml -rjson -e 'puts JSON.generate(YAML.load_file(ARGV[0]))' \
            "$SHOWBACK_ENGINE_FIXTURE/gitops/applications/$name.yaml" |
            jq --arg rev "$SHOWBACK_ENGINE_REVISION" --arg state "$SHOWBACK_ENGINE_STATE" '
              .spec.source.repoURL="https://example.invalid/demo.git" | .spec.source.targetRevision=$rev |
              .status={sync:{status:"Synced",revision:$rev},health:{status:"Healthy"},operationState:{
                phase:"Succeeded",syncResult:{revision:$rev,source:{path:.spec.source.path}}}} |
              if .metadata.name=="040-showback-demo" then
                if $state=="unhealthy" then .status.health.status="Degraded"
                elif $state=="out-of-sync" then .status.sync.status="OutOfSync"
                elif $state=="wrong-source" then .spec.source.path="gitops/stages/040-unrelated"
                elif $state=="wrong-revision" then .status.sync.revision="2222222222222222222222222222222222222222"
                elif $state=="automated" then .spec.syncPolicy.automated={prune:true,selfHeal:true}
                else . end
              else . end'
        ;;
    apply)
        [[ $# == 3 && "$2" == -f && "$3" == - ]] || exit 97
        jq -c '{action:"apply",object:.}' >>"$SHOWBACK_ENGINE_CALLS"
        ;;
    *) printf 'Rejected synthetic oc call\n' >&2; exit 97 ;;
esac
SH
chmod +x "$work/bin/oc"
export PATH="$work/bin:$PATH"
engine() { REPO_ROOT="$work/repo" bash "$ENGINE" "$@"; }

[[ $(engine names 040) == 040-maas-platform ]] || fail 'Default names changed'
engine names 040 --all >"$work/all-names"
[[ $(wc -l <"$work/all-names" | tr -d ' ') == 2 ]] || fail 'Optional app missing from --all'
grep -qx 040-showback-demo "$work/all-names" || fail 'Optional app missing from inventory'
engine applications 040 --revision "$SHOWBACK_ENGINE_REVISION" --repo-url https://example.invalid/demo.git >"$work/apps.json"
jq -e '.items|length==1 and .[0].metadata.name=="040-maas-platform"' "$work/apps.json" >/dev/null ||
    fail 'Default Application generation activated optional component'
engine deploy 040 --revision "$SHOWBACK_ENGINE_REVISION" --repo-url https://example.invalid/demo.git --no-wait >"$work/deploy.log"
jq -se 'length==1 and .[0].action=="apply" and .[0].object.metadata.name=="040-maas-platform"' \
    "$SHOWBACK_ENGINE_CALLS" >/dev/null || fail 'Default deploy touched optional component'

engine status 040 >"$work/absent.log"
grep -q '^SKIP *040-showback-demo .*not activated' "$work/absent.log" || fail 'Absent optional app not visibly skipped'
if grep -q '^OK *040-showback-demo' "$work/absent.log"; then fail 'Absent optional app reported healthy'; fi
reject engine status 040 --app 040-showback-demo
grep -q missing "$work/rejected.log" || fail 'Explicit absent status did not require presence'
reject engine status 040 --app 040-unknown
export SHOWBACK_ENGINE_STATE=discovery-failure
reject engine status 040
if grep -q '^SKIP *040-showback-demo' "$work/rejected.log"; then fail 'Discovery failure became an absent optional app'; fi
grep -q 'Application read failed' "$work/rejected.log" || fail 'Optional discovery failure was not reported'

export SHOWBACK_ENGINE_STATE=healthy
engine status 040 --app 040-showback-demo --revision "$SHOWBACK_ENGINE_REVISION" >"$work/present.log"
grep -q '^OK *040-showback-demo' "$work/present.log" || fail 'Healthy activated optional app rejected'
if grep -q 040-maas-platform "$work/present.log"; then fail 'Explicit status included unselected component'; fi
reject engine status 040 --app 040-showback-demo --revision 2222222222222222222222222222222222222222
grep -q 'reviewed immutable commit' "$work/rejected.log" || fail 'Explicit expected revision was ignored'
for state in unhealthy out-of-sync wrong-source wrong-revision automated; do
    export SHOWBACK_ENGINE_STATE=$state
    reject engine status 040
    grep -q '^FAIL *040-showback-demo' "$work/rejected.log" || fail "Installed $state optional app escaped validation"
done

: >"$SHOWBACK_ENGINE_CALLS"
engine apply 040 --app 040-showback-demo --revision "$SHOWBACK_ENGINE_REVISION" \
    --repo-url https://example.invalid/demo.git
jq -se --arg rev "$SHOWBACK_ENGINE_REVISION" 'length==1 and .[0].object.metadata.name=="040-showback-demo"
    and .[0].object.spec.source.targetRevision==$rev and .[0].object.spec.syncPolicy.automated==null
    and .[0].object.operation==null' "$SHOWBACK_ENGINE_CALLS" >/dev/null || fail 'Explicit preparation started or mispinned app'

cp "$work/repo/gitops/applications/040-showback-demo.yaml" "$work/optional.yaml"
for mutation in \
    '.spec.syncPolicy.automated={prune:true,selfHeal:true}' \
    '.metadata.annotations["demo.rhoai.io/deploy-order"]="99" | del(.metadata.annotations["demo.rhoai.io/deploy-script"])' \
    '.metadata.annotations["demo.rhoai.io/optional"]="false"'; do
    ruby -ryaml -rjson -e 'puts JSON.generate(YAML.load_file(ARGV[0]))' "$work/optional.yaml" |
        jq "$mutation" >"$work/repo/gitops/applications/040-showback-demo.yaml"
    reject engine names 040 --all
done
printf '%s\n' 'PASS optional Application: default exclusion, manual preparation, absent skip, explicit presence and installed drift failures.'
