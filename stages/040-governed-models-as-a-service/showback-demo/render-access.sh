#!/usr/bin/env bash
# Preview detached MaaS candidates. --write regenerates six local files, safely on rerun; never applies them.
# Usage: render-access.sh [--scenario FILE] [--check DIR | --write DIR]
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
source "$REPO_ROOT/scripts/lib.sh"

scenario="$SCRIPT_DIR/scenario.json"
mode=preview
directory=""
usage() {
    printf '%s\n' 'Usage: render-access.sh [--scenario FILE] [--check DIR | --write DIR]' \
        'Default: JSON preview array, no files or cluster calls. --write emits one YAML resource per file.'
}
while (($#)); do
    case "$1" in
        --scenario|--check|--write)
            (($# >= 2)) || { usage >&2; exit 2; }
            if [[ "$1" == --scenario ]]; then
                scenario="$2"
            else
                [[ "$mode" == preview ]] || { usage >&2; exit 2; }
                mode="${1#--}"
                directory="$2"
            fi
            shift 2
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            usage >&2
            exit 2
            ;;
    esac
done
command -v jq >/dev/null
command -v ruby >/dev/null

# Validate the agreed identities and four allowed model paths before emitting or writing anything.
resources="$(jq -ce '
  def positive: type=="number" and .==floor and .>0;
  def name: type=="string" and test("^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?$");
  . as $s |
  if .schema_version!=1 or (.teams|keys)!=["engineering","marketing","support"] or
    (.models|keys)!=["mistral-small4-119b","qwen3-8-27b"] or
    (.teams.engineering.models|keys)!=["qwen3-8-27b"] or
    (.teams.marketing.models|keys)!=["mistral-small4-119b"] or
    (.teams.support.models|keys)!=["mistral-small4-119b","qwen3-8-27b"] or
    ([.teams[].subscription]|unique|length)!=3 or ([.teams[].user]|unique|length)!=3 or
    (.organization_id|type)!="string" or (.organization_id|length)==0 or
    (all(.models[];.namespace|name)|not) then error("invalid scenario or access matrix") else . end |
  [.teams|to_entries[]|.key as $team|.value as $t |
    if ($t.subscription|name) and ($t.user|name) then . else error("invalid identity") end |
    [$t.models|to_entries[]|
      if ((.value.token_limit|positive) and (.value.window|test("^[1-9][0-9]{0,3}[smh]$"))) then
        {name:.key,namespace:$s.models[.key].namespace,
         tokenRateLimits:[{limit:.value.token_limit,window:.value.window}]}
      else error("invalid quota") end] as $refs |
    {organizationId:$s.organization_id,costCenter:$team,
     labels:{environment:"demo",provider:"governed-models",modelSet:"showback-demo"}} as $metering |
    ["MaaSSubscription","MaaSAuthPolicy"][] as $kind |
    ($kind=="MaaSSubscription") as $subscription |
    {apiVersion:"maas.opendatahub.io/v1alpha1",kind:$kind,
     metadata:{name:$t.subscription,namespace:"models-as-a-service",labels:{
       "app.kubernetes.io/name":$t.subscription,"app.kubernetes.io/part-of":"maas",
       "app.kubernetes.io/component":(if $subscription then "maas-subscription" else "maas-auth-policy" end),
       "app.kubernetes.io/managed-by":"argocd","demo.rhoai.io/stage":"040","demo.rhoai.io/team":$team}},
     spec:(if $subscription then
       {owner:{users:[$t.user]},modelRefs:$refs,priority:100,tokenMetadata:$metering}
     else {subjects:{users:[$t.user]},modelRefs:[$refs[]|{name,namespace}],meteringMetadata:$metering} end)}]
' "$scenario")" || exit 2

if [[ "$mode" == preview ]]; then
    printf '%s\n' "$resources" | jq .
    exit 0
fi
if [[ "$mode" == write ]]; then
    mkdir -p "$directory"
elif [[ ! -d "$directory" ]]; then
    printf '%s\n' 'Access manifest directory does not exist.' >&2
    exit 1
fi

while IFS= read -r resource; do
    filename="$(printf '%s' "$resource" | jq -r '
      "team-"+.metadata.labels["demo.rhoai.io/team"]+
      (if .kind=="MaaSSubscription" then "-subscription.yaml" else "-auth-policy.yaml" end)')"
    rendered="$(printf '%s' "$resource" | ruby -rjson -ryaml -e 'puts YAML.dump(JSON.parse(STDIN.read))')"
    if [[ "$mode" == write ]]; then
        printf '%s\n' "$rendered" > "$directory/$filename"
    elif ! cmp -s <(printf '%s\n' "$rendered") "$directory/$filename"; then
        printf 'Detached access manifest differs from scenario: %s\n' "$filename" >&2
        exit 1
    fi
done < <(printf '%s' "$resources" | jq -c '.[]')
