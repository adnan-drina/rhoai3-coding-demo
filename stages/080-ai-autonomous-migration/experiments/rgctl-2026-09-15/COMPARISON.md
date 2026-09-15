# This run against the official v9 run

Both runs start from the **same frozen source**, digest
`322a6149734fd8ce09b638a57312106dce879ec9ab5aa2263939a22c38ac6fd4`, and the same
`decisions.yaml` (ADR-001..016). Both use the same 18-scenario corpus,
`corpus_sha256 d55f314d23e993a1f94d522e41cd474879e82dabf266f5c0ecbd3a1581550d0d`,
and the same v9 source captures. Evidence for both is in `evidence/`.

**Material differences that are not the execution model**, stated before any number:

- v9 ran on a cluster workspace against a shared PostgreSQL; this ran on a laptop
  against a local container. Different I/O, different latency.
- v9's models and this run's are not the same agent configuration, and v9 ran through
  an orchestration layer (board, cards, gates) that this run did not use at all.
- v9 was a first pass through a process that had never completed; this run had the
  v9 evidence available from the start, including its M4 verdict and its two named
  parity FAILs. **That is a real advantage and it is not attributable to the graph.**
- This run reused the v9 source captures rather than re-recording them, saving the
  source-startup and capture work entirely.

For those reasons the elapsed-time figures below are **not** a controlled comparison
and no causal speedup is claimed. The outcome figures are comparable, because they
are measured by the same tooling against the same corpus.

## Outcome

> **Correction, 2026-09-15.** An earlier revision of this file said v9 never reached
> packaging or startup. That was wrong, and the evidence to disprove it was in the
> copied `evidence/official-v9/steps.json` all along: v9 **accepted the package gate**
> at commit `6a4ba85a681bf65518f97316a511176cb38e11ee`
> (`reason: "the package gate passes and discharges rt:package:f4aa0ab756c50669"`,
> measure `[0, 0, 0]`) and **accepted the boot gate** at commit
> `be484e84fa75151ade77d2d8bfb93999aa2d91c4`
> (`reason: "the boot gate passes and discharges rt:boot:4b62542369129feb"`).
> v9 also drove its own compile diagnostics from 233 to 0. **Build and startup are not
> where the two runs differ.** The difference is behavioural coverage and the execution
> effort spent reaching it.

| | official v9 | this run |
|---|---|---|
| `mvn package` clean, tests executed | **reached** — package gate accepted at `6a4ba85` | **yes**, `ValidatorTests` 1/1 |
| packaged artifact boots against the decided DB | **reached** — boot gate accepted at `be484e84` | **yes**, 1.16-1.39 s, profiles `spring-data-jpa,prod` |
| compile diagnostics driven to zero | **yes**, 233 -> 0 | yes, 233 -> 0 |
| parity scenarios run | partial | **18 of 18** |
| parity scenarios PASS | 0 | **17** |
| parity scenarios FAIL | 2 | **1** |
| parity scenarios INCONCLUSIVE | 16 | **0** |
| entry points PASS | **0 of 34** | **20 of 34** |
| entry points FAIL | 2 | 1 |
| entry points INCONCLUSIVE | 32 | 13 |
| ADR-015 product tests | none exist (floor `check-product-tests` failed) | **17 generated, 17 run, 16 PASS** |
| security enabled mode | never reached; every read answered 403 | **anonymous 401, admin 200, admin DELETE 204** |
| M4 verdict | **REFUSE** — 3 failed floors | parity receipt still FAIL (see below) |

v9's three failed floors, and where each stands here:

| v9 failed floor | this run |
|---|---|
| `check-product-tests` (AR-2.8): no product `*Test.java`/`*IT.java` exist | **closed** — 17 generated cases in 6 classes, committed by the harness's own `commit-generated-tests.py`, 16 passing |
| `assert-surefire-results`: empty integration suite | **closed for surefire** — 17 cases executed with results; the failsafe/IT wiring was not exercised |
| `compose-parity-receipt`: 2 FAIL, 32 INCONCLUSIVE | **improved, not closed** — 1 FAIL, 13 INCONCLUSIVE |

v9's two named parity FAILs, both fixed here:

- `sc:cors-preflight-...`: v9 answered with **every** `Access-Control-*` header absent.
  This run answers `Allow-Origin: *`, `Allow-Methods: POST`, `Allow-Headers:
  content-type`, `Max-Age: 1800`, `Expose-Headers: errors, content-type`, and no
  `Allow-Credentials` — the source's exact shape. **PASS.**
