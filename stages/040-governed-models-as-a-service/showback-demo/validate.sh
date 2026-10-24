#!/usr/bin/env bash
# Offline checks for the showback demo: script syntax, the rendered component (team access matrix, opt-in dedicated
# model, live dashboards, metering) and the metering-profile activation helper. Contacts no cluster.
# Usage: stages/040-governed-models-as-a-service/showback-demo/validate.sh
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
source "$REPO_ROOT/scripts/lib.sh"
COMPONENT="$REPO_ROOT/gitops/stages/040-governed-models-as-a-service/040-showback-demo"
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT

syntax=pass
for script in "$SCRIPT_DIR"/*.sh "$SCRIPT_DIR"/tests/*.sh; do
    bash -n "$script" || syntax="syntax error in ${script#"$REPO_ROOT"/}"
done
record 'Shell scripts parse' "$syntax"

kustomize build "$COMPONENT" | yaml_json > "$work/bundle.json"
# The opt-in dedicated offer (Marketing's Mistral) is rendered separately; the access matrix covers both.
kustomize build "$COMPONENT/dedicated" | yaml_json > "$work/dedicated.json"
jq -s 'add' "$work/bundle.json" "$work/dedicated.json" > "$work/all.json"
# Engineering and Support share Qwen; Marketing owns Mistral; Support alone reaches the external models.
if jq -e '
    def refs($kind; $name): [.[] | select(.kind == $kind and .metadata.name == $name) | .spec.modelRefs[] |
        .namespace + "/" + .name] | sort;
    refs("MaaSSubscription"; "team-engineering") == ["internal-models/qwen3-8-27b"]
    and refs("MaaSSubscription"; "team-marketing") == ["internal-models/mistral-small4-119b"]
    and refs("MaaSSubscription"; "team-support") == ["external-models/claude-sonnet-5-5", "external-models/gpt-6-luna",
        "external-models/nemotron-3-ultra-550b-a55b", "internal-models/qwen3-8-27b"]
    and (. as $b | all("team-engineering", "team-marketing", "team-support"; . as $t |
        ($b | refs("MaaSSubscription"; $t)) == ($b | refs("MaaSAuthPolicy"; $t))))
    and all(.[] | select(.kind == "MaaSSubscription"); .spec.owner.users == ["showback-" + (.metadata.name | ltrimstr("team-"))])
' "$work/all.json" >/dev/null; then
    record 'Team access matrix: shared Qwen, dedicated Mistral, external for Support' pass
else record 'Team access matrix: shared Qwen, dedicated Mistral, external for Support' 'Subscriptions or policies differ'; fi

if jq -e '[.[] | select(.kind == "LLMInferenceService")] as $m | ($m | length) == 1
    and $m[0].metadata.name == "mistral-small4-119b" and $m[0].spec.replicas == 0
    and any(.[]; .kind == "MaaSModelRef" and .metadata.name == "mistral-small4-119b")' "$work/dedicated.json" >/dev/null; then
    record 'Opt-in dedicated Mistral model is declared and stopped in Git' pass
else record 'Opt-in dedicated Mistral model is declared and stopped in Git' 'Model or reference differs'; fi

# A second local model on the shared api listener breaks Qwen routing on RHOAI 3.5.2, so the default installs none.
if jq -e 'all(.[]; .kind != "LLMInferenceService" and .kind != "MaaSModelRef")
    and all(.[]; .metadata.name != "team-marketing")' "$work/bundle.json" >/dev/null; then
    record 'Default bundle installs no second local model' pass
else record 'Default bundle installs no second local model' 'The default bundle declares a local model or the dedicated offer'; fi

# Every dashboard panel is laid out, reads the RHOAI datasource and no financial number comes from a static report.
if jq -e '[.[] | select(.kind == "PersesDashboard")] as $d
    | ($d | map(.metadata.name) | sort) == ["dashboard-offer-dedicated-private-admin",
        "dashboard-offer-external-model-admin", "dashboard-offer-shared-private-admin"]
    and all($d[]; .spec.config as $c
        | ([$c.layouts[].spec.items[].content["$ref"] | ltrimstr("#/spec/panels/")] | sort) == ($c.panels | keys | sort)
        and all($c.panels[].spec.queries[]; .spec.plugin.spec.datasource.name == "data-science-prometheus-datasource"
            and (.spec.plugin.spec.query | test("showback_selected_report|service_[a-z_]+_cents") | not)))' \
    "$work/bundle.json" >/dev/null; then
    record 'Three live offer dashboards: every panel laid out and queried from the RHOAI datasource' pass
else record 'Three live offer dashboards: every panel laid out and queried from the RHOAI datasource' 'Dashboard differs'; fi

# The offer catalog drives every private-offer panel: each offered model needs a worker price, shared models a tariff,
# dedicated models a sponsor, and every dedicated model must exist in this bundle.
if jq -e '[.[] | select(.kind == "PrometheusRule" and .metadata.name == "showback-offer-catalog") | .spec.groups[].rules[]] as $r
    | ($r | map(select(.record == "showback_offer_info") | .labels)) as $info | ($info | length) > 0
    and all($info[]; . as $i | any($r[]; .record == "showback_offer_worker_usd_per_hour" and .labels.model == $i.model)
        and (.sponsor | type == "string" and length > 0)
        and (if .offer == "shared" then any($r[]; .record == "showback_offer_tariff_usd_per_million" and .labels.model == $i.model)
             else .offer == "dedicated" end))
    and ([$info[] | select(.offer == "dedicated") | .model] - [.[] | select(.kind == "LLMInferenceService") | .metadata.name]
        | length) == 0' "$work/all.json" >/dev/null; then
    record 'Offer catalog: every offered model has an offering, sponsor and price' pass
else record 'Offer catalog: every offered model has an offering, sponsor and price' 'Catalog incomplete'; fi

# A shared commitment names a team subscription on that shared model whose hourly token limit can carry it in
# 168 working hours; otherwise the team could not use what it pays for.
if jq -e '. as $b | [.[] | select(.kind == "PrometheusRule" and .metadata.name == "showback-offer-catalog")
        | .spec.groups[].rules[] | select(.record == "showback_offer_commitment_tokens")] as $c | ($c | length) > 0
    and all($c[]; (.expr | ltrimstr("vector(") | rtrimstr(")") | tonumber) as $tokens | .labels as $l
        | any($b[]; .kind == "MaaSSubscription" and .metadata.name == $l.subscription
            and any(.spec.modelRefs[]; .name == $l.model and any(.tokenRateLimits[]; .window == "1h" and .limit * 168 >= $tokens))))' \
    "$work/bundle.json" >/dev/null; then
    record 'Shared commitments fit their subscriptions and hourly token limits' pass
else record 'Shared commitments fit their subscriptions and hourly token limits' 'Commitment exceeds or misses its subscription'; fi

if jq -e '[.[] | select(.metadata.labels["app.kubernetes.io/component"] == "external-metering")] as $m
    | ([$m[] | select(.kind == "Deployment") | .metadata.name] | sort) == ["showback-external-metering", "showback-external-metering-db"]
    # The database image is digest-pinned; the backend is the in-cluster build of a pinned commit on pinned bases.
    and all($m[] | select(.kind == "Deployment" and .metadata.name == "showback-external-metering-db");
        all(.spec.template.spec.containers[]; .image | test("@sha256:[a-f0-9]{64}$")))
    and all($m[] | select(.kind == "Deployment" and .metadata.name == "showback-external-metering");
        all(.spec.template.spec.containers[]; .image
            == "image-registry.openshift-image-registry.svc:5000/redhat-ods-monitoring/showback-external-metering:continuous")
        and (.metadata.annotations["image.openshift.io/triggers"] | fromjson
            | any(.[]; .from == {kind: "ImageStreamTag", name: "showback-external-metering:continuous"})))
    and any($m[]; .kind == "BuildConfig" and (.spec.source.git.ref | test("^[a-f0-9]{40}$"))
        and .spec.output.to == {kind: "ImageStreamTag", name: "showback-external-metering:continuous"}
        and ([.spec.source.dockerfile | splits("\n") | select(startswith("FROM "))] as $from
            | ($from | length) == 3 and all($from[]; test("@sha256:[a-f0-9]{64}( AS [a-z]+)?$"))))
    and any($m[]; .kind == "PersistentVolumeClaim" and .metadata.annotations["argocd.argoproj.io/sync-options"] == "Prune=false,Delete=false")
    and any($m[]; .kind == "ConfigMap" and .metadata.name == "showback-external-metering-profile" and (.data.enabled | IN("true", "false")))' \
    "$work/bundle.json" >/dev/null; then
    record 'External metering: pinned backend build, retained database, explicit profile' pass
else record 'External metering: pinned backend build, retained database, explicit profile' 'Metering bundle differs'; fi

if bash "$SCRIPT_DIR/tests/test-metering-profile.sh" > "$work/profile.log" 2>&1; then
    record 'Metering profile activation helper (mocked cluster)' pass
else record 'Metering profile activation helper (mocked cluster)' "$(tail -1 "$work/profile.log")"; fi

echo "Offline only: no cluster, model or provider was contacted."
validation_summary
