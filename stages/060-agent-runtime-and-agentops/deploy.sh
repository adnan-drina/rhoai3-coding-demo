#!/usr/bin/env bash
# Stage 060: the five component Applications, each deployed by this script at one reviewed published revision after
# its own read-only preflight (060 components sync manually by design, .agents/rules/gitops.md):
#   060-openshell-identity  Keycloak realm import, then the OpenShift broker, clients and the two curated personas
#   060-openshell-runtime   the agent sandbox operator and OpenShell gateway, its retained key and issuer, the
#                           startup barrier, and the ai-agents workspace with ai-admin as its administrator
#   060-agent-console       dashboard AgentOps visibility and read-only discovery roles
#   060-mcp-platform        the native MCP lifecycle operator
#   060-agent-tools         the two native OpenShift MCP servers (Gen AI Studio publishing is Stage 040's)
# Credentials stay in memory: they reach curl and oc through stdin or a --config pipe, never arguments or output.
# The ai-agents workspace step runs the OpenShell CLI pinned in source-pins.json: RHOAI_STAGE060_OPENSHELL_CLI, or by
# default ~/.local/share/rhoai3-demo/openshell-<cliRelease>/bin/openshell; its checksum must match cliBinarySha256.
# Usage: stages/060-agent-runtime-and-agentops/deploy.sh [--revision REF] [--component NAME]
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$REPO_ROOT/scripts/lib.sh"
ref="${GIT_REPO_BRANCH:-HEAD}" COMPONENT=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --revision) ref="${2:?}"; shift 2 ;;
    --component) COMPONENT="${2:?}"; shift 2 ;;
    *) sed -n 's/^# Usage: //p' "$0" >&2; exit 1 ;;
  esac
