---
name: generate-product-tests
description: >
  Use at M4, before the destination is packaged and its tests are run, to
  GENERATE the product acceptance tests from the M1 source captures, and again
  at the release floor with --check. The harness owns the generated files: one
  @QuarkusTest case per qualified scenario, asserting the status, canonical
  body, required headers and declared effects the SOURCE was recorded
  producing. A worker never authors or weakens a generated expectation, and an
  unqualified scenario is a manifest gap rather than a silent omission.
license: Apache-2.0
compatibility: Linux seat; Python 3.9+; a JDK and Maven to run what it generates
metadata:
  author: rhoai3-harness-team
  version: "1.0.0"
  hermes:
    tags:
    - gates
    - m4
    category: gates
    kind: guidance
    paths:
      reads: ["/projects/modernized/verification/scenarios", "/projects/modernized/verification/source-oracles"]
      writes: ["/projects/modernized/src/test/java", "/projects/modernized/src/test/resources/generated", "/projects/modernized/evidence/tests"]
---
# Generated product parity tests (M4)

ADR-015 (architect, 2026-09-15): **a harness capability generates the tests
and owns the generated files; workers receive no authority to weaken
generated expectations.** This skill is that capability. It reads the derived
scenario corpus, the M1 source captures and their qualification, and writes
the `@QuarkusTest` cases that ask the destination the recorded question and
assert the recorded answer.

Nothing here decides a verdict. It decides which questions the destination
will be asked, from evidence somebody else recorded.

## When to Use

- **M4, before packaging and before the tests run.** Generate first, so the
  test phase measures the generated cases rather than whatever a worker wrote.
- **M4 release floor, with `--check`.** The generated files on disk must be
  the bytes the manifest binds. An edited expectation refuses.
- **Not** to hand-write a parity test. Not to "fix" a failing generated case
  by changing what it asserts: a generated case that fails is a parity
  finding, and the repair belongs in the destination.
- **Not** a replacement for the packaged-artifact parity gate
  (`capture-source-oracles` / `compare-scenario-parity.py`). `@QuarkusTest`
  execution runs in the test JVM against the development runtime;
  the parity gate runs against the artifact that ships. ADR-015 keeps both.

## What it generates

```bash
python3 "${HERMES_SKILL_DIR}/scripts/generate-product-tests.py" --root /projects/modernized
python3 "${HERMES_SKILL_DIR}/scripts/generate-product-tests.py" --root /projects/modernized --check
```

| Option | Meaning |
|---|---|
| `--out src/test/java` | where the generated sources go |
| `--resources src/test/resources` | where the recorded request bodies are copied |
| `--security-mode disabled\|enabled` | `enabled` lets an authenticating scenario carry its credentials **by reference**; `disabled` makes such a scenario a gap rather than an unauthenticated replay |
| `--reset-cmd '<argv>'` | the reset contract, defaulting to the script `capture-source-oracles` restores with |
| `--check` | verify the files on disk against the manifest digests |

For every scenario whose qualification records `capability: PASS`:

- one test method `parity_<scenario slug>` in
  `<entry point's declaring package>.generated.<SimpleType>ParityTest`,
  annotated `@QuarkusTest`;
- a **real request** through REST Assured — the recorded method, the concrete
  recorded path, the recorded headers (hop-by-hop dropped, `Origin` kept), the
  body bytes from the corpus body file, copied to
  `src/test/resources/generated/<slug>.body` and verified against the digest
  the corpus bound. No mocked controller, no mocked repository, no
  authentication substitute;
- `redirects().follow(false)` — the **first response** is the observation;
- `statusCode(<recorded>)`, then the canonical body digest, then every
  response header the capture asserted (`Location` origin-mapped only, the
  list-valued CORS headers as token sets, everything else literally, a
  recorded `null` asserted as absent), then every declared effect read back
  and compared to its recorded after-state;
- a `@BeforeEach` that runs the **declared reset** and then proves the
  destination is in the state the source started from, by replaying the
  capture's own `before` read-backs (any the reset contract names under
  `initial_state.identity_sequences` are reported as identity-sequence
  checks). There is no `@Transactional` on a generated test: a rolled-back
  test transaction does not undo an HTTP write, so it cannot stand in for a
  reset.

One shared `ParitySupport` class carries the reset runner, the origin map, the
credential-by-reference lookup and the canonical body digest. Its canonical
form is the comparator's, restated for the JVM and documented in the file:
sorted keys, no insignificant whitespace, ASCII escaping, Python's shortest
float repr, one trailing newline — so a digest recorded from the source and a
digest computed in the test mean the same thing.

