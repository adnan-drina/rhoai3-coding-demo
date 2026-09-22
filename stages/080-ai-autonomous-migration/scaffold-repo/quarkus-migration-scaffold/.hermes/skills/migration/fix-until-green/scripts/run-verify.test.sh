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
# H10 (dest v9 t_56adcd76): a verification never re-seals admission; a change
# of the receipt while it ran is recorded and said out loud
grep -qF 'ADMISSION_BEFORE="$(sha256sum "${ROOT}/evidence/planning/admission-receipt.json"' "${SCRIPT}" \
  || fail "the admission receipt digest must be taken before anything runs"
grep -qF 'ADMISSION_RESEALED_DURING_VERIFY' "${SCRIPT}" || fail "a re-seal during the verification must be named"
grep -qF '"resealed_during_verify"' "${SCRIPT}" || fail "run.json must record whether admission was re-sealed during the verification"
# the verdicts this stage produces are of the CANDIDATE: step 4 above rebuilt
# the work list on it, so the live seal cannot match, and the issued card is
# what they bind to instead (v9 card t_222c582a, where every parity card
# reverted on "receipt not authoritative: worklist digest ... != sealed ...")
grep -qF -- '--issued "${PARITY_ISSUED}"' "${SCRIPT}" \
  || fail "the comparison must be told which issued card its verdicts are bound to"
grep -qF 'PARITY_ISSUED="${ROOT}/verification/loop/issued.json"' "${SCRIPT}" \
  || fail "the binding must name the issued card of THIS tree"

# --- the runtime trigger, named and recorded --------------------------------
# The gates that package and start the destination run as soon as the COMPILER
# is satisfied, not when the whole tuple is [0,0,0]: incidents and failing tests
# do not stop Maven from producing an artifact, and a packaging regression is
# what a coordinated multi-file unit is most likely to cause. The audit has to
# say WHY the gate ran, so the trigger is a recorded value and not an inference.
grep -qF 'compile-zero' "${SCRIPT}" || fail "the runtime stage must name its trigger"
grep -qF '["trigger"] = os.environ.get("RT_TRIGGER")' "${SCRIPT}" \
  || fail "run.json must record the runtime trigger"
grep -qF 'if [[ "${RT_TRIGGER}" != "none" ]]; then' "${SCRIPT}" \
  || fail "the runtime gates must be guarded by the named trigger"
grep -qF '[[ "${MODE}" == "diagnostic" ]] && RUNTIME=0' "${SCRIPT}" \
  || fail "diagnostic mode must still never run the runtime gates"
# the trigger itself, extracted from the script and put to fixtures
awk '/RT_TRIGGER="\$\(python3 - /{flag=1; next} flag && /^PYEOF$/{exit} flag{print}' "${SCRIPT}" > "${TMP}/trigger.py"
[[ -s "${TMP}/trigger.py" ]] || fail "could not extract the runtime trigger from ${SCRIPT}"
trigger() {
  local root="${TMP}/t$$_$1"
  mkdir -p "${root}/verification/loop"
  printf '{"schema":"rhoai3.loop-state/v1","measure":%s}' "$2" >"${root}/verification/loop/state.json"
  python3 "${TMP}/trigger.py" "${root}"
}
[[ "$(trigger a '{"known":true,"tuple":[4,0,2]}')" == "compile-zero" ]] \
  || fail "a known measure with no compile error triggers the gates whatever the other slots say"
[[ "$(trigger b '{"known":true,"tuple":[0,0,0]}')" == "compile-zero" ]] || fail "a green measure still triggers them"
[[ "$(trigger c '{"known":true,"tuple":[0,7,0]}')" == "none" ]] || fail "a tree that does not compile has no artifact to package"
[[ "$(trigger d '{"known":false,"tuple":[0,0,0]}')" == "none" ]] \
  || fail "an unrun compiler is not a compile count of zero"

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

# H3: the read oracles of the card's own entry points are re-run beside its
# scenarios (dest v9 t_4d75569c: a read-oracle obligation names no scenario and
# a scoped run that skipped every read oracle could never re-measure it). The
# plan names them one per line after its head, for run-parity.py --read-oracle
worklist_eps() {
  cat >"$1/evidence/planning/worklist.json" <<'JSON'
{"schema":"rhoai3.worklist/v1","items":[
 {"id":"parity:aaaa","source":"parity","gate":"parity","entry_point":"ep:x.Owner#list():http","scenario":"sc:a-first","scenarios":["sc:a-first"]},
 {"id":"parity:bbbb","source":"parity","gate":"parity","entry_point":"ep:x.Owner#list():http","scenario":"","scenarios":["sc:a-first"]},
 {"id":"parity:cccc","source":"parity","gate":"parity","entry_point":"ep:x.Vet#list():http","scenario":"","scenarios":[]}],
 "clusters":[]}
JSON
}
RO="${TMP}/ro"; mkroot "${RO}"; boot_ok "${RO}"; worklist_eps "${RO}"; issued "${RO}" "parity" '["parity:aaaa","parity:bbbb"]'
[[ "$(plan "${RO}")" == $'run:sc:a-first\noracle:ep:x.Owner#list():http' ]] \
  || fail "the plan names the card's entry points, one per oracle line, and nobody else's: $(plan "${RO}")"
