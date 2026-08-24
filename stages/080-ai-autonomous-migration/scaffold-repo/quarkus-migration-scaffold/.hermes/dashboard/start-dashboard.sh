#!/usr/bin/env bash
# Single Hermes dashboard launcher (DB-4). Writes /tmp/hermes-dashboard.status.
# Observability only — always exit 0 so a missing UI never fails the seat.
set -u
DASH_STATUS="/tmp/hermes-dashboard.status"
PROJECT_DIR="${PROJECT_DIR:-/projects/modernized}"
: "${HERMES_HOME:=/projects/modernized/.hermes/home}"
: "${HERMES_MANAGED_DIR:=/projects/.platform/hermes}"

dash_fail() {
  echo "ERROR: Hermes dashboard: $*"
  printf 'state=failed\nreason=%s\n' "$*" >"${DASH_STATUS}"
}

dash_listening() {
  python3 -c 'import socket;s=socket.socket();s.settimeout(0.5);s.connect(("127.0.0.1",9119))' 2>/dev/null
}

dash_bind() {
  python3 -c '
import pathlib
want = "239F"
addrs = []
for proc in ("/proc/net/tcp", "/proc/net/tcp6"):
    p = pathlib.Path(proc)
    if not p.exists():
        continue
    for line in p.read_text().splitlines()[1:]:
        f = line.split()
        lip, lp = f[1].split(":")
        if lp.upper() == want and f[3] == "0A":
            addrs.append(lip)
print("0.0.0.0" if any(a in ("00000000", "00000000000000000000000000000000") for a in addrs) else ("127.0.0.1" if addrs else "none"))
'
}

if [ ! -f "${HERMES_MANAGED_DIR}/config.yaml" ] || ! grep -q "basic_auth" "${HERMES_MANAGED_DIR}/config.yaml"; then
  dash_fail "Managed Scope dashboard.basic_auth missing; refusing unauthenticated 0.0.0.0 bind"
  exit 0
fi

# Operator 191234Zop / Review 191423ZR: honour image ENV / caller, else overlay bake.
# Do not override to dest hermes_cli/web_dist (that pointed away from the bake).
: "${HERMES_WEB_DIST:=/usr/local/share/hermes/web_dist}"
export HERMES_WEB_DIST

if [ ! -s "${HERMES_WEB_DIST}/index.html" ]; then
  dash_fail "overlay web_dist missing at ${HERMES_WEB_DIST}/index.html (no dest-side install-web-dist; --skip-build never creates a dist)"
  exit 0
fi

if dash_listening; then
  b="$(dash_bind)"
  if [ "${b}" = "0.0.0.0" ]; then
    printf 'state=listening\nbind=0.0.0.0:9119\n' >"${DASH_STATUS}"
    echo "Hermes dashboard already listening on 0.0.0.0:9119"
  else
    dash_fail "already bound ${b:-unknown}:9119, not 0.0.0.0 (che-gateway would 503)"
  fi
  exit 0
fi

cd "${PROJECT_DIR}" 2>/dev/null || cd /projects/modernized || true
start_dash() {
  nohup env HERMES_WEB_DIST="${HERMES_WEB_DIST}" \
    hermes dashboard --skip-build --host 0.0.0.0 --port 9119 --no-open \
    >/tmp/hermes-dashboard.log 2>&1 &
  echo $!
}
pid="$(start_dash)"
echo "Hermes dashboard postStart: launched pid=${pid} bind 0.0.0.0:9119"
ok=0
for _ in $(seq 1 10); do
  sleep 1
  if dash_listening; then ok=1; break; fi
done
if [ "${ok}" -ne 1 ]; then
  echo "WARN: dashboard not listening after 10s — one restart"
  kill "${pid}" 2>/dev/null || true
  pid="$(start_dash)"
  sleep 3
  if dash_listening; then ok=1; fi
fi
if [ "${ok}" -ne 1 ]; then
  dash_fail "not listening after start+restart; see /tmp/hermes-dashboard.log"
  exit 0
fi
b="$(dash_bind)"
if [ "${b}" != "0.0.0.0" ]; then
  dash_fail "listening but bind=${b:-unknown} (need 0.0.0.0 for che-gateway)"
  exit 0
fi
printf 'state=listening\nbind=0.0.0.0:9119\npid=%s\n' "${pid}" >"${DASH_STATUS}"
nohup bash -c '
  for _ in $(seq 1 36); do
    sleep 5
    if python3 -c "import socket;s=socket.socket();s.settimeout(0.5);s.connect((\"127.0.0.1\",9119))" 2>/dev/null; then
      continue
    fi
    echo "dashboard-watchdog: port 9119 down — restart once" >>/tmp/hermes-dashboard.log
    nohup env HERMES_WEB_DIST="'"${HERMES_WEB_DIST}"'" \
      hermes dashboard --skip-build --host 0.0.0.0 --port 9119 --no-open \
      >>/tmp/hermes-dashboard.log 2>&1 &
    exit 0
  done
' >/tmp/hermes-dashboard-watchdog.log 2>&1 &
echo "Hermes dashboard postStart: LISTENING on 0.0.0.0:9119 (watchdog armed)"
exit 0