`Location` is compared after mapping **only** the declared source origin to
the destination's, computed at run time from RestAssured's base URI and port.
The root path is not part of an origin and is not rewritten; no identifier is
normalized; no expected value is ever read back off the destination.

Credentials never appear in a generated file. `--security-mode enabled` emits
`ParitySupport.credential("<NAME>")`, which resolves a system property, else
an environment variable, and the manifest records the reference names.

## The manifest

`evidence/tests/generated-manifest.json`, which the release floor consumes:

```json
{
  "schema": "rhoai3.generated-tests/v1",
  "corpus_sha256": "…",
  "cases": [{"scenario": "sc:…", "class": "…ParityTest", "method": "parity_…", "entry_point": "ep:…", "…": "…"}],
  "gaps":  [{"scenario": "sc:…", "capability": "FAIL|INCONCLUSIVE", "kind": "…", "reason": "…"}],
  "files": [{"path": "src/test/java/…", "sha256": "…"}],
  "evidence_bundle_sha256": "…", "source_digest": "…", "qualification_sha256": "…",
  "security_mode": "disabled", "generator_version": "1.0.0", "reset_contract": {"…": "…"}
}
```

**Exact execution accounting.** Every scenario the corpus names is in `cases`
or in `gaps`; `totals` states both counts and the scenario count they must
add to. A case names the entry point it is linked to, the capture it was
generated from (`capture_sha256`), the request digest it replays, the headers
it asserts and the effects it reads back. A gap carries the qualification's
own reason. Nothing is silently omitted.

## What refuses

Exit 1, `REFUSE: GENERATE_TESTS …`, and nothing is written:

- a corpus that is neither derived nor authored, or whose derivation receipt,
  body bytes or request digests no longer bind (the loader's own rules);
- no evidence bundle in the tree to bind the generated tests to;
- no capture receipt, or one taken against another corpus or another bundle;
- no qualification, or one that judged another corpus or another bundle;
- a qualification record whose `capture_sha256` is not the capture on disk —
  **requalify after recapture**; a stale judgement is not a judgement;
- no reset contract in the tree and no `--reset-cmd`: a `@BeforeEach` that
  cannot restore the recorded state would assert against whatever it found;
- `--check`: a generated file that is missing, whose bytes moved, or an
  unlisted `.java` in a generated package; and a manifest written for another
  corpus.

A single scenario that cannot be generated faithfully is never a partial
test — it is a **gap**: no entry point whose declaring type is a Java type, a
request digest that is not the one the source answered, a capture with no
status or no header map for an exchange that requires one, a read-back nobody
took, an effect set the capture does not match, or an authenticating scenario
under `--security-mode disabled`.

## How the M4 road calls it

1. `generate-product-tests.py --root .` — **before** packaging and before the
   test phase, so the reports the phase produces are the generated cases'.
2. the destination is packaged and its tests run; every generated case must
   run with zero skips, failures and errors, against the tree and
   configuration under test.
3. `generate-product-tests.py --root . --check` at the release floor, beside
   the other pinned gates, so the verdict cites tests the harness still owns.
4. `check-domain-parity`'s product-test floor reads the same manifest: a
   family it requires is covered by generated cases, and a gap is visible
   rather than absent.

The packaged-artifact parity run (`run-parity.py`, `compose-parity-receipt.py`)
is unchanged and still required.

## Verification

- `scripts/generate-product-tests.test.py` — accounting (one method per PASS
  scenario, a named gap for every other, the four floor-consumed fields on
  every case); determinism across two runs with no date in the Java; the
  manifest's complete binding; `--check` refusing a weakened expectation, an
  unlisted file and a missing manifest; each refusal above; both security
  modes, including that no literal credential reaches a generated file; a
  renamed specimen (packages, types, routes, scenario ids) producing
  structurally identical output; no specimen literal in the generator; the
  generated Java balanced, carrying `@QuarkusTest` and a REST Assured chain,
  and compiled by `javac -proc:none` against compile-only stubs for
  `@QuarkusTest`, REST Assured and JUnit; and the generated canonical body
  digest cross-checked against the comparator's own canonical form on a JVM.
  The two JDK-dependent checks skip with a message when no JDK is on PATH.

## Scripts

- `scripts/generate-product-tests.py` — the producer and the `--check` gate
- `scripts/generate-product-tests.test.py` — the selftest
