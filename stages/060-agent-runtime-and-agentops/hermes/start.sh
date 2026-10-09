#!/bin/bash
set -euo pipefail
umask 077
# Empty directory uploads may omit the checkout; create only our owned workdir.
if [[ ! -e /sandbox/workspace && ! -L /sandbox/workspace ]]; then
  mkdir -m 700 /sandbox/workspace
fi
[[ -d /sandbox/workspace && ! -L /sandbox/workspace && "$(stat -c %u /sandbox/workspace)" == "$(id -u)" ]] || { echo 'Hermes workspace is absent or unsafe' >&2; exit 1; }
cd /sandbox/workspace
# The listener secret is local agent-owned state, distinct from protected MaaS credentials.
[[ -f /sandbox/state/setup-ready && ! -L /sandbox/state/setup-ready && -f /sandbox/state/hermes/config.yaml && ! -L /sandbox/state/hermes/config.yaml ]] || exit 1
for directory in /sandbox/state /sandbox/state/auth; do
  [[ -d "$directory" && ! -L "$directory" && "$(stat -c %u "$directory")" == "$(id -u)" ]] || exit 1
done
# OpenShift fsGroup may add setgid; clear it without admitting group/other access.
auth_mode="$(stat -c %a /sandbox/state/auth)"
[[ "$auth_mode" == 700 || "$auth_mode" == 2700 ]] || exit 1
chmod g-s /sandbox/state/auth
chmod 700 /sandbox/state/auth
[[ "$(stat -c %a /sandbox/state/auth)" == 700 ]] || exit 1
secret=/sandbox/state/auth/server-key
[[ -f "$secret" && ! -L "$secret" && -s "$secret" && "$(stat -c %a "$secret")" == 600 && "$(stat -c %u "$secret")" == "$(id -u)" ]] || { echo 'Hermes listener credential is absent or unsafe' >&2; exit 1; }
API_SERVER_KEY="$(cat "$secret")"
[[ ${#API_SERVER_KEY} -ge 32 ]] || exit 1
export API_SERVER_KEY
export API_SERVER_ENABLED=true API_SERVER_HOST=127.0.0.1 API_SERVER_PORT=8642 API_SERVER_MODEL_NAME=hermes
export HERMES_MAX_ITERATIONS=4 HERMES_MAX_TOKENS=1024 HERMES_DISABLE_LAZY_INSTALLS=1
# Launch the existing native console entrypoint through the image-private ELF.
exec /opt/hermes-venv/bin/python3.11 /opt/hermes-venv/bin/hermes gateway run --external-supervisor
