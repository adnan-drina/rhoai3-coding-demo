#!/usr/bin/env bash
# Stage 010 validation: OpenShift GitOps, the component Applications, ODF, RHOAI and its observability stack, access,
# the sandbox bucket connections, the console Perses integration, and native metrics and trace round trips.
# Read-only (local port-forwards only); credential values are compared inside jq, never printed or passed as arguments.
# --login-personas signs the demo personas in again (browser; OAuth tokens expire) into their own kubeconfigs from .env
# (RHOAI_ADMIN_KUBECONFIG, RHOAI_DEVELOPER_KUBECONFIG), never your default kubeconfig; --private-window prints the login
# URL instead of opening the browser, so an existing ai-admin browser session is not reused.
# Usage: stages/010-openshift-ai-platform-foundation/validate.sh [--component 010-sandbox-storage|010-console-observability | --login-personas [admin|developer] [--private-window]]
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
ROOT_DIR="$REPO_ROOT"
source "$REPO_ROOT/scripts/lib.sh"
COMPONENT="" LOGIN="" OPEN_BROWSER=true
while [[ $# -gt 0 ]]; do
  case "$1" in
    --component) COMPONENT=${2:?}; shift 2 ;;
    --login-personas) LOGIN="admin developer"; [[ "${2:-}" == admin || "${2:-}" == developer ]] && { LOGIN=$2; shift; }; shift ;;
    --private-window) OPEN_BROWSER=false; shift ;;
    *) sed -n 's/^# Usage: //p' "$0" >&2; exit 1 ;;
  esac
done
load_env
check_oc_logged_in

# ── Persona sessions (interactive) ────────────────────────────────────────────
login_personas() {
  local server persona var kubeconfig user actual rc=0
  server="$(oc --request-timeout=10s whoami --show-server)"
  for persona in $LOGIN; do
    if [[ "$persona" == admin ]]; then var=ADMIN; kubeconfig="${RHOAI_ADMIN_KUBECONFIG:-}"; user="${RHOAI_ADMIN_USER:-}"
    else var=DEVELOPER; kubeconfig="${RHOAI_DEVELOPER_KUBECONFIG:-}"; user="${RHOAI_DEVELOPER_USER:-}"; fi
    kubeconfig="${kubeconfig/#\~/$HOME}"
    [[ -n "$kubeconfig" && -n "$user" ]] || { log_error "set RHOAI_${var}_KUBECONFIG and RHOAI_${var}_USER in .env"; rc=1; continue; }
    mkdir -p "$(dirname "$kubeconfig")"
    if [[ ! -s "$kubeconfig" ]]; then
      # A new persona kubeconfig carries the guarded context's cluster trust (server plus CA data or its TLS setting),
      # never its user credentials, so the browser login reaches the same API server.
      (umask 077; oc config view --minify --raw -o json | jq '{apiVersion: "v1", kind: "Config",
        clusters: [{name: "persona-cluster", cluster: .clusters[0].cluster}], users: [],
        contexts: [{name: "persona", context: {cluster: "persona-cluster"}}], "current-context": "persona"}' >"$kubeconfig")
    fi
    if [[ "$OPEN_BROWSER" == true ]]; then
      echo "── Sign in as ${user} in the browser window that opens (session saved to ${kubeconfig})"
      oc login --web --kubeconfig "$kubeconfig" "$server" >/dev/null
    else
      echo "── Open the URL below in a private browser window and sign in as ${user} (session saved to ${kubeconfig})"
      oc login --web --auto-open-browser=false --kubeconfig "$kubeconfig" "$server"
    fi
    chmod 600 "$kubeconfig"
    actual="$(oc --kubeconfig "$kubeconfig" --request-timeout=10s whoami 2>/dev/null || true)"
    if [[ "$actual" == "$user" ]]; then
      log_success "${persona}: logged in as ${actual}"
    else
      rm -f "$kubeconfig"  # never leave another user's session in this persona's kubeconfig
      log_error "${persona}: logged in as '${actual:-nobody}', expected ${user}; run again with --private-window"
      rc=1
    fi
  done
  return "$rc"
}
if [[ -n "$LOGIN" ]]; then login_personas; exit; fi

