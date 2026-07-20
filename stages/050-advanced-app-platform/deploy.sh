#!/usr/bin/env bash
# Stage 050: Advanced Application Platform — Deploy
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$REPO_ROOT/scripts/lib.sh"

STAGE_NAME="050-advanced-app-platform"

load_env
check_oc_logged_in

# Pre-flight: these values have no safe default — the stage deploys broken
# without them (Developer Hub crashes, pipelines never trigger). Fail here,
# before anything is applied, rather than leave a green-but-broken platform.
require_env GITHUB_TOKEN \
  "GitHub personal access token (classic, 'repo' scope) for owner ${GITHUB_OWNER:-<your GitHub org/user>}. Developer Hub's scaffolder uses it to read and publish the golden-path template repositories, and every build pipeline uses it to clone the application repo. If it is empty, the Developer Hub backend crashes on startup (scaffolder plugin) and pipelines cannot fetch source. Create at https://github.com/settings/tokens and put it in .env as GITHUB_TOKEN=..."
require_env GITHUB_WEBHOOK_SECRET \
  "Shared secret configured on the GitHub repository webhook. The pipeline EventListener validates each push's HMAC signature against it, so a commit only triggers a build when the signature matches. Without it, commit-triggered pipeline runs never fire. Use any long random string and set the same value on the repo webhook; put it in .env as GITHUB_WEBHOOK_SECRET=..."
assert_required_env

log_step "Stage 050: Advanced Application Platform"
log_info "Components: devspaces, pipelines, sonarqube, rhdh, migiq"

# --- Provision build-pipeline secrets from .env (never committed) ---
oc get namespace app-platform-build >/dev/null 2>&1 || oc create namespace app-platform-build

if [[ -n "${GITHUB_WEBHOOK_SECRET:-}" ]]; then
  oc create secret generic github-webhook-secret -n app-platform-build \
    --from-literal=token="${GITHUB_WEBHOOK_SECRET}" \
    --dry-run=client -o yaml | oc apply -f -
  log_info "github-webhook-secret provisioned"
else
  log_warn "GITHUB_WEBHOOK_SECRET not set in .env — webhook-triggered pipeline runs will fail until it is provisioned"
fi

if [[ -n "${GITHUB_TOKEN:-}" ]]; then
  oc create secret generic github-basic-auth -n app-platform-build \
    --from-literal=.git-credentials="https://token:${GITHUB_TOKEN}@github.com" \
    --from-literal=.gitconfig=$'[credential "https://github.com"]\n  helper = store' \
    --dry-run=client -o yaml | oc apply -f -
  log_info "github-basic-auth provisioned"
else
  # Empty secret keeps the PipelineRun workspace binding satisfied for public repos.
  oc get secret github-basic-auth -n app-platform-build >/dev/null 2>&1 || \
    oc create secret generic github-basic-auth -n app-platform-build \
      --from-literal=.git-credentials="" \
      --from-literal=.gitconfig=""
  log_info "GITHUB_TOKEN not set — github-basic-auth left empty (public repos only)"
fi

# Source-of-truth pipeline credentials live in app-platform-build; the
# project-provisioner CronJob copies them into every namespace labeled
# rhoai3.redhat.com/pipeline-project=true (each project runs its own
# pipeline instantiated from pipelines/project-pipeline).
if [[ -n "${IMAGE_REGISTRY:-}" && -n "${QUAY_ROBOT_USER:-}" && -n "${QUAY_ROBOT_TOKEN:-}" ]]; then
  REGISTRY_HOST="${IMAGE_REGISTRY%%/*}"
  for quay_secret in quay-push-secret quay-pull-secret; do
    oc create secret docker-registry "$quay_secret" -n app-platform-build \
      --docker-server="${REGISTRY_HOST}" \
      --docker-username="${QUAY_ROBOT_USER}" \
      --docker-password="${QUAY_ROBOT_TOKEN}" \
      --dry-run=client -o yaml | oc apply -f -
  done
  oc create configmap app-platform-build-config -n app-platform-build \
    --from-literal=IMAGE_REGISTRY="${IMAGE_REGISTRY}" \
    --dry-run=client -o yaml | oc apply -f -
  log_info "quay push/pull secrets + IMAGE_REGISTRY=${IMAGE_REGISTRY} provisioned (source)"
else
  # Empty secret keeps the PipelineRun workspace binding satisfied; the
  # pipeline falls back to the internal OpenShift registry.
  for quay_secret in quay-push-secret quay-pull-secret; do
    oc get secret "$quay_secret" -n app-platform-build >/dev/null 2>&1 || \
      oc create secret generic "$quay_secret" -n app-platform-build
  done
  log_info "IMAGE_REGISTRY/QUAY_* not set — pipelines use the internal registry"
fi

