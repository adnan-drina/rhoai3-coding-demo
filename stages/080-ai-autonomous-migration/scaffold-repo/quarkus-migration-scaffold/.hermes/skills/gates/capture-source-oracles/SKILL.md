---
name: capture-source-oracles
description: >
  Use to record the expected runtime behaviour of the legacy system from
  the running source system itself, per admitted entry point (HTTP
  responses mechanically; scheduled, messaging, batch, and lifecycle
  entry points from operator-captured observations), and at M4 VERIFY to
  compare the destination against those records with a receipt-bound
  parity verdict. Expected values are never written by a worker or a
  model; a missing capture is INCONCLUSIVE, never a pass.
license: Apache-2.0
compatibility: Linux seat; Python 3.11+; network to the source and destination systems
metadata:
  author: rhoai3-harness-team
  version: "1.0.1"
  hermes:
    tags:
    - gates
    - m4
    category: gates
    kind: guidance
    paths:
      reads: ["/projects/modernized/evidence/planning"]
      writes: ["/projects/modernized/verification/source-oracles", "/projects/modernized/verification/parity"]
---
# Source-side oracles and runtime parity (M4)

M4 expected values come from the runnable source system or mechanical
evidence (SAD §8 step 8). This skill owns
`verification/source-oracles/*.json` (captured from the legacy system)
and `verification/parity/*.json` (destination comparison), both
append-only execution evidence bound to the admission receipt digest.
G-1..G-4 domain gates (`check-domain-parity`) and the M4 verdict
composer (`compose-m4-verdict`) are unchanged consumers.

## When to Use

- **Capture** once per planning cycle, against the legacy application
  running from the frozen source (any environment named in
  `decisions.yaml`), before M3 finishes.
- **Compare** on the `M4 VERIFY` card for every `parity:<entry point>`
  assertion the admitted DAG lists, with the destination running.
- **Not** to write an expected value by hand. `UNCAPTURED` oracles make
  the parity assertion INCONCLUSIVE and M4 cannot complete around it.

## Procedure

Reads are captured by request. Writes go through the **scenario corpus**: a
complete recorded request against a known initial state, with the effects that
prove what it did.

```bash
# 0. derive the corpus at M1, from the frozen source's own evidence (the
#    bundle's entry points, the OpenAPI examples, the seed rows, the
#    @CrossOrigin policies). Gaps are recorded, never filled in.
python3 "${HERMES_SKILL_DIR}/scripts/derive-source-scenarios.py" --root /projects/modernized

# 1. capture at M1 — one command, one runtime. It packages the frozen source,
#    starts it, restores the initial state before each scenario that asks for
#    it, replays the derived corpus, then captures the idempotent reads
#    through the same running source (corpus path_vars supply any templated
#    segment) and stops what it started. No admission receipt is needed: M1
#    precedes M2, so the capture binds to the evidence bundle.
python3 "${HERMES_SKILL_DIR}/scripts/capture-source-scenarios.py" --root /projects/modernized

#    then qualify what was captured against each scenario's own contract;
#    the parity receipt counts only qualified captures as coverage. This is
#    the third M1 step of this skill (paved-road-m1 steps.json), and it
#    RECORDS its verdict: only a refusal to judge exits non-zero
python3 "${HERMES_SKILL_DIR}/scripts/qualify-source-captures.py" --root /projects/modernized

#    reads alone, against a source someone else is running:
python3 "${HERMES_SKILL_DIR}/scripts/capture-source-oracles.py" --root /projects/modernized \
  --base-url http://legacy:9966/petclinic --path-var ownerId=1 --any-status \
  --observation 'ep:org.acme.jobs.SyncJob#sync():scheduled=/tmp/legacy-sync.log'

# 2. compare at M4, with the destination up. The scenario comparator restores
#    the declared initial state first and proves the destination is in it.
python3 "${HERMES_SKILL_DIR}/scripts/compare-runtime-parity.py" --root /projects/modernized \
  --dest-url http://localhost:8080/petclinic --entry-point 'ep:…'
python3 "${HERMES_SKILL_DIR}/scripts/compare-scenario-parity.py" --root /projects/modernized \
  --scenario 'sc:create-owner' --dest-url http://localhost:8080/petclinic
python3 "${HERMES_SKILL_DIR}/scripts/compose-parity-receipt.py" --root /projects/modernized
```

| Entry-point kind | Oracle | Mechanism |
|---|---|---|
| HTTP `GET`/`HEAD` | status + canonical JSON body (or text SHA-256) + asserted response headers when captured | requested mechanically; a templated path needs `--path-var` |
| HTTP `POST`/`PUT`/`PATCH`/`DELETE` | a scenario: complete request + initial state + declared effects + asserted headers (`Location`, `Access-Control-*`) | the corpus; a write with no effect declared refuses. The capture is the FIRST response (redirects are never followed) with the raw header values. `Location` is compared after mapping only the declared source origin to the destination's (path, escaping, query and fragment untouched); list-valued CORS headers compare as token sets. Every header the source exposes via `@CrossOrigin(exposedHeaders=…)` — read from M1's structure model, never from text — is asserted too, beside Location and the CORS set: a source that exposes an `errors` header has made it part of its contract, and a 400 whose errors moved elsewhere must not pass. A header the exchange requires — `Location` on a 201/3xx, the permission headers on a cross-origin exchange — against a capture with no `headers` map is INCONCLUSIVE: re-capture. "Required" is about COVERAGE, not value: a recorded null for one of them (no credential permission, say) is a legitimate observation and is compared as recorded |
| HTTP `OPTIONS` preflight | the permission headers the source answered (`Allow-Origin`, `Allow-Credentials`, `Allow-Methods`, `Allow-Headers`, `Max-Age`; `Expose-Headers` is the actual request's, not the preflight's) | a scenario carrying `Origin` + `Access-Control-Request-Method` (+ the request headers the actual call sends), no identity; it declares no effects |
| scheduled, messaging, batch, event, lifecycle | operator-captured observation file (log excerpt, queue dump, table export); normalized line set with timestamps stripped | `--observation <id>=<file>` |

## The security mode of an oracle (ADR-014)

The frozen source has a security switch, and its two settings are two
behaviours: disabled, every request is anonymous; enabled, the same request
answers 401 or 403 unless it carries an identity the policy allows. Each is
captured **separately** and each artifact says which it is, so no receipt of
one mode can stand for the other. A destination started with security enabled
is compared against enabled captures only.

| Mode | Captures | Qualification | Scenario verdicts | Receipt |
|---|---|---|---|---|
| `disabled` (default) | `verification/source-oracles/scenarios/` | `…/scenarios/_qualification.json` | `verification/parity/scenarios/` | `verification/parity/receipt.json` |
| `enabled` | `verification/source-oracles/scenarios-enabled/` | `…/scenarios-enabled/_qualification.json` | `verification/parity/scenarios-enabled/` | `verification/parity/receipt-enabled.json` |
| `enabled` + `--fixture-variant NAME` | `…/scenarios-enabled-<NAME>/` | `…/scenarios-enabled-<NAME>/_qualification.json` | `verification/parity/scenarios-enabled-<NAME>/` | `verification/parity/receipt-enabled-<NAME>.json` |

Every path is resolved through `_scenarios.py`
(`scenario_oracles_dir`, `qualification_path`, `scenario_parity_dir`,
`parity_receipt_path`, `capture_receipt_path`), so every consumer resolves the
same one. `_capture.json` records `security_mode`, `source_config` and
`credential_refs`; each scenario capture and each parity verdict records
`security_mode`; `_qualification.json` and the parity receipt record the mode
they judged, so an M4 verdict can name it.