grep -qF -- 'PARITY_ARGS+=(--read-oracle "${ep}")' "${SCRIPT}" || fail "the scoped comparison must pass the card's read oracles to the runner"
grep -qF '"read_oracles_rerun": sorted(reruns)' "${SCRIPT}" || fail "run.json must carry the read oracles the runner re-ran"
grep -qF 'rec_p = root / "verification" / "parity" / "_run.json"' "${SCRIPT}" \
  || fail "what was re-run is read from the runner's own record, never from what was asked"

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

# --- the runtime-feedback sweep ---------------------------------------------
# decisions.loop.runtime_feedback v1: once the destination boots, compare the
# WHOLE phase on this candidate, on any card, so a behavioural failure enters
# the next work-list rebuild as a parity obligation instead of waiting for M4.
feedback() { printf 'loop:\n  runtime_feedback: %s\n' "$2" >"$1/decisions.yaml"; }
candidate() { printf '{"schema":"rhoai3.verify-run/v1","candidate_sha256":"%s"}' "$2" >"$1/verification/build/run.json"; }
bound() { printf '{"schema":"rhoai3.parity-receipt/v1","binding":{"mode":"%s","candidate_sha256":"%s"}}' "$2" "$3" >"$1/verification/parity/receipt.json"; }

H="${TMP}/h"; mkroot "${H}"; boot_ok "${H}"; worklist "${H}"; issued "${H}" "" '["err:1"]'; candidate "${H}" "c0ffee"
[[ "$(plan "${H}")" == "no" ]] || fail "with the mode absent a compile card still runs no comparison: $(plan "${H}")"
feedback "${H}" off
[[ "$(plan "${H}")" == "no" ]] || fail "the mode off is the v9 behaviour: $(plan "${H}")"
feedback "${H}" v1
[[ "$(plan "${H}")" == "sweep:" ]] || fail "v1 must sweep the whole phase after a passing startup gate: $(plan "${H}")"

# a card whose startup gate did not pass has nothing to compare, and the sweep
# is not a card's obligation, so it is silent rather than a WARN
I="${TMP}/i"; mkroot "${I}"; boot_bad "${I}"; worklist "${I}"; issued "${I}" "" '["err:1"]'; feedback "${I}" v1; candidate "${I}" "c0ffee"
[[ "$(plan "${I}")" == "no" ]] || fail "no boot, no sweep: $(plan "${I}")"

# THE COST GUARD: a receipt already bound to this candidate digest measured this
# exact tree, so the sweep would replay it for nothing
J="${TMP}/j"; mkroot "${J}"; mkdir -p "${J}/verification/parity"; boot_ok "${J}"; worklist "${J}"
issued "${J}" "" '["err:1"]'; feedback "${J}" v1; candidate "${J}" "c0ffee"
bound "${J}" candidate c0ffee
[[ "$(plan "${J}")" == done:* ]] || fail "a receipt already bound to this candidate must skip the sweep by name: $(plan "${J}")"
bound "${J}" candidate "another"
[[ "$(plan "${J}")" == "sweep:" ]] || fail "a receipt bound to ANOTHER candidate measured another tree: $(plan "${J}")"
bound "${J}" sealed c0ffee
[[ "$(plan "${J}")" == "sweep:" ]] || fail "a SEALED receipt is the M4 road's, not this candidate's: $(plan "${J}")"

# and a parity CARD is unaffected by the mode: its own comparison stays scoped
K="${TMP}/k"; mkroot "${K}"; boot_ok "${K}"; worklist "${K}"; issued "${K}" "parity" '["parity:aaaa","parity:bbbb"]'; feedback "${K}" v1
[[ "$(plan "${K}")" == "run:sc:a-first,sc:b-second" ]] || fail "a parity card keeps its own scoped comparison: $(plan "${K}")"

# what the two triggers are recorded as, and that the sweep is never scoped
grep -qF 'PARITY_TRIGGER="runtime-feedback"' "${SCRIPT}" || fail "the sweep must record why it ran"
grep -qF 'PARITY_TRIGGER="issued-card"' "${SCRIPT}" || fail "a card's own comparison must record why it ran"
grep -qF '"trigger": os.environ.get("PARITY_TRIGGER")' "${SCRIPT}" || fail "run.json must carry the parity trigger"

echo "OK: run-verify parity stage (acceptance-only and after the runtime gates; not run for a compile or packaging card \
or with no issued card; run for a parity card scoped to its own scenarios plus the read oracles of its own entry points (H3) and bound to that issued card, so the work \
list this verification rebuilt on the candidate is not read as a stale seal; skipped by name when the startup gate did \
not pass; forced unscoped by --parity) + the RUNTIME TRIGGER (compile-zero: known measure and no compile error, \
whatever the incident and test slots say; an unrun compiler is not zero; recorded in run.json; diagnostic mode still \
never runs the gates) + the RUNTIME-FEEDBACK SWEEP (decisions.loop.runtime_feedback v1 compares the whole phase on any \
card once the destination boots, is silent with no boot and with the mode off or absent, is skipped by name when the \
receipt is already bound to this candidate digest but not when it is bound to another candidate or to the seal, leaves \
a parity card's own scoped comparison alone, and records which of the two triggers ran)"
