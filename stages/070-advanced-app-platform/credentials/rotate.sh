#!/usr/bin/env bash
# Rotate one Stage 070 platform credential through its provider's API, write the new value into its Secret(s), then
# prove the replacement works and the predecessor is refused. Explicit operator action; never part of a routine sync.
# Changes: the provider credential and the named Secret keys of COMPONENT (see README.md); annotation_copy changes
# only Secret metadata. Refuses unless the checkout and the live Stage 070 Applications are exactly the reviewed
# published REVISION, --execute is given and the report file does not exist yet. Not safe to rerun blindly: one run per
# component with a new report path; a partial result needs diagnosis first. The report holds results, never credentials.
# Usage: stages/070-advanced-app-platform/credentials/rotate.sh COMPONENT --revision SHA --report FILE [--repo-url URL] [--secret NAMESPACE/NAME] [--execute]
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
source "$REPO_ROOT/scripts/lib.sh"
COMPONENTS="gitlab_oidc scm_client publisher devspaces_oauth sonar sonar_projects delivery_writers argo mta annotation_copy"
usage() { sed -n 's/^# Usage: //p' "$0" >&2; exit 1; }
COMPONENT="" REVISION="" REPORT="" REPO_URL="" SECRET="" EXECUTE=false
while [[ $# -gt 0 ]]; do
  case "$1" in
    --revision) [[ $# -ge 2 ]] || usage; REVISION=$2; shift 2 ;;
    --report) [[ $# -ge 2 ]] || usage; REPORT=$2; shift 2 ;;
    --repo-url) [[ $# -ge 2 ]] || usage; REPO_URL=$2; shift 2 ;;
    --secret) [[ $# -ge 2 ]] || usage; SECRET=$2; shift 2 ;;
    --execute) EXECUTE=true; shift ;;
    -*) usage ;;
    *) [[ -z "$COMPONENT" && " $COMPONENTS " == *" $1 "* ]] || usage; COMPONENT=$1; shift ;;
  esac
done
[[ -n "$COMPONENT" && -n "$REVISION" && -n "$REPORT" ]] || usage
if [[ -n "$SECRET" && "$COMPONENT" != annotation_copy ]] || [[ -z "$SECRET" && "$COMPONENT" == annotation_copy ]]; then
  log_error "--secret is required only for annotation_copy"; exit 1
fi
load_env
check_oc_logged_in
REPO_URL=${REPO_URL:-${GIT_REPO_URL:-}}
[[ -n "$REPO_URL" ]] || { log_error "Pass --repo-url or set GIT_REPO_URL in .env"; exit 1; }

PROVISIONER=platform-provisioner
SONAR_KEY=rhoai3.io/sonar-project-key
SONAR_TYPE=rhoai3.io/sonar-token-type
SONAR_NAME=rhoai3.io/sonar-token-name
LAST_APPLIED=kubectl.kubernetes.io/last-applied-configuration
die() { log_error "$*"; exit 1; }

# ── Guards: reviewed published revision, deployed and reconciled; explicit execution; a new report ───────────────────
# A locally modified rotation implementation or another publication refuses, as deployment refuses unpublished source.
SELECTED=$("$REPO_ROOT/scripts/stage-apps.sh" select 070 --ref "$REVISION" --repo-url "$REPO_URL") ||
  die "Use the reviewed published correction revision"
[[ "$SELECTED" == "$REVISION" ]] || die "Use the reviewed published correction revision"
"$REPO_ROOT/scripts/stage-apps.sh" status 070 --revision "$REVISION" --repo-url "$REPO_URL" >/dev/null ||
  die "Deploy and qualify the corrected pinned stage before rotation"
[[ "$EXECUTE" == true ]] || die "Rotation requires the explicit --execute flag"
[[ ! -e "$REPORT" ]] || die "Preserve the existing rotation report; do not silently rotate twice"

# ── HTTP: tokens and passwords reach curl only through --config, bodies only through stdin ──────────────────────────
# _curl METHOD URL AUTH KIND: AUTH names a variable holding one header line (empty name: no credential); KIND is none,
# json or form (body on stdin). Prints the body and, on a last line, the HTTP status.
_curl() {
  local method=$1 url=$2 auth=${3:-} kind=${4:-none} body=()
  case "$kind" in
    json) body=(-H 'Content-Type: application/json' --data-binary @-) ;;
    form) body=(-H 'Content-Type: application/x-www-form-urlencoded' --data-binary @-) ;;
  esac
  if [[ -z "$auth" ]]; then
    curl -sS --max-time 60 -X "$method" -w '\n%{http_code}' ${body[@]+"${body[@]}"} "$url" || die "$method ${url%%\?*} failed"
  else
    curl -sS --max-time 60 -X "$method" -w '\n%{http_code}' ${body[@]+"${body[@]}"} \
      --config <(printf 'header = "%s"\n' "${!auth}") "$url" || die "$method ${url%%\?*} failed"
  fi
}
# http ...: the body of a 2xx response; anything else stops the run (API responses never reach logs).
http() {
  local response code
  response=$(_curl "$@") || exit 1
  code=${response##*$'\n'}
  [[ "$code" == 2?? ]] || die "$1 ${2%%\?*} returned HTTP $code"
  printf '%s' "${response%$'\n'*}"
}
# http_code ...: the status only (body discarded).
http_code() { local response; response=$(_curl "$@") || exit 1; printf '%s' "${response##*$'\n'}"; }
# rejected CODE: true for 400/401/403, false for 2xx, anything else stops the run.
rejected() {
  case "$1" in
    400|401|403) echo true ;;
    2??) echo false ;;
    *) die "Unexpected HTTP $1 while checking a refused credential" ;;
  esac
}
FORM='def form: to_entries | map("\(.key | @uri)=\(.value | tostring | @uri)") | join("&");'
basic() { printf '%s' "$1" | base64 | tr -d '\n'; }
hex12() { od -An -N6 -tx1 /dev/urandom | tr -d ' \n'; }
route() {
  local host
  host=$(oc get route "$1" -n "$2" -o jsonpath='{.spec.host}') && [[ -n "$host" ]] || die "Route $2/$1 not found"
  echo "https://$host"
}
# secret_json NAMESPACE NAME: the Secret object (kept in variables only, never printed).
secret_json() { oc --request-timeout=30s get secret "$2" -n "$1" -o json; }
# field JSON KEY: one decoded data key.
field() { printf '%s' "$1" | jq -r --arg k "$2" '.data[$k] // empty | @base64d'; }
# claims TOKEN_VARIABLE: the JWT payload of the token held in that variable.
claims() {
  printf '%s' "${!1}" | jq -R -c 'split(".")[1] | gsub("-"; "+") | gsub("_"; "/")
    | ((4 - length % 4) % 4) as $pad | (if $pad > 0 then . + ("=" * $pad) else . end) | @base64d | fromjson'
}