Every consumer reads the **corpus of the mode it runs in**: the capture, the
qualification gate, the comparator and the receipt composer all resolve it
through `load_corpus(root, security_mode, variant)`, so an enabled run replays
`verification/scenarios-enabled/corpus.json` and can never grade the enabled
source against the anonymous requests sitting beside it.

### Where a body differs (H1a)

A body mismatch in a scenario or read-oracle verdict carries `body_diff`:
`{"kind": "json"|"text"|"unavailable", "differences": [{"path", "kind":
order|value|missing|extra|type|length, "expected", "observed"}], "order_only",
"summary", "truncated"}` (plus `total` when more than 50 differences exist).
A list with the same elements in another order is one `order` difference;
the summary collapses indices to `[*]`. Values are shortened. The
destination body is retained beside the verdict under `_bodies/` (capped,
digested, never inside the record); read oracles now retain the source body
under `verification/source-oracles/bodies/`. The receipt row carries
`body_diffs` pointers (`scenario`, `summary`, `order_only`, `kind`,
`verdict_file`).

### CORS with security enabled (ADR-020)

The enabled corpus declares the source's CORS policies and derives, per
policy, from the disabled corpus's own requests: `sc:cors-enabled-preflight-*`
(browser preflight, no credentials), `sc:cors-enabled-actual-anonymous-*`,
`sc:cors-enabled-actual-authenticated-*` (a declared identity the route's
guard accepts) and `sc:cors-enabled-probe-authenticated-*` —
`scenario_type: diagnostic-probe`, the only OPTIONS the loader admits with
credentials, never counted as browser-preflight coverage. A diagnostic probe
is non-gating (ADR-021): it is not required of its entry point, counts in no
verdict, `not_passed` or coverage, and its result is listed under the
receipt's `diagnostics`. Its classification is bound at capture and fixed by
the first recorded result (`verification/parity/classification*.json`); a
corpus that relabels a compared scenario is refused by the comparator and
counted as required by the composer (`classification_refusals`). The capture decides
every expectation; qualification records `browser_access: permits|prevents`
(a matched source rejection is parity, not a demonstrated permission), and
the enabled receipt stays INCONCLUSIVE on CORS until a qualified browser
preflight is on record (`cors.outcomes`).

The receipt keeps first-response redirect parity and target reachability
apart: a PASSing redirect whose target is dead stays PASS on its entry-point
row (`navigation: failed`) and the failure is its own row under
`navigation_obligations`, which fails the receipt.

### Fixture variants of a mode's baseline

A mode's baseline is the **declared dataset**. Some behaviour the architect's
exits ask about is not reachable from it — what the source answers for an
identity the seed *enables*, once that identity is disabled — and the answer
is never to edit the dataset every other capture is taken against. A declared
**fixture variant** is that state, recorded separately: the declared dataset
with the Operator's statements applied *after* it, its own corpus, its own
captures, its own qualification, verdicts and receipt, all under the same
path suffix, and the baseline restored and **verified** afterwards.
`normalize_variant` refuses a name a directory could not carry, a name that
reads as a mode, and a variant of the suffix-less default mode. Each artifact
records `security_variant`, and the comparator, the qualification gate and the
receipt composer refuse to mix a variant's evidence with the baseline's,
naming both states — the cross-mode reuse ADR-014 forbids, arriving through
the dataset instead of the switch.

```bash
V="${HERMES_SKILL_DIR}/scripts"
python3 "$V/derive-source-scenarios.py"  --root /projects/modernized --security-mode enabled --fixture-variant identity-disabled
python3 "$V/capture-source-scenarios.py" --root /projects/modernized --security-mode enabled --fixture-variant identity-disabled
python3 "$V/qualify-source-captures.py"  --root /projects/modernized --security-mode enabled --fixture-variant identity-disabled
python3 "$V/compare-scenario-parity.py"  --root /projects/modernized --security-mode enabled --fixture-variant identity-disabled \
  --scenario sc:fixture-identity-disabled-auth-allowed-read-root --dest-url "$DEST_URL"
bash   "$V/reset-parity-db.sh"           --root /projects/modernized          # the restoration: baseline, verified
```

