#!/usr/bin/env bash
# Mint a MaaS API key for each showback team user (showback-engineering, showback-marketing, showback-support).
# Creates a missing user in the existing `sso` Keycloak realm, signs in through the normal OpenShift OAuth browser
# flow and asks MaaS for the user's own key on the team subscription. Passwords and keys stay in a private state
# directory (default ~/.config/rhoai3-showback, override with SHOWBACK_STATE_DIR); never in Git or arguments.
# Usage: team-keys.sh [--teams engineering,marketing,support] [--hours 8] [--insecure]
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
source "$REPO_ROOT/scripts/lib.sh"
teams=engineering,marketing,support hours=8 insecure=false
fail() { log_error "$*"; exit 1; }
while (($#)); do
    case "$1" in
        --teams) teams=${2:?}; shift 2 ;;
        --hours) hours=${2:?}; shift 2 ;;
        --insecure) insecure=true; shift ;;
        -h|--help) sed -n 's/^# Usage: //p' "$0"; exit 0 ;;
        *) fail "Unknown argument: $1" ;;
    esac
done
[[ "$hours" =~ ^[0-9]+$ && "$hours" -ge 1 ]] || fail '--hours must be a positive integer'
for command in jq curl ruby openssl; do command -v "$command" >/dev/null || fail "Missing $command"; done
load_env
check_oc_logged_in
STATE=${SHOWBACK_STATE_DIR:-$HOME/.config/rhoai3-showback}
umask 077
mkdir -p "$STATE/work"
chmod 700 "$STATE"
work="$STATE/work"
tls=(--proto '=https'); [[ "$insecure" == false ]] || tls+=(--insecure)

SSO="https://$(oc --request-timeout=15s get route keycloak -n keycloak -o jsonpath='{.spec.host}')"
OAUTH="https://$(oc --request-timeout=15s get route oauth-openshift -n openshift-authentication -o jsonpath='{.spec.host}')"
API="https://$(oc --request-timeout=15s get gateway maas-default-gateway -n openshift-ingress -o json |
    jq -er '.spec.listeners[] | select(.name == "api") | .hostname')"
printf '%s\n' "$API" > "$STATE/gateway-url"
# The dedicated model is served on its own listener (Gateway listener mistral-small4).
printf 'https://%s\n' "$(oc --request-timeout=15s get gateway maas-default-gateway -n openshift-ingress -o json |
    jq -er '.spec.listeners[] | select(.name == "mistral-small4") | .hostname')" > "$STATE/dedicated-url"

# Tokens reach curl through its configuration input, never process arguments.
http() {
    local method=$1 url=$2 token=${3:-} body=${4:-}
    local args=(--config - --silent --show-error --connect-timeout 10 --max-time 30 "${tls[@]}"
        --request "$method" --output "$work/body" --dump-header "$work/headers" --write-out '%{http_code}')
    [[ -z "$body" ]] || args+=(--header 'Content-Type: application/json' --data-binary "@$body")
    HTTP_STATUS=$({ [[ -z "$token" ]] || printf 'header = "Authorization: Bearer %s"\n' "$token"; true; } |
        curl "${args[@]}" "$url") || fail "HTTP request to $url failed"
}
ADMIN_TOKEN=$(oc --request-timeout=15s get secret keycloak-initial-admin -n keycloak -o json |
    jq -j '.data | map_values(@base64d) | {grant_type: "password", client_id: "admin-cli"} + . |
        to_entries | map((.key | @uri) + "=" + (.value | @uri)) | join("&")' |
    curl --silent --show-error --connect-timeout 10 --max-time 30 "${tls[@]}" --data-binary @- \
        "$SSO/realms/master/protocol/openid-connect/token" | jq -er '.access_token')

# Create the user if missing; set a new password when this machine has none stored for an existing demo user.
ensure_user() {
    local user=$1 password_file="$STATE/$1.password" id
    http GET "$SSO/admin/realms/sso/users?username=$user&exact=true" "$ADMIN_TOKEN"
    [[ "$HTTP_STATUS" == 200 ]] || fail "Keycloak user lookup failed for $user"
    id=$(jq -r '.[0].id // ""' "$work/body")
    [[ -z "$id" || ! -s "$password_file" ]] || return 0
    openssl rand -hex 24 > "$password_file"
    if [[ -z "$id" ]]; then
        jq -n --arg u "$user" --rawfile p "$password_file" '{username: $u, enabled: true, emailVerified: true,
            email: ($u + "@example.invalid"), firstName: "Showback", lastName: $u, requiredActions: [],
            credentials: [{type: "password", value: ($p | rtrimstr("\n")), temporary: false}]}' > "$work/request.json"
        http POST "$SSO/admin/realms/sso/users" "$ADMIN_TOKEN" "$work/request.json"
        [[ "$HTTP_STATUS" == 201 ]] || fail "Creating $user failed (HTTP $HTTP_STATUS)"
        log_info "Created $user in the sso realm"
    else
        jq -n --rawfile p "$password_file" '{type: "password", value: ($p | rtrimstr("\n")), temporary: false}' \
            > "$work/request.json"
        http PUT "$SSO/admin/realms/sso/users/$id/reset-password" "$ADMIN_TOKEN" "$work/request.json"
        [[ "$HTTP_STATUS" == 204 ]] || fail "Setting a password for $user failed (HTTP $HTTP_STATUS)"
        log_info "Set a new password for existing $user"
    fi
    rm -f "$work/request.json"
}