done
load_env
check_oc_logged_in
require_env GIT_REPO_URL "reviewed Stage 060 source repository"
assert_required_env
STAGE_APPS="$REPO_ROOT/scripts/stage-apps.sh"
GITOPS=gitops/stages/060-agent-runtime-and-agentops
REVISION=$("$STAGE_APPS" select 060 --ref "$ref" --repo-url "$GIT_REPO_URL")
export RHOAI_STAGE060_EXPECTED_REVISION="$REVISION"
W=$(mktemp -d)
trap 'while read -r p; do kill "$p" 2>/dev/null || true; done <"$W/pids"; rm -rf "$W"' EXIT
: >"$W/pids"
fail() { log_error "$*"; exit 1; }
get() { oc --request-timeout=15s get "$@" --ignore-not-found -o json; }
# Apply one component pinned to the revision, start its sync (an unchanged render gets no automatic operation), wait.
reconcile() {
  "$STAGE_APPS" apply 060 --app "$1" --revision "$REVISION" --repo-url "$GIT_REPO_URL"
  "$STAGE_APPS" sync 060 --app "$1"
  "$STAGE_APPS" wait 060 --app "$1" --revision "$REVISION" --repo-url "$GIT_REPO_URL" --timeout "$2"
}
# An existing component must not be mid-operation when this deploy starts.
idle() {
  local app
  app=$(get applications.argoproj.io "$1" -n openshift-gitops)
  [[ -z "$app" ]] || jq -e '.operation == null and (.status.operationState.phase // "") != "Running"
    and (.status.operationState.phase // "") != "Terminating"' <<<"$app" >/dev/null || fail "$1 has an operation in progress"
}

# ── Keycloak admin API ────────────────────────────────────────────────────────
KC_BASE="" KC_TOKEN=""
keycloak_base() {
  local route
  route=$(get route keycloak -n keycloak)
  jq -e '.spec.tls.termination == "reencrypt"' <<<"$route" >/dev/null || fail "Keycloak route must be reencrypt"
  KC_BASE="https://$(jq -r '.spec.host' <<<"$route")"
  # The bootstrap administrator Secret must belong to the environment Keycloak.
  get secret keycloak-initial-admin -n keycloak | jq -e --arg uid "$(oc --request-timeout=15s get keycloak keycloak -n keycloak -o jsonpath='{.metadata.uid}')" \
    'any(.metadata.ownerReferences[]?; .uid == $uid and .kind == "Keycloak")' >/dev/null || fail "Foreign identity bootstrap owner"
}
kc_login() {
  KC_TOKEN=$(oc --request-timeout=15s get secret keycloak-initial-admin -n keycloak -o json |
    jq -j '.data | "grant_type=password&client_id=admin-cli&username=\(.username | @base64d | @uri)&password=\(.password | @base64d | @uri)"' |
    curl -s --max-time 15 --data-binary @- "$KC_BASE/realms/master/protocol/openid-connect/token" | jq -r '.access_token // empty')
  [[ -n "$KC_TOKEN" ]] || fail "Keycloak administrator login failed"
}
# kc METHOD PATH [optional]: an admin API call (request body on stdin for POST/PUT); prints the response body.
# A 404 is empty output when optional. Redirects are not followed.
kc() {
  local method=$1 path=$2 status body=()
  [[ "$method" == GET ]] || body=(-H 'Content-Type: application/json' --data-binary @-)
  status=$(curl -s --max-time 15 --max-filesize 2097152 -X "$method" --config <(printf 'header = "Authorization: Bearer %s"\n' "$KC_TOKEN") \
    ${body[@]+"${body[@]}"} -D "$W/kc.headers" -o "$W/kc.body" -w '%{http_code}' "$KC_BASE$path") || status=000
  if [[ "$status" == 404 && "${3:-}" == optional ]]; then return 0; fi
  [[ "$status" =~ ^2 ]] || fail "Identity API status $status ($method ${path%%\?*})"
  cat "$W/kc.body"
}
realm() { kc GET "/admin/realms/openshell$1" "${2:-}"; }
MARKER=rhoai3-coding-demo BROKER=openshell-broker

# ── 060-openshell-identity ────────────────────────────────────────────────────
# Read-only: everything the setup would touch is absent or carries this demo's marker and exact credentials.
identity_preflight() {
  local name uid users user id seed runtime oauth bootstrap_clients="[]" broker="" exists_realm
  exists_realm=$(realm "" optional)
  if [[ -n "$exists_realm" ]]; then
    jq -e --arg m "$MARKER" '.attributes["openshell-managed"] == $m' <<<"$exists_realm" >/dev/null || fail "Foreign openshell realm"
    realm /roles/default-roles-openshell/composites | jq -e 'all(.[]; .name != "openshell-platform-admin")' >/dev/null || fail "Administrative default role"
    for name in openshell-cli openshell-bootstrap; do
      users=$(realm "/clients?clientId=$name")
      jq -e --arg m "$MARKER" 'length <= 1 and all(.[]; .attributes["openshell-managed"] == $m)' <<<"$users" >/dev/null || fail "Foreign client $name"
      [[ "$name" == openshell-bootstrap ]] && bootstrap_clients=$users
    done
    broker=$(realm /identity-provider/instances/openshift-v4 optional)
    [[ -z "$broker" ]] || jq -e --arg b "$BROKER" --arg m "$MARKER" '.providerId == "openshift-v4" and .config.clientId == $b
      and .config["openshell-managed"] == $m' <<<"$broker" >/dev/null || fail "Foreign broker"
    for name in ai-admin ai-developer; do
      uid=$(oc --request-timeout=15s get user "$name" -o jsonpath='{.metadata.uid}')
      users=$(realm "/users?username=$name&exact=true")
      jq -e 'length <= 1' <<<"$users" >/dev/null || fail "Ambiguous user $name"
      [[ $(jq length <<<"$users") == 1 ]] || continue
      jq -e --arg m "$MARKER" --arg u "$uid" '.[0].attributes["openshell-managed"] == [$m] and .[0].attributes["openshift-uid"] == [$u]' <<<"$users" >/dev/null ||
        fail "Foreign user $name"
      id=$(jq -r '.[0].id' <<<"$users")
      [[ $(realm "/users/$id/groups" | jq length) == 0 ]] || fail "Unexpected group role grants for $name"
      realm "/users/$id/role-mappings/realm/composite" | jq -e 'all(.[]; .name != "openshell-platform-admin")' >/dev/null || fail "Composite admin grant for $name"
      [[ $(realm "/users/$id/credentials" | jq length) == 0 ]] || fail "Unexpected local credentials for $name"
      realm "/users/$id/federated-identity" | jq -e --arg u "$uid" --arg n "$name" '. == [] or . == [{identityProvider: "openshift-v4", userId: $u, userName: $n}]' \
        >/dev/null || fail "Foreign broker identity for $name"
    done
  fi
  seed=$(get keycloakrealmimport openshell-realm -n keycloak)
  [[ -z "$seed" ]] || jq -e --arg m "$MARKER" '.metadata.deletionTimestamp == null and (.metadata.ownerReferences // [] | length) == 0
    and .spec.keycloakCRName == "keycloak" and .spec.realm.attributes["openshell-managed"] == $m' <<<"$seed" >/dev/null || fail "Foreign or terminating realm import"
  oauth=$(get oauthclient "$BROKER")
  [[ -z "$oauth" ]] || jq -e '.metadata.deletionTimestamp == null and (.metadata.ownerReferences // [] | length) == 0
    and .metadata.labels["app.kubernetes.io/managed-by"] == "openshell-identity"' <<<"$oauth" >/dev/null || fail "Foreign OAuthClient $BROKER"
  runtime=$(oc --request-timeout=15s get secret openshell-auth -n keycloak --ignore-not-found -o name)
  if [[ -n "$runtime" ]]; then
    # Credential values are compared inside jq; nothing is printed.
    get secret openshell-auth -n keycloak | jq -e --argjson seed "${seed:-null}" '.metadata as $m
      | $m.deletionTimestamp == null and ($m.ownerReferences // [] | length) == 0 and $m.labels["app.kubernetes.io/managed-by"] == "openshell-identity"
      and $seed != null and $m.annotations["demo.rhoai.io/realm-import-uid"] == $seed.metadata.uid
      and (.data | keys) == ["bootstrap-client-secret", "broker-client-secret"] and all(.data[]; (@base64d | length) >= 32)' >/dev/null ||
      fail "Foreign or invalid openshell-auth credentials"
    if [[ -n "$oauth" ]]; then
      jq -n -e --slurpfile s <(get secret openshell-auth -n keycloak) --slurpfile o <(get oauthclient "$BROKER") \
        '$o[0].secret == ($s[0].data["broker-client-secret"] | @base64d) and $o[0].metadata.annotations["demo.rhoai.io/realm-import-uid"]
          == $s[0].metadata.annotations["demo.rhoai.io/realm-import-uid"]' >/dev/null || fail "Partial or mismatched OAuth credentials"
    fi
    if [[ $(jq length <<<"$bootstrap_clients") == 1 ]]; then
      jq -n -e --slurpfile s <(get secret openshell-auth -n keycloak) --slurpfile c <(realm "/clients/$(jq -r '.[0].id' <<<"$bootstrap_clients")/client-secret") \
        '$c[0].value == ($s[0].data["bootstrap-client-secret"] | @base64d)' >/dev/null || fail "Bootstrap credential rotation refused"
    fi
  else
    [[ -z "$oauth" && -z "$broker" && $(jq length <<<"$bootstrap_clients") == 0 ]] || fail "Partial credential-bearing identity state; rotation refused"
  fi
  log_success "Identity preflight: no foreign or partial identity state"
}
# Configure the broker, clients and curated personas; idempotent and never rotates credentials.
identity_setup() {
  local candidate status import_uid profile missing name uid users id old client found cid roles bootstrap ra
  # A native offline realm import can leave the master administrator's composite cache stale (upstream #45966):
  # one supported cache refresh, only after this demo's exact import completed.
  candidate=$(realm "")
  if ! jq -e '(.attributes // {} | length) > 0 or .id != null' <<<"$candidate" >/dev/null; then
    status=$(curl -s --max-time 15 -o /dev/null -w '%{http_code}' --config <(printf 'header = "Authorization: Bearer %s"\n' "$KC_TOKEN") \
      "$KC_BASE/admin/realms/openshell/roles" || echo 000)
    [[ "$status" == 200 || "$status" == 403 ]] || fail "Identity API status $status (GET roles)"
    if [[ "$status" == 403 ]]; then
      get keycloakrealmimport openshell-realm -n keycloak | jq -e --arg m "$MARKER" '.metadata.annotations["argocd.argoproj.io/tracking-id"]
        == "060-openshell-identity:k8s.keycloak.org/KeycloakRealmImport:keycloak/openshell-realm" and .spec.keycloakCRName == "keycloak"
        and .spec.realm.attributes["openshell-managed"] == $m and any(.status.conditions[]?; .type == "Done" and .status == "True")' >/dev/null ||
        fail "Realm import is not this demo's completed import; cache refresh refused"
      id=$(kc GET "/admin/realms/master/users?username=$(oc --request-timeout=15s get secret keycloak-initial-admin -n keycloak -o json |
        jq -r '.data.username | @base64d | @uri')&exact=true" | jq -r 'if length == 1 then .[0].id else "" end')
      [[ -n "$id" ]] && kc GET "/admin/realms/master/users/$id/role-mappings/realm/composite" | jq -e 'any(.[]; .name == "admin")' >/dev/null ||
        fail "Effective master admin required for cache recovery"
      kc POST /admin/realms/master/clear-realm-cache </dev/null >/dev/null
      kc_login
      log_info "Native master cache refreshed once; identity guards retained"
    fi
  fi
  identity_preflight
  realm "" | jq -e --arg m "$MARKER" '.attributes["openshell-managed"] == $m and .registrationAllowed == false and .editUsernameAllowed == false' \
    >/dev/null || fail "Realm settings differ"
  realm /authentication/flows | jq -e 'any(.[]; .alias == "openshell-prelinked-only")' >/dev/null || fail "Pre-linked-only flow missing"
  realm /authentication/flows/openshell-prelinked-only/executions | jq -e 'length == 1 and .[0].providerId == "deny-access-authenticator"
    and .[0].requirement == "REQUIRED"' >/dev/null || fail "Pre-linked-only flow differs"
  # Native User Profile discards undeclared attributes; declare only the two administrator-owned fields.
  ATTRIBUTES='[{"name":"openshell-managed","permissions":{"view":["admin"],"edit":["admin"]},"multivalued":false},
               {"name":"openshift-uid","permissions":{"view":["admin"],"edit":["admin"]},"multivalued":false}]'
  profile=$(realm /users/profile)
  jq -e --argjson want "$ATTRIBUTES" '. as $p | all($want[]; . as $d | [$p.attributes[]? | select(.name == $d.name)] as $e
    | ($e | length) <= 1 and (($e | length) == 0 or ($d | to_entries | all(. as $kv | $e[0][$kv.key] == $kv.value))))' <<<"$profile" >/dev/null ||
    fail "Foreign ownership of a user profile field"
  missing=$(jq -c --argjson want "$ATTRIBUTES" '. as $p | [$want[] | . as $d | select(all($p.attributes[]?; .name != $d.name))]' <<<"$profile")
  [[ "$missing" == "[]" ]] || jq -c --argjson add "$missing" '.attributes += $add' <<<"$profile" | realm_write PUT /users/profile
  realm /users/profile | jq -e --argjson want "$ATTRIBUTES" '. as $p | all($want[]; . as $d | any($p.attributes[]?; . as $x | $d | to_entries | all(. as $kv | $x[$kv.key] == $kv.value)))' \
    >/dev/null || fail "User profile readback differs"
  import_uid=$(oc --request-timeout=15s get keycloakrealmimport openshell-realm -n keycloak -o jsonpath='{.metadata.uid}')
  # Credentials: reuse this setup's own Secret, or create one (the broker OAuthClient must not exist without it).
  if [[ -n "$(oc --request-timeout=15s get secret openshell-auth -n keycloak --ignore-not-found -o name)" ]]; then
    get secret openshell-auth -n keycloak | jq -e --arg uid "$import_uid" '.metadata.annotations["demo.rhoai.io/realm-import-uid"] == $uid' >/dev/null ||
      fail "openshell-auth belongs to another realm import"
  else
    [[ -z "$(get oauthclient "$BROKER")" ]] || fail "Partial foreign credential state"
    BROKER_SECRET=$(openssl rand -base64 48 | tr '+/' '-_' | tr -d '=\n') BOOTSTRAP_SECRET=$(openssl rand -base64 48 | tr '+/' '-_' | tr -d '=\n') \
      jq -n --arg uid "$import_uid" '{apiVersion: "v1", kind: "Secret", type: "Opaque",
        metadata: {name: "openshell-auth", namespace: "keycloak", labels: {"app.kubernetes.io/managed-by": "openshell-identity", "demo.rhoai.io/stage": "060"},
          annotations: {"demo.rhoai.io/realm-import-uid": $uid}},
        stringData: {"broker-client-secret": $ENV.BROKER_SECRET, "bootstrap-client-secret": $ENV.BOOTSTRAP_SECRET}}' |
      oc --request-timeout=15s create -f - >/dev/null || fail "Could not create openshell-auth"
  fi
  # The OpenShift OAuthClient for the broker: create with the stored secret, or patch only its non-secret fields.
  REDIRECT="$KC_BASE/realms/openshell/broker/openshift-v4/endpoint"
  old=$(get oauthclient "$BROKER")
  if [[ -n "$old" ]]; then
    jq -n -e --slurpfile s <(get secret openshell-auth -n keycloak) --argjson o "$old" --arg uid "$import_uid" '$o.metadata as $m
      | ($m.ownerReferences // [] | length) == 0 and $m.deletionTimestamp == null and $m.labels["app.kubernetes.io/managed-by"] == "openshell-identity"
      and $m.annotations["demo.rhoai.io/realm-import-uid"] == $uid and $o.secret == ($s[0].data["broker-client-secret"] | @base64d)' >/dev/null ||
      fail "Broker OAuthClient is foreign or its credential differs (rotation refused)"
    jq -c --arg r "$REDIRECT" '[{op: "test", path: "/metadata/uid", value: .metadata.uid}, {op: "test", path: "/metadata/resourceVersion", value: .metadata.resourceVersion},
      {op: "add", path: "/redirectURIs", value: [$r]}, {op: "add", path: "/grantMethod", value: "prompt"},
      {op: "add", path: "/scopeRestrictions", value: [{literals: ["user:info"]}]}]' <<<"$old" |
      oc --request-timeout=15s patch oauthclient "$BROKER" --type=json --patch-file=/dev/stdin >/dev/null || fail "Could not update $BROKER"
  else
    get secret openshell-auth -n keycloak | jq -c --arg b "$BROKER" --arg r "$REDIRECT" --arg uid "$import_uid" '{apiVersion: "oauth.openshift.io/v1",
      kind: "OAuthClient", metadata: {name: $b, labels: {"app.kubernetes.io/managed-by": "openshell-identity", "demo.rhoai.io/stage": "060"},
        annotations: {"demo.rhoai.io/realm-import-uid": $uid}}, secret: (.data["broker-client-secret"] | @base64d),
      redirectURIs: [$r], grantMethod: "prompt", scopeRestrictions: [{literals: ["user:info"]}]}' |
      oc --request-timeout=15s create -f - >/dev/null || fail "Could not create $BROKER"
  fi
  # The Keycloak identity provider brokering OpenShift logins (secret from the stored credential, through stdin).
  old=$(realm /identity-provider/instances/openshift-v4 optional)
  [[ -z "$old" ]] || jq -e --arg b "$BROKER" '.providerId == "openshift-v4" and .config.clientId == $b' <<<"$old" >/dev/null || fail "Foreign broker"
  get secret openshell-auth -n keycloak | jq -c --arg server "$(oc --request-timeout=15s whoami --show-server)" --arg b "$BROKER" --arg m "$MARKER" '{alias: "openshift-v4",
    displayName: "OpenShift", providerId: "openshift-v4", enabled: true, trustEmail: false, storeToken: false, addReadTokenRoleOnCreate: false,
    firstBrokerLoginFlowAlias: "openshell-prelinked-only", config: {baseUrl: $server, clientId: $b,
      clientSecret: (.data["broker-client-secret"] | @base64d), defaultScope: "user:info", syncMode: "IMPORT", "openshell-managed": $m}}' |
    if [[ -n "$old" ]]; then realm_write PUT /identity-provider/instances/openshift-v4; else realm_write POST /identity-provider/instances; fi
  roles=$(jq -n --argjson u "$(realm /roles/openshell-user)" --argjson a "$(realm /roles/openshell-platform-admin)" '{"openshell-user": $u, "openshell-platform-admin": $a}')
  # Clients: the public CLI (PKCE, device grant) and the confidential bootstrap service account, each scoped to one role.
  for client in openshell-cli openshell-bootstrap; do
    found=$(realm "/clients?clientId=$client")
    jq -e --arg m "$MARKER" 'length <= 1 and all(.[]; .attributes["openshell-managed"] == $m)' <<<"$found" >/dev/null || fail "Foreign client $client"
    get secret openshell-auth -n keycloak | jq -c --arg c "$client" --arg m "$MARKER" '{enabled: true, protocol: "openid-connect", fullScopeAllowed: false,
      protocolMappers: [{name: "openshell-resource-audience", protocol: "openid-connect", protocolMapper: "oidc-audience-mapper", consentRequired: false,
        config: {"included.client.audience": "openshell-gateway", "id.token.claim": "false", "access.token.claim": "true", "introspection.token.claim": "true"}}]}
      + if $c == "openshell-cli" then {clientId: $c, publicClient: true, standardFlowEnabled: true, directAccessGrantsEnabled: false,
          redirectUris: ["http://127.0.0.1/*"], attributes: {"pkce.code.challenge.method": "S256", "oauth2.device.authorization.grant.enabled": "true", "openshell-managed": $m}}
        else {clientId: $c, publicClient: false, standardFlowEnabled: false, directAccessGrantsEnabled: false, serviceAccountsEnabled: true,
          secret: (.data["bootstrap-client-secret"] | @base64d), attributes: {"openshell-managed": $m}} end' |
      if [[ $(jq length <<<"$found") == 1 ]]; then realm_write PUT "/clients/$(jq -r '.[0].id' <<<"$found")"; else realm_write POST /clients; fi
    cid=$(realm "/clients?clientId=$client" | jq -r '.[0].id')
    jq -c --arg c "$client" '[if $c == "openshell-cli" then .["openshell-user"] else .["openshell-platform-admin"] end]' <<<"$roles" |
      realm_write POST "/clients/$cid/scope-mappings/realm"
    [[ "$client" == openshell-bootstrap ]] && bootstrap=$(realm "/clients/$cid/service-account-user" | jq -r '.id')
  done
  jq -c '[.["openshell-platform-admin"]]' <<<"$roles" | realm_write POST "/users/$bootstrap/role-mappings/realm"
  # Curated personas: pre-linked to their OpenShift identities, no local credentials, the user role only.
  for name in ai-admin ai-developer; do
    uid=$(oc --request-timeout=15s get user "$name" -o jsonpath='{.metadata.uid}')
    [[ -n "$uid" ]] || fail "OpenShift user $name has not logged in yet"
    users=$(realm "/users?username=$name&exact=true")
    if [[ $(jq length <<<"$users") == 0 ]]; then
      jq -n -c --arg n "$name" --arg m "$MARKER" --arg u "$uid" '{username: $n, enabled: true, emailVerified: false,
        attributes: {"openshell-managed": [$m], "openshift-uid": [$u]}}' | realm_write POST /users
      users=$(realm "/users?username=$name&exact=true")
    fi
    jq -e --arg m "$MARKER" --arg u "$uid" 'length == 1 and .[0].attributes["openshell-managed"] == [$m] and .[0].attributes["openshift-uid"] == [$u]' \
      <<<"$users" >/dev/null || fail "Foreign or ambiguous user $name"
    id=$(jq -r '.[0].id' <<<"$users")
    LINK=$(jq -n -c --arg u "$uid" --arg n "$name" '{identityProvider: "openshift-v4", userId: $u, userName: $n}')
    case "$(realm "/users/$id/federated-identity" | jq -r --argjson l "$LINK" 'if . == [] then "none" elif . == [$l] then "linked" else "foreign" end')" in
      none) realm_write POST "/users/$id/federated-identity/openshift-v4" <<<"$LINK" ;;
      linked) ;;
      *) fail "Foreign federation link for $name" ;;
    esac
    [[ $(realm "/users/$id/credentials" | jq length) == 0 ]] || fail "Password/credential enrollment is not permitted for $name"
    [[ $(realm "/users/$id/groups" | jq length) == 0 ]] || fail "Unexpected group role grants for $name"
    realm "/users/$id/role-mappings/realm/composite" | jq -e 'all(.[]; .name != "openshell-platform-admin")' >/dev/null || fail "Administrative grant for $name"
    jq -c '[.["openshell-user"]]' <<<"$roles" | realm_write POST "/users/$id/role-mappings/realm"
  done
  # Broker-only realm: personas are pre-linked to immutable OpenShift identities and never use profile attributes, so
  # the default user profile's required email and names must not stop their first login with an update-profile form.
  ra=$(realm /authentication/required-actions/VERIFY_PROFILE)
  if jq -e '.enabled != false' <<<"$ra" >/dev/null; then
    jq -c '.enabled = false | .defaultAction = false' <<<"$ra" | realm_write PUT /authentication/required-actions/VERIFY_PROFILE
  fi
  realm /authentication/required-actions/VERIFY_PROFILE | jq -e '.enabled == false' >/dev/null || fail "Verify Profile required action still enabled"
  log_success "Identity: realm openshell, broker scope user:info, personas ai-admin and ai-developer with role openshell-user; unknown broker logins denied; no profile prompt"
}
realm_write() { kc "$1" "/admin/realms/openshell$2" >/dev/null; }