- The **derivation** reuses the mode's own scenarios of the declared class
  (`security.fixtures[NAME].scenarios`) unchanged — same method, path,
  headers, identity and body bytes, bound by id and body digest — so a
  difference in the answer is the dataset and nothing else. It emits one
  `sc:fixture-<NAME>-<base>` per selected scenario, records the fixture's
  statements verbatim, and names the declared dataset (path and digest) they
  are applied after. What it expects is what the Operator declared: a `4xx`
  where `intent: refuse`, and otherwise a usable first response, because an
  expectation nobody declared is not invented. The base's effect assertions
  do not travel — they judge what a request did against the *baseline*.
  Its effect **read requests** do, for a refused write (ADR-018): a refused
  PUT/POST/DELETE carries them with `role: unchanged_under_refusal`, and
  `effects_reader.strategy` says how they are read:
  - `second_identity` — a declared identity (`security.identities`, by
    `credential_ref`) that is neither the refused nor the invalid one and
    holds every role the refused one holds reads before and after the
    request under the variant; the contract adds `after_equals_before`.
  - `revert_then_read` — chosen when no such identity is declared (no
    identity is invented). The derivation computes `fixture.revert` from the
    fixture's statements, only when each is a single-column
    `UPDATE t SET c = v WHERE k = w` whose baseline value the declared
    dataset defines (`_variant_revert.py`; otherwise
    `REVERT_NOT_COMPUTABLE: …`). The reads are taken as the request's own
    identity on the declared baseline; the request is sent on the variant;
    on the destination `reset-parity-db.sh --revert-variant NAME` then runs
    only that revert (it raises `REVERT_UNEXPECTED_STATE` and changes nothing
    unless it finds exactly the variant state) and the reads are judged
    against the source's own post-request reads. On the source (ADR-020) the
    request is sent to the source running against a same-engine database held
    by a server process built from the engine jar its artifact ships
    (`_source_store.py`, `reset-db/StoreDb.java`; the datasource key is read
    from the source's own `application*.properties`): the post-request
    snapshot is retained and digested, only the fixture rows are reverted
    (checked), and the reads are taken through the still-running source —
    `source_effects.observed: true`. Where no store can be held the capture
    records `observed: false` with the reason, and the comparator keeps the
    destination's no-effect result, the response result and the source
    effect (INCONCLUSIVE) apart in `results`; the scenario is not PASS. The
    contract adds `before_reads_usable` and `after_equals_before`. Every
    variant scenario declares `reset_before`, and the comparator re-applies
    the variant after a revert-then-read scenario.
  - ADR-021 (derivation v4): "unchanged" is a DATABASE claim. A refused write
    (either strategy) carries `effects_db_scope` — the source-schema tables
    its route and read-backs name, plus every table whose foreign key
    references one of them, with the rule recorded — and its contract adds
    `db_unchanged`. The capture reads every row and column of that scope in
    one transaction immediately before the request and again after it,
    before any revert (`source_effects.db`: both observations, digests,
    comparison and its definition). Qualification recomputes the comparison
    from the retained bytes; HTTP read-backs are kept beside it and never
    qualify "unchanged" (a disagreement is recorded, the database decides).
    The comparator reports the source effect as OBSERVED only with that
    comparison.
  With neither, the write carries no read-back, `effects_unobservable` names
  both reasons, and the comparator stays INCONCLUSIVE with them. Corpora are
  stamped `derived_from.variant_derivation`; one derived under an older
  derivation is refused by the loader ("derive the variant again").
- The **capture** builds the variant dataset from exactly the bytes the
  corpus names (a frozen source that moved underneath it is refused), writes
  it to `…/scenarios-enabled-<NAME>/_variant-dataset.sql`, and starts the
  source with `security.fixtures[NAME].dataset_config_key` pointed at it
  through a `file:` URL alongside the mode's own switch. The receipt records
  the statements verbatim, the declared dataset's digest and the variant
  dataset's.
- The **reset** (`reset-parity-db.sh --variant NAME`) loads the schema and the
  derived baseline, **verifies** the baseline, and only then applies the
  declared statements — so what the variant varies is a baseline the run
  proved. Restoring is the same script with no `--variant`, which loads the
  baseline and verifies it again.

### Who the enabled mode authenticates as: `decisions.yaml`

The switch and the identities are the Operator's **decision**, backed by an
ADR, not arguments typed at a shell — an identity on a command line is not
reviewable, is not in the tree the run is reproduced from, and nothing
downstream can say where it came from. `decisions.yaml` carries a `security:`
section, and `--from-decisions` (the default for `--security-mode enabled`
whenever no `--identity` / `--credential-ref` is given) is how both the
derivation and the capture read it:

```yaml
security:
  adr: ADR-014
  switch:                                    # the specimen's own property
    key: petclinic.security.enable
    disabled_value: "false"
    enabled_value: "true"
  identities:
    - name: admin                            # as the source's own seed spells it
      credential_ref: PETCLINIC_ADMIN_CREDENTIAL   # the NAME of an env var holding user:password
      roles: [ROLE_OWNER_ADMIN, ROLE_VET_ADMIN, ROLE_ADMIN]
  invalid_credential_ref: PETCLINIC_INVALID_CREDENTIAL
  request_policy: authenticated              # what the ENABLED configuration requires of every request
  fixtures:                                  # separately recorded variants of the source baseline
    - name: identity-disabled                # becomes the suffix of this variant's directories
      intent: refuse                         # the Operator states the source refuses these; omit to expect its own answer
      scenarios: auth-allowed                # the class of derived scenario this variant is recorded for
      dataset_config_key: spring.sql.init.data-locations   # the KEY the source reads its dataset location from
      statements:                            # the SPECIMEN's own SQL, applied AFTER the declared dataset
        - UPDATE users SET enabled = false WHERE username = 'admin'
```

Every value except `roles`, the fixtures' `statements` and their declared
`intent` is a key or a name. The statements are opaque here — nothing parses
or rewrites them — and they are recorded verbatim in the evidence because
they are fixture SQL, not credentials, and a run nobody can re-apply them
from is not reproducible. `request_policy` and `fixtures` are optional and
each is checked as what it is: a policy nothing implements, a fixture name a
directory could not carry, an empty statement list, an unknown scenario class
or intent, and a missing `dataset_config_key` are all typed gaps by field. `planner.decisions` refuses a
`credential_ref` that looks like a value (it carries `:` or whitespace) and an
identity that names none, and it names the FIELD rather than echoing what it
holds. The section is optional: a specimen with no security switch has no
enabled mode, and the M1 steps then record that reason rather than deriving or
capturing anything. The capture fills `--source-config` from
`switch.key=switch.enabled_value`, so the source is started the way the corpus
it replays was derived for.

A declared credential the workspace does not hold stops the capture **before
the source starts**: `_capture.json` is written with `status: idle` and a
reason naming the missing environment **variable**. The qualification of that
mode then records the same reason with `verdict: INCONCLUSIVE` and no
scenario. A missing fixture is a recorded blocker (ADR-014) — never an
invented identity, never silence.

```bash
# the enabled mode, driven from the decided file (the usual form)
export PETCLINIC_ADMIN_CREDENTIAL='<user>:<password>'   # the value stays in the environment
python3 "${HERMES_SKILL_DIR}/scripts/derive-source-scenarios.py" --root /projects/modernized --security-mode enabled
python3 "${HERMES_SKILL_DIR}/scripts/capture-source-scenarios.py" --root /projects/modernized --security-mode enabled

# ... or stated on the command line, for a fixture or one policy at a time
python3 "${HERMES_SKILL_DIR}/scripts/capture-source-scenarios.py" --root /projects/modernized \
  --security-mode enabled \
  --source-config petclinic.security.enable=true \
  --credential-ref PETCLINIC_ADMIN_CREDENTIAL
python3 "${HERMES_SKILL_DIR}/scripts/qualify-source-captures.py" --root /projects/modernized --security-mode enabled
python3 "${HERMES_SKILL_DIR}/scripts/compare-scenario-parity.py" --root /projects/modernized \
  --scenario 'sc:…' --dest-url http://localhost:8080/petclinic --security-mode enabled
python3 "${HERMES_SKILL_DIR}/scripts/compose-parity-receipt.py" --root /projects/modernized --security-mode enabled
```

- `--source-config KEY=VALUE` (repeatable) is passed to the runtime as a JVM
  system property **and** as the runner's own `--key=value` argument, and is
  recorded verbatim on the capture receipt. A value equal to a credential the
  environment holds is refused before the source starts; the refusal names the
  key, never the value.
- `--credential-ref NAME` (repeatable) declares an environment variable holding
  `user:password`. A scenario asks for it by name —
  `identity: {"kind": "basic", "credential_ref": NAME}` — and the capture sends
  `Authorization: Basic …` built at request time. Only the NAME is written
  down: no password, no account, no header value. A scenario naming a
  reference the capture was not given is a gap, never a quiet anonymous
  request.
- A scenario may declare `asserted_headers` — headers **this exchange** makes
  part of the contract, on top of the ones the source exposes through CORS.
  The enabled derivation puts `WWW-Authenticate` on every refusal probe: a
  source that answers 401 with a challenge has stated how to authenticate, and
  a destination that drops it has changed what a client sees. The capture
  asserts the union, records it as `asserted_headers_extra` (with the
  scenario's own in `asserted_headers_scenario`), and the comparator reads that
  union back and diffs it under the existing header rules — so a dropped
  challenge is a named `header WWW-Authenticate … vs …` diff, not a silence.
- Reads (`capture-source-oracles.py`) are captured in the **disabled** mode
  only: `verification/source-oracles/` is not mode-scoped, so the enabled
  capture skips them and its receipt says so (`reads_note`).
- Mixing refuses, everywhere: `compare-scenario-parity.py` prints
  `REFUSE: SCENARIO_PARITY mode mismatch`, and the qualification gate and the
  receipt composer refuse a directory whose `_capture.json` records another
  mode. A capture that records no mode at all is a pre-ADR-014 capture and is
  the disabled mode, and only that.
- The enabled mode has its **own corpus**, derived per authorization policy:
  see *Deriving the enabled-mode corpus* below. `verification/scenarios/` is
  the disabled corpus, `verification/scenarios-enabled/` the enabled one
  (`corpus_path`, `derive_receipt_path`); a corpus records the
  `security_mode` it is for and the loader refuses to read one mode's corpus
  as the other's.

## The scenario corpus

Scenario responses and before/after probes retain body evidence under
`verification/source-oracles/scenarios/bodies/<scenario>/`. Verify the file
against `evidence.retained_sha256`; for complete bodies it also matches
`evidence.raw_body_sha256`. The row's `body_sha256` remains the parity digest:
canonical JSON for JSON, raw bytes otherwise. Recompute that normalization
from the retained bytes and check it against the row before qualifying them.
The 1 MiB cap is explicit: `truncated: true` cannot prove full-list presence
or absence. Retain complete evidence before qualifying that scenario; do not
weaken its predicate. An unreadable exposed-header model refuses capture
before starting the source. `CAPTURED` still requires separate qualification.

### Deriving the corpus

`verification/scenarios/corpus.json` (`rhoai3.scenario-corpus/v1`) is a
**producer output**: `scripts/derive-source-scenarios.py` derives it from
evidence the harness already holds, and nothing in it is authored by a worker
or signed by a person. The concrete URLs come from the evidence bundle's entry
points; the request bodies from the frozen source's OpenAPI document (its own
`example` values, `$ref` and `allOf` resolved, `id` never sent on a create);
the seeded identifiers (`path_vars`, the row an update or delete addresses)
from `src/main/resources/db/<engine>/populateDB.sql`; the cross-origin
exchanges from every `@CrossOrigin` policy, and whether a delete's
references survive it from every JPA relationship, both in M1's structure
model. One scenario per rule per write entry point — `create`,
`create-invalid` (one property violating a declared `pattern` or `minLength`,
verified against the pattern), `update`, `delete` (`delete-referenced` or
`delete-cascading` where a row is referenced) — one `read` per entry point
whose mapping declares no HTTP method, and per policy a
`cors-actual` read and a `cors-preflight`. Each scenario records `derived_from` (which inputs produced
it) and `qualify` (what its capture must show).

**A data read declares `reset_before` too.** The derivation does **not** skip
the reset for a scenario just because it declares no effect: a `GET` of a
collection answers with whatever rows it finds, so its recorded body is only
deterministic if it reads a restored state — `sc:cors-actual-*` is a
collection GET and keeps `reset_before: true`, whatever the order the corpus
is walked in. What such a scenario does not have is a recorded **before**
state: the capture records the state the source started from by probing the
scenario's own effects, so one that declares none can never have one. That is
the comparator's business, not the derivation's — see *What refuses, and why*
below.

A **delete** addresses a row the database will let go. Every schema file
beside the seed (any `*.sql` in the same directory declaring `CREATE TABLE`,
found by content — petclinic's is `initDB.sql`, and every file read is listed
in `_derive.json`) is parsed for `FOREIGN KEY (col) REFERENCES table (col)`,
inline on a column or added by `ALTER TABLE`. The positive delete takes the
lowest seed row of the resource's table that nothing references; when every
row is referenced there is **no** unreferenced positive delete and a typed gap
names the constraint (`every seed row of specialties is referenced
(FK_VET_SPECIALTIES_SPECIALTIES/vet_specialties.specialty_id); no deletable
row derivable`). The table is named by the path variable's own mapping
(`{petTypeId}` → `types`), else the route's segments with the same
singular/plural tolerance; a table that cannot be named is a gap and the row
falls back to the path variable's.

A referenced row is a different question, and **the schema does not answer
it**. A foreign key with no `ON DELETE CASCADE` says the DATABASE will refuse;
it does not say the SOURCE will, because the application may remove the
references itself first. Measured on v9 (2026-09-14): the derived negatives
expected a refusal for owners, pets, types and vets and the frozen source
deleted all four (204); only `specialties` refused. So the other half of the
evidence is the persistence model in M1's structure model, read from the
annotations and their values — never from text. For the lowest referenced row,
each constraint that reaches it is classified:

- the **application** removes it — the delete target's entity declares a
  relationship whose target entity maps to the referencing table with
  `cascade` containing `ALL`/`REMOVE` or `orphanRemoval = true`
  (`Owner.pets @OneToMany(cascade = ALL)`), or the referencing table is the
  join table of a `@ManyToMany` the entity **owns** (it declares the
  `@JoinTable`, or the other side declares `mappedBy` pointing at its field —
  `Vet.specialties @JoinTable(vet_specialties)`);
- the **schema** removes it — the constraint itself declares `ON DELETE
  CASCADE` / `SET NULL`;
- **nothing** removes it — the entity declares neither (`Specialty` is the
  inverse `@ManyToMany` side; `PetType` declares nothing at all, `Pet.type`
  being a `@ManyToOne` on the child).

An entity is mapped to its table by `@Table(name)` when present, else by its
simple name with the same singular/plural tolerance, and that mapping is
recorded as evidence. A relationship's target entity is derived from
`targetEntity`, from the field type when that is itself an entity, from
`mappedBy` (the entity declaring a field of that name typed as this one) and
last from the field name — the structure model records the ERASED field type
(`java.util.Set`), so a collection's element type is never read off the field.

Each answer derives a different scenario, and nothing is derived from the
answer nobody has:

| the reference is removed by | scenario | contract |
|---|---|---|
| the application, or the schema's own `ON DELETE` rule | one positive `sc:delete-cascading-<resource>-<id>` on the lowest referenced row | `expect_status: [200, 204]`, the item reads back `404`, and so does each referencing row a **bound item route** can read (at most three, the cap noted in `derived_from`); with no such route the effect list is the item alone and `derived_from` says the children are unobservable through routes |
| nothing | one negative `sc:delete-referenced-<resource>-<id>` | any `4xx`, and the item still readable (`200`) afterwards |
| not derivable — no structure model, an entity or field that maps to no table, a cascade token this derivation does not know | **neither**; a typed gap (`delete-referenced ep:…: whether the application removes pets.owner_id references is not derivable (…)`) | — |

Both carry the FK evidence **and** the application-removal evidence in
`derived_from`, so the qualification record can quote which annotation on
which field decided it (or `none declared`). The gate needs no new check
kind: a cascading delete's effects are one `after_effect_status` map of
effect id → `404`.

An entry point whose mapping declares **no HTTP method** is not a gap. Spring
MVC reads `@RequestMapping` without `method` as matching EVERY method, so a
GET is a request the evidence supports, and one read scenario `sc:read-<path
slug>` is derived for it: a GET of the concrete path (path variables through
the same `path_vars` rule), `body_absent`, `reset_before: false`, no effects,
`derived_from` naming `structure:<controller>#<member> @RequestMapping without
method → GET (Spring: no method matches every method)`. Its contract is the
source's **own first response** — status, headers and body, redirects never
followed — because neither class is knowable in advance: petclinic's root
mapping answers `302` to `servletContextPath + "/swagger-ui/index.html"`,
another such mapping renders a page. So `qualify` states
`usable_first_response` and nothing else: qualification judges whether the
evidence can be judged at all and RECORDS the status class it observed
(`observed_status_class`), PASS on a usable non-5xx answer, INCONCLUSIVE
otherwise. At M4 the comparator compares that first response, `Location`
included, after mapping only the declared source origin — so a redirect target
that moved is a parity mismatch typed by its diffs. Measured on v9
(2026-09-14): this mapping was a gap, nothing observed it, and the destination
then replaced the SpEL `@Value("#{servletContext.contextPath}")` with
`@Value("")` — a redirect out of the destination's own root path that no
scenario could see. A method-less mapping whose handler declares a
`@RequestBody` parameter derives **no** GET (it consumes a body) and a typed
gap says so, as do a wildcard route and a member M1's structure model does not
record (a servlet mapping is not a request the corpus can derive).

What cannot be derived is a **gap**, recorded in the corpus and the receipt
and never filled in: a required property without an example, a path variable
no seed row supplies, a mapping with neither an HTTP method nor a method-less
`@RequestMapping` to derive one from. The corpus is bound
to the evidence bundle by digest in `verification/scenarios/_derive.json`;
the loader refuses a derived corpus edited after derivation (its digest no
longer matches), one derived against another bundle, or one whose receipt is
not `status: ok`. A hand-authored corpus naming `approved_by` is now the
**exception** (a specimen whose evidence cannot be derived); a placeholder
approver (`TODO`, `<who>`) is refused, and the derivation refuses to overwrite
a hand-authored corpus at its output path.

### Deriving the enabled-mode corpus (ADR-014)

The same source with its security switch enabled is a different behaviour,
and ADR-014 says what an oracle of it must show: **each distinct
authorization policy exercised with an allowed identity, anonymous access,
invalid credentials and an authenticated identity lacking the required
role**, compared against the source's own outcomes, challenges and
denied-write effects included — and, where the fixtures for that are not
there, a **blocker** rather than a manufactured identity.

```bash
# the usual form: the identities are the ones decisions.yaml declares
python3 "${HERMES_SKILL_DIR}/scripts/derive-source-scenarios.py" --root /projects/modernized \
  --security-mode enabled

# the explicit form, for a fixture or one policy at a time. The credentials
# stay in the environment; only the NAMES are passed and recorded
python3 "${HERMES_SKILL_DIR}/scripts/derive-source-scenarios.py" --root /projects/modernized \
  --security-mode enabled \
  --identity admin=PARITY_ADMIN --identity helper=PARITY_HELPER \
  --identity invalid=PARITY_WRONG \
  --identity-roles helper=ROLE_VET_ADMIN        # optional where the seed says it
```

- `--from-decisions` reads the identities, their credential references and the
  source's switch from `decisions.yaml` (see *Who the enabled mode
  authenticates as* above) — the default whenever `--security-mode enabled` is
  given with no `--identity`. The corpus and the receipt record
  `identities_from` and `security_switch`, so which declaration this corpus
  came from is on the artifact. Passing both `--from-decisions` and
  `--identity` is refused: a corpus must be able to say where its identities
  came from. With no section the derivation writes `_derive.json` with
  `status: idle` and the reason, and derives no corpus.
