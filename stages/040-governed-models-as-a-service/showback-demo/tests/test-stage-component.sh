#!/usr/bin/env bash
# Exercise the Stage 040 opt-in shell branches with synthetic API responses; never invokes a live transport.
# Usage: stages/040-governed-models-as-a-service/showback-demo/tests/test-stage-component.sh
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../../.." && pwd)"
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
fail() { echo "Stage component test: $*" >&2; exit 1; }
stage=stages/040-governed-models-as-a-service
mkdir -p "$work/repo/$stage" "$work/repo/scripts" "$work/bin"
cp "$REPO_ROOT/$stage/deploy.sh" "$REPO_ROOT/$stage/validate.sh" "$work/repo/$stage/"
cp "$REPO_ROOT/scripts/lib.sh" "$work/repo/scripts/"
kustomize build "$REPO_ROOT/gitops/stages/040-governed-models-as-a-service/040-showback-demo" |
    ruby -ryaml -rjson -e 'puts JSON.generate(YAML.load_stream(STDIN.read).compact)' >"$work/desired.json"
export SHOWBACK_CONTROL_DESIRED="$work/desired.json" SHOWBACK_CONTROL_LOG="$work/control.log"
export SHOWBACK_CONTROL_STATE=healthy
export RHOAI_EXPECTED_API_SERVER=unit.invalid GIT_REPO_URL=https://example.invalid/demo.git
export RHOAI_STAGE040_SHOWBACK_EXPECTED_REVISION=1111111111111111111111111111111111111111
cat >"$work/repo/scripts/stage-apps.sh" <<'SH'
#!/usr/bin/env bash
set -euo pipefail
printf '%s\n' "$*" >>"$SHOWBACK_CONTROL_LOG"
case "$1" in
    select) printf '%s\n' 1111111111111111111111111111111111111111 ;;
    preflight|apply|sync|wait) : ;;
    status) [[ "$SHOWBACK_CONTROL_STATE" != bad-app ]] ;;
    *) exit 97 ;;
