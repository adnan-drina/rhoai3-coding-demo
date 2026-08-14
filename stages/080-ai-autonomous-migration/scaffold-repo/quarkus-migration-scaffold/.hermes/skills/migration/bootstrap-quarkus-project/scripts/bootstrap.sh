#!/usr/bin/env bash
# DD1 — destination create path RETIRED (Operator E-20260814T065925Z).
# Foundation stories author pom.xml from the T-1 reference; do not generate.
set -euo pipefail

case "${1:-}" in
  -h|--help)
    cat <<'USAGE'
bootstrap.sh — RETIRED create path (DD1).

quarkus create app / quarkus-maven-plugin:create into the destination is
retired. Author pom.xml per skill bootstrap-quarkus-project,
then lint with check-pom-platform-pins.py.

Exit: 0 only for --help; 1 CREATE_PATH_RETIRED for any other invocation.
USAGE
    exit 0
    ;;
esac

printf '%s\n' \
  "CREATE_PATH_RETIRED: do not quarkus create / maven :create into the destination (DD1 E-20260814T065925Z)." \
  "Author pom.xml from T-1 + `.hermes/pins.json`; see skill bootstrap-quarkus-project." \
  >&2
exit 1