- `--identity NAME=CREDENTIAL_REF` (repeatable) declares which environment
  variable holds the credential that authenticates as the **seeded identity**
  `NAME` (the value the identity store's own rows carry). The reserved name
  `invalid` declares a reference the Operator states is *not* a valid
  credential. No password is ever read here, and only the reference is
  written down — into the scenario's `identity`, its `derived_from` and the
  receipt. The disabled mode refuses both options: it sends no credential.
- `--identity-roles NAME=ROLE[,ROLE…]` (repeatable) declares what that
  identity holds. Where M1's structure model maps the identity store, the
  roles are **derived from the seed** instead: the table carrying a column
  whose seeded values are the roles the policies accept is the role table,
  its single foreign key names the identity table, and both must be mapped by
  a JPA entity — the same seed parse the delete rules use. A declaration the
  seed contradicts is a typed gap and **the seed is used**. An identity whose
  roles neither source settles is used for no probe.
- **The request is not derived again.** A policy is probed over the
  qualified-shaped scenario the *disabled* corpus already carries for the
  entry point it guards, reused method, path, headers and body bytes, bound
  by that scenario's id and body digest (`base_scenario`,
  `base_body_sha256`, and the base corpus digest in the receipt). The two
  modes then send the same bytes, and a difference in the answer is the
  security switch. Cross-origin exchanges are not reused: they are the CORS
  oracle's scenarios, and a probe carrying an `Origin` would answer two
  questions at once.