# --- RHDH GitHub integration (scaffolder templates publish to GitHub) ---
oc get namespace rhdh >/dev/null 2>&1 || oc create namespace rhdh
if [[ -n "${GITHUB_TOKEN:-}" ]]; then
  oc create secret generic rhdh-github -n rhdh \
    --from-literal=GITHUB_TOKEN="${GITHUB_TOKEN}" \
    --dry-run=client -o yaml | oc apply -f -
  log_info "rhdh-github secret provisioned (scaffolder + catalog access)"
else
  oc get secret rhdh-github -n rhdh >/dev/null 2>&1 || \
    oc create secret generic rhdh-github -n rhdh --from-literal=GITHUB_TOKEN=""
  log_warn "GITHUB_TOKEN not set — RHDH golden-path templates cannot publish repositories"
fi

apply_stage_app "$STAGE_NAME"

# --- Coolstore dev environment: seed build ---
# The demo starts from a DEPLOYED brownfield system: the coolstore
# component's Deployment pins :latest, which only exists after one
# successful pipeline run. Seed it here so a green PipelineRun and a
# running app exist before the first demo exercise.
COOLSTORE_REPO="coolstore-inventory-service"
COOLSTORE_REPO_URL="https://github.com/adnan-drina/${COOLSTORE_REPO}.git"

seed_coolstore() {
  log_step "Coolstore seed: golden-path topic, pipeline run, deployment"

  # 0. Provisioning label — the 050 Application ignores Namespace label diffs
  #    (ignoreDifferences + RespectIgnoreDifferences), so the label in
  #    namespace.yaml only lands when Argo first CREATES the namespace; a
  #    label added to an existing namespace never reaches the cluster via
  #    sync. Assert it here so the project-provisioner picks the namespace up.
  if oc get namespace coolstore-dev >/dev/null 2>&1; then
    oc label namespace coolstore-dev rhoai3.redhat.com/pipeline-project=true --overwrite >/dev/null
  fi

  # 1. Golden-path topic — the EventListener CEL filter only admits pushes
  #    from repos carrying it, so future coolstore pushes rebuild :latest.
  if [[ -n "${GITHUB_TOKEN:-}" ]]; then
    local topics
    topics=$(curl -fsS -H "Authorization: Bearer ${GITHUB_TOKEN}" \
      -H "Accept: application/vnd.github+json" \
      "https://api.github.com/repos/adnan-drina/${COOLSTORE_REPO}/topics" \
      | python3 -c "import sys,json; print(' '.join(json.load(sys.stdin).get('names',[])))" 2>/dev/null || echo "")
    if [[ " ${topics} " != *" rhoai3-golden-path "* ]]; then
      local names_json
      names_json=$(python3 -c "import json,sys; print(json.dumps({'names': sorted(set(sys.argv[1].split() + ['rhoai3-golden-path']))}))" "${topics}")
      curl -fsS -X PUT -H "Authorization: Bearer ${GITHUB_TOKEN}" \
        -H "Accept: application/vnd.github+json" \
        "https://api.github.com/repos/adnan-drina/${COOLSTORE_REPO}/topics" \
        -d "${names_json}" >/dev/null \
        && log_info "rhoai3-golden-path topic set on ${COOLSTORE_REPO}" \
        || log_warn "could not set repo topic — webhook pushes will not trigger builds"
    else
      log_info "rhoai3-golden-path topic already present on ${COOLSTORE_REPO}"
    fi
  else
    log_warn "GITHUB_TOKEN not set — skipping repo topic; set it so pushes trigger builds"
  fi

  # 2. Skip the seed only when the environment is running AND its own
  #    per-project pipeline has a green run (a deployment left over from an
  #    earlier pipeline generation is not enough — validate.sh checks both).
  local green_runs
  green_runs=$(oc get pipelinerun -n coolstore-dev \
    -l backstage.io/kubernetes-id=${COOLSTORE_REPO} \
    -o jsonpath='{range .items[*]}{.status.conditions[?(@.type=="Succeeded")].status}{"\n"}{end}' 2>/dev/null \
    | grep -c "True" || true)
  if [[ "$(oc get deployment coolstore-inventory-service -n coolstore-dev \
      -o jsonpath='{.status.availableReplicas}' 2>/dev/null)" == "1" && "${green_runs}" -ge 1 ]]; then
    log_info "coolstore-inventory-service already Available with a green pipeline run — skipping seed run"
    return 0
  fi

  # 3. Wait for Argo to materialize coolstore's own pipeline instance.
  log_info "Waiting for the coolstore-dev app-push pipeline (Argo sync)…"
  local i
  for i in $(seq 1 60); do
    oc get pipeline.tekton.dev app-push -n coolstore-dev >/dev/null 2>&1 \
      && oc get task.tekton.dev tag-latest -n coolstore-dev >/dev/null 2>&1 && break
    sleep 10
  done
  if ! oc get task.tekton.dev tag-latest -n coolstore-dev >/dev/null 2>&1; then
    log_warn "pipeline/tasks not present yet — re-run deploy.sh after the Application syncs"
    return 1
  fi

  # 3b. Distribute pipeline credentials into project namespaces NOW (the
  # CronJob reconciles every 2 minutes; the seed needs them immediately).
  log_info "Running project-provisioner to distribute pipeline credentials…"
  oc delete job project-provisioner-seed -n app-platform-build --ignore-not-found >/dev/null 2>&1
  if oc create job project-provisioner-seed -n app-platform-build \
      --from=cronjob/project-provisioner >/dev/null 2>&1; then
    oc wait job/project-provisioner-seed -n app-platform-build \
      --for=condition=Complete --timeout=180s >/dev/null \
      && log_info "project credentials distributed" \
      || log_warn "project-provisioner run did not complete — the CronJob retries every 2 minutes"
  else
    log_warn "could not trigger project-provisioner — the CronJob reconciles on schedule"
  fi

  # 4. Seed PipelineRun at the repo HEAD (labels feed the RHDH Tekton tab).
  local head_sha
  head_sha=$(curl -fsS ${GITHUB_TOKEN:+-H "Authorization: Bearer ${GITHUB_TOKEN}"} \
    -H "Accept: application/vnd.github+json" \
    "https://api.github.com/repos/adnan-drina/${COOLSTORE_REPO}/commits/main" \
    | python3 -c "import sys,json; print(json.load(sys.stdin)['sha'])")
  log_info "Seeding pipeline run for ${COOLSTORE_REPO}@${head_sha:0:7}"

  local run_name
  run_name=$(oc create -f - -o jsonpath='{.metadata.name}' <<EOF
apiVersion: tekton.dev/v1
kind: PipelineRun
metadata:
  generateName: ${COOLSTORE_REPO}-seed-
  namespace: coolstore-dev
  labels:
    backstage.io/kubernetes-id: ${COOLSTORE_REPO}
    app.kubernetes.io/name: ${COOLSTORE_REPO}
spec:
  pipelineRef:
    name: app-push
  params:
    - name: repo-url
      value: ${COOLSTORE_REPO_URL}
    - name: repo-name
      value: ${COOLSTORE_REPO}
    - name: revision
      value: ${head_sha}
  workspaces:
    - name: source
      volumeClaimTemplate:
        spec:
          accessModes: [ReadWriteOnce]
          resources:
            requests:
              storage: 1Gi
    - name: basic-auth
      secret:
        secretName: github-basic-auth
    - name: dockerconfig
      secret:
        secretName: quay-push-secret
    - name: maven-cache
      persistentVolumeClaim:
        claimName: maven-cache
EOF
)
  log_info "PipelineRun ${run_name} created — waiting for it to succeed (cold cache can take ~15 min)"
  if ! oc wait pipelinerun "${run_name}" -n coolstore-dev \
      --for=condition=Succeeded --timeout=1800s; then
    log_error "Seed PipelineRun did not succeed. Inspect it with:"
    echo "  tkn pipelinerun logs ${run_name} -n coolstore-dev  # or the Pipelines console view"
    return 1
  fi
  log_info "Seed PipelineRun succeeded — :latest image published"

  # 5. Roll the deployment onto the fresh image and wait for readiness.
  oc rollout restart deployment/coolstore-inventory-service -n coolstore-dev
  oc rollout status deployment/coolstore-inventory-service -n coolstore-dev --timeout=300s
  log_info "coolstore-inventory-service is running: https://$(oc get route coolstore-inventory-service -n coolstore-dev -o jsonpath='{.spec.host}')"
}

