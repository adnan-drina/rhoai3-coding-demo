#!/usr/bin/env bash
# Explicitly create two new showback users in the existing SSO authority and mint their own ephemeral MaaS keys.
# Normal OpenShift/Keycloak browser-form OAuth is used; no impersonation, realm import, client change or model traffic.
# Private credentials and recovery evidence persist only in a NEW directory under /private/tmp. Never overwrite users.
# Usage: qualify-qwen-identities.sh [--execute --output NEW_PRIVATE_DIR] [--insecure]
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
source "$REPO_ROOT/scripts/lib.sh"
execute=false output='' insecure=false
fail() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }
while (($#)); do
    case "$1" in
        --execute) execute=true; shift ;;
        --output) output=${2:?}; shift 2 ;;
        --insecure) insecure=true; shift ;;
        -h|--help) sed -n 's/^# Usage: //p' "$0"; exit 0 ;;
        *) fail 'Unknown argument' ;;
    esac
done
if [[ "$execute" == false ]]; then
    jq -n '{evidence_kind:"preview",network_requests:0,users:["showback-engineering","showback-support"],
      subscriptions:["team-engineering","team-support"],key_lifetime:"1h",inference_requests:0,
      changes:["two new marked SSO users","two genuine OpenShift logins","two owner-created ephemeral MaaS keys"]}'
    exit 0
fi
[[ "$output" == /private/tmp/* && ! -e "$output" && ! -L "$output" ]] || fail 'Use a new directory under /private/tmp'
for command in jq curl ruby openssl; do command -v "$command" >/dev/null || fail "Missing $command"; done
load_env
check_oc_logged_in
umask 077
mkdir -m 700 "$output"
tls=(); [[ "$insecure" == false ]] || tls=(--insecure)
SSO="https://$(oc --request-timeout=15s get route keycloak -n keycloak -o jsonpath='{.spec.host}')"
OAUTH="https://$(oc --request-timeout=15s get route oauth-openshift -n openshift-authentication -o jsonpath='{.spec.host}')"
SERVER=$(oc --request-timeout=15s whoami --show-server)
oc --request-timeout=15s get oauth cluster -o json > "$output/oauth-authority.json"
jq -e --arg issuer "$SSO/realms/sso" '[.spec.identityProviders[]|select(.name=="rhbk" and
  .type=="OpenID" and .openID.issuer==$issuer)]|length==1' "$output/oauth-authority.json" >/dev/null || fail 'SSO authority differs'
oc --request-timeout=15s get gateway maas-default-gateway -n openshift-ingress -o json > "$output/gateway.json"
API="https://$(jq -er '.spec.listeners[]|select(.name=="api")|.hostname' "$output/gateway.json")"
export SHOWBACK_GATEWAY_URL="https://$(jq -er '.spec.listeners[]|select(.name=="qwen3-8")|.hostname' "$output/gateway.json")"

# Tokens are never process arguments. HTTP bodies, headers and cookies are private recovery evidence.
http() {
    local method=$1 url=$2 token=${3:-} body=${4:-} content=${5:-application/json}
    local args=(--config - --silent --show-error --connect-timeout 10 --max-time 30 "${tls[@]}"
      --request "$method" --output "$output/http-body" --dump-header "$output/http-headers" --write-out '%{http_code}')
    [[ -z "$body" ]] || args+=(--header "Content-Type: $content" --data-binary "@$body")
    HTTP_STATUS=$({ [[ -z "$token" ]] || printf 'header = "Authorization: Bearer %s"\n' "$token"; true; } |
      curl "${args[@]}" "$url") || fail 'HTTP transport failed; private recovery evidence retained'
}
ADMIN_TOKEN=$(oc --request-timeout=15s get secret keycloak-initial-admin -n keycloak -o json |
  jq -j '.data|map_values(@base64d)|{grant_type:"password",client_id:"admin-cli"} + .|
    to_entries|map((.key|@uri)+"="+(.value|@uri))|join("&")' |
  curl --silent --show-error --connect-timeout 10 --max-time 30 "${tls[@]}" --data-binary @- \
    "$SSO/realms/master/protocol/openid-connect/token" | jq -er '.access_token')

# Refuse all collisions before the first write. Never reset an existing account's password or groups.
for team in engineering support; do
    http GET "$SSO/admin/realms/sso/users?username=showback-$team&exact=true" "$ADMIN_TOKEN"
    [[ "$HTTP_STATUS" == 200 ]] && jq -e 'length==0' "$output/http-body" >/dev/null || fail 'Demo username already exists'
    oc --request-timeout=15s get user "showback-$team" --ignore-not-found -o json > "$output/$team-existing-user.json"
    [[ ! -s "$output/$team-existing-user.json" ]] || fail 'OpenShift demo username already exists'
done

location() { ruby -e 'puts File.read(ARGV[0]).lines.reverse.find{|s|s.match?(/^location:/i)}.to_s.sub(/^location:\s*/i, "").strip' "$1"; }
resolve() { ruby -ruri -e 'puts URI.join(ARGV[0],ARGV[1])' "$1" "$2"; }
login() {
    local team=$1 dir="$output/$1" url action next token step
    mkdir -m 700 "$dir"
    url="$OAUTH/oauth/authorize?client_id=openshift-browser-client&response_type=token&redirect_uri=$(
      printf '%s' "$OAUTH/oauth/token/display" | jq -Rr @uri)&scope=user%3Afull"
    # Browser flow without automatic cross-origin credential forwarding. Every hop stays on the two known origins.
    for step in 1 2 3 4 5 6 7 8; do
        case "$url" in "$OAUTH/"*|"$SSO/"*) ;; *) fail 'Unexpected login origin' ;; esac
        curl --silent --show-error --connect-timeout 10 --max-time 30 "${tls[@]}" \
          --cookie "$dir/cookies" --cookie-jar "$dir/cookies" --dump-header "$dir/headers" \
          --output "$dir/body" "$url" || fail 'OAuth login transport failed'
        next=$(location "$dir/headers")
        if [[ "$next" == *'#access_token='* ]]; then
            printf '%s' "$next" | ruby -ruri -e \
              'puts URI.decode_www_form(STDIN.read.split("#",2).last).to_h.fetch("access_token")' > "$dir/token"
            return
        fi
        if [[ -n "$next" ]]; then
            url=$(resolve "$url" "$next")
            continue
        fi
        action=$(ruby -rcgi -e 's=File.read(ARGV[0]); f=s[/<form\b[^>]*id="kc-form-login"[^>]*>/];
          puts CGI.unescapeHTML(f.to_s[/action="([^"]+)"/,1].to_s)' "$dir/body")
        if [[ -n "$action" ]]; then
            [[ "$action" == "$SSO/realms/sso/login-actions/"* ]] || fail 'Unexpected Keycloak login form'
            jq -j --slurpfile u "$output/$team-user-request.json" '{username:$u[0].username,password:$u[0].credentials[0].value,
              credentialId:""}|to_entries|map((.key|@uri)+"="+(.value|@uri))|join("&")' |
              curl --silent --show-error --connect-timeout 10 --max-time 30 "${tls[@]}" \
                --cookie "$dir/cookies" --cookie-jar "$dir/cookies" --dump-header "$dir/headers" \
                --output "$dir/body" --data-binary @- "$action" || fail 'Keycloak login failed'
            next=$(location "$dir/headers")
            [[ -n "$next" ]] || fail 'Keycloak did not finish genuine user login'
            url=$(resolve "$action" "$next")
            continue
        fi
        # The browser client normally auto-approves its scope. Preserve an unexpected consent page for review.
        fail 'Unexpected OAuth page; private login evidence retained'
    done
    fail 'OAuth redirect bound reached'
}