- **A guarded read gets its own base.** The disabled corpus derives no
  scenario for a plain `GET` — the idempotent reads are captured outside it —
  so a policy on a read had no request to be probed over, which is exactly the
  authorization the enabled mode exists to prove. When the entry point states
  `GET` and its route is made concrete by the path variables the *disabled*
  corpus already resolved out of the source's own seed, the derivation writes
  that read itself, in the shape a read has (`GET`, no body, no effect,
  `reset_before: false`, `usable_first_response`), and probes it. The
  scenarios say so: `base_source: derived-read`, an empty `base_scenario`, the
  route in `base_route`, and evidence naming the entry point and the path
  value taken. A route with a variable nothing resolves keeps its `auth-base`
  gap — a concrete URL is never invented to reach a probe.
- **Expression grammar.** `hasRole(…)`, `hasAnyRole(…)` and the role list of
  `@RolesAllowed` / `@Secured`, where a role is a quoted literal or a constant
  reference (`@roles.OWNER_ADMIN`, `#roles.OWNER_ADMIN`, `Roles.OWNER_ADMIN`,
  `T(a.b.Roles).OWNER_ADMIN`) resolved through the **structure model's own
  field values** — the harness never knows what a role is called. Anything
  else (a combination, `hasAuthority`, a bean call) is the typed gap
  `auth-policy <expression>: not in the supported grammar` and derives
  nothing: an identity "lacking the role" of an expression nobody read is a
  false expectation.
- **A bean reference is not a type reference.** `@roles` / `#roles` is a SpEL
  bean name, so it resolves to the type that carries a component stereotype
  (`@Component`, `@Service`, `@Named`) and whose *decapitalized simple name*
  is that name — or whose stereotype **states** it (`@Component("theRoles")`
  registers `theRoles` and nothing else). `Roles.X` and `T(a.b.Roles).X` name
  the type itself and need no stereotype. Each scenario carries the
  resolution: `structure:Roles @Component → bean roles; Roles.VET_ADMIN =
  "ROLE_VET_ADMIN" (constant from sealed structure)`.
- **Where the constant's VALUE comes from.** M1's extractor records a field's
  compile-time `String` initializer as `constant` in `rhoai3.structure/v1`, so
  the sealed model carries the role name itself. A run whose structure model
  was sealed **before** that key existed records the constants type with its
  fields and no values; rather than refuse it, the derivation compiles the
  **frozen source** (`analysis_copy`, `src/main/java`) with the dest-model
  extractor — its own build classpath when the build producer published one,
  otherwise a partial attribution, which a literal initializer does not need —
  and resolves from there. Only when a policy actually names a constant the
  sealed model lacks, and the sealed model keeps precedence wherever it has a
  value. The receipt records the run in `inputs.constants` (tool, tree, source
  digest, model digest, resolution, which references it answered), and the
  scenarios say `(constant from frozen-source model)`. With neither model
  carrying it, the typed `auth-policy … not in the supported grammar` gap
  stands and nothing is derived.