# update_secret NAMESPACE NAME: merges the stringData object on stdin (null: metadata only) into the Secret, retaining
# unrelated keys and identity metadata and dropping the last-applied copy; creates the Secret when it is absent.
update_secret() {
  local ns=$1 name=$2 values error
  values=$(cat)
  if error=$(oc get secret "$name" -n "$ns" -o name 2>&1 >/dev/null); then
    :
  elif [[ "$error" == *"(NotFound)"* ]]; then
    if printf '%s' "$values" | jq -c --arg n "$name" --arg ns "$ns" '{apiVersion: "v1", kind: "Secret",
        metadata: {name: $n, namespace: $ns, annotations: {}}} + (if . == null then {} else {stringData: .} end)' |
        oc create -f - -o name >/dev/null 2>"$WORK/create.err"; then
      return 0
    fi
    grep -q '(AlreadyExists)' "$WORK/create.err" || die "Secret creation refused; payload redacted"
  elif [[ "$error" != *"(Forbidden)"* ]]; then
    die "Secret lookup refused; payload redacted"
  fi
  printf '%s' "$values" | jq -c --arg la "$LAST_APPLIED" '(if . == null then {} else {stringData: .} end)
      + {metadata: {annotations: {($la): null}}}' |
    oc patch secret "$name" -n "$ns" --type=merge --patch-file=/dev/stdin -o name >/dev/null ||
    die "Secret update refused; payload redacted"
}