seed_coolstore || log_warn "Coolstore seed incomplete — see messages above; re-run deploy.sh to retry"

log_info "ArgoCD handles orchestration via sync waves (per component):"
log_info "  devspaces:   operator -> CheCluster -> workspaces -> MaaS keys"
log_info "  pipelines:   Pipelines/TAS operators -> build namespace -> pipeline + triggers"
log_info "  sonarqube:   db secret hook -> PostgreSQL -> SonarQube -> PostSync gate/token job"
log_info "  rhdh:        operator -> config -> Backstage CR -> PostSync OIDC"
log_info "  migiq:       MTA operator -> Tackle -> Lightspeed/MaaS hooks"
log_info "RHDH OIDC brokers through the migiq MTA Keycloak; PostSync jobs wait, so"
log_info "ordering resolves within this one Application."
echo ""
log_info "Monitor progress:"
echo "  oc get application ${STAGE_NAME} -n openshift-gitops -w"
echo "  oc get csv -n openshift-operators | grep -E 'pipelines|rhtas'"
echo "  oc get checluster devspaces -n openshift-devspaces"
echo "  oc get pods -n sonarqube"
echo "  oc get pods -n rhdh"
echo "  oc get tackle mta -n openshift-mta"
echo ""
log_info "After deploy:"
echo "  oc get route -n rhdh                     # Developer Hub"
echo "  oc get route sonarqube -n sonarqube      # SonarQube"
echo "  oc get route app-platform-listener -n app-platform-build  # webhook URL"
echo ""