- **What each probe expects.** `sc:auth-allowed-*` states no status — the
  source's actual outcome is what the capture records (`usable_first_response`)
  — and keeps the base scenario's assertions about what the request *did*.
  `sc:auth-anonymous-*`, `sc:auth-invalid-*` and `sc:auth-norole-*` expect any
  `4xx` (401 and 403 are both the source's own answer) and, for a write, the
  base scenario's read-backs unchanged across it; the two unauthenticated ones
  also assert the challenge header `WWW-Authenticate` on the first response
  (`asserted_headers`).
- **Who reads the state back (`effects_identity`).** A refused write has to
  show that nothing changed, and the caller it refused is answered `401` by
  the read-backs too: on v9 the before/after probes of every
  `sc:auth-anonymous-*` and `sc:auth-invalid-*` write answered 401, so all 15
  qualified INCONCLUSIVE with *`before eff:… answered 401, not 2xx; its body
  cannot stand for the collection`*. Each negative probe therefore names an
  `effects_identity` — the identity the policy accepts, the same one its
  `auth-allowed` sibling runs as, by credential REFERENCE — and the capture
  and the comparator take the read-backs as that one while the request itself
  stays exactly the request the source refused. The scenario says so in
  `derived_from.evidence` (`effects-identity:<who> holds <roles>,
  credential_ref <NAME>; the before and after read-backs are taken as this
  identity`). Where no declared identity holds the role there is nobody to
  read the state back as: `after_equals_before` is **not** stated (a
  predicate nothing could settle is not a contract) and the gap
  `auth-effects <policy> <entry point>: … the state this policy's refusals
  leave is not observable` stands instead.
- **Blockers, never inventions.** No declared identity holding the role, none
  lacking it (`auth-norole <policy>: no declared identity lacks <roles>; the
  seed provides none`), no invalid credential declared, or no qualified-shaped
  base scenario for a guarded entry point — each is a typed gap with no
  scenario. Reads are captured outside the corpus, so a policy guarding a
  plain `GET` has no base to reuse and says so.

#### The request policy: routes no annotation names

`anyRequest().authenticated()` guards the routes that carry **no**
`@PreAuthorize` as surely as the annotated ones — on the pilot specimen the
root redirect among them — and a derivation that walks only the annotations
leaves them unprobed, which reads at M4 as *nothing to prove* rather than
*not measured*. Only the Operator can read that off the source's own
configuration, so it is declared: `decisions.yaml`'s
`security.request_policy: authenticated`.

With it declared, the derivation adds one implicit policy
(`authz:request-authenticated`) over **every HTTP entry point it has a
request for** — a qualified-shaped scenario in the disabled corpus, or a
derivable read base — and probes each with an identity the policy accepts
(the least privileged declared one), anonymously, and with the credential
declared invalid. On the pilot specimen `sc:read-root` therefore gets
`sc:auth-allowed-read-root`, `sc:auth-anonymous-read-root` and
`sc:auth-invalid-read-root`. There is no fourth probe: no identity
authenticates and still fails a policy whose whole requirement is
authentication. Entry points an **explicit** policy already guards keep
theirs — a role is more than a login, and the probes that prove it are not
replaced. Every scenario says where the guard came from
(`policy:<id> decisions.security.request_policy authenticated → every
request`) rather than citing an annotation nobody wrote, the corpus and the
receipt record `request_policy`, and an entry point the policy covers that
nothing can request is a named `auth-base` gap. A tree that declares none
probes none and the receipt carries `request_policy_note` saying so.

**One seam this producer does not own.** `capture-source-scenarios.py` (like
`compose-parity-receipt.py`) still loads `verification/scenarios/corpus.json`
for every mode: `load_corpus(root, security_mode, variant)` and
`asserted_headers` are there to be passed through when those builders take
them up.

### Qualifying captures

`CAPTURED` records an observation, including an unexpected one.
`scripts/qualify-source-captures.py` checks every capture against its
scenario's `qualify` block and writes
`verification/source-oracles/scenarios/_qualification.json` with **two
results per scenario**:

- `evidence`: `USABLE` or `UNUSABLE` — can this capture be judged at all?
  It must exist and be `CAPTURED`, be bound to this corpus, this bundle and
  this very request (`request_sha256`), every retained body the contract
  reads must be present, digest-bound (`retained_sha256`, `raw_body_sha256`,
  not `truncated`, `body_sha256` recomputing) and every read-back the
  contract reads must have been taken as the identity the scenario names for
  its effects (`effects_identity`, else the request's own) and must have
  answered 2xx. Evidence is judged **before**
  intent: with unusable evidence `capability` is INCONCLUSIVE, never FAIL,
  while `known_failures` still records what was observed (a 500 is on the
  record, not hidden).
- `capability`: `PASS | FAIL | INCONCLUSIVE` — did the source demonstrate
  what the scenario intends? `qualify.intent` is `positive` (create, update,
  delete, cors-actual, cors-preflight: the source performed it) or
  `negative` (create-invalid: the source rejected as intended — the status,
  a parsed field error naming the property, and no effect).

The checks: `expect_status`; `usable_first_response` (a read derived from a
method-less mapping: the capture carries a first response at all — the class
is not asserted, it is recorded); `expect_status_class` (`4xx`: the source
refused, and which 4xx is its own choice — a derived `delete-referenced`
states exactly this); `location: absolute-under-base` (absolute, on
the capture's `source.base_url` origin, under its path, compared literally);
`creates_one_entity` with `identity_field` (derived from the collection
GET's OpenAPI response schema — the items' `id`, else the first readOnly
integer; `null` makes the gate INCONCLUSIVE "collection identity not
derivable"): exactly one entity with a NEW identity appears after the
create, it carries every key/value of the request body, every prior entity
is still present unchanged, and the Location's last path segment is that
identity — a duplicate row with an existing id and a Location pointing at
999 FAILs naming each broken condition; `after_contains_body`;
`before_lacks_body` (hand-authored corpora); `after_equals_before` (same
digest and status, both read-backs 2xx and retained);
`errors_header_names_field` (the `errors` header must parse as JSON —
petclinic's BindingErrorsResponse is an array of objects — and carry an
element whose values include the property: not JSON is INCONCLUSIVE "errors
header not parseable", no such element is FAIL); `after_effect_status`;
`cors_allow_origin`, `cors_expose_headers`, `cors_allow_method`,
`cors_allow_headers` (token sets). Each record is bound to the exact capture
it judged (`capture_sha256`, `request_sha256`, `corpus_sha256`,
`evidence_bundle_sha256`).

Evidence is weighed first and intent second, and the two are not the same
question. An UNUSABLE capture — absent, unbound, a retained body that is not
whole or not its digest, a read-back that did not answer 2xx, an `errors`
header that does not parse, a 5xx the contract does not name — is
INCONCLUSIVE, never FAIL, with what was observed in `known_failures`. With
usable evidence the capability is judged over the predicates that could be
judged: **any judged predicate failing is FAIL**, none failing with at least
one unjudgeable (`creates_one_entity` where the document names no
`identity_field`) is INCONCLUSIVE, all judged and passing is PASS. A 400
carrying a well-formed errors header is usable evidence, so an
`expect_status` miss on it is a judged failure — on v9 that mismatch was
reported INCONCLUSIVE because the same create's identity was unanswerable,
and went unrecorded. The unjudgeable predicate stays in `checks` (`ok: null`)
and in `unjudged` either way.

Negative scenarios are derived **one per constrained property**
(`sc:create-invalid-<resource>-<property>`), so a `firstName` rejection is
never mistaken for `telephone` coverage.

The gate is an **M1 step** (`paved-road-m1` `steps.json`, right after
`capture-source-scenarios`), and its verdict is a record, not a refusal: it
exits 0 whenever a bound qualification document was written, PASS, FAIL or
INCONCLUSIVE alike (`OK: qualification FAIL (4 of 19 not qualified) → …`),
and exits 1 only when it cannot judge at all — no corpus, a corpus that is
neither derived nor authored, a provenance whose digests no longer bind, or
not one capture on disk. A FAIL is a fact about the SOURCE, which M4 turns
into a coverage gap and which never becomes a destination card, so failing
the step on it would have been a refusal to record what the source does.
`compose-parity-receipt.py` reads the records: a qualification whose
`capture_sha256` no longer matches the capture on disk is stale
(`requalify after recapture`, INCONCLUSIVE); a scenario qualified
INCONCLUSIVE, or with no record, makes its entry point INCONCLUSIVE
(`capture not qualified: …`) and is listed under `coverage_gaps` with
`kind: inconclusive-qualification` — a capability nobody judged is a
capability nobody demonstrated, and without that entry the M4 coverage
account could not see it; a derived corpus with no qualification at all
is INCONCLUSIVE (`captures not qualified`). A **positive** scenario whose
capability is FAIL is a **source-side fixture failure** (a create the source
answered 400 for): the source did not perform the operation, so parity
is not asked — `compare-scenario-parity.py` writes INCONCLUSIVE `source
fixture failed qualification: …`, the entry point is INCONCLUSIVE, the
scenario is listed under `coverage_gaps` with `kind: fixture-failed`, it
earns no parity credit and never becomes a destination repair card
(`worklist.parity_items` issues obligations only from FAIL verdicts). A
negative scenario whose capability is PASS compares parity normally and is
counted as negative coverage only (`coverage.negative` on the row). The M4
coverage account (`compose-coverage-account.py`) records every receipt
coverage gap as an `uncovered_capabilities` entry and denies replacement
credit to any `replaced_by` entry point carrying a positive one. An
Operator-authored corpus without a qualification file keeps its previous
behaviour.

The operation for a route is found by path (exact, else the longest document
path the route ends with); a path match whose `operationId` names a
different controller member is a typed gap (`conflicting binding: path X ↔
operationId Y ≠ member Z`). When the document's paths do not name the
code's routes (petclinic documents `/owner` while the controller maps
`/api/owners`) an explicit adapter binds by `operationId` equal to the entry
point's method name, same HTTP method, provided exactly one controller
member of that name exists in the bundle or one is singled out by a
compatible request schema (the parameter DTO and the schema share a stem
after `Dto|Fields|Request|Input|Payload`: `OwnerDto` ↔ `OwnerFields`); tags
only narrow, never establish, and a surviving ambiguity is a gap. A name
match is not yet a binding: the operation's **path variables must be exactly
resolvable through the route's** — the same set of names, compared literally
(one variable on each side under a different name still binds, since the
path binder this adapter stands in for matches with the names erased). A
difference is a typed gap and **no scenario at all**, positive or invalid
(`create ep:…addPet: operationId addPet binds POST /owner/{ownerId}/pet
(variables: ownerId) to route /api/pets (variables: none); path-variable sets
differ; not bound`): on v9 that binding handed `POST /api/pets` a
`PetFields` body whose identity the route cannot express, the source answered
400, and the gate could only say INCONCLUSIVE. The discrepancy that DOES bind
is recorded in `derived_from.evidence`
(`openapi-path:/owner≠route:/api/owners; bound by operationId addOwner`).
The derivation receipt also binds every body file's bytes and every
scenario's `request_sha256`; a body edited after derivation is refused.

### The corpus document

Start from `.hermes/planning/scenarios.example.json` only for the
hand-authored exception; it carries the shape and the rules below. An optional `path_vars`
map supplies the values the idempotent reads need for templated paths, from
the source's own seeded data. Each scenario carries the
method, a **concrete** URL (never a route pattern — the route stays in the
inventory and is associated with scenario URLs), the headers, how it
authenticates (**by environment-variable reference**), the body bytes or an
explicit `body_absent: true`, whether the initial state is restored first, the
effects that prove the write, and the permitted normalization.

`identity` accepts two kinds. `{"kind": "none"}` (the default, and the only
one the disabled mode uses) is an anonymous request. `{"kind": "basic",
"credential_ref": NAME}` names one environment variable holding
`user:password`; `{"kind": "basic", "user_env": A, "password_env": B}` names
the two halves separately. A reference is part of what makes a request the
same request, so it is digested; a key that would hold the credential itself
(`password`, `secret`, `token`, `authorization`) is refused outright, and so
is any other kind.

An **enabled-mode** corpus carries a little more, and the loader reads it the
same way: `security_mode: "enabled"` on the document and on every scenario
(a corpus of one mode never loads as the other's), `identities` and
`invalid_credential_ref` (names and roles beside the credential REFERENCE,
never a credential), `authorization_policies` (id, annotation, expression,
the roles it accepts, the entry points it guards), and per scenario the
`authorization_policy` it exercises, the `base_scenario` and
`base_body_sha256` of the disabled-mode request it reuses, and the
`asserted_headers` a refusal must be read with.

CORS is covered per policy. `cors_policies` declares each one (`id`, the
`request_headers` its actual calls send); a scenario that sends `Origin` names
its `cors_policy`. Each policy needs an actual cross-origin exchange and a
preflight, and every policy the frozen source declares — each distinct
`@CrossOrigin`, each CORS registry, read from M1's structure model — must be
declared. Missing coverage makes the parity receipt INCONCLUSIVE.

Ownership: the Operator owns intent and environment authorization; the M1
producer owns execution; implementation workers own neither and never see an
expected value.

What refuses, and why:

- A path with `{...}` or `*` in a scenario. A scenario is a request.
- A scenario that neither names a body nor states it has none. An absent body
  (a `DELETE`) is a fact to record, not an omission to infer.
- A write scenario with no declared effect. An identical response does not
  prove the write happened.
- A replay whose reconstructed request digest differs from the one the source
  answered. **This is the defect the corpus exists for**: the comparator used
  to send the recorded method and path with no body, so a `POST` the source
  answered `201` for was replayed empty, answered `400`, and compared `FAIL`
  against a destination that behaved identically.
- A source capture taken against a different corpus digest. Re-capture the
  source rather than comparing across corpora.
- A `204` that deleted nothing. The response matches and the effect does not.
- A destination that is **not in the state the source started from**. Each
  capture records the effect probes *before* the request too, and the
  comparator restores the declared initial state (`reset_before`) and then
  proves it. Without that, a delete against a destination whose row was
  already absent passed on both the response and the effect. A scenario that
  declares `reset_before` and **effects** whose capture recorded no before
  state is INCONCLUSIVE: those probes were asked for, so re-capture the
  source. A scenario that declares `reset_before` and **no effects** is a
  different case and is **not** a refusal: the capture records the before
  state by probing the scenario's own effects, so one that declares none never
  had a before state for anyone to record. It is reset like any other — the
  request may depend on the seeded rows, and a collection read's body is only
  deterministic against a restored state — and then compared on its first
  response: the verdict notes `before_state: none declared`, PASS when the
  response matches, FAIL typed by its diffs when it does not, never
  INCONCLUSIVE for the absence of a state nobody could have recorded.
  Measured on v9's first M4 parity receipt (2026-09-15): `sc:cors-actual-*`
  (a `GET` with `effects: []`) came back INCONCLUSIVE on exactly that absence.
- A declared reset that could not run. The comparison does not happen.
- A required scenario with **no result**, a result bound to another receipt or
  another corpus, or two results for one scenario. The required set comes from
  the corpus, never from which files exist.

### Which records a receipt is composed from (`orphaned_records`)

`compose-parity-receipt.py` composes over the records on **disk**, and that is
deliberate: it is what lets a scoped run (`run-parity.py --scenario`) keep the
verdicts the last full run left for every scenario the filter was not scoped
to, so the receipt still states every entry point. It composes only over the
records that **belong** to it:

- the file name is `scenario_slug(id)` of a scenario the **current** corpus
  declares, and the record holds that scenario;
- `corpus_sha256` is this corpus's digest (a record carrying **none** is not a
  leftover but a comparison that refused before it could bind one: it stays,
  and the row refuses it by name);
- `security_mode` and `security_variant` are this receipt's.

Every other file in `verification/parity/scenarios*/` is listed in the receipt
under `orphaned_records` (`path`, `kind` in `undeclared-scenario` /
`name-mismatch` / `stale-corpus` / `other-mode` / `unreadable`, and the
`reason`) and is counted in **no** row, total or verdict. A required scenario
whose only record on disk is an orphan is INCONCLUSIVE **for the orphan's
reason**, not as a plain absence.

Measured on destination v9: that directory still held
`cors-preflight-<digest>.json` and `cors-actual-<digest>.json` from an earlier
naming scheme beside the current `sc_cors-preflight-<...>.json` records. The
composer read them as this corpus's evidence, each became an INCONCLUSIVE row
whose reason was `no scenario 'cors-preflight-<digest>' in
verification/scenarios/corpus.json` or an `N result files` problem, and the
receipt came back **33 INCONCLUSIVE of 34** after a scoped run that compared
one scenario and changed nothing else.

`paved-road-m4/scripts/run-parity.py` prunes them before composing: each
orphan is **moved** (never deleted) to
`verification/parity/_orphaned/<stamp>/` with an `_index.json`
(`rhoai3.parity-orphans/v1`) naming where each came from and why, and the move
is recorded in `_run.json` as `orphaned`. With no corpus nothing can be judged
to belong to one, so nothing is moved.

## Verification

- Every oracle file carries `receipt_sha256`, the entry point id, and
  `status` in `CAPTURED` / `UNCAPTURED` / `INCONCLUSIVE`.
- `compare-runtime-parity.py` exits 0 only on `PASS`; `FAIL` and
  `INCONCLUSIVE` exit 1 and are named in the parity record, so the K2
  hook refuses `kanban_complete` on that card.
- `compose-parity-receipt.py` writes `verification/parity/receipt.json`
  binding every parity verdict to the receipt digest; it is produced by
  this script (an independent producer), not by the verdict author. It
  records the `security_mode` it composed and never composes over evidence
  from another mode: captures or a qualification of another mode are a
  refusal, and a parity record of another mode is an orphan (above).

### The bounded navigation check (ADR-016)

The comparison compares the **first** response and never follows a redirect:
following one records the target's answer as the source's and drops the
`Location` that said where it pointed. That is deliberate and unchanged.

ADR-016 asks for more than the first response, though. A root redirect passes
its comparison when the status and the literal `Location` after origin mapping
are the source's — and the ruling also requires that **that legacy address
serves the replacement UI or redirects to its effective address**, proven by a
separate bounded navigation reaching the real UI and a usable OpenAPI document
in the packaged production artifact, without a redirect loop. A dead
compatibility URL is refused by name. A 302 to a 404 satisfies the comparison
and satisfies none of that.

So `paved-road-m4/scripts/run-parity.py` performs the navigation **beside** the
comparison, never inside it, after the scenario phase and before the composer:

- for every scenario whose recorded first response **on the destination** was a
  3xx with a `Location`, it GETs that address (absolute, or resolved against the
  destination base), follows at most `--nav-max-hops` hops (default 3) and stops
  at the first non-3xx — on the **destination only**;
- `ok` is a 2xx at the end, `dead` a 4xx/5xx or a connection that could not be
  made, `loop` a URL the walk already asked, `too-many-hops` a chain still
  redirecting when the budget ran out;
- it carries **no credentials** unless the scenario declares an
  `effects_identity`, and then the same reference, resolved from the
  environment;
- each walk is recorded as `verification/parity/navigation/<slug>.json`
  (`rhoai3.parity-navigation/v1`: `scenario`, `start`, `hops`, `final_status`,
  `terminal`) and summarised in `_run.json`. `--no-navigation` records
  `navigation: skipped` and walks nothing.

`compose-parity-receipt.py` reads those records. An entry point whose
comparison **PASSed** and whose navigation is `dead`, `loop` or
`too-many-hops` becomes `FAIL` with `kind: navigation` and the reason
`redirect target <url> is <terminal> on the destination (<final_status>)`; a
passing navigation adds `navigation: ok` to the row. A comparison that FAILED
keeps its own diff and its own typing. The work list turns a `navigation` row
into a `PARITY` obligation with cause `redirect-target-dead`, at the controller
that answers the redirect.

### Which destination a verdict is of (`binding`)

Every scenario verdict and the receipt record what they are a measurement
**of**, as `binding`:

| mode | the tree | the seal | who runs it |
| --- | --- | --- | --- |
| `sealed` (default) | the accepted tree | the live admission receipt must still seal what is on disk | the M4 road |
| `candidate` (`--issued`) | the candidate an issued card was verified on | not asked: the acceptance verify rebuilt the work list on that candidate | fix-until-green's acceptance path |

`--issued <verification/loop/issued.json>` (also on `compose-parity-receipt.py`
and on `paved-road-m4/scripts/run-parity.py`, which passes it to both) records
`{mode, candidate_sha256, issued_receipt_sha256, card}` on every verdict and on
the receipt. Optional `--candidate SHA` / `--issued-receipt SHA` state what the
caller believes; they are checked, never trusted.

Measured on destination v9, card `t_222c582a` (PARITY_CORS, attempt 4): the
worker wrote the right CORS properties and the acceptance path re-ran the
comparison, which came back INCONCLUSIVE with `receipt not authoritative:
worklist digest 26403fd1ecb0 != sealed eceefe4d20b9`. `run-verify.sh` rebuilds
the work list on the candidate before the parity stage, so the live seal's
worklist digest is the accepted tree's and can never match. The composer
refused for the same reason, the stale FAIL stayed on disk, and the card was
REVERTED — as was every parity card.

Bind what can be bound; refuse the rest **by name**: no issued card, an issued
card minted under a receipt that is not the one on disk, a `--candidate` or
`--issued-receipt` that is not what the tree and the card say, or a candidate
digest in `verification/build/run.json` that is not the tree being compared (an
edit after verification). In candidate mode the composer also refuses a
scenario verdict measured for another card, on another candidate or under
another receipt; a **sealed**-bound verdict still counts, because those are the
ones the last full M4 run left for every scenario a scoped run was not scoped
to.
- `scripts/capture-source-oracles.test.py`: HTTP capture and compare
  PASS/FAIL against a local stub server; non-HTTP compare with matching
  and diverging observations; missing oracle → INCONCLUSIVE; a
  destination failure cannot be completed around (exit 1 recorded).

## Scripts

- `scripts/derive-source-scenarios.py` — M1 producer: derive the corpus from
  the bundle, the OpenAPI examples, the seed rows, the seed schema's foreign
  keys, the JPA relationships that decide whether the application removes those
  references itself, and the CORS policies; gaps recorded, bound to the bundle in
  `verification/scenarios/_derive.json` (which also lists every SQL file read)
- `scripts/derive-source-scenarios.py --security-mode enabled` — the same
  producer, deriving the enabled-mode corpus into
  `verification/scenarios-enabled/`: four probes per authorization policy over
  the disabled corpus's own requests, identities by credential reference,
  blockers recorded (see *Deriving the enabled-mode corpus*)
- `scripts/derive-source-scenarios.py --security-mode enabled --fixture-variant NAME`
  — the same producer again, deriving a declared fixture variant of that
  mode's baseline into `verification/scenarios-enabled-<NAME>/`: the mode's
  own scenarios of the declared class over the varied dataset, statements
  recorded verbatim (see *Fixture variants of a mode's baseline*)
- `scripts/capture-source-oracles.py` — read capture from the source system
- `scripts/capture-source-scenarios.py` — M1 producer: package and start the
  frozen source, restore state, capture the derived scenarios (the effect
  read-backs taken as the scenario's `effects_identity` where it names one),
  clean up
- `scripts/qualify-source-captures.py` — the qualification gate and the third
  M1 step: every capture against its scenario's `qualify` contract, reading the
  retained bodies by digest; PASS / FAIL / INCONCLUSIVE per scenario, all three
  recorded and exiting 0; exit 1 only on a refusal to judge
- `scripts/reset-parity-db.sh [--variant NAME]` — restore the decided
  instance to the declared baseline and verify it; with `--variant`, apply
  that fixture's declared statements after the verified baseline (restoring is
  the same script with no `--variant`)
- `scripts/compare-runtime-parity.py` — destination comparison for reads
- `scripts/compare-scenario-parity.py` — recorded-request replay plus effects;
  `--issued` binds the verdict to the candidate and the issued card
- `scripts/compose-parity-receipt.py` — receipt-bound parity receipt; an entry
  point covered by scenarios passes only when every one of them passes, and one
  whose comparison passed while its redirect target is dead, loops or never
  settles (`verification/parity/navigation/`) becomes `FAIL` typed `navigation`;
  it composes only over the records that belong to the current corpus, mode and
  variant and names the rest under `orphaned_records`;
  `--issued` composes over the candidate an issued card was verified on
- `scripts/reset-parity-db.sh` — restore the decided instance to the initial
  state the corpus names (drop and recreate the schema, apply the schema and
  seed assets `decisions.yaml` points at)
- `scripts/_scenarios.py` — the corpus model, the request digest, the
  security-mode paths, the credential references and the source's declared
  CORS and authorization policies
- `scripts/capture-source-oracles.test.py`, `scripts/scenario-parity.test.py`,
  `scripts/scenario-derivation.test.py` — selftests (the last one: derivation,
  loader binding, qualification and the receipt's use of it)