# ── Report: written on every exit once a rotation starts; results only ────────────────────────────────────────────
WORK=$(mktemp -d)
CHECKS='{}'
PHASE=starting
GITLAB_ROOT_HEADER=""
add_check() { CHECKS=$(printf '%s' "$CHECKS" | jq -c --arg k "$1" --argjson v "$2" '. + {($k): $v}'); }
finish() {
  local rc=$? code
  set +e
  if [[ -n "$GITLAB_ROOT_HEADER" ]]; then
    # Revoke the temporary root token; a failed revocation is reported, never retried silently.
    code=$( (_curl DELETE "$GITLAB/api/v4/personal_access_tokens/self" GITLAB_ROOT_HEADER none) | tail -n 1)
    [[ "$code" == 2?? ]] || log_error "Revoke the temporary GitLab token stage070-reviewed-rotation by hand (HTTP ${code:-none})"
    GITLAB_ROOT_HEADER=""
  fi
  mkdir -p "$(dirname "$REPORT")"
  (umask 077; jq -n --arg component "$COMPONENT" --arg revision "$REVISION" --arg phase "$PHASE" --argjson checks "$CHECKS" \
    --argjson done "$([[ "$PHASE" == starting ]] && echo false || echo true)" '{utc: (now | todate), component: $component,
      revision: $revision, passed: ($phase == "verified"), phase: $phase} + (if $done then {checks: $checks} else {} end)' >"$REPORT")
  chmod 600 "$REPORT"
  rm -rf "$WORK"
  exit "$rc"
}
trap finish EXIT

# ── Providers ─────────────────────────────────────────────────────────────────────────────────────────────────────
SSO="" GITLAB="" KEYCLOAK_HEADER=""
providers() {
  SSO=$(route keycloak keycloak)
  GITLAB=$(route gitlab gitlab-system)
}
# Keycloak master-realm admin token, from keycloak-initial-admin (all its keys are form fields, as the admin CLI login).
# Run in the main shell (not inside $(...)) so the token is kept for the following calls.
keycloak_login() {
  local response
  [[ -z "$KEYCLOAK_HEADER" ]] || return 0
  response=$(secret_json keycloak keycloak-initial-admin | jq -j "$FORM"' .data | map_values(@base64d)
      | {grant_type: "password", client_id: "admin-cli"} + . | form' |
    http POST "$SSO/realms/master/protocol/openid-connect/token" "" form)
  KEYCLOAK_HEADER="Authorization: Bearer $(printf '%s' "$response" | jq -er '.access_token')"
}
keycloak() { http "$1" "$SSO/admin/realms/platform/$2" KEYCLOAK_HEADER "${3:-none}"; }
keycloak_code() { http_code "$1" "$SSO/admin/realms/platform/$2" KEYCLOAK_HEADER none; }
# GitLab root API through a one-day personal access token minted in the one Ready trusted toolbox; revoked on exit.
# gitlab_root_login runs in the main shell before the first root_api call, so the exit trap can revoke the token.
gitlab_root_login() {
  local pod token
  [[ -z "$GITLAB_ROOT_HEADER" ]] || return 0
  pod=$(oc get pods -n gitlab-system -l app=toolbox,release=gitlab -o json | jq -r '[.items[] | select(any(.status.conditions[]?;
      .type == "Ready" and .status == "True"))] | if length == 1 then .[0].metadata.name else empty end')
  [[ -n "$pod" ]] || die "Expected one Ready trusted GitLab toolbox"
  token=$(oc exec -n gitlab-system "$pod" -c toolbox -- gitlab-rails runner \
    "u=User.find_by_username!('root'); t=u.personal_access_tokens.create!(name:'stage070-reviewed-rotation',scopes:['api'],expires_at:1.day.from_now); puts t.token" |
    tail -n 1)
  [[ "$token" == glpat-* ]] || die "GitLab did not produce its temporary operator token"
  GITLAB_ROOT_HEADER="PRIVATE-TOKEN: $token"
}
root_api() {
  [[ -n "$GITLAB_ROOT_HEADER" ]] || die "gitlab_root_login must run first"
  http "$1" "$GITLAB/api/v4/$2" GITLAB_ROOT_HEADER "${3:-none}"
}

