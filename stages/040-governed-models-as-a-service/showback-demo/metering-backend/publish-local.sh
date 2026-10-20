#!/usr/bin/env bash
# Publish a locally validated build to this demo's existing internal registry. Creates only the declared
# ImageStream when absent, with its exact GitOps tracking identity; refuses foreign ownership. Does not deploy.
# Usage: publish-local.sh --build BUILD_EVIDENCE_DIR --connection LOCAL_PODMAN_CONNECTION
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../../.." && pwd)"
source "$REPO_ROOT/scripts/lib.sh"
build='' connection=''
while (( $# )); do
    case "$1" in
        --build) build=${2:?}; shift 2 ;;
        --connection) connection=${2:?}; shift 2 ;;
        *) sed -n 's/^# Usage: //p' "$0" >&2; exit 1 ;;
    esac
done
[[ -f "$build/build.json" && -f "$build/image.json" && -n "$connection" ]] || {
    log_error 'A successful build evidence directory and local Podman connection are required'; exit 1;
}
[[ ! -e "$build/publication.json" ]] || { log_error 'Publication evidence already exists'; exit 1; }
engine=(podman --connection "$connection")
podman system connection list --format json | jq -e --arg name "$connection" \
    'any(.[]; .Name == $name and (.URI | test("^ssh://[^@]+@(127\\.0\\.0\\.1|localhost):")))' >/dev/null || {
    log_error 'Only an explicit local Podman connection is allowed'; exit 1;
}
jq -e '.exit_code == 0 and .platform == "linux/amd64" and .published == false' "$build/build.json" >/dev/null
image=$(jq -r '.local_image' "$build/build.json")
patch_sha=$(jq -r '.patch_sha256' "$build/build.json")
"${engine[@]}" image inspect "$image" | jq -e --slurpfile expected "$build/image.json" \
    --arg patch "$patch_sha" '.[0] | .Id == $expected[0].Id and .Architecture == "amd64" and .Os == "linux"
        and .Labels["io.showback.patch.sha256"] == $patch' >/dev/null || {
    log_error 'Local image differs from its build evidence'; exit 1;
}
load_env
check_oc_logged_in
oc whoami
oc project
oc get configs.imageregistry.operator.openshift.io cluster -o json | jq -e \
    '.spec.managementState == "Managed" and .spec.defaultRoute == true
      and .spec.storage.emptyDir == null' >/dev/null || { log_error 'Persistent managed registry required'; exit 1; }
namespace=redhat-ods-monitoring
name=showback-external-metering
tracking="040-showback-demo:image.openshift.io/ImageStream:$namespace/$name"
existing=$(oc --request-timeout=10s get imagestream "$name" -n "$namespace" --ignore-not-found -o json)
if [[ -n "$existing" ]]; then
    jq -e --arg tracking "$tracking" '.metadata.annotations["argocd.argoproj.io/tracking-id"] == $tracking
      and (.metadata.ownerReferences // [] | length) == 0 and .metadata.deletionTimestamp == null' \
      <<<"$existing" >/dev/null || { log_error 'ImageStream has not been adopted by this component'; exit 1; }
else
    # The image build precedes the first workload deployment; bootstrap precisely this declared artifact holder.
    oc kustomize "$REPO_ROOT/gitops/stages/040-governed-models-as-a-service/040-showback-demo/metering" |
      ruby -ryaml -rjson -e 'puts JSON.generate(YAML.load_stream(STDIN.read).compact)' |
      jq --arg tracking "$tracking" '.[] | select(.kind == "ImageStream"
        and .metadata.name == "showback-external-metering" and .metadata.namespace == "redhat-ods-monitoring")
        | .metadata.annotations["argocd.argoproj.io/tracking-id"] = $tracking' | oc create -f - >/dev/null
fi
route=$(oc get route default-route -n openshift-image-registry -o jsonpath='{.spec.host}')
[[ -n "$route" ]] || { log_error 'Registry route is unavailable'; exit 1; }
umask 077
private=$(mktemp -d)
trap 'rm -rf "$private"' EXIT
oc whoami -t | "${engine[@]}" login --tls-verify=false --username=showback-publisher \
    --password-stdin --authfile "$private/auth.json" "$route" >/dev/null
"${engine[@]}" push --tls-verify=false --authfile "$private/auth.json" --digestfile "$private/digest" \
    "$image" "docker://$route/$namespace/$name:patch-${patch_sha:0:12}" >"$build/push.log" 2>&1
digest=$(cat "$private/digest")
[[ "$digest" =~ ^sha256:[a-f0-9]{64}$ ]] || { log_error 'Registry returned an invalid digest'; exit 1; }
oc get imagestreamtag "$name:patch-${patch_sha:0:12}" -n "$namespace" -o json |
    jq -e --arg digest "$digest" '.image.metadata.name == $digest' >/dev/null || {
    log_error 'Published image digest failed registry readback'; exit 1;
}
reference="image-registry.openshift-image-registry.svc:5000/$namespace/$name@$digest"
jq -n --arg image "$reference" --arg patch "$patch_sha" --arg source "$(jq -r '.source_commit' "$build/build.json")" \
    --arg published "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
    '{image:$image,patch_sha256:$patch,source_commit:$source,published_at:$published,registry_digest_verified:true}' \
    >"$build/publication.json"
printf 'Published and verified: %s\n' "$reference"