deploy_identity() {
  idle 060-openshell-identity
  "$STAGE_APPS" preflight 060 --repo-url "$GIT_REPO_URL" --app 060-openshell-identity
  keycloak_base; kc_login
  identity_preflight
  reconcile 060-openshell-identity 300
  oc --request-timeout=15s wait keycloakrealmimport/openshell-realm -n keycloak --for=condition=Done --timeout=300s
  identity_setup
}

# ── 060-openshell-runtime ─────────────────────────────────────────────────────
RUNTIME_PATH="$GITOPS/060-openshell-runtime"
# tracked KIND NAME NAMESPACE: exists, tracked exactly by 060-openshell-runtime, unowned; prints the object.
tracked() {
  local obj
  obj=$(get "$1" "$2" -n "$3")
  jq -e --arg ns "$3" '.metadata as $m | (if (.apiVersion | contains("/")) then (.apiVersion | split("/")[0]) else "" end) as $g
    | ($m.annotations["argocd.argoproj.io/tracking-id"] // "") == "060-openshell-runtime:\($g)/\(.kind):\($m.namespace // "openshift-gitops")/\($m.name)"
    and ($m.ownerReferences // [] | length) == 0 and $m.deletionTimestamp == null' <<<"$obj" >/dev/null || fail "Foreign runtime object $1/$2"
  echo "$obj"
}
# patch_data KIND NAME NAMESPACE: merge the JSON object on stdin into .data, guarded by uid and resourceVersion.
# Values stay in memory and pipes (a Secret's data included).
patch_data() {
  local add obj
  add=$(cat)
  obj=$(get "$1" "$2" -n "$3")
  jq -n -e --slurpfile o <(printf '%s' "$obj") --slurpfile a <(printf '%s' "$add") '(($o[0].data // {}) + $a[0]) == ($o[0].data // {})' >/dev/null && return 0
  jq -n -c --slurpfile o <(printf '%s' "$obj") --slurpfile a <(printf '%s' "$add") '$o[0] as $x | [{op: "test", path: "/metadata/uid", value: $x.metadata.uid},
    {op: "test", path: "/metadata/resourceVersion", value: $x.metadata.resourceVersion}, {op: "add", path: "/data", value: (($x.data // {}) + $a[0])}]' |
    oc --request-timeout=15s patch "$1" "$2" -n "$3" --type=json --patch-file=/dev/stdin >/dev/null || fail "Could not update $1/$2"
}
# Initialize the retained key-encryption key and the issuer (prepare), then release the startup barrier once the
# native controller is qualified (full).
runtime_setup() {
  local issuer csv installed sub
  get applications.argoproj.io 060-openshell-runtime -n openshift-gitops | jq -e --arg rev "$REVISION" --arg repo "$GIT_REPO_URL" --arg path "$RUNTIME_PATH" '
    {repoURL: $repo, targetRevision: $rev, path: $path} as $src | .spec as $s | .status.operationState as $op
    | ($s.source == $src) and $s.project == "rhoai-demo" and (.metadata.ownerReferences // [] | length) == 0 and .metadata.deletionTimestamp == null
    and ($op.phase == "Running" or $op.phase == "Succeeded") and $op.syncResult.revision == $rev and $op.syncResult.source == $src
    and ($s.syncPolicy.syncOptions | index("RespectIgnoreDifferences=true")) != null
    and all(["Secret", "openshell-credentials", ["/data/key-encryption-key"]], ["ConfigMap", "openshell-identity", ["/data/issuer"]],
        ["ConfigMap", "openshell-runtime-ready", ["/data/controller-ready", "/data/source-revision", "/data/controller-csv-uid"]];
      . as [$k, $n, $p] | any($s.ignoreDifferences[]?; (.group // "") == "" and .kind == $k and .name == $n and .namespace == "openshell"
        and (.jsonPointers == $p or .jsonPointers == ["/data"])))' >/dev/null ||
    fail "060-openshell-runtime is not this revision's operation, or a runtime field delegation is missing"
  tracked namespace openshell openshell >/dev/null
  tracked configmap openshell-identity openshell >/dev/null
  tracked configmap openshell-runtime-ready openshell >/dev/null
  tracked secret openshell-credentials openshell >/dev/null
  # The retained key decodes to 32 bytes; a new one is generated only when no runtime storage exists yet.
  if get secret openshell-credentials -n openshell | jq -e '(.data // {})["key-encryption-key"] // "" | . != ""' >/dev/null; then
    [[ $(oc --request-timeout=15s get secret openshell-credentials -n openshell -o jsonpath='{.data.key-encryption-key}' | base64 -d | base64 -d | wc -c | tr -d ' ') == 32 ]] ||
      fail "Invalid retained encryption key"
  else
    # Not get(): --ignore-not-found prints nothing for an empty list, which would read as retained storage.
    [[ $(oc --request-timeout=15s get pvc -n openshell -o json | jq '.items | length') == 0 ]] ||
      fail "Missing key with retained storage; rotation refused"
    KEY=$(openssl rand 32 | base64 | tr -d '\n' | base64 | tr -d '\n') jq -n -c '{"key-encryption-key": $ENV.KEY}' |
      patch_data secret openshell-credentials openshell
  fi
  keycloak_base
  issuer="$KC_BASE/realms/openshell"
  curl -s --max-time 15 "$issuer/.well-known/openid-configuration" | jq -e --arg i "$issuer" '.issuer == $i and (.jwks_uri | startswith($i + "/"))' >/dev/null ||
    fail "Issuer discovery mismatch"
  jq -n -c --arg i "$issuer" '{issuer: $i}' | patch_data configmap openshell-identity openshell
  [[ "${1:-}" == --prepare-only ]] && { log_info "Runtime issuer and retained key initialized; controller gate remains closed"; return; }
  sub=$(tracked subscription agent-sandbox-operator agent-sandbox-system)
  jq -e '.spec.installPlanApproval == "Automatic" and .spec.source == "redhat-operators" and .spec.channel == "preview-0.9"
    and .status.installedCSV == .status.currentCSV' <<<"$sub" >/dev/null || fail "Agent sandbox Subscription differs"
  installed=$(jq -r '.status.installedCSV' <<<"$sub")
  csv=$(get csv "$installed" -n agent-sandbox-system)
  jq -e '.status.phase == "Succeeded" and (.spec.version | split(".")[:2]) == ["0", "9"] and (.spec.install.spec.deployments | length) > 0' <<<"$csv" >/dev/null ||
    fail "Agent sandbox CSV is not a Succeeded 0.9 release"
  while IFS= read -r declared; do
    get deployment "$(jq -r '.name' <<<"$declared")" -n agent-sandbox-system | jq -e --argjson d "$declared" --arg uid "$(jq -r '.metadata.uid' <<<"$csv")" '
      (.spec.replicas // 1) as $n | .status as $s
      | any(.metadata.ownerReferences[]?; .uid == $uid and .kind == "ClusterServiceVersion" and (.apiVersion | startswith("operators.coreos.com/")))
      and $n >= 1 and $s.observedGeneration == .metadata.generation
      and all("replicas", "updatedReplicas", "availableReplicas", "readyReplicas"; $s[.] == $n)
      and ([.spec.template.spec.containers[] | {name, image}]) as $live
      | all($d.spec.template.spec.containers[]; (.image | contains("@sha256:")) and ({name, image} | IN($live[])))' >/dev/null ||
      fail "Native controller rollout incomplete or its image differs"
  done < <(jq -c '.spec.install.spec.deployments[]' <<<"$csv")
  get crd sandboxes.agents.x-k8s.io | jq -e 'any(.status.conditions[]?; .type == "Established" and .status == "True")
    and any(.spec.versions[]; .served and (.name == "v1alpha1" or .name == "v1beta1"))' >/dev/null || fail "Sandbox API is not served"
  jq -n -c --arg rev "$REVISION" --arg uid "$(jq -r '.metadata.uid' <<<"$csv")" '{"controller-ready": "true", "source-revision": $rev, "controller-csv-uid": $uid}' |
    patch_data configmap openshell-runtime-ready openshell
  log_success "Native Automatic CSV, controller and Sandbox API qualified; startup barrier released"
}
# Port-forward a Service; prints the local port.
forward() {
  local log="$W/forward-$2.log" port
  oc port-forward -n "$1" "service/$2" ":$3" --address=127.0.0.1 >"$log" 2>&1 &
  echo "$!" >>"$W/pids"; disown "$!" 2>/dev/null || true
  for _ in $(seq 1 75); do
    port=$(sed -n 's/^Forwarding from 127.0.0.1:\([0-9]*\) .*/\1/p' "$log" | head -1)
    [[ -n "$port" ]] && { echo "$port"; return 0; }
    sleep 0.2
  done
  fail "Port-forward to $2 unavailable"
}
# The ai-agents gateway workspace with ai-admin as its only administrator, through the pinned native CLI and a
# private temporary profile holding the bootstrap token (removed on exit). No sandbox, provider or model changes.
ai_agents_setup() {
  local pins="$REPO_ROOT/$RUNTIME_PATH/chart/source-pins.json" cli issuer user uid id token port home dir labels
  cli=${RHOAI_STAGE060_OPENSHELL_CLI:-$HOME/.local/share/rhoai3-demo/openshell-$(jq -r '.cliRelease' "$pins")/bin/openshell}
  [[ -f "$cli" && $(shasum -a 256 "$cli" | cut -d' ' -f1) == $(jq -r '.cliBinarySha256' "$pins") ]] ||
    fail "Install the pinned OpenShell CLI at $cli or set RHOAI_STAGE060_OPENSHELL_CLI (chart/source-pins.json cliBinarySha256)"
  get applications.argoproj.io 060-openshell-runtime -n openshift-gitops | jq -e --arg rev "$REVISION" '.spec.source.targetRevision == $rev
    and .status.sync.revision == $rev and .status.sync.status == "Synced" and .status.health.status == "Healthy" and .operation == null' >/dev/null ||
    fail "Exact runtime GitOps revision is not ready"
  get namespace ai-agents | jq -e '.metadata.labels["rhoai3.redhat.com/openshell-workspace"] == "true" and .metadata.labels["opendatahub.io/dashboard"] == "true"
    and .metadata.deletionTimestamp == null' >/dev/null || fail "GitOps workspace namespace is not admitted"
  get rolebinding openshell-sandbox -n ai-agents | jq -e '.roleRef == {apiGroup: "rbac.authorization.k8s.io", kind: "Role", name: "openshell-sandbox"}
    and .subjects == [{kind: "ServiceAccount", name: "openshell", namespace: "openshell"}]' >/dev/null || fail "Native gateway workspace binding differs"
  issuer=$(oc --request-timeout=15s get configmap openshell-identity -n openshell -o jsonpath='{.data.issuer}')
  [[ "$issuer" == https://*/realms/openshell ]] || fail "Unexpected native issuer"
  keycloak_base; kc_login
  user=$(realm "/users?username=ai-admin&exact=true")
  uid=$(oc --request-timeout=15s get user ai-admin -o jsonpath='{.metadata.uid}')
  jq -e --arg m "$MARKER" --arg u "$uid" 'length == 1 and .[0].enabled and .[0].attributes["openshell-managed"] == [$m] and .[0].attributes["openshift-uid"] == [$u]' \
    <<<"$user" >/dev/null || fail "Managed ai-admin identity is absent, ambiguous or mapped differently"
  id=$(jq -r '.[0].id' <<<"$user")
  realm "/users/$id/federated-identity" | jq -e --arg u "$uid" '. == [{identityProvider: "openshift-v4", userId: $u, userName: "ai-admin"}]' >/dev/null ||
    fail "Native broker identity mapping differs"
  token=$(get secret openshell-auth -n keycloak | jq -j '"grant_type=client_credentials&client_id=openshell-bootstrap&client_secret=\(.data["bootstrap-client-secret"] | @base64d | @uri)"' |
    curl -s --max-time 15 --data-binary @- "$issuer/protocol/openid-connect/token" | jq -r '.access_token // empty')
  [[ -n "$token" ]] || fail "Bootstrap token request failed"
  CLAIMS=$(cut -d. -f2 <<<"$token" | tr '_-' '/+' | awk '{ while (length($0) % 4) $0 = $0 "="; print }' | base64 -d)
  jq -e --arg i "$issuer" '.iss == $i and (.realm_access.roles | index("openshell-platform-admin")) != null' <<<"$CLAIMS" >/dev/null ||
    fail "Native bootstrap is not platform administrator"
  port=$(forward openshell openshell 8080)
  home="$W/cli-home" dir="$W/cli-home/openshell/gateways/openshell"
  mkdir -p "$dir/mtls" && chmod 700 "$home"
  echo openshell >"$home/openshell/active_gateway"
  jq -n -c --arg i "$issuer" --argjson p "$port" '{name: "openshell", gateway_endpoint: "https://127.0.0.1:\($p)", is_remote: true, gateway_port: $p,
    auth_mode: "oidc", oidc_issuer: $i, oidc_client_id: "openshell-bootstrap", oidc_audience: "openshell-gateway"}' >"$dir/metadata.json"
  oc --request-timeout=15s get secret openshell-server-tls -n openshell -o jsonpath='{.data.ca\.crt}' | base64 -d >"$dir/mtls/ca.crt"
  (umask 077; TOKEN=$token jq -n -c --arg i "$issuer" --argjson exp "$(jq '.exp' <<<"$CLAIMS")" \
    '{access_token: $ENV.TOKEN, expires_at: $exp, issuer: $i, client_id: "openshell-bootstrap"}' >"$dir/oidc_token.json")
  ocli() { XDG_CONFIG_HOME="$home" "$cli" --gateway openshell "$@" 2>/dev/null || fail "Bounded native workspace operation failed (errors suppressed)"; }
  listed() { ocli "$@" -o json | jq -e -c 'if (.next_page_token // "") != "" then error("more than one page") else . end' ||
    fail "Native workspace inventory exceeds one page; no partial reconciliation"; }
  LABELS='{"app.kubernetes.io/managed-by":"openshell-runtime","app.kubernetes.io/part-of":"rhoai3-coding-demo"}'
  case "$(listed workspace list | jq -r --argjson l "$LABELS" '[.workspaces[] | select(.name == "ai-agents")]
      | if length == 0 then "absent" elif length == 1 and .[0].labels == $l and .[0].status == "Active" then "ours" else "foreign" end')" in
    absent) ocli workspace create --name ai-agents --label app.kubernetes.io/managed-by=openshell-runtime --label app.kubernetes.io/part-of=rhoai3-coding-demo >/dev/null ;;
    ours) ;;
    *) fail "Foreign, ambiguous or inactive ai-agents workspace; takeover refused" ;;
  esac
  case "$(listed workspace member list --workspace ai-agents | jq -r --arg id "$id" '.members
      | if length == 0 then "none" elif length == 1 and .[0].subject == $id and .[0].role == "admin" then "ours" else "foreign" end')" in
    none) ocli workspace member add --workspace ai-agents --subject "$id" --role admin >/dev/null ;;
    ours) ;;
    *) fail "Unexpected native membership; rewriting refused" ;;
  esac
  listed workspace member list --workspace ai-agents | jq -e --arg id "$id" '.members | length == 1 and .[0].subject == $id and .[0].role == "admin"' >/dev/null ||
    fail "Native membership readback differs"
  rm -rf "$home"
  log_success "Workspace ai-agents with ai-admin as its native administrator (configuration only; no agent or inference)"
}

deploy_runtime() {
  local deadline
  check_operator_policy "$REPO_ROOT/$RUNTIME_PATH/chart/controller"
  idle 060-openshell-runtime
  "$STAGE_APPS" preflight 060 --repo-url "$GIT_REPO_URL" --app 060-openshell-runtime
  "$STAGE_APPS" apply 060 --app 060-openshell-runtime --revision "$REVISION" --repo-url "$GIT_REPO_URL"
  "$STAGE_APPS" sync 060 --app 060-openshell-runtime
  deadline=$((SECONDS + 180))
  until oc --request-timeout=10s get secret/openshell-credentials configmap/openshell-identity configmap/openshell-runtime-ready -n openshell >/dev/null 2>&1; do
    (( SECONDS < deadline )) || fail "Runtime prerequisite creation timed out"
    sleep 5
  done
  # The sync request precedes status population; wait for this revision's own operation.
  deadline=$((SECONDS + 60))
  until get applications.argoproj.io 060-openshell-runtime -n openshift-gitops | jq -e --arg rev "$REVISION" '.status.operationState as $o
      | ($o.phase == "Running" or $o.phase == "Succeeded") and $o.syncResult.revision == $rev and $o.syncResult.source == .spec.source' >/dev/null; do
    (( SECONDS < deadline )) || fail "The runtime sync operation did not start within 60 s"
    sleep 3
  done
  runtime_setup --prepare-only
  check_operator_policy "$REPO_ROOT/$RUNTIME_PATH/chart/controller" --wait 900
  runtime_setup
  "$STAGE_APPS" wait 060 --app 060-openshell-runtime --revision "$REVISION" --repo-url "$GIT_REPO_URL" --timeout 600
  ai_agents_setup
}

# ── 060-agent-console ─────────────────────────────────────────────────────────
deploy_console() {
  get applications.argoproj.io 060-openshell-runtime -n openshift-gitops | jq -e --arg repo "$GIT_REPO_URL" --arg path "$RUNTIME_PATH" '.metadata.deletionTimestamp == null
    and .status.health.status == "Healthy" and .status.sync.status == "Synced" and .spec.source.repoURL == $repo and .spec.source.path == $path' >/dev/null ||
    fail "The OpenShell runtime must be deployed and healthy first"
  get crd sandboxes.agents.x-k8s.io | jq -e 'any(.status.conditions[]?; .type == "Established" and .status == "True")' >/dev/null ||
    fail "Native Sandbox CRD is not established"
  "$STAGE_APPS" delegated 010 OdhDashboardConfig odh-dashboard-config redhat-ods-applications --group opendatahub.io | grep -qx /spec/dashboardConfig/agentOps ||
    fail "Stage 010 has not delegated agentOps"
  for ns in openshell-admin openshell-developer; do
    [[ -n "$(get namespace "$ns")" ]] || fail "Workspace namespace $ns is missing"
  done
  "$STAGE_APPS" preflight 060 --repo-url "$GIT_REPO_URL" --app 060-agent-console
  reconcile 060-agent-console 300
  "$SCRIPT_DIR/validate.sh" --component 060-agent-console
}

# ── 060-mcp-platform ──────────────────────────────────────────────────────────
deploy_mcp_platform() {
  "$STAGE_APPS" delegated 010 DataScienceCluster default-dsc --group datasciencecluster.opendatahub.io | grep -qx /spec/components/mcplifecycleoperator ||
    fail "Stage 010 has not delegated the native MCP component"
  get datasciencecluster default-dsc | jq -e '.metadata.deletionTimestamp == null' >/dev/null || fail "DataScienceCluster missing or terminating"
  get odhdashboardconfig odh-dashboard-config -n redhat-ods-applications | jq -e '.spec.dashboardConfig.mcpCatalog == true' >/dev/null ||
    fail "The MCP Catalog must already be enabled (Stage 040)"
  idle 060-mcp-platform
  "$STAGE_APPS" preflight 060 --repo-url "$GIT_REPO_URL" --app 060-mcp-platform
  reconcile 060-mcp-platform 300
  # The operator, its API and its workload follow the DataScienceCluster by minutes.
  local deadline=$((SECONDS + 180))
  until "$SCRIPT_DIR/validate.sh" --component 060-mcp-platform >/dev/null 2>&1; do
    (( SECONDS < deadline )) || { "$SCRIPT_DIR/validate.sh" --component 060-mcp-platform || true; fail "Native MCP operator not ready"; }
    sleep 5
  done
}

# ── 060-agent-tools ───────────────────────────────────────────────────────────
deploy_agent_tools() {
  get datasciencecluster default-dsc | jq -e '.spec.components.mcplifecycleoperator.managementState == "Managed"' >/dev/null ||
    fail "Native MCP lifecycle must be enabled first (060-mcp-platform)"
  get crd mcpservers.mcp.x-k8s.io | jq -e 'any(.spec.versions[]; .name == "v1alpha1" and .served)
    and any(.status.conditions[]?; .type == "Established" and .status == "True")' >/dev/null || fail "Native MCPServer API is not served"
  idle 060-agent-tools
  "$STAGE_APPS" preflight 060 --repo-url "$GIT_REPO_URL" --app 060-agent-tools
  # Never adopt an existing native Service implicitly: a Service without its MCPServer is foreign.
  for name in openshift-mcp-server openshift-mcp-server-rw; do
    [[ -n "$(get mcpservers.mcp.x-k8s.io "$name" -n mcp-servers 2>/dev/null)" || -z "$(get service "$name" -n mcp-servers 2>/dev/null)" ]] ||
      fail "Existing Service $name cannot be adopted implicitly"
  done
  reconcile 060-agent-tools 600
  "$SCRIPT_DIR/validate.sh" --component 060-agent-tools
}

case "$COMPONENT" in
  "") deploy_identity; deploy_runtime; deploy_console; deploy_mcp_platform; deploy_agent_tools ;;
  060-openshell-identity) deploy_identity ;;
  060-openshell-runtime) deploy_runtime ;;
  060-agent-console) deploy_console ;;
  060-mcp-platform) deploy_mcp_platform ;;
  060-agent-tools) deploy_agent_tools ;;
  *) fail "Unknown component $COMPONENT" ;;
esac
log_success "Stage 060 ${COMPONENT:-components} reconciled at ${REVISION:0:12}; persona handshake and agent lifecycle remain explicit acceptance steps."