# ── Keycloak confidential clients ─────────────────────────────────────────────────────────────────────────────────
client_id() {
  keycloak GET "clients?clientId=$1" | jq -er --arg c "$1" 'if length == 1 and .[0].clientId == $c then .[0].id else empty end' ||
    die "Keycloak client identity is ambiguous"
}
# rotate_client CLIENT PERSIST: regenerate the client secret, persist it with the PERSIST function (reads NEW_SECRET),
# drop the rotated (grace) secret, and prove the old one is no longer current.
rotate_client() {
  local name=$1 persist=$2 client old current code
  keycloak_login
  client=$(client_id "$name")
  old=$(keycloak GET "clients/$client/client-secret" | jq -r '.value')
  NEW_SECRET=$(keycloak POST "clients/$client/client-secret" | jq -r '.value')
  [[ "$NEW_SECRET" != "$old" ]] || die "Keycloak did not replace the credential"
  "$persist"
  code=$(keycloak_code DELETE "clients/$client/client-secret/rotated")
  [[ "$code" == 2?? || "$code" == 404 ]] || die "Removing the rotated secret returned HTTP $code"
  code=$(OLD="$old" CLIENT="$name" jq -j -n "$FORM"' {grant_type: "client_credentials", client_id: $ENV.CLIENT,
      client_secret: $ENV.OLD} | form' | http_code POST "$SSO/realms/platform/protocol/openid-connect/token" "" form)
  # Browser-only clients reject this grant even with a good secret; their proof is the current-secret read-back.
  add_check old_client_credentials_grant_refused "$(rejected "$code")"
  current=$(keycloak GET "clients/$client/client-secret" | jq -r '.value')
  add_check client_id_preserved "$([[ $(client_id "$name") == "$client" ]] && echo true || echo false)"
  add_check new_current_secret_matches "$([[ "$current" == "$NEW_SECRET" ]] && echo true || echo false)"
  add_check old_secret_not_current "$([[ "$current" != "$old" ]] && echo true || echo false)"
}

rotate_gitlab_oidc() {
  local provider
  provider=$(secret_json gitlab-system gitlab-oidc | jq -c '.data.provider | @base64d | fromjson')
  printf '%s' "$provider" | jq -e --arg iss "$SSO/realms/platform" \
    '.args.client_options.identifier == "gitlab" and .args.issuer == $iss' >/dev/null ||
    die "GitLab provider is not bound to the retained platform issuer"
  PROVIDER=$provider
  persist_gitlab_oidc() {
    printf '%s' "$PROVIDER" | NEW_SECRET="$NEW_SECRET" jq -c '{provider: (.args.client_options.secret = $ENV.NEW_SECRET | tojson)}' |
      update_secret gitlab-system gitlab-oidc
  }
  rotate_client gitlab persist_gitlab_oidc
  oc rollout restart deployment/gitlab-webservice-default -n gitlab-system >/dev/null
  oc rollout status deployment/gitlab-webservice-default -n gitlab-system --timeout=300s >/dev/null
}

rotate_scm_client() {
  persist_scm_client() {
    NEW_SECRET="$NEW_SECRET" jq -n -c '{client_secret: $ENV.NEW_SECRET}' | update_secret gitlab-system stage070-scm-provisioner
  }
  rotate_client stage070-scm-provisioner persist_scm_client
}

# ── GitLab ────────────────────────────────────────────────────────────────────────────────────────────────────────
rotate_publisher() {
  local stored previous user new old_header new_header
  stored=$(secret_json rhdh gitlab-publisher)
  old_header="PRIVATE-TOKEN: $(field "$stored" token)"
  previous=$(http GET "$GITLAB/api/v4/personal_access_tokens/self" old_header)
  gitlab_root_login
  user=$(root_api GET "users/$(printf '%s' "$previous" | jq -r '.user_id')")
  [[ $(printf '%s' "$user" | jq -r '.username') == rhdh-publisher ]] || die "Publisher token belongs to another account"
  # Create and persist a replacement before revoking the predecessor.
  new=$(printf '%s' "$previous" | jq -c --arg name "stage070-publisher-rotation-$(hex12)" '{name: $name, scopes, expires_at}' |
    root_api POST "users/$(printf '%s' "$user" | jq -r '.id')/personal_access_tokens" json)
  printf '%s' "$new" | jq -e --argjson prev "$previous" '(.scopes | sort) == ($prev.scopes | sort)
      and .user_id == $prev.user_id and .expires_at == $prev.expires_at' >/dev/null ||
    die "Publisher replacement changed authority"
  printf '%s' "$new" | jq -c '{token}' | update_secret rhdh gitlab-publisher
  printf '%s' "$new" | jq -c '{GITLAB_PUBLISHER_TOKEN: .token}' | update_secret rhdh rhdh-gitlab
  new_header="PRIVATE-TOKEN: $(printf '%s' "$new" | jq -r '.token')"
  http GET "$GITLAB/api/v4/personal_access_tokens/self" new_header >/dev/null
  root_api DELETE "personal_access_tokens/$(printf '%s' "$previous" | jq -r '.id')" >/dev/null
  add_check identity_scopes_expiry_preserved "$(printf '%s' "$new" | jq --argjson prev "$previous" '.expires_at == $prev.expires_at')"
  add_check old_token_refused "$(rejected "$(http_code GET "$GITLAB/api/v4/personal_access_tokens/self" old_header)")"
}

