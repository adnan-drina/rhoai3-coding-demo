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
# It talks JDBC through the destination's own driver rather than a command-line
# client: the workspace that runs the comparison has a JDK and that driver on
# disk, and no psql. A reset that cannot run would turn every reset_before
# scenario INCONCLUSIVE, which is a tooling gap masquerading as a finding.
#
#   reset-parity-db.sh --root /projects/modernized [--driver /path/to/driver.jar]
#
# Exit 0 reset, 1 refused, 2 usage.
set -euo pipefail
ROOT=""
DRIVER=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --root) ROOT="${2:-}"; shift 2 ;;
    --driver) DRIVER="${2:-}"; shift 2 ;;
    *) echo "usage: reset-parity-db.sh --root <dest> [--driver <jar>]" >&2; exit 2 ;;
  esac
done
[[ -n "${ROOT}" && -d "${ROOT}" ]] || { echo "FAIL: --root must be an existing directory" >&2; exit 2; }
ROOT="$(cd "${ROOT}" && pwd)"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

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
URL="${!URL_ENV:-}"
DB_USER="${!USER_ENV:-}"
DB_PASSWORD="${!PASS_ENV:-}"
[[ -n "${URL}" && -n "${DB_USER}" && -n "${DB_PASSWORD}" ]] || { echo "FAIL: RESET ${URL_ENV}, ${USER_ENV} and ${PASS_ENV} must be set (the decision references them by name)" >&2; exit 1; }

SQL_FILES=()
for rel in "${SCHEMA_SQL}" "${SEED_SQL}"; do
  [[ "${rel}" == "-" ]] && continue
  [[ -f "${ROOT}/${rel}" ]] || { echo "FAIL: RESET decisions.yaml names ${rel}, which is not in the tree" >&2; exit 1; }
  SQL_FILES+=("${ROOT}/${rel}")
done

# The driver, found under its OWN group directory. A bare artifact glob is not
# a driver: ~/.m2 also holds org.testcontainers:postgresql, which matched
# postgresql-*.jar and produced "No suitable driver found".
if [[ -z "${DRIVER}" ]]; then
  case "${DB_KIND}" in
    postgresql) GROUP_DIR="org/postgresql/postgresql" ;;
    mysql) GROUP_DIR="com/mysql/mysql-connector-j" ;;
    mariadb) GROUP_DIR="org/mariadb/jdbc/mariadb-java-client" ;;
    mssql) GROUP_DIR="com/microsoft/sqlserver/mssql-jdbc" ;;
    h2) GROUP_DIR="com/h2database/h2" ;;
    *) echo "FAIL: RESET no driver coordinate for db_kind ${DB_KIND}; pass --driver" >&2; exit 1 ;;
  esac
  DRIVER="$(find "${HOME}/.m2/repository/${GROUP_DIR}" -name "*.jar" ! -name "*sources*" ! -name "*javadoc*" 2>/dev/null | sort -V | tail -1)"
fi
[[ -n "${DRIVER}" && -f "${DRIVER}" ]] || { echo "FAIL: RESET no ${DB_KIND} JDBC driver found under ~/.m2; pass --driver <jar>" >&2; exit 1; }

WORK="$(mktemp -d)"
trap 'rm -rf "${WORK}"' EXIT
javac -d "${WORK}" "${HERE}/reset-db/ResetDb.java" >"${WORK}/javac.log" 2>&1 || { echo "FAIL: RESET could not compile the reset runner: $(tail -3 "${WORK}/javac.log")" >&2; exit 1; }
# read the jar directly: `unzip -l | grep -q` closes the pipe on the first
# match, and under pipefail that reads as a failure (the same trap the stage
# validator hit)
REGISTERS="$(python3 -c 'import sys, zipfile; print("yes" if "META-INF/services/java.sql.Driver" in zipfile.ZipFile(sys.argv[1]).namelist() else "no")' "${DRIVER}" 2>/dev/null || echo no)"
if [[ "${REGISTERS}" != "yes" ]]; then
  echo "FAIL: RESET $(basename "${DRIVER}") registers no JDBC driver; pass --driver <jar>" >&2
  exit 1
fi
java -cp "${DRIVER}:${WORK}" ResetDb "${URL}" "${DB_USER}" "${DB_PASSWORD}" ${SQL_FILES[@]+"${SQL_FILES[@]}"}
echo "OK: reset to the initial state (${SCHEMA_SQL}, ${SEED_SQL}) using $(basename "${DRIVER}")"
