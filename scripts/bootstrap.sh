#!/usr/bin/env bash
# Bootstrap OpenShift GitOps for RHOAI demo
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$REPO_ROOT/scripts/lib.sh"

load_env
check_oc_logged_in

# Auto-detect repo URL from git remote (supports forks)
GIT_REPO_URL=$(git -C "$REPO_ROOT" remote get-url origin 2>/dev/null || echo "https://github.com/adnan-drina/rhoai3-coding-demo.git")
# Convert SSH URLs (git@github.com:user/repo.git) to HTTPS for ArgoCD
if [[ "$GIT_REPO_URL" == git@* ]]; then
    GIT_REPO_URL=$(echo "$GIT_REPO_URL" | sed 's|git@github.com:|https://github.com/|')
fi
GIT_REPO_URL="${GIT_REPO_URL%.git}.git"
log_info "Repository: $GIT_REPO_URL"

# Update all ArgoCD Applications to use the detected repo URL
if [[ "$GIT_REPO_URL" != "https://github.com/adnan-drina/rhoai3-coding-demo.git" ]]; then
    log_step "Updating ArgoCD Applications for fork: $GIT_REPO_URL"
    if [[ "$(uname)" == "Darwin" ]]; then
        sed -i '' "s|https://github.com/adnan-drina/rhoai3-coding-demo.git|${GIT_REPO_URL}|g" \
            "$REPO_ROOT"/gitops/argocd/app-of-apps/step-*.yaml
    else
        sed -i "s|https://github.com/adnan-drina/rhoai3-coding-demo.git|${GIT_REPO_URL}|g" \
            "$REPO_ROOT"/gitops/argocd/app-of-apps/step-*.yaml
    fi
    log_success "Updated $(ls "$REPO_ROOT"/gitops/argocd/app-of-apps/step-*.yaml | wc -l | tr -d ' ') Application files"
fi

log_step "Installing OpenShift GitOps operator"

cat <<EOF | oc apply -f -
apiVersion: operators.coreos.com/v1alpha1
kind: Subscription
metadata:
  name: openshift-gitops-operator
  namespace: openshift-operators
spec:
  channel: gitops-1.15
  name: openshift-gitops-operator
  source: redhat-operators
  sourceNamespace: openshift-marketplace
EOF

log_info "Waiting for GitOps operator..."
sleep 30
until oc get namespace openshift-gitops &>/dev/null; do sleep 5; done

log_step "Configuring Argo CD RBAC"

cat <<EOF | oc apply -f -
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: openshift-gitops-cluster-admin
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: ClusterRole
  name: cluster-admin
subjects:
- kind: ServiceAccount
  name: openshift-gitops-argocd-application-controller
  namespace: openshift-gitops
EOF

log_step "Configuring resource tracking method"

until oc get argocd openshift-gitops -n openshift-gitops &>/dev/null; do sleep 5; done
oc patch argocd openshift-gitops -n openshift-gitops --type merge \
    -p '{"spec":{"resourceTrackingMethod":"annotation"}}' 2>/dev/null \
    && log_success "Resource tracking set to annotation (GitOps 1.19 default)" \
    || log_warn "Could not patch ArgoCD tracking method (may not be ready yet)"

log_step "Configuring custom resource health checks"

# PVC: WaitForFirstConsumer PVCs stay Pending until a pod mounts them.
# ISVC: ArgoCD default health check misreads KServe condition format.
# TrustyAIService: ArgoCD has no built-in health check for this CRD.
oc patch argocd openshift-gitops -n openshift-gitops --type merge -p '{
  "spec": {
    "resourceHealthChecks": [
      {
        "group": "",
        "kind": "PersistentVolumeClaim",
        "check": "hs = {}\nif obj.status ~= nil and obj.status.phase ~= nil then\n  if obj.status.phase == \"Pending\" then\n    hs.status = \"Healthy\"\n    hs.message = \"Waiting for first consumer\"\n  elseif obj.status.phase == \"Bound\" then\n    hs.status = \"Healthy\"\n    hs.message = obj.status.phase\n  else\n    hs.status = \"Progressing\"\n    hs.message = obj.status.phase\n  end\nelse\n  hs.status = \"Progressing\"\n  hs.message = \"Waiting for PVC status\"\nend\nreturn hs"
      },
      {
        "group": "serving.kserve.io",
        "kind": "InferenceService",
        "check": "hs = {}\nif obj.status ~= nil and obj.status.conditions ~= nil then\n  for _, c in ipairs(obj.status.conditions) do\n    if c.type == \"Ready\" then\n      if c.status == \"True\" then\n        hs.status = \"Healthy\"\n        hs.message = \"Ready\"\n      elseif c.status == \"False\" then\n        hs.status = \"Degraded\"\n        hs.message = c.message or \"Not ready\"\n      else\n        hs.status = \"Progressing\"\n        hs.message = c.message or \"Waiting\"\n      end\n      return hs\n    end\n  end\nend\nhs.status = \"Progressing\"\nhs.message = \"Waiting for conditions\"\nreturn hs"
      },
      {
        "group": "trustyai.opendatahub.io",
        "kind": "TrustyAIService",
        "check": "hs = {}\nif obj.status ~= nil and obj.status.conditions ~= nil then\n  for _, c in ipairs(obj.status.conditions) do\n    if c.type == \"Available\" then\n      if c.status == \"True\" then\n        hs.status = \"Healthy\"\n        hs.message = c.reason or \"Available\"\n      elseif c.status == \"False\" then\n        hs.status = \"Degraded\"\n        hs.message = c.message or \"Not available\"\n      else\n        hs.status = \"Progressing\"\n        hs.message = c.message or \"Waiting\"\n      end\n      return hs\n    end\n  end\nend\nhs.status = \"Progressing\"\nhs.message = \"Waiting for conditions\"\nreturn hs"
      }
    ]
  }
}' 2>/dev/null \
    && log_success "PVC + InferenceService + TrustyAIService health checks configured" \
    || log_warn "Could not configure health checks"

log_step "Creating Argo CD project"

cat <<EOF | oc apply -f -
apiVersion: argoproj.io/v1alpha1
kind: AppProject
metadata:
  name: rhoai-demo
  namespace: openshift-gitops
spec:
  destinations:
  - namespace: '*'
    server: https://kubernetes.default.svc
  clusterResourceWhitelist:
  - group: '*'
    kind: '*'
  sourceRepos:
  - '*'
EOF

log_success "Bootstrap complete"
log_info "Argo CD: $(oc get route openshift-gitops-server -n openshift-gitops -o jsonpath='{.spec.host}' 2>/dev/null || echo 'loading...')"
