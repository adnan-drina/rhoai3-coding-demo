#!/usr/bin/env bash
# Read-only: each sandbox bucket claim is Bound and its dashboard connection Secret maps the claim's bucket,
# endpoint and credentials, with the ownership and metadata the dashboard needs. Credential values are compared,
# never printed. Authenticated S3 operations and workbench consumption are separate acceptance.
# Usage: stages/010-openshift-ai-platform-foundation/validate-sandbox-storage.sh
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$REPO_ROOT/scripts/shared/validate-lib.sh"

read_json() { oc --request-timeout=10s get "$@" -n demo-sandbox -o json; }
yes_no() { jq -e "$@" >/dev/null && echo yes || echo no; }

for pair in rhoai-models:Models rhoai-workbench:Workbench; do
    claim=${pair%%:*}
    display=${pair#*:}
    obc=$(read_json obc "$claim")
    bucket=$(read_json configmap "$claim")
    credentials=$(read_json secret "$claim")
    connection=$(read_json secret "$claim-connection")
    obc_uid=$(jq -r '.metadata.uid' <<<"$obc")

    bound() { yes_no '.status.phase == "Bound"' <<<"$obc"; }
    tracked() {
        jq -s -e 'all(.[]; .metadata.annotations["argocd.argoproj.io/tracking-id"] // "" | startswith("010-sandbox-storage:"))' \
            <<<"$obc$connection" >/dev/null && echo yes || echo no
    }
    owned_by_claim() {
        jq -s -e --arg uid "$obc_uid" \
            'all(.[]; any(.metadata.ownerReferences[]?; .kind == "ObjectBucketClaim" and .uid == $uid))' \
            <<<"$bucket$credentials" >/dev/null && echo yes || echo no
    }
    bucket_config() {
        yes_no --arg claim "$claim" \
            '.data.BUCKET_NAME == $claim and .data.BUCKET_PORT == "443" and (.data.BUCKET_HOST // "") != ""' <<<"$bucket"
    }
    # Compares the claim's generated keys with the connection's, inside jq, so no value reaches the shell.
    credentials_match() {
        jq -n -e --argjson s "$credentials" --argjson t "$connection" \
            'all("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY"; ($s.data[.] // "") != "" and $t.data[.] == $s.data[.])' \
            >/dev/null && echo yes || echo no
    }
    connection_target() {
        jq -n -e --argjson b "$bucket" --argjson t "$connection" --arg claim "$claim" \
            '($t.data | map_values(@base64d)) as $d
            | $d.AWS_S3_BUCKET == $claim
            and $d.AWS_S3_ENDPOINT == "https://" + $b.data.BUCKET_HOST + ":443"
            and $d.AWS_DEFAULT_REGION == ($b.data.BUCKET_REGION // "us-east-1" | if . == "" then "us-east-1" else . end)' \
            >/dev/null && echo yes || echo no
    }
    connection_metadata() {
        yes_no --arg display "$display" '.metadata as $m
            | $m.annotations["opendatahub.io/connection-type-protocol"] == "s3"
            and $m.annotations["openshift.io/display-name"] == $display
            and $m.labels["opendatahub.io/dashboard"] == "true"
            and $m.labels["opendatahub.io/managed"] != "true"' <<<"$connection"
    }
    # The connection's values come from the claim at runtime; Git (last-applied) must not declare any data.
    no_declared_data() {
        yes_no '(.metadata.annotations["kubectl.kubernetes.io/last-applied-configuration"] // "{}" | fromjson)
            | ((.data // {}) | length) == 0 and ((.stringData // {}) | length) == 0' <<<"$connection"
    }

    check "$display: claim $claim Bound" bound yes
    check "$display: claim and connection tracked by 010-sandbox-storage" tracked yes
    check "$display: bucket ConfigMap and credential Secret owned by the claim" owned_by_claim yes
    check "$display: bucket name, host and port" bucket_config yes
    check "$display: connection carries the claim's access key and secret key" credentials_match yes
    check "$display: connection bucket, endpoint and region match the claim" connection_target yes
    check "$display: connection type s3, display name, dashboard label, not dashboard-managed" connection_metadata yes
    check "$display: Git declares no credential data for the connection" no_declared_data yes
done
echo "Scope: configuration only; authenticated S3 operations and workbench consumption are separate acceptance."
validation_summary