- `sc:read-root`: v9 answered `303` with
  `http://localhost:9966/petclinic/petclinic//swagger-ui/index.html`. This run answers
  `302` with `http://localhost:8081/petclinic/swagger-ui/index.html`, the ADR-016 exit
  condition. **PASS.**

v9's 32 INCONCLUSIVE were 24 "no parity record" (the comparator never ran) plus 7
aborted on `403` from the ADR-005/014 security gap plus 1 missing initial state. All
three causes are gone here: every scenario ran, no 403s, and the initial state is
verified before each comparison.

## The 14 entry points still not passing

**1 FAIL — `SpecialtyRestController#deleteSpecialty`, `sc:delete-referenced-specialties-1`.**
Status, content type and resulting state all match the source: `400`,
`text/plain;charset=UTF-8`, the specialty not deleted. **The body does not match, and
this is unresolved, not impossible.** The source's recorded body is

```json
{"className":"org.springframework.dao.DataIntegrityViolationException",
 "exMessage":"... constraint [FK_VET_SPECIALTIES_SPECIALTIES] ..."}
```

It names a Spring class that the compatibility path does not provide and a constraint
name that belongs to HSQLDB, not to the PostgreSQL instance ADR-009 chose. The
destination answers the same shape with
`org.hibernate.exception.ConstraintViolationException` and the PostgreSQL constraint
name.

An earlier revision of this file called that difference "structurally unreachable" and
said byte parity would require re-introducing a retired Spring class and forging a
foreign-key name from another engine. **That claim is withdrawn: it does not follow.**
The recorded body contains a *serialized* exception class name and a *serialized*
constraint name; emitting either string requires no Spring class on the classpath and
no HSQLDB foreign key, only a translation of the destination's error into the response
shape the source emitted.

This is therefore an **open error-response compatibility issue**. It is to be
investigated as a bounded response translation — a mapping from the destination's
persistence failure to the source's recorded `className` and `exMessage` fields,
derived from the source captures — **before** any contract change is proposed. It is
neither impossible nor waivable on the present evidence.

Separately, and independently of the body: the source's own behaviour here is a
failure — it could not delete a referenced specialty — and that failure is faithfully
preserved, including by deliberately NOT reordering that fragment's statements the way
the PetType fragment was reordered.

**13 INCONCLUSIVE — "no parity record".** Twelve POST/PUT entry points and one
wildcard-path GET have **no scenario in the corpus**, so there is nothing to compare.
This is a corpus coverage gap, identical in kind to 24 of v9's INCONCLUSIVEs, and it
is not something a migration can close. Closing it needs scenarios derived and
captured for those entry points.

**Plus 1 recorded coverage gap**, identical to v9's:
`sc:delete-referenced-pettypes-1` failed qualification **on the source side** — the
frozen Spring application deleted a referenced pet type with 204 where a 4xx was
expected. The destination reproduces the source's 204 and the same resulting 404, but
the fixture is not usable as a parity oracle.

## Account of the application's capabilities

| | count |
|---|---|
| entry points, total | 34 |
| **passed** — compared against a recorded source response and equal | **20** |
| **failed** — compared and different | **1** (body only; open error-response compatibility issue) |
| **untested** — no recorded source response to compare against | **13** |

Security: **disabled mode is parity-verified** (all 20 passes are in disabled mode,
which is the mode the captures were recorded in). **Enabled mode is behaviourally
verified but not parity-verified** — anonymous 401, wrong credential 401, `admin` 200,
`admin` DELETE 204 — because no enabled-mode source captures exist in the copied
evidence. ADR-014 requires separately bound captures for both modes; that obligation
is open.

## Effort, with the caveat above

These figures describe effort, not speed: this execution consumed the decisions and
the v9 evidence that the earlier run had to produce, so the two are not comparable as
rates and no causal speedup is claimed.

| | official v9 | this run |
|---|---|---|
| wall clock | 21 cards over 2026-09-14/15 | 56 minutes to the final parity result |
| orchestration units | 21 cards, a board, a loop | 13 application commits, no board |
| human/Operator interventions | 3 Operator steps (ADR-008/012/013) + 3 architect rulings (ADR-014/015/016) | **zero human interventions during this execution, using accumulated decisions and v9 evidence** — the ADR-shaped calls I made myself are listed in `INTERVENTIONS.md` |
| retries on the same evidence and scope | not measured here | 0 |
| reversions | 0 | 0 |
