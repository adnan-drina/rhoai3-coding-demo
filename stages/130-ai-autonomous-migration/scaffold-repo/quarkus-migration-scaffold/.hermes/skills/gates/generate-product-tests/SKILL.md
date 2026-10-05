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
      writes: ["/projects/modernized/src/parity-test/java", "/projects/modernized/src/parity-test/resources/generated", "/projects/modernized/evidence/tests", "/projects/modernized/pom.xml"]
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

- **M4, after the parity runner and before the pre-verdict runner.** Generate
  first, so the test phase the runner drives measures the generated cases
  rather than whatever a worker wrote. Never at M1, M2 or inside the M3 loop:
  the generated cases are not part of the loop's measure.
- **M4 release floor, with `--check`.** The generated files on disk must be
  the bytes the manifest binds. An edited expectation refuses.
- **Not** to hand-write a parity test. Not to "fix" a failing generated case
  by changing what it asserts: a generated case that fails is a parity
  finding, and the repair belongs in the destination.
- **Not** a replacement for the packaged-artifact parity gate
  (`capture-source-oracles` / `compare-scenario-parity.py`). `@QuarkusTest`
  execution runs in the test JVM against the development runtime;
  the parity gate runs against the artifact that ships. ADR-015 keeps both.

## Where the tests live, and when they run

**The generated cases execute in the M4 phase and in no other.** They are
written to a dedicated source root:

| | |
|---|---|
| sources | `src/parity-test/java` |
| resources | `src/parity-test/resources` |
| what compiles them | the `m4-parity` profile in the destination `pom.xml` |
| what activates it | the M4 pre-verdict runner (`mvn -Pm4-parity test`) |

Not `src/test/java`. A generated case measures PARITY, and parity is measured
once, against the tree M4 is closing on. Under the loop's own test root every
M3 verify would compile and run these cases; their failures would enter the
loop's measure — the tuple that decides ACCEPTED vs REVERTED — and revert the
step under verification for a reason that has nothing to do with it. The
phase rule is mechanical, not advisory: `--out` or `--resources` pointing
under `src/test/` is a refusal.

### The pom profile is harness-owned, and it is written at bootstrap

`bootstrap-destination.py` writes the block, from the same module this
producer writes it from (`scripts/parity_pom.py` — one definition of what
makes the generated tests runnable at all). So the profile is part of the
**committed** pom before M4 begins, and the rewrite below finds it
byte-identical and changes nothing. That is deliberate: the generated files
are written at M4, into a tree `assert-retrievable-tree` still requires to be
committed, and a pom the harness first edited at M4 would make that gate
refuse for the harness's own doing.

The destination `pom.xml` carries exactly one marked block:

```xml
    <!-- rhoai3:generated-tests:begin -->
    …<profile><id>m4-parity</id>… org.codehaus.mojo:build-helper-maven-plugin
       add-test-source      @ generate-test-sources → src/parity-test/java
       add-test-resource    @ generate-test-resources → src/parity-test/resources
     … maven-surefire-plugin (and maven-failsafe-plugin when the pom declares it)
       <systemPropertyVariables>
         <quarkus.test.profile>…the decided build profiles…</quarkus.test.profile>
         <…the declared security switch…>…the generated suite's mode…</…>
         …everything the base pom's own test-plugin configuration sets…
    <!-- rhoai3:generated-tests:end -->
```

- a re-run replaces **exactly** that block and nothing else in the pom; an
  `m4-parity` profile found OUTSIDE the markers is a refusal, not something to
  take over;
- the plugin is pinned (`3.6.0`) and the pin is recorded in the manifest.
  `probe-bom-managed.py` measures the BOM's `dependencyManagement`, which
  never manages a build plugin, so it cannot answer for this artifact; when a
  probe result does list it, the version is dropped and the BOM's is used —
  the evidence decides, not the constant;
- the block is printed on a `POM:` line and recorded under `pom_profile` /
  `pom_profile_sha256`. On a bootstrapped tree that line reads *already
  current*; a rewrite there means something moved the block after the
  bootstrap, and the floor will say so.

### The profile hands the test JVM two values the destination declares

Measured on destination v9 with the real platform build: `mvn -B -Pm4-parity
test` failed in the generated `@QuarkusTest` classes' augmentation with every
profile-guarded bean `@Vetoed`; and once the profile did reach the test JVM,
17 of 18 cases answered 401. Both causes were configurations the destination
had already DECLARED and that never reached surefire. So the block configures
the test plugin with:

| property | where the value comes from | what it prevents |
|---|---|---|
| `quarkus.test.profile` | `decisions.yaml` `build_profiles.active`, comma-joined — the same value the bootstrap writes as `-Dquarkus.profile` in `.mvn/maven.config` and as `quarkus.profile` in `application.properties` | `@QuarkusTest` augments under the TEST profile, which `quarkus.profile` does not select, so every profile-guarded implementation is `@Vetoed` and the suite measures a destination that has none |
| the declared security switch | `decisions.yaml` `security.switch.key`, set to `disabled_value`/`enabled_value` for the manifest's `security_mode` | the frozen source's own `src/test/resources` are on the test classpath and would otherwise flip the mode under the generated suite, which would then answer for a configuration nobody captured |

Neither is a test-only override, and the block says so in its own comment:
each restates, where the test JVM reads it, a value the destination already
declares. Nothing here is a specimen literal — the profile names and the
switch key come from the declaration.

- every property the base pom's own surefire (or failsafe) configuration sets
  is restated in the profile's copy. The base `<build>` is never edited;
- `decisions.yaml` declares no `security` section → the switch is **not**
  pinned, and the manifest records `security_mode_pinned: false` with a
  `pin_notes` entry saying the mode is decided by whatever the test classpath
  sets. Silence there would read as "pinned";