# ── Core foundation ───────────────────────────────────────────────────────────
validate_core() {
  # Dex emits OpenShift Group membership; direct Kubernetes role bindings do not
  # grant Argo CD permissions. Verify the operator-reconciled policy, not just CR intent.
  GITOPS_ACCESS=$(oc --request-timeout=10s get group rhoai-gitops-admins -o json 2>/dev/null |
    jq -r 'if (.users // []) | index("admin") then "pass" else "admin membership missing" end' || echo "group inspection failed")
  record "GitOps SSO administrator group" "$GITOPS_ACCESS"
  GITOPS_POLICY=$(oc --request-timeout=10s get configmap argocd-rbac-cm -n openshift-gitops -o json 2>/dev/null |
    jq -r '.data // {} | if ((."policy.csv" // "") | split("\n") | map(gsub("\\s"; "")) | index("g,rhoai-gitops-admins,role:admin"))
        and ((.scopes // "") | contains("groups")) and ((."policy.default" // "") | test("^\\s*$"))
      then "pass" else "mapping missing or broad default policy" end' || echo "policy inspection failed")
  record "GitOps reconciled group policy with empty default" "$GITOPS_POLICY"

  csv_phase_from_subscription() {
    local namespace="$1" subscription="$2"
    local installed_csv
    installed_csv=$(oc get subscription "$subscription" -n "$namespace" \
      -o jsonpath='{.status.installedCSV}' --insecure-skip-tls-verify=true 2>/dev/null || echo "")
    if [[ -z "$installed_csv" ]]; then
      echo ""
      return
    fi
    oc get csv "$installed_csv" -n "$namespace" \
      -o jsonpath='{.status.phase}' --insecure-skip-tls-verify=true 2>/dev/null || echo ""
  }

  native_ready() {
    local kind="$1" name="$2" require_generation="$3"
    oc --request-timeout="${RHOAI_OC_REQUEST_TIMEOUT:-10s}" get "$kind" "$name" -o json 2>/dev/null |
      jq -r --arg gen "$require_generation" '(.status // {}) as $s
        | if $s.phase == "Ready" and any($s.conditions[]?; .type == "Ready" and .status == "True")
            and ($gen == "false" or ($s.observedGeneration // 0) >= (.metadata.generation // 1))
          then "pass" else "native Ready/current-generation contract not satisfied" end' ||
      echo "native status unavailable"
  }

  # ── 1. OpenShift GitOps operator ─────────────────────────────────────────────
  GITOPS_CSV=$(csv_phase_from_subscription openshift-operators openshift-gitops-operator)
  [[ "$GITOPS_CSV" == "Succeeded" ]] && R="pass" || R="phase=${GITOPS_CSV:-not found}"
  record "OpenShift GitOps operator CSV Succeeded" "$R"

  # ── 2. ArgoCD instance Available ─────────────────────────────────────────────
  ARGOCD_PHASE=$(oc get argocd openshift-gitops -n openshift-gitops \
    -o jsonpath='{.status.phase}' --insecure-skip-tls-verify=true 2>/dev/null || echo "")
  [[ "$ARGOCD_PHASE" == "Available" ]] && R="pass" || R="phase=${ARGOCD_PHASE:-not found}"
  record "ArgoCD instance Available" "$R"

  # ── 3. Component Applications Synced + Healthy at one revision ──────────────
  STAGE_APPS="$ROOT_DIR/scripts/stage-apps.sh"
  revision_args=()
  [[ -n "${RHOAI_STAGE010_EXPECTED_REVISION:-}" ]] && revision_args=(--revision "$RHOAI_STAGE010_EXPECTED_REVISION")
  if APP_STATUS=$("$STAGE_APPS" status 010 ${revision_args[@]+"${revision_args[@]}"} 2>&1); then R="pass"
  else R="$(printf '%s\n' "$APP_STATUS" | grep -E '^(  - |ERROR)' | head -3 | tr '\n' ' ')"; fi
  record "Stage 010 component Applications (all seven) Synced/Healthy at one revision" "$R"

  # ── 4. ODF operator ───────────────────────────────────────────────────────────
  ODF_CSV=$(csv_phase_from_subscription openshift-storage odf-operator)
  [[ "$ODF_CSV" == "Succeeded" ]] && R="pass" || R="phase=${ODF_CSV:-not found}"
  record "ODF operator CSV Succeeded" "$R"

  # ── 5. NooBaa Ready ───────────────────────────────────────────────────────────
  NOOBAA_PHASE=$(oc get noobaa noobaa -n openshift-storage \
    -o jsonpath='{.status.phase}' --insecure-skip-tls-verify=true 2>/dev/null || echo "")
  [[ "$NOOBAA_PHASE" == "Ready" ]] && R="pass" || R="phase=${NOOBAA_PHASE:-not found}"
  record "NooBaa phase Ready" "$R"

  # ── 6. RHOAI operator ────────────────────────────────────────────────────────
  RHOAI_CSV=$(csv_phase_from_subscription redhat-ods-operator rhods-operator)
  [[ "$RHOAI_CSV" == "Succeeded" ]] && R="pass" || R="phase=${RHOAI_CSV:-not found}"
  record "RHOAI operator CSV Succeeded" "$R"

  # ── 7. RHOAI observability prerequisite operators ────────────────────────────
  check_operator_policy "$ROOT_DIR/gitops/stages/010-openshift-ai-platform-foundation" --verify

  COO_CSV=$(csv_phase_from_subscription openshift-cluster-observability-operator cluster-observability-operator)
  [[ "$COO_CSV" == "Succeeded" ]] && R="pass" || R="phase=${COO_CSV:-not found}"
  record "Cluster Observability Operator CSV Succeeded" "$R"

  OTEL_CSV=$(csv_phase_from_subscription openshift-opentelemetry-operator opentelemetry-product)
  [[ "$OTEL_CSV" == "Succeeded" ]] && R="pass" || R="phase=${OTEL_CSV:-not found}"
  record "Red Hat build of OpenTelemetry Operator CSV Succeeded" "$R"

  TEMPO_CSV=$(csv_phase_from_subscription openshift-tempo-operator tempo-product)
  [[ "$TEMPO_CSV" == "Succeeded" ]] && R="pass" || R="phase=${TEMPO_CSV:-not found}"
  record "Tempo Operator CSV Succeeded" "$R"

  # ── 8. DSCInitialization Ready ────────────────────────────────────────────────
  record "DSCInitialization phase and condition Ready" "$(native_ready dscinitialization default-dsci false)"

  # ── 9. RHOAI observability stack and dashboard flag ──────────────────────────
  OBS_MGMT=$(oc get dscinitialization default-dsci \
    -o jsonpath='{.spec.monitoring.managementState}' --insecure-skip-tls-verify=true 2>/dev/null || echo "")
  OBS_NS=$(oc get dscinitialization default-dsci \
    -o jsonpath='{.spec.monitoring.namespace}' --insecure-skip-tls-verify=true 2>/dev/null || echo "")
  [[ "$OBS_MGMT" == "Managed" && "$OBS_NS" == "redhat-ods-monitoring" ]] \
    && R="pass" || R="managementState=${OBS_MGMT:-missing} namespace=${OBS_NS:-missing}"
  record "RHOAI observability stack configured in DSCInitialization" "$R"

  OBS_METRICS_REPLICAS=$(oc get dscinitialization default-dsci \
    -o jsonpath='{.spec.monitoring.metrics.replicas}' --insecure-skip-tls-verify=true 2>/dev/null || echo "")
  OBS_METRICS_SIZE=$(oc get dscinitialization default-dsci \
    -o jsonpath='{.spec.monitoring.metrics.storage.size}' --insecure-skip-tls-verify=true 2>/dev/null || echo "")
  OBS_TRACES_BACKEND=$(oc get dscinitialization default-dsci \
    -o jsonpath='{.spec.monitoring.traces.storage.backend}' --insecure-skip-tls-verify=true 2>/dev/null || echo "")
  OBS_TRACES_RATIO=$(oc get dscinitialization default-dsci \
    -o jsonpath='{.spec.monitoring.traces.sampleRatio}' --insecure-skip-tls-verify=true 2>/dev/null || echo "")
  [[ "$OBS_METRICS_REPLICAS" == "1" && "$OBS_METRICS_SIZE" == "5Gi" ]] \
    && R="pass" || R="metricsReplicas=${OBS_METRICS_REPLICAS:-missing} metricsSize=${OBS_METRICS_SIZE:-missing}"
  record "RHOAI observability metrics configured" "$R"
  [[ "$OBS_TRACES_BACKEND" == "pv" && "$OBS_TRACES_RATIO" == "0.1" ]] \
    && R="pass" || R="tracesBackend=${OBS_TRACES_BACKEND:-missing} sampleRatio=${OBS_TRACES_RATIO:-missing}"
  record "RHOAI observability traces configured" "$R"

  OBS_DASHBOARD=$(oc get odhdashboardconfig odh-dashboard-config -n redhat-ods-applications \
    -o jsonpath='{.spec.dashboardConfig.observabilityDashboard}' --insecure-skip-tls-verify=true 2>/dev/null || echo "")
  [[ "$OBS_DASHBOARD" == "true" ]] && R="pass" || R="observabilityDashboard=${OBS_DASHBOARD:-missing}"
  record "RHOAI Observability dashboard menu enabled" "$R"

  # Native observability functional acceptance replaces legacy workaround-presence checks.
  validate_persona() {
    local label="$1" kubeconfig="$2" expected_user="$3" actual_user server permission guarded_server
    local refresh="run stages/010-openshift-ai-platform-foundation/validate.sh --login-personas"
    if [[ -z "$kubeconfig" || ! -f "$kubeconfig" ]]; then
      record_warn "$label real authenticated session" "no persona session; $refresh"
      return
    fi
    server=$(oc --kubeconfig="$kubeconfig" --request-timeout="${RHOAI_OC_REQUEST_TIMEOUT:-10s}" whoami --show-server 2>/dev/null || true)
    actual_user=$(oc --kubeconfig="$kubeconfig" --request-timeout="${RHOAI_OC_REQUEST_TIMEOUT:-10s}" whoami 2>/dev/null || true)
    guarded_server=$(oc --request-timeout="${RHOAI_OC_REQUEST_TIMEOUT:-10s}" whoami --show-server)
    if [[ "$server" == "$guarded_server" && -z "$actual_user" ]]; then
      record_warn "$label real authenticated session" "session expired; $refresh"
      return
    fi
    if [[ "$server" != "$guarded_server" || "$actual_user" != "$expected_user" ]]; then
      record "$label real authenticated session" "identity or cluster mismatch"
      return
    fi
    permission=$(oc --kubeconfig="$kubeconfig" --request-timeout="${RHOAI_OC_REQUEST_TIMEOUT:-10s}" auth can-i update deployments.apps -n demo-sandbox 2>/dev/null || true)
    [[ "$permission" == yes ]] && R="pass" || R="project permission denied"
    record "$label real session project access" "$R"
  }
  validate_persona administrator "${RHOAI_ADMIN_KUBECONFIG:-}" "${RHOAI_ADMIN_USER:-}"
  validate_persona developer "${RHOAI_DEVELOPER_KUBECONFIG:-}" "${RHOAI_DEVELOPER_USER:-}"

  # ── 10. DataScienceCluster Ready ──────────────────────────────────────────────
  record "DataScienceCluster Ready at current generation" "$(native_ready datasciencecluster default-dsc true)"

  # ── 12. RHOAI Dashboard route responds ───────────────────────────────────────
  DASHBOARD_HOST=$(oc get route rhods-dashboard -n redhat-ods-applications \
    -o jsonpath='{.spec.host}' --insecure-skip-tls-verify=true 2>/dev/null || echo "")
  if [[ -n "$DASHBOARD_HOST" ]]; then
    HTTP_CODE=$(curl -sk -o /dev/null -w "%{http_code}" "https://$DASHBOARD_HOST" 2>/dev/null || echo "000")
    [[ "$HTTP_CODE" =~ ^(200|301|302|303)$ ]] && R="pass" || R="http=$HTTP_CODE"
    record "RHOAI Dashboard route reachable (https://$DASHBOARD_HOST)" "$R"
  else
    record "RHOAI Dashboard route reachable" "route not found"
  fi

  # Native Auth and foundation component ownership.
  record "Native Auth Ready at current generation" "$(native_ready auth.services.platform.opendatahub.io auth true)"
  # Later stages enable components 010-rhoai-platform delegates through ignoreDifferences.
  # Dashboard and workbenches are Managed; the listed components stay Removed unless Stage 010 delegated the field.
  delegated=$("$ROOT_DIR/scripts/stage-apps.sh" delegated 010 DataScienceCluster default-dsc \
    --group datasciencecluster.opendatahub.io 2>/dev/null | sed -n 's#^/spec/components/##p' | jq -R . | jq -s -c . || echo '[]')
  COMPONENT_CHECK=$(oc --request-timeout=15s get datasciencecluster default-dsc -o json 2>/dev/null |
    jq -r --argjson delegated "$delegated" '.spec.components as $c
      | ["ogx", "aigateway", "mcplifecycleoperator", "sparkoperator", "trainer"] - $delegated | . as $removed
      | if all(("dashboard", "workbenches"); $c[.].managementState == "Managed")
          and all($removed[]; $c[.].managementState == "Removed")
        then "pass" else "component ownership mismatch" end' || echo "component inspection failed")
  record "Foundation component ownership" "$COMPONENT_CHECK"

  # Existing provider authentication and explicit group membership.
  IDP=$(oc get oauth cluster -o jsonpath='{.spec.identityProviders[*].name}' 2>/dev/null || true)
  [[ -n "$IDP" ]] && R="pass" || R="no identity provider"
  record "Existing identity provider configured" "$R"
  : "${RHOAI_ADMIN_USER:?Set existing RHOAI_ADMIN_USER for access validation}"
  : "${RHOAI_DEVELOPER_USER:?Set existing RHOAI_DEVELOPER_USER for access validation}"
  for mapping in "rhods-admins:$RHOAI_ADMIN_USER" "rhoai-developers:$RHOAI_DEVELOPER_USER"; do
    group="${mapping%%:*}"; user="${mapping#*:}"
    members=$(oc get group "$group" -o jsonpath='{.users[*]}' 2>/dev/null || true)
    if printf '%s\n' "$members" | tr ' ' '\n' | grep -Fxq "$user"; then R="pass"; else R="membership missing"; fi
    record "Configured persona in $group" "$R"
  done

  # ── 15. demo-sandbox data science project exists ─────────────────────────────
  DS_LABEL=$(oc get namespace demo-sandbox \
    -o jsonpath='{.metadata.labels.opendatahub\.io/dashboard}' --insecure-skip-tls-verify=true 2>/dev/null || echo "")
  [[ "$DS_LABEL" == "true" ]] && R="pass" || R="dashboard-label=${DS_LABEL:-missing}"
  record "demo-sandbox data science project present" "$R"

  # ── 16. environment Keycloak ready (prerequisite, not owned by GitOps) ───────
  KC_READY=$(oc get keycloak keycloak -n keycloak \
    -o jsonpath='{.status.conditions[?(@.type=="Ready")].status}' --insecure-skip-tls-verify=true 2>/dev/null || echo "")
  [[ "$KC_READY" == "True" ]] && R="pass" || R="ready=${KC_READY:-not found}"
  record "Environment Keycloak keycloak/keycloak Ready" "$R"

  # ── 17. OpenShift login uses the environment Keycloak (rhbk provider) ────────
  IDP_TYPE=$(oc get oauth cluster -o jsonpath='{.spec.identityProviders[?(@.name=="rhbk")].type}' \
    --insecure-skip-tls-verify=true 2>/dev/null || echo "")
  [[ "$IDP_TYPE" == "OpenID" ]] && R="pass" || R="identity-provider=${IDP_TYPE:-missing}"
  record "OpenShift OAuth rhbk identity provider present" "$R"

  # ── 18. RHOAI admins can manage demo-sandbox ─────────────────────────────────
  ADMIN_RB=$(oc get rolebinding rhods-admins-admin -n demo-sandbox \
    -o jsonpath='{.roleRef.name}' --insecure-skip-tls-verify=true 2>/dev/null || echo "")
  [[ "$ADMIN_RB" == "admin" ]] && R="pass" || R="rolebinding=${ADMIN_RB:-missing}"
  record "rhods-admins admin on demo-sandbox" "$R"
}

# ── 010-sandbox-storage: each bucket claim Bound and its dashboard connection mapping the claim ────────────────
validate_sandbox_storage() {
  sandbox_json() { oc --request-timeout=10s get "$@" -n demo-sandbox -o json; }
  yes_no() { jq -e "$@" >/dev/null && echo yes || echo no; }

  for pair in rhoai-models:Models rhoai-workbench:Workbench; do
      claim=${pair%%:*}
      display=${pair#*:}
      obc=$(sandbox_json obc "$claim")
      bucket=$(sandbox_json configmap "$claim")
      credentials=$(sandbox_json secret "$claim")
      connection=$(sandbox_json secret "$claim-connection")
      obc_uid=$(jq -r '.metadata.uid' <<<"$obc")

      bound() { yes_no '.status.phase == "Bound"' <<<"$obc"; }
      tracked() {
          jq -s -e 'all(.[]; .metadata.annotations["argocd.argoproj.io/tracking-id"] // "" | startswith("010-sandbox-storage:"))' \
              < <(printf '%s%s' "$obc" "$connection") >/dev/null && echo yes || echo no
      }
      owned_by_claim() {
          jq -s -e --arg uid "$obc_uid" \
              'all(.[]; any(.metadata.ownerReferences[]?; .kind == "ObjectBucketClaim" and .uid == $uid))' \
              < <(printf '%s%s' "$bucket" "$credentials") >/dev/null && echo yes || echo no
      }
      bucket_config() {
          yes_no --arg claim "$claim" \
              '.data.BUCKET_NAME == $claim and .data.BUCKET_PORT == "443" and (.data.BUCKET_HOST // "") != ""' <<<"$bucket"
      }
      # Compares the claim's generated keys with the connection's, inside jq, so no value reaches the shell.
      credentials_match() {
          jq -n -e --slurpfile s <(printf '%s' "$credentials") --slurpfile t <(printf '%s' "$connection") \
              '$s[0] as $s | $t[0] as $t
              | all("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY"; ($s.data[.] // "") != "" and $t.data[.] == $s.data[.])' \
              >/dev/null && echo yes || echo no
      }
      connection_target() {
          jq -n -e --argjson b "$bucket" --slurpfile t <(printf '%s' "$connection") --arg claim "$claim" \
              '($t[0].data | map_values(@base64d)) as $d
              | $d.AWS_S3_BUCKET == $claim
              and $d.AWS_S3_ENDPOINT == "https://" + $b.data.BUCKET_HOST + ":443"
              and $d.AWS_DEFAULT_REGION == ($b.data.BUCKET_REGION // "us-east-1" | if . == "" then "us-east-1" else . end)' \
              >/dev/null && echo yes || echo no
      }
      connection_metadata() {
          printf '%s' "$connection" | yes_no --arg display "$display" '.metadata as $m
              | $m.annotations["opendatahub.io/connection-type-protocol"] == "s3"
              and $m.annotations["openshift.io/display-name"] == $display
              and $m.labels["opendatahub.io/dashboard"] == "true"
              and $m.labels["opendatahub.io/managed"] != "true"'
      }
      # The connection's values come from the claim at runtime; Git (last-applied) must not declare any data.
      no_declared_data() {
          printf '%s' "$connection" | yes_no '(.metadata.annotations["kubectl.kubernetes.io/last-applied-configuration"] // "{}" | fromjson)
              | ((.data // {}) | length) == 0 and ((.stringData // {}) | length) == 0'
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
}

# ── 010-console-observability: Git-declared console plugins enabled; console-owned Perses current ──────────────
validate_console_observability() {
  NS=openshift-cluster-observability-operator
  PLUGINS_FILE="$REPO_ROOT/gitops/stages/010-openshift-ai-platform-foundation/010-console-observability/console-plugins.yaml"
  read_json() { oc --request-timeout=10s get "$@" -o json; }

  app=$(read_json application 010-console-observability -n openshift-gitops)
  uiplugin=$(read_json uiplugins.observability.openshift.io monitoring)
  declared=$(ruby -ryaml -rjson -e 'puts JSON.generate(YAML.load_file(ARGV[0])["spec"]["plugins"])' "$PLUGINS_FILE")
  installed=$(read_json consoleplugins.console.openshift.io | jq -c '[.items[].metadata.name]')
  enabled=$(read_json console.operator.openshift.io cluster | jq -c '.spec.plugins // []')
  uid=$(jq -r '.metadata.uid' <<<"$uiplugin")
  owned_by() { jq -c --arg uid "$1" '[.items[] | select(any(.metadata.ownerReferences[]?; .uid == $uid))]'; }
  perses=$(read_json perses -n "$NS" | owned_by "$uid")
  deployments=$(read_json deployments -n "$NS" | owned_by "$uid")
  statefulsets=$(read_json statefulsets -n "$NS" | owned_by "$(jq -r '.[0].metadata.uid // ""' <<<"$perses")")

  reconciled() {
      jq -e '.spec.source as $src | .status as $s
          | ($src.targetRevision | length) == 40
          and $s.sync.status == "Synced" and $s.sync.revision == $src.targetRevision
          and $s.health.status == "Healthy"
          and $s.operationState.phase == "Succeeded"
          and $s.operationState.syncResult.revision == $src.targetRevision
          and $s.operationState.syncResult.source.path == $src.path' <<<"$app" >/dev/null && echo yes || echo no
  }
  perses_ui() {
      jq -e '.spec.type == "Monitoring" and .spec.monitoring.perses.enabled == true
          and (.metadata.annotations["argocd.argoproj.io/tracking-id"] // "" | startswith("010-console-observability:"))' \
          <<<"$uiplugin" >/dev/null && echo yes || echo no
  }
  # Git declares the whole plugin list: every declared plugin that is installed is enabled, and nothing else is installed.
  declared_enabled() {
      jq -nr --argjson d "$declared" --argjson i "$installed" --argjson e "$enabled" \
          '[$d[] | select(. as $p | ($i | index($p)) and ($e | index($p) | not))] | if length == 0 then "yes" else join(", ") end'
  }
  nothing_undeclared() {
      jq -nr --argjson d "$declared" --argjson i "$installed" \
          '[$i[] | select(. as $p | $d | index($p) | not)] | if length == 0 then "yes" else join(", ") end'
  }
  one_perses_available() {
      jq -e 'length == 1 and any(.[0].status.conditions[]?; .type == "Available" and .status == "True")' \
          <<<"$perses" >/dev/null && echo yes || echo no
  }
  deployments_current() {
      jq -e 'length > 0 and all(.[]; (.spec.replicas // 1) as $n | .status as $s
          | $n > 0 and $s.observedGeneration == .metadata.generation
          and $s.updatedReplicas == $n and $s.readyReplicas == $n and $s.availableReplicas == $n)' \
          <<<"$deployments" >/dev/null && echo yes || echo no
  }
  statefulset_current() {
      jq -e 'length == 1 and (.[0] | (.spec.replicas // 1) as $n | .status as $s
          | $n > 0 and $s.observedGeneration == .metadata.generation
          and $s.updatedReplicas == $n and $s.readyReplicas == $n
          and ($s.currentRevision // "") != "" and $s.currentRevision == $s.updateRevision)' \
          <<<"$statefulsets" >/dev/null && echo yes || echo no
  }

  check "010-console-observability Synced, Healthy and last synced at its pinned revision" reconciled yes
  check "Monitoring UIPlugin enables Perses and is tracked by 010-console-observability" perses_ui yes
  check "Every installed console plugin that Git declares is enabled" declared_enabled yes
  check "No installed console plugin is missing from Git" nothing_undeclared yes
  check "Exactly one console-owned Perses, Available" one_perses_available yes
  check "Console-owned Deployments current and available" deployments_current yes
  check "Perses StatefulSet current and ready" statefulset_current yes
  echo "Scope: native console/Perses readiness; datasource persona permissions and browser checks are separate."
}

# ── Native data plane as the administrator: a metrics query and one synthetic trace through the collector ──────
validate_foundation_services() {
  read_json() { oc --request-timeout=20s get "$@" -o json; }
  TOKEN=$(oc whoami -t)  # memory only: reaches curl through --config on stdin, never an argument or a log line
  WORK=$(mktemp -d)
  # check() runs each probe in a subshell, so port-forward PIDs are recorded in a file for cleanup.
  cleanup() {
      while read -r pid; do kill "$pid" 2>/dev/null || true; done < <(cat "$WORK/pids" 2>/dev/null)
      rm -rf "$WORK"
  }
  trap cleanup EXIT

  # Authenticated HTTPS (demo certificates, -k) or plain HTTP to a local port-forward; prints the response body.
  api() {
      local url=$1; shift
      printf 'header = "Authorization: Bearer %s"\n' "$TOKEN" |
          curl --config - -sk --max-time 20 -H 'Accept: application/json' "$@" "$url"
  }

  # Port-forward a Service port to a free local port; prints the local port.
  forward() {
      local service=$1 namespace=$2 port=$3 log="$WORK/forward-$1-$3.log"
      oc -n "$namespace" port-forward "service/$service" ":$port" --address=127.0.0.1 >"$log" 2>&1 &
      echo "$!" >>"$WORK/pids"
      for _ in $(seq 1 50); do
          local local_port
          local_port=$(sed -n 's/^Forwarding from 127.0.0.1:\([0-9]*\) .*/\1/p' "$log" | head -1)
          if [[ -n "$local_port" ]]; then echo "$local_port"; return 0; fi
          sleep 0.1
      done
      return 1
  }

  dsci=$(read_json dscinitialization default-dsci)
  NS=$(jq -r '.spec.monitoring.namespace' <<<"$dsci")
  monitors=$(read_json monitorings.services.platform.opendatahub.io)

  dsci_ready() {
      jq -e '.status.phase == "Ready" and any(.status.conditions[]?; .type == "Ready" and .status == "True")' \
          <<<"$dsci" >/dev/null && echo yes || echo no
  }
  monitoring_ready() {
      jq -e '(.items | length) == 1 and (.items[0] | .status.phase == "Ready"
          and .status.observedGeneration == .metadata.generation
          and any(.status.conditions[]?; .type == "Ready" and .status == "True"))' \
          <<<"$monitors" >/dev/null && echo yes || echo no
  }
  # The native namespace proxy needs the namespace parameter for its SAR and label filter. Recency is checked in
  # PromQL on the server clock; an empty answer (Thanos during an observability resync) is retried for ~30 s.
  metrics_query() {
      local port result query='up == 1 and (time() - timestamp(up) >= 0) and (time() - timestamp(up) <= 120)'
      port=$(forward data-science-prometheus-namespace-proxy "$NS" 8443) || { echo "no port-forward"; return; }
      for _ in 1 2 3 4 5 6; do
          result=$(api "https://127.0.0.1:$port/api/v1/query" -G --data-urlencode "query=$query" \
              --data-urlencode "namespace=$NS") || result='{}'
          if jq -e --arg ns "$NS" '.status == "success"
              and any(.data.result[]?; .metric.namespace == $ns and (.value[1] | tonumber) == 1)' \
              <<<"$result" >/dev/null 2>&1; then echo yes; return; fi
          sleep 5
      done
      jq -r '"status \(.status // "none"), \(.data.result // [] | length) samples"' <<<"$result" 2>/dev/null || echo no
  }
  collector_config() {
      read_json opentelemetrycollector data-science-collector -n "$NS" | jq -e '.spec.config | type == "object"
          and (.receivers.otlp.protocols | has("http"))
          and (.service.pipelines.traces.receivers | index("otlp") != null)' >/dev/null && echo yes || echo no
  }
  # Tempo authorizes a virtual resource that oc can-i can mis-map; a SubjectAccessReview checks the exact attributes.
  collector_can_write_tempo() {
      local sa
      sa=$(read_json statefulset data-science-collector-collector -n "$NS" | jq -r '.spec.template.spec.serviceAccountName')
      jq -n --arg user "system:serviceaccount:$NS:$sa" --arg ns "$NS" '{apiVersion: "authorization.k8s.io/v1",
          kind: "SubjectAccessReview", spec: {user: $user,
          resourceAttributes: {group: "tempo.grafana.com", resource: $ns, name: "traces", verb: "create"}}}' |
          oc --request-timeout=20s create --raw /apis/authorization.k8s.io/v1/subjectaccessreviews -f - |
          jq -e '.status.allowed == true' >/dev/null && echo yes || echo no
  }
  # Send one synthetic span through the collector, then read it back from Tempo by its trace ID (up to 90 s).
  trace_roundtrip() {
      local trace_id span_id start port endpoint host tempo_port url path body deadline
      trace_id=$(uuidgen | tr -d '-' | tr 'A-F' 'a-f')
      span_id=${trace_id:0:16}
      start=$(($(date +%s) * 1000000000))
      echo "[INFO] Synthetic trace ID $trace_id" >&2
      port=$(forward data-science-collector-collector "$NS" 4318) || { echo "no collector port-forward"; return; }
      body=$(jq -n --arg t "$trace_id" --arg s "$span_id" --arg start "$start" --arg end "$((start + 1000000))" \
          '{resourceSpans: [{resource: {attributes: [{key: "service.name", value: {stringValue: "foundation-validation"}}]},
            scopeSpans: [{scope: {name: "foundation-validation"}, spans: [{traceId: $t, spanId: $s,
            name: "foundation-roundtrip", kind: 1, startTimeUnixNano: $start, endTimeUnixNano: $end}]}]}]}')
      api "http://127.0.0.1:$port/v1/traces" -H 'Content-Type: application/json' --data "$body" |
          jq -e '(.partialSuccess.rejectedSpans // 0) == 0' >/dev/null || { echo "collector rejected the span"; return; }
      url=$(read_json persesdatasource tempo-datasource -n "$NS" | jq -r '.spec.config.plugin.spec.proxy.spec.url')
      [[ "$url" == https://* ]] || { echo "no Tempo datasource endpoint"; return; }
      endpoint=${url#https://}
      host=${endpoint%%/*}
      path=/${endpoint#*/}
      [[ "$endpoint" == */* ]] || path=/
      tempo_port=${host##*:}
      [[ "$host" == *:* ]] || tempo_port=443
      port=$(forward "${host%%.*}" "$NS" "$tempo_port") || { echo "no Tempo port-forward"; return; }
      deadline=$((SECONDS + 90))
      local encoded
      encoded=$(printf '%s' "$trace_id" | xxd -r -p | base64)
      while ((SECONDS < deadline)); do
          if api "https://127.0.0.1:$port${path%/}/api/traces/$trace_id" -H "X-Scope-OrgID: $NS" -f 2>/dev/null |
              jq -e --arg id "$trace_id" --arg b64 "$encoded" '[(.batches // .resourceSpans // [])[]
                  | (.scopeSpans // .instrumentationLibrarySpans // [])[] | .spans[]?.traceId]
                  | any(. as $x | ($x | ascii_downcase) == $id or $x == $b64)' >/dev/null 2>&1; then
              echo yes; return
          fi
          sleep 3
      done
      echo "trace not found in Tempo within 90 s"
  }

  check "DSCInitialization Ready" dsci_ready yes
  check "Exactly one native Monitoring, Ready at its current generation" monitoring_ready yes
  check "Authenticated native metrics query returns a recent healthy target in $NS" metrics_query yes
  check "Collector exposes an OTLP/HTTP trace receiver" collector_config yes
  check "Collector service account may write the native Tempo tenant" collector_can_write_tempo yes
  check "One synthetic trace traverses the collector and is read back from Tempo by its exact ID" trace_roundtrip yes
  echo "Scope: administrator data-plane probes; persona sessions and browser UI acceptance are separate."
}

case "$COMPONENT" in
  "") validate_core; validate_sandbox_storage; validate_console_observability; validate_foundation_services ;;
  010-sandbox-storage) validate_sandbox_storage ;;
  010-console-observability) validate_console_observability ;;
  *) echo "Unknown component $COMPONENT" >&2; exit 1 ;;
esac
validation_summary