location() { ruby -e 'puts File.read(ARGV[0]).lines.reverse.find { |s| s.match?(/^location:/i) }.to_s.sub(/^location:\s*/i, "").strip' "$1"; }
resolve() { ruby -ruri -e 'puts URI.join(ARGV[0], ARGV[1])' "$1" "$2"; }

# OpenShift browser-client OAuth flow through Keycloak; every hop must stay on the two known origins.
login() {
    local user=$1 url action next step jar="$work/$1.cookies"
    rm -f "$jar"
    url="$OAUTH/oauth/authorize?client_id=openshift-browser-client&response_type=token&redirect_uri=$(
        printf '%s' "$OAUTH/oauth/token/display" | jq -Rr @uri)&scope=user%3Afull"
    for step in 1 2 3 4 5 6 7 8; do
        case "$url" in "$OAUTH/"*|"$SSO/"*) ;; *) fail 'Unexpected login origin' ;; esac
        curl --silent --show-error --connect-timeout 10 --max-time 30 "${tls[@]}" --cookie "$jar" --cookie-jar "$jar" \
            --dump-header "$work/headers" --output "$work/body" "$url" || fail 'OAuth login request failed'
        next=$(location "$work/headers")
        [[ -z "$next" ]] || next=$(resolve "$url" "$next")
        if [[ "$next" == *'#access_token='* ]]; then
            printf '%s' "$next" | ruby -ruri -e 'print URI.decode_www_form(STDIN.read.split("#", 2).last).to_h.fetch("access_token")'
            rm -f "$jar"
            return
        fi
        if [[ -n "$next" ]]; then url=$next; continue; fi
        action=$(ruby -rcgi -e 's = File.read(ARGV[0]); f = s[/<form\b[^>]*id="kc-form-login"[^>]*>/]
            puts CGI.unescapeHTML(f.to_s[/action="([^"]+)"/, 1].to_s)' "$work/body")
        [[ "$action" == "$SSO/realms/sso/login-actions/"* ]] || fail "Unexpected login page for $user"
        jq -nj --arg u "$user" --rawfile p "$STATE/$user.password" '{username: $u, password: ($p | rtrimstr("\n")),
            credentialId: ""} | to_entries | map((.key | @uri) + "=" + (.value | @uri)) | join("&")' |
            curl --silent --show-error --connect-timeout 10 --max-time 30 "${tls[@]}" --cookie "$jar" --cookie-jar "$jar" \
                --dump-header "$work/headers" --output "$work/body" --data-binary @- "$action" || fail 'Keycloak login failed'
        next=$(location "$work/headers")
        [[ -n "$next" ]] || fail "Keycloak rejected the stored password for $user; delete $STATE/$user.password and rerun"
        url=$(resolve "$action" "$next")
    done
    fail 'OAuth redirect limit reached'
}

IFS=, read -r -a selected <<<"$teams"
for team in "${selected[@]}"; do
    case "$team" in engineering|marketing|support) ;; *) fail "Unknown team: $team" ;; esac
    user="showback-$team" subscription="team-$team"
    ensure_user "$user"
    OWNER_TOKEN=$(login "$user")
    jq -n --arg s "$subscription" --arg n "showback-$team-$(date -u +%Y%m%dT%H%M%SZ)" --arg e "${hours}h" \
        '{name: $n, subscription: $s, expiresIn: $e}' > "$work/request.json"
    http POST "$API/v1/api-keys" "$OWNER_TOKEN" "$work/request.json"
    unset OWNER_TOKEN
    [[ "$HTTP_STATUS" == 201 ]] || fail "MaaS key request for $user failed (HTTP $HTTP_STATUS): $(jq -c '.' "$work/body" 2>/dev/null)"
    jq -e --arg s "$subscription" '.subscription == $s and (.key | type == "string" and length > 0)' "$work/body" >/dev/null ||
        fail "MaaS returned a key for another subscription"
    jq -r '.key' "$work/body" > "$STATE/$team.key"
    jq '{id, name, subscription, expiresAt: (.expirationDate // .expiresAt)}' "$work/body" > "$STATE/$team.key.json"
    log_success "$user: key on $subscription, expires in ${hours}h"
done
rm -f "$work/body" "$work/headers" "$work/request.json"
unset ADMIN_TOKEN
log_info "Keys are in $STATE; generate load with $(dirname "$0")/generate-load.sh"