- `--check` asks the DECLARATION, not only the digest: a block whose bytes
  match its own manifest and that pins neither value is refused as
  `stale block: regenerate with --reapply-catalog`. That is the state of every
  tree bootstrapped before these pins existed, and the digest cannot see it;
- the recipe for such a tree is
  `bootstrap-destination.py --root <dest> --reapply-catalog`, which rewrites
  the block from the same shared definition and records the change.

## What it generates

```bash
python3 "${HERMES_SKILL_DIR}/scripts/generate-product-tests.py" --root /projects/modernized
python3 "${HERMES_SKILL_DIR}/scripts/generate-product-tests.py" --root /projects/modernized --check
```

| Option | Meaning |
|---|---|
| `--out src/parity-test/java` | where the generated sources go (the default; never a root the M3 loop compiles) |
| `--resources src/parity-test/resources` | where the recorded request bodies are copied |
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
  `src/parity-test/resources/generated/<slug>.body` and verified against the digest
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
  "files": [{"path": "src/parity-test/java/…", "sha256": "…"}],
  "pom_profile_sha256": "…", "pom_profile": {"profile_id": "m4-parity", "plugin": {"…": "…"}},
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
- no `pom.xml` in the tree, a pom that is not parseable XML, a pom that
  already declares an `m4-parity` profile outside the markers, or one whose
  markers are unbalanced;
- `--out` or `--resources` under `src/test/java` / `src/test/resources`: the
  generated cases would run in every M3 verify;
- `--check`: a generated file that is missing, whose bytes moved, or an
  unlisted `.java` in a generated package; a manifest written for another
  corpus; a manifest with no `pom_profile_sha256`; and the `m4-parity` block
  edited or gone — a suite nothing compiles is a suite that never ran.

A single scenario that cannot be generated faithfully is never a partial
test — it is a **gap**: no entry point whose declaring type is a Java type, a
request digest that is not the one the source answered, a capture with no
status or no header map for an exchange that requires one, a read-back nobody
took, an effect set the capture does not match, or an authenticating scenario
under `--security-mode disabled`.

## Committing what was generated

```bash
python3 "${HERMES_SKILL_DIR}/scripts/commit-generated-tests.py" --root /projects/modernized
```

The generated files land in a tree `assert-retrievable-tree` requires to be
committed against `HEAD`, and an untracked generated file is dirt to that
gate. The gate is **not** weakened: a verdict composed over a tree nobody can
retrieve says nothing about what was measured. This step is what makes the
tree retrievable again, and it is narrow on purpose:

- it refuses unless the manifest exists and `--check` passes — committing an
  edited expectation would make the edit the harness's own, and `--check`
  would never see it again;
- it commits **only** the manifest's `files[]`, the manifest, and whatever
  else sits under the generated roots. Any other change to `src/` or
  `pom.xml` — a worker's edit, a stray build artifact, a moved pom — is a
  refusal that names it. Whoever made that change commits it;
- author `generate-product-tests <generate-product-tests@local>`, message
  `m4: generated product tests (corpus <sha12>, generator <version>)`;
- idempotent: with nothing to commit it says so and exits 0, so a phase re-run
  is not a failure.

## How the M4 road calls it

1. `generate-product-tests.py --root .` — a step of `paved-road-m4`, after the
   batch parity runner and **before** the pre-verdict runner, so the rebuild
   that runner drives is what executes the generated cases.
2. `commit-generated-tests.py --root .` — the next step, before anything reads
   the tree, so `assert-retrievable-tree` measures a committed tree rather
   than the harness's own leftovers.
3. `run-m4-pre-verdict.sh` runs `mvn -Pm4-parity test` (no `clean`) and then
   snapshots the reports to `evidence/m4-pre-rebuild/test-reports`; every
   generated case must run there with zero skips, failures and errors,
   against the tree and configuration under test.
4. `generate-product-tests.py --root . --check` is one of that runner's
   feeding gates, with its own receipt under `evidence/receipts/gates/`, so
   the verdict cites tests — and a profile — the harness still owns.
5. `check-domain-parity`'s product-test floor reads the same manifest, and
   scans the generated root beside `src/test/java`: a declared capability is
   covered by an executed generated case, and a gap is visible rather than
   absent.

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
  And the pom: the marked block is added (with or without an existing
  `<profiles>`), it is idempotent across two runs, the pom stays parseable
  XML, the manifest binds the block on disk and records the plugin pin, a
  foreign `m4-parity` profile refuses, a tree with no `pom.xml` refuses,
  `--out`/`--resources` under the loop's test roots refuse, and `--check`
  refuses both an edited block and a missing one. And the pins, on a fixture
  whose decisions name OTHER profiles and another switch: both properties are
  in the block, what the base pom's test plugins already set is kept, the base
  `<build>` is untouched, an absent `security` section pins no switch and says
  so in the manifest, and a block that matches its own digest while pinning
  neither is refused as a stale block.

## Scripts

- `scripts/parity_pom.py` — the `m4-parity` block: its text, its digest, the
  plugin pin, the two declared values it hands the test JVM, and the
  idempotent rewrite. Imported by the producer **and** by
  `bootstrap-destination.py`, because two copies would be two definitions of
  what makes the generated tests runnable
- `scripts/generate-product-tests.py` — the producer and the `--check` gate
- `scripts/commit-generated-tests.py` — commits the generated suite, and only it
- `scripts/generate-product-tests.test.py` — the producer's selftest
- `scripts/commit-generated-tests.test.py` — the commit step's selftest, which
  also asserts the interaction: `assert-retrievable-tree` refuses the
  untracked suite and passes once this step has committed it
