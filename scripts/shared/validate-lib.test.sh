#!/usr/bin/env bash
# contains (validate-lib.sh) under pipefail -- architect review B3, 2026-10-01:
# a match early in large output is found (grep -q exits early and SIGPIPE turned the producer's exit into
# "missing"), absence is absence, and a FAILING producer still fails the pipeline even when its partial
# output matched (contains must never hide a producer error).
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
export VALIDATE_LIB_OFFLINE=1
source "$ROOT/scripts/shared/validate-lib.sh"
fails=0
t() { if [[ "$2" == "$3" ]]; then echo "ok $1"; else echo "FAIL $1 (got $2, want $3)"; fails=$((fails + 1)); fi; }
big() { echo "needle"; head -c 4000000 /dev/zero | tr '\0' 'x'; echo; }
r=$( (set -o pipefail; big | contains needle) && echo present || echo missing); t "large output, early match" "$r" present
r=$( (set -o pipefail; big | grep -q needle) && echo present || echo missing); t "control: plain grep -q on the same input is the v30 false negative" "$r" missing
r=$( (set -o pipefail; big | contains haystack) && echo present || echo missing); t "absence is absence" "$r" missing
r=$( (set -o pipefail; { echo needle; exit 3; } | contains needle) && echo present || echo missing); t "a failing producer fails even when its output matched" "$r" missing
r=$( (set -o pipefail; printf 'a\nb\n' | contains -c b) ); t "contains prints nothing (only the status)" "$r" ""

# check_stage_applications: the status checker's exit code is authoritative.
stage_case() {  # $1 = stub output, $2 = stub exit code; prints "pass/fail" counts
  ( python3() { printf '%b' "$STUB_OUT"; return "$STUB_RC"; }
    STUB_OUT="$1" STUB_RC="$2" VALIDATE_PASS=0 VALIDATE_FAIL=0
    check_stage_applications 070 >/dev/null; echo "$VALIDATE_PASS/$VALIDATE_FAIL" )
}
t "all components OK" "$(stage_case 'OK   070-a\nOK   070-b\n' 0)" "2/0"
t "one component FAIL" "$(stage_case 'OK   070-a\nFAIL 070-b\n  - 070-b: health Degraded\n' 1)" "1/1"
t "stage-wide failure without a FAIL line still fails" "$(stage_case 'OK   070-a\nOK   070-b\n  - 070: mixed revisions\n' 1)" "2/1"
exit "$fails"
