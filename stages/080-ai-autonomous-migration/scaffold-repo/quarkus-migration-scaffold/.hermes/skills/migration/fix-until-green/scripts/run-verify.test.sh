#!/usr/bin/env bash
# run-verify selftest: the PARITY stage's admission, statically and without Maven.
#
# What is asked here is not "does the comparison work" (run-parity.test.py asks
# that) but "does the acceptance path run it for the right card, and for no
# other". The stage decides from the issued card and the startup gate's own
# receipt, in one block of python inside run-verify.sh; this test extracts THAT
# block -- the text that ships, not a copy of it -- and puts fixtures to it.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPT="${SCRIPT_DIR}/run-verify.sh"
HERMES="$(cd "${SCRIPT_DIR}/../../../.." && pwd)"
TMP="$(mktemp -d)"
trap 'rm -rf "${TMP}"' EXIT

fail() { echo "FAIL: $*" >&2; exit 1; }

bash -n "${SCRIPT}" || fail "run-verify.sh does not parse"

# the runner the stage calls, where the stage names it
RUNNER="${SCRIPT_DIR}/../../../paved-road/paved-road-m4/scripts/run-parity.py"
[[ -f "${RUNNER}" ]] || fail "the parity stage names a runner that is not there: ${RUNNER}"

# the stage is part of the ACCEPTANCE path only, it never runs when the runtime
# gates were skipped, and it never runs on a verification that already refused
grep -qF 'if [[ "${MODE}" == "acceptance" && "${RUNTIME}" -eq 1 && "${VERIFY_RC}" -eq 0 ]]; then' "${SCRIPT}" \
  || fail "the parity stage must be guarded by acceptance mode, the runtime gates and a clean verify"
# what it records, and the re-measure that turns the new verdicts into the list
grep -qF 'runtime' "${SCRIPT}" || fail "run.json must carry the parity stage's outcome"
grep -qF 'parity-before.json' "${SCRIPT}" || fail "the receipt the comparison started from must be kept"
grep -qF -- '--scenario' "${SCRIPT}" || fail "the comparison must be scoped to the card's scenarios"
# the verdicts this stage produces are of the CANDIDATE: step 4 above rebuilt
# the work list on it, so the live seal cannot match, and the issued card is
# what they bind to instead (v9 card t_222c582a, where every parity card
# reverted on "receipt not authoritative: worklist digest ... != sealed ...")
grep -qF -- '--issued "${PARITY_ISSUED}"' "${SCRIPT}" \
  || fail "the comparison must be told which issued card its verdicts are bound to"
grep -qF 'PARITY_ISSUED="${ROOT}/verification/loop/issued.json"' "${SCRIPT}" \
  || fail "the binding must name the issued card of THIS tree"

# --- the admission itself, extracted from the script ------------------------
awk '/PARITY_PLAN="\$\(python3 - /{flag=1; next} flag && /^PYEOF$/{exit} flag{print}' "${SCRIPT}" > "${TMP}/plan.py"
[[ -s "${TMP}/plan.py" ]] || fail "could not extract the parity stage's admission from ${SCRIPT}"

mkroot() {
  local root="$1"
  mkdir -p "${root}/.hermes" "${root}/verification/loop" "${root}/verification/build" "${root}/evidence/planning"
  ln -s "${HERMES}/lib" "${root}/.hermes/lib"
}

boot_ok() { printf '{"schema":"rhoai3.verify-boot/v1","gate":"boot","ran":true,"rc":0,"ready":true}' >"$1/verification/build/boot.json"; }
boot_bad() { printf '{"schema":"rhoai3.verify-boot/v1","gate":"boot","ran":true,"rc":1,"ready":false}' >"$1/verification/build/boot.json"; }
worklist() {
  cat >"$1/evidence/planning/worklist.json" <<'JSON'
{"schema":"rhoai3.worklist/v1","items":[
 {"id":"parity:aaaa","source":"parity","gate":"parity","scenarios":["sc:b-second","sc:a-first"]},
 {"id":"parity:bbbb","source":"parity","gate":"parity","scenarios":["sc:a-first"]},
 {"id":"parity:cccc","source":"parity","gate":"parity","scenarios":["sc:not-on-this-card"]}],
 "clusters":[]}
JSON
}
issued() { printf '{"schema":"rhoai3.loop-issued/v1","cluster":"c:1","gate":"%s","items":%s}' "$2" "$3" >"$1/verification/loop/issued.json"; }

plan() { python3 "${TMP}/plan.py" "$1" "${2:-false}"; }

# a card that is not a parity card: the comparison is not run at all (it starts
# the packaged destination and replays scenarios; no other card pays for that)
A="${TMP}/a"; mkroot "${A}"; boot_ok "${A}"; worklist "${A}"; issued "${A}" "" '["err:1"]'
[[ "$(plan "${A}")" == "no" ]] || fail "a card with no gate must not run the comparison: $(plan "${A}")"
B="${TMP}/b"; mkroot "${B}"; boot_ok "${B}"; worklist "${B}"; issued "${B}" "package" '["rt:package:1"]'
[[ "$(plan "${B}")" == "no" ]] || fail "a packaging card must not run the comparison: $(plan "${B}")"
# no issued card at all
C="${TMP}/c"; mkroot "${C}"; boot_ok "${C}"; worklist "${C}"
[[ "$(plan "${C}")" == "no" ]] || fail "with no issued card there is nothing to scope a comparison to: $(plan "${C}")"

# a parity card: the comparison runs, scoped to the scenarios ITS OWN
# obligations are made of -- deduplicated, ordered, and nobody else's
D="${TMP}/d"; mkroot "${D}"; boot_ok "${D}"; worklist "${D}"; issued "${D}" "parity" '["parity:aaaa","parity:bbbb"]'
[[ "$(plan "${D}")" == "run:sc:a-first,sc:b-second" ]] || fail "the comparison must be scoped to this card's scenarios: $(plan "${D}")"

# the startup gate did not pass in this verification: there is no started
# destination to compare, and a stage that cannot measure says so rather than
# leaving a stale receipt to be read as this candidate's
E="${TMP}/e"; mkroot "${E}"; boot_bad "${E}"; worklist "${E}"; issued "${E}" "parity" '["parity:aaaa"]'
[[ "$(plan "${E}")" == skip:* ]] || fail "a failing startup gate must skip the comparison, named: $(plan "${E}")"
F="${TMP}/f"; mkroot "${F}"; worklist "${F}"; issued "${F}" "parity" '["parity:aaaa"]'
[[ "$(plan "${F}")" == skip:* ]] || fail "an absent startup receipt is not a passing gate: $(plan "${F}")"

# --parity forces the stage for a tree nobody issued a card for (an Operator
# re-measuring the phase); with no obligations it names no scenario and the
# whole phase is compared
G="${TMP}/g"; mkroot "${G}"; boot_ok "${G}"; worklist "${G}"
[[ "$(plan "${G}" true)" == "run:" ]] || fail "--parity must force an unscoped comparison: $(plan "${G}" true)"

echo "OK: run-verify parity stage (acceptance-only and after the runtime gates; not run for a compile or packaging card \
or with no issued card; run for a parity card scoped to its own scenarios and bound to that issued card, so the work \
list this verification rebuilt on the candidate is not read as a stale seal; skipped by name when the startup gate did \
not pass; forced unscoped by --parity)"
