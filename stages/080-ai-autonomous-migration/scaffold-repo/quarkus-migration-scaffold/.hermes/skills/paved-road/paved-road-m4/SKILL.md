---
name: paved-road-m4
description: >
  Pin only this on the M4 VERIFY card (K4 mints it when the work list
  reaches empty). Index for the closing phase: record what the legacy
  system does, measure the destination against it, run the fail-closed
  pre-verdict runner, compose the verdict from measured exit codes, lint
  it. The verdict is composed, never chosen: a non-empty failed_floors is
  a REFUSE. Never for M1, M2, M3, or story implementation.
license: Apache-2.0
compatibility: Linux seat; Hermes v0.20.5 Kanban; Python 3.11+
metadata:
  author: rhoai3-harness-team
  version: "1.0.0"
  hermes:
    tags:
    - paved-road
    - m4
    category: paved-road
    kind: guidance
---
# Paved road: M4 VERIFY (oracles → parity → pre-verdict → verdict → lint)

`steps.json` is the contract; `audit.json` is generated from it
(`python3 .hermes/lib/paved_road.py generate --steps steps.json --out audit.json`).
The reviewer runs `scripts/assert-paved-road-audit.py` over the official
Kanban log; silence, a missing KEEP artifact, or an unmatched `[exit 1]`
refuses.

M4 answers one question with evidence: does the destination do what the
source did. Everything here is measurement. Nothing here decides.

## Procedure (in order)

1. `skill_view capture-source-oracles` → run its **comparison** scripts. The
   source was recorded at M1; M4 asks the destination the same questions.
   Reads: `compare-runtime-parity.py` per admitted entry point, against
   `verification/source-oracles/<slug>.json`. Writes:
   `compare-scenario-parity.py` per scenario the approved corpus requires —
   it restores the declared initial state, proves the destination is in it,
   replays the complete recorded request (body and headers included) and
   reads back every declared effect. Then compose the receipt-bound summary
   (`compose-parity-receipt.py`, KEEP `verification/parity/receipt.json`);
   an entry point covered by scenarios passes only when every **required**
   one passed. An expected value comes only from the M1 capture. Never from
   the card body, never from what the destination happens to return, never
   from what you believe the legacy did, and never by re-capturing the
   source now — that would record its answer to a question the destination
   has already been asked.
2. `skill_view check-domain-parity` → run its evaluators. G-1 to G-4
   measured against the referent, each writing its own verdict. A REFUSE
   is a real outcome; the next step is to report it, not to soften it.
3. `bash .hermes/skills/gates/check-release-readiness/scripts/run-m4-pre-verdict.sh /projects/modernized`
   — the fail-closed runner: it snapshots the test reports **before any
   rebuild**, parses surefire, refuses a card body that pre-specifies a
   verdict, asserts the tree is retrievable, runs the pinned feeding
   gates so their receipts exist, then asserts that every pinned gate
   ran, that the G-4 claims are consistent, and that the fence was not
   evaded. KEEP `evidence/receipts/gates`. The feeding gates must run
   before the receipts are asserted, or the floor refuses on an empty
   directory.
4. `skill_view compose-m4-verdict` → author
   `evidence/verdicts/m4-verdict.json` from the measured exit codes and
   nothing else, with an explicit `failed_floors`. A non-empty
   `failed_floors` makes the verdict `REFUSE`. `idle: true` is a legal
   floor result; a floor you did not run is not. Then compose
   `evidence/verdicts/coverage-account.json` (`compose-coverage-account.py`)
   and carry its counts in the verdict's `coverage_account`: every source an
   accepted ADR retired gets a row naming its replacement scenario and its
   remaining gap.
5. `skill_view check-release-readiness` → lint what you just wrote: the
   verdict against its schema, the floor receipts, the claim tokens, and the
   coverage account against `decisions.yaml` and the parity receipt. This
   step can agree or refuse. It cannot change the verdict or the account.
6. Terminator: `kanban_request_review` with `reviewer=reviewer`, then end
   the turn. `kanban_block` kind=needs_input for an external or platform
   failure (no destination to call, no database, MaaS down). Never
   `kanban_complete`; never dest-dispatch M5.

## What refuses, and why that is the point

- A verdict that names a floor you did not run.
- A retirement with no row in the coverage account, a claimed replacement
  whose scenario did not pass, or a verdict reporting fewer gaps than the
  account holds. A disclosed gap does not refuse; a hidden one does.
- A verdict written before the pre-verdict runner (the runner is what
  makes the receipts the verdict cites exist).
- An expected runtime value that is not in an oracle.
- A card body that already contains a verdict token: the runner refuses
  it, because a pre-specified verdict is not a measurement.
- `PROVISIONAL_ACCEPT` without a retrievable tree: uncommitted `src/` or
  `pom.xml` means there is nothing to ship.

## Operator

A REFUSE verdict is the run's honest result, not a failure of the loop.
The Operator reads `failed_floors`, fixes the cause (a harness defect, a
catalog gap, an ADR in `decisions.yaml`), and either re-opens the work
with `fix-until-green/scripts/rewind.py` or accepts the refusal and
records why. Do not re-run M4 hoping for a different answer: the same
measurement on the same tree returns the same verdict.

## Self-test

`python3 scripts/selftest.py` (golden only, never on a card): steps.json ↔
audit.json sync, the kind rules (oracles first, runner before the
producer, `compose-m4-verdict` the only producer, lint after it), the
fixture PASS/REFUSE set, and the coverage lint.
