#!/bin/bash
set -euo pipefail
umask 077
cd /sandbox/workspace
# The listener secret is local agent-owned state, distinct from protected MaaS credentials.
[[ -f /sandbox/state/setup-ready && ! -L /sandbox/state/setup-ready && -f opencode.json && ! -L opencode.json ]] || exit 1
for directory in /sandbox/state /sandbox/state/auth; do
  [[ -d "$directory" && ! -L "$directory" && "$(stat -c %u "$directory")" == "$(id -u)" ]] || exit 1
done
# OpenShift fsGroup may add setgid; clear it without admitting group/other access.
auth_mode="$(stat -c %a /sandbox/state/auth)"
[[ "$auth_mode" == 700 || "$auth_mode" == 2700 ]] || exit 1
chmod g-s /sandbox/state/auth
chmod 700 /sandbox/state/auth
[[ "$(stat -c %a /sandbox/state/auth)" == 700 ]] || exit 1
secret=/sandbox/state/auth/server-password
[[ -f "$secret" && ! -L "$secret" && -s "$secret" && "$(stat -c %a "$secret")" == 600 && "$(stat -c %u "$secret")" == "$(id -u)" ]] || { echo 'OpenCode listener credential is absent or unsafe' >&2; exit 1; }
OPENCODE_SERVER_PASSWORD="$(cat "$secret")"
[[ ${#OPENCODE_SERVER_PASSWORD} -ge 32 ]] || exit 1
export OPENCODE_SERVER_PASSWORD
exec /usr/local/bin/opencode serve --hostname 127.0.0.1 --port 4096