rotate_devspaces_oauth() {
  local old app_id previous new
  old=$(secret_json openshift-devspaces gitlab-oauth-config)
  app_id=$(field "$old" id)
  gitlab_root_login
  previous=$(root_api GET applications | jq -c --arg id "$app_id" '[.[] | select(.application_id == $id)]
      | if length == 1 and .[0].application_name == "Dev Spaces" then .[0] else empty end')
  [[ -n "$previous" ]] || die "Dev Spaces OAuth application identity mismatch"
  new=$(root_api POST "applications/$(printf '%s' "$previous" | jq -r '.id')/renew-secret")
  # GitLab returns application_name/callback_url, unlike request fields.
  # https://docs.gitlab.com/api/applications/#renew-an-application-secret
  printf '%s' "$new" | OLD_SECRET="$(field "$old" secret)" jq -e --argjson prev "$previous" 'def scopes: if type == "string"
      then split(" ") else . end | sort;
      ([.id, .application_id, .application_name, .callback_url, .confidential]
        == [$prev.id, $prev.application_id, $prev.application_name, $prev.callback_url, $prev.confidential])
      and (.scopes | scopes) == ($prev.scopes | scopes) and (.secret // "") != "" and .secret != $ENV.OLD_SECRET' >/dev/null ||
    die "OAuth renewal changed authority or retained the old secret"
  printf '%s' "$new" | jq -c '{secret}' | update_secret openshift-devspaces gitlab-oauth-config
  # invalid_grant proves client authentication; invalid_client rejects it.
  oauth_error() {
    local response code
    response=$(SECRET="$1" ID="$app_id" REDIRECT="$(printf '%s' "$previous" | jq -r '.callback_url')" jq -j -n "$FORM"'
        {grant_type: "authorization_code", client_id: $ENV.ID, client_secret: $ENV.SECRET, code: "stage070-invalid-code",
         redirect_uri: $ENV.REDIRECT} | form' | _curl POST "$GITLAB/oauth/token" "" form)
    code=${response##*$'\n'}
    [[ "$code" != 2?? ]] || die "An intentionally invalid authorization code was accepted"
    printf '%s' "${response%$'\n'*}" | jq -r '.error // empty'
  }
  add_check application_authority_preserved true
  add_check old_secret_refused "$([[ $(oauth_error "$(field "$old" secret)") == invalid_client ]] && echo true || echo false)"
  add_check new_secret_authenticates "$([[ $(oauth_error "$(printf '%s' "$new" | jq -r '.secret')") == invalid_grant ]] &&
    echo true || echo false)"
}

rotate_delivery_writers() {
  local all count i ns old_header projects expiry new new_header
  all=$(oc --request-timeout=30s get secret -A --field-selector metadata.name=gitlab-delivery-writer -o json)
  count=$(printf '%s' "$all" | jq '.items | length')
  for ((i = 0; i < count; i++)); do
    ns=$(printf '%s' "$all" | jq -r ".items[$i].metadata.namespace")
    old_header="PRIVATE-TOKEN: $(printf '%s' "$all" | jq -r ".items[$i].data.token | @base64d")"
    projects=$(http GET "$GITLAB/api/v4/projects?membership=true&simple=true" old_header)
    [[ $(printf '%s' "$projects" | jq 'length') == 1 ]] || die "Delivery writer token is not bound to exactly one project"
    expiry=$(jq -n -r 'now + 90 * 86400 | strflocaltime("%Y-%m-%d")')
    new=$(jq -n -c --arg e "$expiry" '{expires_at: $e}' |
      http POST "$GITLAB/api/v4/projects/$(printf '%s' "$projects" | jq -r '.[0].id')/access_tokens/self/rotate" old_header json)
    printf '%s' "$new" | jq -e --arg e "$expiry" '(.token // "") != "" and .expires_at == $e' >/dev/null ||
      die "GitLab did not rotate the delivery writer token"
    printf '%s' "$new" | jq -c --arg e "$expiry" '{token, expires_at: $e}' | update_secret "$ns" gitlab-delivery-writer
    new_header="PRIVATE-TOKEN: $(printf '%s' "$new" | jq -r '.token')"
    add_check "${ns}_new_valid" "$(http GET "$GITLAB/api/v4/personal_access_tokens/self" new_header | jq 'type == "object"')"
    add_check "${ns}_old_refused" "$(rejected "$(http_code GET "$GITLAB/api/v4/personal_access_tokens/self" old_header)")"
  done
}

# ── SonarQube ─────────────────────────────────────────────────────────────────────────────────────────────────────
sonar_valid() {
  local header="Authorization: Basic $(basic "$1:")"
  http GET "$SONAR/api/authentication/validate" header | jq '.valid == true'
}

rotate_sonar() {
  local admin password old control name new previous_name previous_owner
  admin=$(secret_json sonarqube sonarqube-admin)
  control=$(secret_json app-platform-build sonarqube-credentials)
  old=$(field "$control" token)
  # Pipeline host stays cluster-local; this operator tool runs externally.
  SONAR=$(route sonarqube sonarqube)
  password=$(field "$admin" password)
  [[ -n "$password" ]] || password=$(field "$admin" admin-password)
  [[ -n "$password" ]] || die "Sonar administrator secret schema mismatch"
  SONAR_ADMIN="Authorization: Basic $(basic "admin:$password")"
  previous_name=$(printf '%s' "$control" | jq -r '.metadata.annotations["rhoai3.io/control-token-name"] // "platform-pipeline"')
  previous_owner=$(printf '%s' "$control" | jq -r '.metadata.annotations["rhoai3.io/control-token-owner"] // "admin"')
  # The control credential belongs to the technical user the configure-sonarqube hook creates.
  name="platform-pipeline-rotation-$(hex12)"
  new=$(jq -j -n --arg login "$PROVISIONER" --arg name "$name" "$FORM"' {login: $login, name: $name, type: "USER_TOKEN"} | form' |
    http POST "$SONAR/api/user_tokens/generate" SONAR_ADMIN form)
  printf '%s' "$new" | jq -c '{token}' | update_secret app-platform-build sonarqube-credentials
  jq -n -c --arg name "$name" --arg owner "$PROVISIONER" \
    '{metadata: {annotations: {"rhoai3.io/control-token-name": $name, "rhoai3.io/control-token-owner": $owner}}}' |
    oc patch secret sonarqube-credentials -n app-platform-build --type=merge --patch-file=/dev/stdin >/dev/null
  jq -j -n --arg login "$previous_owner" --arg name "$previous_name" "$FORM"' {login: $login, name: $name} | form' |
    http POST "$SONAR/api/user_tokens/revoke" SONAR_ADMIN form >/dev/null
  add_check old_token_refused "$(sonar_valid "$old" | jq 'not')"
  add_check new_token_valid "$(sonar_valid "$(printf '%s' "$new" | jq -r '.token')")"
}

# Re-mint each enrolled project's analysis token under the provisioner user, update its Secret and the workspace
# mirrors, then revoke the administrator's token of the same name.
rotate_sonar_projects() {
  local admin control stored mirrors admin_tokens count i ns key name old new mirror_rows m mns mname
  admin=$(secret_json sonarqube sonarqube-admin)
  SONAR=$(route sonarqube sonarqube)
  SONAR_ADMIN="Authorization: Basic $(basic "admin:$(field "$admin" password)")"
  # SonarQube mints a project analysis token only for the calling user: authenticate as the provisioner.
  control=$(secret_json app-platform-build sonarqube-credentials)
  SONAR_PROVISIONER="Authorization: Basic $(basic "$(field "$control" token):")"
  sonar_tokens() { http GET "$SONAR/api/user_tokens/search?login=$1" SONAR_ADMIN | jq -c '.userTokens | map({(.name): .}) | add // {}'; }
  admin_tokens=$(sonar_tokens admin)
  stored=$(oc --request-timeout=30s get secret -A --field-selector metadata.name=sonarqube-credentials -o json |
    jq -c --arg t "$SONAR_TYPE" '[.items[] | select(.metadata.annotations[$t] == "PROJECT_ANALYSIS_TOKEN")]')
  mirrors=$(for mns in wksp-ai-developer wksp-ai-admin; do oc --request-timeout=30s get secret -n "$mns" -o json; done |
    jq -s -c '[.[].items[] | select(.metadata.name | endswith("-sonar-credentials"))]')
  count=$(printf '%s' "$stored" | jq 'length')
  for ((i = 0; i < count; i++)); do
    ns=$(printf '%s' "$stored" | jq -r ".[$i].metadata.namespace")
    key=$(printf '%s' "$stored" | jq -r --arg k "$SONAR_KEY" ".[$i].metadata.annotations[\$k]")
    name=$(printf '%s' "$stored" | jq -r --arg k "$SONAR_NAME" ".[$i].metadata.annotations[\$k]")
    old=$(printf '%s' "$stored" | jq -r ".[$i].data.token | @base64d")
    if ! printf '%s' "$admin_tokens" | jq -e --arg n "$name" 'has($n)' >/dev/null; then
      if sonar_tokens "$PROVISIONER" | jq -e --arg n "$name" 'has($n)' >/dev/null && [[ $(sonar_valid "$old") == true ]]; then
        add_check "${ns}_already_migrated" true
      else
        add_check "${ns}_already_migrated" false
      fi
      continue
    fi
    new=$(jq -j -n --arg name "$name" --arg key "$key" "$FORM"' {name: $name, type: "PROJECT_ANALYSIS_TOKEN", projectKey: $key} | form' |
      http POST "$SONAR/api/user_tokens/generate" SONAR_PROVISIONER form)
    printf '%s' "$new" | jq -e '.type == "PROJECT_ANALYSIS_TOKEN" and (.token // "") != ""' >/dev/null ||
      die "SonarQube did not emit a project analysis token"
    printf '%s' "$new" | jq -c '{token}' | update_secret "$ns" sonarqube-credentials
    mirror_rows=$(printf '%s' "$mirrors" | jq -r --arg k "$SONAR_KEY" --arg key "$key" \
      '.[] | select(.metadata.annotations[$k] == $key) | "\(.metadata.namespace) \(.metadata.name)"')
    while read -r mns mname; do
      [[ -z "$mname" ]] || printf '%s' "$new" | jq -c '{SONAR_TOKEN: .token}' | update_secret "$mns" "$mname"
    done <<<"$mirror_rows"
    jq -j -n --arg name "$name" "$FORM"' {login: "admin", name: $name} | form' |
      http POST "$SONAR/api/user_tokens/revoke" SONAR_ADMIN form >/dev/null
    add_check "${ns}_new_valid" "$(sonar_valid "$(printf '%s' "$new" | jq -r '.token')")"
    add_check "${ns}_old_refused" "$(sonar_valid "$old" | jq 'not')"
  done
  add_check no_admin_project_tokens_left "$(sonar_tokens admin | jq '[.[] | select(.type == "PROJECT_ANALYSIS_TOKEN")] | length == 0')"
}

# ── Argo CD: the OpenShift GitOps operator owns the rhdh local user's token (Secret rhdh-local-user, key apiToken);
#    deleting the Secret makes it issue a new one. Developer Hub's copy then follows. ─────────────────────────────────
rotate_argo() {
  local base before old_uid old_token old_claims new_claims after i argo_header
  base=$(route openshift-gitops-server openshift-gitops)
  before=$(secret_json openshift-gitops rhdh-local-user)
  old_uid=$(printf '%s' "$before" | jq -r '.metadata.uid')
  old_token=$(field "$before" apiToken)
  old_claims=$(claims old_token) || die "Argo credential is not the expected reader account"
  printf '%s' "$old_claims" | jq -e '.sub == "rhdh:apiKey" and .iss == "argocd"' >/dev/null ||
    die "Argo credential is not the expected reader account"
  oc delete secret rhdh-local-user -n openshift-gitops --wait=true >/dev/null
  NEW_TOKEN=""
  for ((i = 0; i < 60; i++)); do
    if after=$(secret_json openshift-gitops rhdh-local-user 2>/dev/null) &&
        [[ $(printf '%s' "$after" | jq -r '.metadata.uid') != "$old_uid" ]]; then
      NEW_TOKEN=$(field "$after" apiToken)
      [[ -z "$NEW_TOKEN" ]] || break
    fi
    sleep 5
  done
  [[ -n "$NEW_TOKEN" ]] || die "The GitOps operator did not issue a new reader token"
  new_claims=$(claims NEW_TOKEN) || die "Argo replacement changed reader identity or kept the old token"
  printf '%s' "$new_claims" | jq -e --argjson old "$old_claims" '.sub == $old.sub and .jti != $old.jti' >/dev/null ||
    die "Argo replacement changed reader identity or kept the old token"
  argo_header="Authorization: Bearer $NEW_TOKEN"
  add_check new_reader_valid "$(http GET "$base/api/v1/applications" argo_header | jq 'type == "object"')"
  NEW_TOKEN="$NEW_TOKEN" jq -n -c '{RHDH_ARGOCD_TOKEN: $ENV.NEW_TOKEN}' | update_secret rhdh rhdh-secrets
  add_check reader_identity_preserved true
  argo_header="Authorization: Bearer $old_token"
  add_check old_reader_refused "$(rejected "$(http_code GET "$base/api/v1/applications" argo_header)")"
}

# ── MTA: the MaaS API key of mta-maas-provisioner (subscription mta-migration-ai); no inference is made ─────────────
rotate_mta() {
  local host base old key_id previous new_id revoked code current principal=system:serviceaccount:openshift-mta:mta-maas-provisioner
  host=$(oc get gateway.gateway.networking.k8s.io maas-default-gateway -n openshift-ingress -o json |
    jq -r '[.spec.listeners[] | .hostname // "" | select(startswith("maas."))] | if length == 1 then .[0] else empty end')
  [[ -n "$host" ]] || die "Expected one MaaS API listener"
  base="https://$host/maas-api/v1/api-keys"
  MTA_HEADER="Authorization: Bearer $(oc create token mta-maas-provisioner -n openshift-mta --duration=10m)"
  old=$(secret_json openshift-mta kai-api-keys)
  key_id=$(field "$old" MAAS_KEY_ID)
  previous=$(http GET "$base/$key_id" MTA_HEADER)
  printf '%s' "$previous" | jq -e --arg p "$principal" '.username == $p and .subscription == "mta-migration-ai"' >/dev/null ||
    die "Foreign MaaS predecessor"
  NEW_KEY=$(printf '%s' "$previous" | jq -c '{name: "mta-reviewed-rotation", subscription}' | http POST "$base" MTA_HEADER json)
  printf '%s' "$NEW_KEY" | jq -c '{OPENAI_API_KEY: .key, MAAS_KEY_ID: .id}' | update_secret openshift-mta kai-api-keys
  new_id=$(printf '%s' "$NEW_KEY" | jq -r '.id')
  http DELETE "$base/$key_id" MTA_HEADER >/dev/null
  revoked=$(_curl GET "$base/$key_id" MTA_HEADER)
  code=${revoked##*$'\n'}
  if [[ "$code" == 404 ]]; then revoked='{"status":"revoked"}'
  elif [[ "$code" == 2?? ]]; then revoked=${revoked%$'\n'*}
  else die "Reading the revoked key returned HTTP $code"; fi
  current=$(http GET "$base/$new_id" MTA_HEADER)
  add_check owner_and_subscription_preserved "$(printf '%s' "$current" | jq --arg p "$principal" --argjson prev "$previous" \
    '.username == $p and .subscription == $prev.subscription')"
  add_check old_key_revoked "$(printf '%s' "$revoked" | jq '.status == "revoked"')"
  add_check new_key_active "$(printf '%s' "$current" | jq '.status == "active"')"
  add_check inference_performed false
}

# ── annotation_copy: remove the last-applied copy from one exact Secret; values, type and UID unchanged ──────────────
rotate_annotation_copy() {
  local ns name before after
  [[ "$SECRET" =~ ^[a-z0-9][a-z0-9-]*/[a-z0-9][a-z0-9.-]*$ ]] || die "Annotation cleanup requires one exact namespace/Secret name"
  ns=${SECRET%%/*}
  name=${SECRET#*/}
  before=$(secret_json "$ns" "$name")
  echo null | update_secret "$ns" "$name"
  after=$(secret_json "$ns" "$name")
  add_check secret_identity_preserved "$(printf '%s' "$after" | jq --slurpfile b <(printf '%s' "$before") '.metadata.uid == $b[0].metadata.uid')"
  add_check data_and_type_preserved "$(printf '%s' "$after" | jq --slurpfile b <(printf '%s' "$before") \
    '.data == $b[0].data and .type == $b[0].type')"
  add_check annotation_removed "$(printf '%s' "$after" | jq --arg la "$LAST_APPLIED" '.metadata.annotations // {} | has($la) | not')"
}

# ── Run ───────────────────────────────────────────────────────────────────────────────────────────────────────────
log_step "Rotate $COMPONENT at ${REVISION:0:12} (report: $REPORT)"
[[ "$COMPONENT" == annotation_copy ]] || providers
"rotate_$COMPONENT"
if printf '%s' "$CHECKS" | jq -e 'del(.inference_performed) | all(.[]; . == true)' >/dev/null; then
  PHASE=verified
else
  PHASE=verification_failed
  die "Credential rotation is not verified; preserve the report and investigate"
fi
log_success "PASS: $COMPONENT replacement and predecessor checks; no inference"
