#!/usr/bin/env bash
# contains (validate-lib.sh) under pipefail -- architect review B3, 2026-10-01:
# a match early in large output is found (grep -q exits early and SIGPIPE turned the producer's exit into
# "missing"), absence is absence, and a FAILING producer still fails the pipeline even when its partial
# output matched (contains must never hide a producer error).
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
source "$ROOT/scripts/shared/validate-lib.sh"
fails=0
t() { if [[ "$2" == "$3" ]]; then echo "ok $1"; else echo "FAIL $1 (got $2, want $3)"; fails=$((fails + 1)); fi; }
big() { echo "needle"; head -c 4000000 /dev/zero | tr '\0' 'x'; echo; }
r=$( (set -o pipefail; big | contains needle) && echo present || echo missing); t "large output, early match" "$r" present
r=$( (set -o pipefail; big | grep -q needle) && echo present || echo missing); t "control: plain grep -q on the same input is the v30 false negative" "$r" missing
r=$( (set -o pipefail; big | contains haystack) && echo present || echo missing); t "absence is absence" "$r" missing
r=$( (set -o pipefail; { echo needle; exit 3; } | contains needle) && echo present || echo missing); t "a failing producer fails even when its output matched" "$r" missing
r=$( (set -o pipefail; printf 'a\nb\n' | contains -c b) ); t "contains prints nothing (only the status)" "$r" ""
exit "$fails"