esac
SH
cat >"$work/bin/oc" <<'SH'
#!/usr/bin/env bash
set -euo pipefail
[[ "${1:-}" == --request-timeout=* ]] && shift
case "${1:-}" in
    whoami)
        [[ "$SHOWBACK_CONTROL_STATE" != guard-failure ]] || exit 1
        [[ "${2:-}" == --show-server ]] && echo https://api.unit.invalid:6443 || echo synthetic-user
        ;;
    kustomize) ruby -rjson -ryaml -e 'JSON.parse(File.read(ARGV[0])).each { |d| puts YAML.dump(d) }' "$SHOWBACK_CONTROL_DESIRED" ;;
    get)
        kind=$2; name=${3:-}
        case "$kind" in
            namespace)
                [[ "$name" != showback-reporting ]] || exit 97
                echo '{"status":{"phase":"Active"}}'
                ;;
            crd) jq -n '{items:[range(4)|{status:{conditions:[{type:"Established",status:"True"}]}}]}' ;;
            clusterrole)
                [[ "$name" == edit && "$SHOWBACK_CONTROL_STATE" != missing-role ]] || exit 1
                jq -n --arg state "$SHOWBACK_CONTROL_STATE" '{rules:[{apiGroups:["mlflow.kubeflow.org"],
                  resources:["experiments"],verbs:(if $state=="incomplete-role" then ["get","list"]
                    else ["get","list","create","update","delete"] end)}]}'
                ;;
            applications.argoproj.io)
                [[ "$SHOWBACK_CONTROL_STATE" != discovery-failure ]] || exit 29
                [[ "$SHOWBACK_CONTROL_STATE" != absent ]] || exit 0
                echo application/040-showback-demo
                ;;
            pods)
                if [[ "$SHOWBACK_CONTROL_STATE" == lingering-pod ]]; then echo '{"items":[{}]}'
                else echo '{"items":[]}' ; fi
                ;;
            *)
                jq -ce --arg kind "${kind%%.*}" --arg name "$name" --arg state "$SHOWBACK_CONTROL_STATE" '
                  .[] | select(.kind==$kind and .metadata.name==$name) |
                  .metadata.annotations["argocd.argoproj.io/tracking-id"]=("040-showback-demo:"
                    + (if (.apiVersion|contains("/")) then (.apiVersion|split("/")[0]) else "" end)
                    + "/"+.kind+":"+(.metadata.namespace // "openshift-gitops")+"/"+.metadata.name) |
                  if .kind=="Deployment" then
                    if $state=="active-spec" then .spec.replicas=1
                    elif $state=="active-status" then .status.replicas=1
                    elif $state=="wrong-owner" then .metadata.annotations["argocd.argoproj.io/tracking-id"]="foreign"
                    else . end
                  elif .metadata.name=="showback-selected-report" and $state=="selected-report" then .data={unexpected:"report"}
                  elif .metadata.name=="showback-selected-report" and $state=="omitted-empty-data" then del(.data)
                  elif .kind=="RoleBinding" and $state=="wrong-role" then .roleRef.name="cluster-admin"
                  elif .kind=="RoleBinding" and $state=="wrong-subject" then .subjects[0].name="system:authenticated"
                  else . end' "$SHOWBACK_CONTROL_DESIRED"
                ;;
        esac
        ;;
    *) echo 'Unexpected synthetic oc call' >&2; exit 97 ;;
esac
SH
chmod +x "$work/bin/oc" "$work/repo/scripts/stage-apps.sh"
export PATH="$work/bin:$PATH"
component_validate() { bash "$work/repo/$stage/validate.sh" --component 040-showback-demo; }
component_deploy() { bash "$work/repo/$stage/deploy.sh" --component 040-showback-demo; }
component_validate >"$work/healthy.log" 2>&1 || { cat "$work/healthy.log" >&2; fail 'Healthy stopped component rejected'; }
export SHOWBACK_CONTROL_STATE=omitted-empty-data
component_validate >"$work/empty-data.log" 2>&1 || fail 'API omission of empty ConfigMap data rejected'
for state in bad-app active-spec active-status wrong-owner selected-report lingering-pod wrong-role wrong-subject; do
    export SHOWBACK_CONTROL_STATE=$state
    if component_validate >"$work/rejected.log" 2>&1; then fail "Validator accepted $state"; fi
done

for state in guard-failure missing-role incomplete-role; do
    export SHOWBACK_CONTROL_STATE=$state
    : >"$SHOWBACK_CONTROL_LOG"
    if component_deploy >"$work/rejected.log" 2>&1; then fail "Deploy accepted $state"; fi
    if grep -Eq '^(apply|sync|wait) ' "$SHOWBACK_CONTROL_LOG"; then fail "$state allowed a write"; fi
done
export SHOWBACK_CONTROL_STATE=healthy
: >"$SHOWBACK_CONTROL_LOG"
component_deploy >"$work/deploy.log" 2>&1 || { cat "$work/deploy.log" >&2; fail 'Explicit stopped deploy control flow failed'; }
cut -d ' ' -f 1 "$SHOWBACK_CONTROL_LOG" >"$work/sequence"
printf '%s\n' select preflight apply sync wait status >"$work/expected"
cmp -s "$work/sequence" "$work/expected" || fail 'Opt-in lifecycle order or scope changed'
if grep -E '^(preflight|apply|sync|wait|status) ' "$SHOWBACK_CONTROL_LOG" |
    grep -v -- '--app 040-showback-demo' >/dev/null; then fail 'Component operation widened to the stage'; fi

# Run the actual presence branch in isolation: a failed discovery must not skip the installed-component check.
{
    printf 'source "%s/scripts/lib.sh"\nTIMEOUT=10s\n' "$work/repo"
    printf 'showback_stopped() { echo yes; }\n'
    sed -n '/^showback_application=/,/^fi$/p' "$work/repo/$stage/validate.sh"
} >"$work/presence.sh"
[[ -s "$work/presence.sh" ]] || fail 'Optional presence branch missing'
export SHOWBACK_CONTROL_STATE=absent
bash "$work/presence.sh" >"$work/absent.log" 2>&1 || fail 'Absent optional component rejected'
[[ ! -s "$work/absent.log" ]] || fail 'Absent optional component was checked'
export SHOWBACK_CONTROL_STATE=healthy
bash "$work/presence.sh" >"$work/present.log" 2>&1 || fail 'Installed optional presence branch failed'
grep -q 'Installed optional showback bundle' "$work/present.log" || fail 'Installed component was skipped'
export SHOWBACK_CONTROL_STATE=discovery-failure
if bash "$work/presence.sh" >"$work/discovery.log" 2>&1; then fail 'Failed optional discovery was treated as absent'; fi
grep -q 'Cannot determine whether' "$work/discovery.log" || fail 'Discovery error was hidden'
printf '%s\n' 'PASS Stage 040 component branches: stopped ownership, residual workload/report rejection, guarded prerequisites and scoped sync order.'