for team in engineering support; do
    export SHOWBACK_NEW_PASSWORD
    SHOWBACK_NEW_PASSWORD=$(openssl rand -hex 24)
    jq -n --arg user "showback-$team" '{username:$user,enabled:true,emailVerified:true,
      email:($user+"@example.invalid"),firstName:"Showback",lastName:$user,requiredActions:[],
      attributes:{"rhoai3.owner":["showback-qwen-live"]},
      credentials:[{type:"password",value:$ENV.SHOWBACK_NEW_PASSWORD,temporary:false}]}' > "$output/$team-user-request.json"
    unset SHOWBACK_NEW_PASSWORD
    http POST "$SSO/admin/realms/sso/users" "$ADMIN_TOKEN" "$output/$team-user-request.json"
    [[ "$HTTP_STATUS" == 201 ]] || fail 'New SSO user creation failed; preserve recovery journal'
    location "$output/http-headers" > "$output/$team-created-location"
    login "$team"
    OWNER_TOKEN=$(cat "$output/$team/token")
    http GET "$SERVER/apis/user.openshift.io/v1/users/~" "$OWNER_TOKEN"
    [[ "$HTTP_STATUS" == 200 ]] && jq -e --arg u "showback-$team" '.metadata.name==$u' "$output/http-body" >/dev/null ||
      fail 'OpenShift genuine owner identity mismatch'
    cp "$output/http-body" "$output/$team/openshift-user.json"
    http GET "$API/v1/subscriptions" "$OWNER_TOKEN"
    [[ "$HTTP_STATUS" == 200 ]] && jq -e --arg s "team-$team" 'type=="array" and
      any(.[];.subscription_id_header==$s)' "$output/http-body" >/dev/null || fail 'Owner subscription not discoverable'
    cp "$output/http-body" "$output/$team/subscriptions.json"
    jq -n --arg s "team-$team" --arg n "showback-qwen-$(date -u +%Y%m%dT%H%M%SZ)" \
      '{name:$n,subscription:$s,expiresIn:"1h",ephemeral:true}' > "$output/key-request.json"
    http POST "$API/v1/api-keys" "$OWNER_TOKEN" "$output/key-request.json"
    [[ "$HTTP_STATUS" == 201 ]] || fail 'Owner API key creation failed'
    cp "$output/http-body" "$output/$team/key-created.json"
    jq -e --arg s "team-$team" '.subscription==$s and .ephemeral==true and (.key|type=="string" and length>0)
      and (.id|type=="string" and length>0)' "$output/http-body" >/dev/null || fail 'Created key subscription differs'
    key_id=$(jq -er '.id' "$output/http-body")
    http GET "$API/v1/api-keys/$(printf '%s' "$key_id" | jq -Rr @uri)" "$OWNER_TOKEN"
    [[ "$HTTP_STATUS" == 200 ]] && jq -e --arg u "showback-$team" --arg s "team-$team" \
      '.username==$u and .subscription==$s and .status=="active"' "$output/http-body" >/dev/null || fail 'Server key owner differs'
    cp "$output/http-body" "$output/$team/key-metadata.json"
    jq '{username,subscription,status,ephemeral,id,expirationDate}' "$output/http-body" > "$output/$team/identity-check.json"
    unset OWNER_TOKEN
done
unset ADMIN_TOKEN
jq -n --slurpfile engineering "$output/engineering/identity-check.json" --slurpfile support "$output/support/identity-check.json" \
  '{schema_version:1,evidence_kind:"observed",identity_checks:[$engineering[0],$support[0]],
    inference_requests:0,credentials:"private directory only; keys expire after one hour"}' > "$output/identity-summary.json"
printf 'Genuine team-owned keys verified; private credentials and recovery evidence: %s\n' "$output"
