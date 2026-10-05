#!/usr/bin/env bash
# Reconcile native Stage040 desired state; runtime credentials remain outside Git.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
REPO_ROOT="$ROOT_DIR"
source "$ROOT_DIR/scripts/shared/lib.sh"
load_env
check_oc_logged_in
revision="${1:-${GIT_REPO_BRANCH:-}}"
[[ -n "$revision" ]] || { echo 'ERROR: select the reviewed published branch.' >&2; exit 1; }
export GIT_REPO_URL
remote_sha=$(git ls-remote "${GIT_REPO_URL:?Set GIT_REPO_URL}" "refs/heads/$revision" | awk '{print $1}')
[[ "$remote_sha" =~ ^[0-9a-f]{40}$ && "$remote_sha" == "$(git -C "$ROOT_DIR" rev-parse HEAD)" ]] || { echo 'ERROR: published revision differs from reviewed checkout.' >&2; exit 1; }
paths=(gitops/stages/040-governed-models-as-a-service gitops/argocd/app-of-apps/040-governed-models-as-a-service.yaml stages/040-governed-models-as-a-service scripts/shared)
[[ -z $(git -C "$ROOT_DIR" status --porcelain -- "${paths[@]}") ]] || { echo 'ERROR: publish all reviewed Stage040 source before deployment.' >&2; exit 1; }
state=$(python3 "$SCRIPT_DIR/preflight.py")
"$ROOT_DIR/stages/020-gpu-infrastructure-private-ai/validate.sh" --readiness
"$ROOT_DIR/scripts/platform/require-node-sizing.sh"
work=$(mktemp -d);trap 'rm -rf "$work"' EXIT
oc --request-timeout=10s get ingresscontroller default -n openshift-ingress-operator -o json > "$work/ingress.json"
ruby -ryaml -rjson -ruri -e '
a=YAML.load_file(ARGV[0]);a["spec"]["source"]["repoURL"]=ENV.fetch("GIT_REPO_URL");a["spec"]["source"]["targetRevision"]=ARGV[1]
domain=JSON.parse(File.read(ARGV[2])).dig("status","domain");abort "ERROR: native ingress domain is unavailable." unless domain && domain.match?(/\A[a-z0-9.-]+\z/)
patches=[]
["maas","qwen3-6-maas","qwen3-8-maas"].each_with_index{|host,i|patches << {"op"=>"replace","path"=>"/spec/listeners/#{i}/hostname","value"=>"#{host}.#{domain}"}}
a["spec"]["source"]["kustomize"]={"patches"=>[
 {"target"=>{"group"=>"gateway.networking.k8s.io","version"=>"v1","kind"=>"Gateway","name"=>"maas-default-gateway","namespace"=>"openshift-ingress"},"patch"=>JSON.generate(patches)},
 {"target"=>{"group"=>"maas.opendatahub.io","version"=>"v1alpha1","kind"=>"MaaSModelRef","name"=>"gpt-6-luna","namespace"=>"external-models"},"patch"=>JSON.generate([{ "op"=>"replace","path"=>"/spec/endpointOverride","value"=>"https://maas.#{domain}"}])}
]};provider=URI.parse(ENV.fetch("REDHAT_MODELS_BASE_URL"));abort "ERROR: approved Red Hat provider endpoint must be HTTPS." unless provider.scheme=="https" && provider.port==443 && ["","/","/v1","/v1/"].include?(provider.path) && provider.host && !provider.userinfo && !provider.query && !provider.fragment
 a["spec"]["source"]["kustomize"]["patches"] << {"target"=>{"group"=>"inference.opendatahub.io","version"=>"v1alpha1","kind"=>"ExternalProvider","name"=>"redhat-models","namespace"=>"external-models"},"patch"=>JSON.generate([{"op"=>"replace","path"=>"/spec/endpoint","value"=>provider.host}])}
 a["spec"]["source"]["kustomize"]["patches"] << {"target"=>{"group"=>"maas.opendatahub.io","version"=>"v1alpha1","kind"=>"MaaSModelRef","name"=>"minimax-m2","namespace"=>"external-models"},"patch"=>JSON.generate([{"op"=>"replace","path"=>"/spec/endpointOverride","value"=>"https://maas.#{domain}"}])};puts YAML.dump(a)' "$ROOT_DIR/gitops/argocd/app-of-apps/040-governed-models-as-a-service.yaml" "$remote_sha" "$work/ingress.json" > "$work/application.yaml"
# The first modifying action is this stage's own immutable Application.
oc --request-timeout=10s apply -f "$work/application.yaml"
"$SCRIPT_DIR/setup-provider-secret.sh"
RHOAI_STAGE040_PROVIDER_SECRET=redhat-models-provider-api-key "$SCRIPT_DIR/setup-provider-secret.sh"
"$SCRIPT_DIR/approve-operators.sh"
if [[ "$state" == fresh ]]; then
 "$SCRIPT_DIR/setup-database.sh" --fresh-database
else
 "$SCRIPT_DIR/setup-database.sh"
fi
for _ in $(seq 1 240); do
 if "$SCRIPT_DIR/validate.sh" --readiness; then
  echo 'PASS Native Stage040 readiness. Bounded real inference/stream/auth/metrics and user Studio visual acceptance are separate.'
  exit 0
 fi
 sleep 10
done
echo 'ERROR: Stage040 native readiness timed out; inspect exact operator/component conditions. No generated operands were patched.' >&2
exit 1
