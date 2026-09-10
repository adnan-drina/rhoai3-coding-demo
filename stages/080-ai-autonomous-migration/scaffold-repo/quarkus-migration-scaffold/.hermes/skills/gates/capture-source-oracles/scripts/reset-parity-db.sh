#!/usr/bin/env bash
# Restore the decided datasource's isolated instance to the initial state the
# scenario corpus names: drop and recreate the schema, then apply the schema
# and seed assets decisions.yaml points at.
#
# The reset is part of the evidence, not a convenience. A scenario that
# declares reset_before is only meaningful if the state it starts from is the
# state the corpus says it is, and an effect probe on a mutated database
# proves nothing. Credentials come from the environment by the names the
# decision records; nothing here reads or prints a secret.
#
#   reset-parity-db.sh --root /projects/modernized [--psql psql]
#
# Exit 0 reset, 1 refused, 2 usage.
set -euo pipefail
ROOT=""
PSQL="psql"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --root) ROOT="${2:-}"; shift 2 ;;
    --psql) PSQL="${2:-}"; shift 2 ;;
    *) echo "usage: reset-parity-db.sh --root <dest> [--psql psql]" >&2; exit 2 ;;
  esac
done
[[ -n "${ROOT}" && -d "${ROOT}" ]] || { echo "FAIL: --root must be an existing directory" >&2; exit 2; }
ROOT="$(cd "${ROOT}" && pwd)"

read -r DB_KIND URL_ENV USER_ENV PASS_ENV SCHEMA_SQL SEED_SQL < <(python3 - "${ROOT}" <<'PYEOF'
import sys
from pathlib import Path
root = Path(sys.argv[1])
sys.path.insert(0, str(root / ".hermes" / "lib"))
from planner.decisions import datasource, load_decisions
ds = datasource(load_decisions(root))
if not ds:
    raise SystemExit("FAIL: RESET the effective datasource is not decided in decisions.yaml")
print(" ".join(str(ds.get(k) or "-") for k in ("db_kind", "jdbc_url_env", "username_env", "password_env", "schema_sql", "seed_sql")))
PYEOF
)
[[ "${DB_KIND}" == "postgresql" ]] || { echo "FAIL: RESET this script resets a postgresql instance; the decision says ${DB_KIND}" >&2; exit 1; }
URL="${!URL_ENV:-}"
DB_USER="${!USER_ENV:-}"
DB_PASSWORD="${!PASS_ENV:-}"
[[ -n "${URL}" && -n "${DB_USER}" && -n "${DB_PASSWORD}" ]] || { echo "FAIL: RESET ${URL_ENV}, ${USER_ENV} and ${PASS_ENV} must be set (the decision references them by name)" >&2; exit 1; }
# jdbc:postgresql://host:port/db → the pieces psql needs
BODY="${URL#jdbc:postgresql://}"
HOSTPORT="${BODY%%/*}"
DB_NAME="${BODY#*/}"
DB_NAME="${DB_NAME%%\?*}"
DB_HOST="${HOSTPORT%%:*}"
DB_PORT="${HOSTPORT##*:}"
[[ "${DB_PORT}" == "${DB_HOST}" ]] && DB_PORT=5432
for rel in "${SCHEMA_SQL}" "${SEED_SQL}"; do
  [[ "${rel}" == "-" ]] && continue
  [[ -f "${ROOT}/${rel}" ]] || { echo "FAIL: RESET decisions.yaml names ${rel}, which is not in the tree" >&2; exit 1; }
done
export PGPASSWORD="${DB_PASSWORD}"
run() { "${PSQL}" -q -v ON_ERROR_STOP=1 -h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_USER}" -d "${DB_NAME}" "$@"; }
run -c 'DROP SCHEMA IF EXISTS public CASCADE' -c 'CREATE SCHEMA public'
for rel in "${SCHEMA_SQL}" "${SEED_SQL}"; do
  [[ "${rel}" == "-" ]] && continue
  run -f "${ROOT}/${rel}"
done
echo "OK: reset ${DB_NAME} at ${DB_HOST}:${DB_PORT} to the initial state (${SCHEMA_SQL}, ${SEED_SQL})"
