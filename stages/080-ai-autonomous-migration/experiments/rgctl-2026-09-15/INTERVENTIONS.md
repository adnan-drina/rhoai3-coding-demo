# Interventions, revisions and decisions I made myself

## Human interventions

**Zero human interventions during this execution**, using the accumulated decisions
(ADR-001..016) and the v9 evidence as inputs. No approval gate was waited on and no
Operator step was requested. That phrasing is deliberate: the decisions this run
consumed were produced by earlier human work, so "autonomous" describes the execution,
not the authority. Everything below is a decision an ADR would have carried in the
official process and that I made myself — **assisted-equivalent in authority**, and
needing ratification before anything here ships.

## Decisions I made that an ADR should have decided

| # | Decision | Why it was mine to make, and what was rejected |
|---|---|---|
| **D-1** | `throws DataAccessException` clauses deleted; `ObjectRetrievalFailureException` / `EmptyResultDataAccessException` replaced by a destination-owned unchecked `EntityNotFoundException` | `DataAccessException` is unchecked, so the clauses were decorative and no caller catches that type. The other two ARE caught, in six places in `ClinicServiceImpl`, and that catch is the source's not-found path (returns `null`, controller answers 404). Rejected: deleting the catch blocks, which would have turned every missing entity into a 500. |
| **D-2** | `@Transactional(readOnly = true)` -> `@Transactional` | Jakarta has no `readOnly` attribute. Spring's is a hint to the provider, not a boundary, and the propagation is unchanged. 16 occurrences in one file. Recorded rather than silently dropped. |
| **D-3** | `@Valid` removed from request-body parameters; validation invoked explicitly at the same point | Leaving `@Valid` makes the platform answer 400 **before** the method body runs, which loses the `errors` header the source emits on an invalid payload. Validation still runs, with the same constraints, at the same place in the flow. |
| **D-4** | Three Jackson behaviours restored globally: creator `required` markers cleared for creator parameters, absent containers arrive empty, properties serialised in field declaration order | Each is a difference between the Jackson the source ran and the one this platform ships, and each changes an observable response. All three are general mapper settings; none names a class, property or payload of this specimen. Rejected: editing the generated DTOs or the API document, which would change the contract instead of restoring the runtime. |
| **D-5** | **The destination's seed dataset was changed to match the source's declared initial state. No expectation was changed.** | `verification/scenarios/corpus.json` declares `initial_state.dataset` to be `src/main/resources/db/hsqldb/populateDB.sql`; ADR-009 names `db/postgresql/populateDB.sql` as `seed_sql`. The two files are identical apart from **17 date literals** (13 pet birth dates, 4 visit dates) and, separately, the postgresql schema asset restarts every identity sequence at a fixed 100 where the source engine's IDENTITY continues from the seeded maximum. Both were realigned **in the destination's own seed and schema assets**, derived from the declared dataset — not from any recorded response. Every source oracle, capture, expectation and digest is untouched. This is a defect in ADR-009's asset choice, not in the destination code, and it is the single change here most in need of ratification. |
| **D-6** | ADR-014 enabled mode implemented from **one** artifact with `quarkus.http.auth.basic=true` always, the switch governing authorization only | The platform resolves `quarkus.http.auth.basic` at **build** time — it says so: `Build time property cannot be changed at runtime`. Binding the mechanism to a runtime switch is therefore impossible without two artifacts. With the switch off, every `@PreAuthorize` short-circuits through `@securityMode.disabled()` and no credential is required or consulted, which is what the source did when its `BasicAuthenticationConfig` was conditioned out. Rejected, per ADR-014: unconditional permit-all, a privileged anonymous identity, deleting authorization semantics. |
| **D-7** | The `PetType` fragment's `em.remove` dropped; the `Specialty` fragment's statement order left alone | Under Hibernate 6 the PetType fragment's removal-before-cascade fails the flush; the source's recorded response is 204 with the type and its pets gone, and the bulk statements produce exactly that. The Specialty fragment has the same shape but its recorded source response is **400** — the source hit the `vet_specialties` foreign key. Reordering that one would turn a recorded failure into a success. The source's bug is preserved. |

## Manifest revisions (scope changes) — 4

| | Trigger | Change |
|---|---|---|
| **R-1** | `mvn package` reached test compilation | WU-3 extended to `src/test/java/.../ValidatorTests.java`. The main-source census never covered it. Assertions unchanged, including the literal expected message. |
| **R-2** | Augmentation, then the compiler | WU-5 gained a second edit: `@Inject` of the `*Override` **interface** is ambiguous because the generated Spring Data repository also carries that interface as a bean type. Switched to the concrete class. |
| **R-3** | Parity run 1 | New unit WU-8: seed dataset, serialization order and absolute root `Location`. None of these were predictable from the compiler or the graph. |
| **R-4** | Parity runs 2 and 3 | New units WU-9 (Hibernate 6 HQL strictness), WU-10 (cascade order, exception mapping, identity sequences). |

## Retries and reversions

| measure | count |
|---|---|
| repairs reverted | **0** |
| units abandoned and re-grouped | **0** |
| repeated attempts with the **same** evidence and scope | **0** |
| corrective second attempts within a unit, each with **new** evidence | **6** (WU-3 two nested-paren scope misses; WU-5 injection ambiguity; WU-6 bean-name then expression syntax; WU-8 regex miss then mapper-feature lever; WU-10 whitespace mismatch) |
| times the two-attempt rule forced a strategy rethink | **1** — WU-8's property order: after `MapperFeature.SORT_CREATOR_PROPERTIES_FIRST` failed twice with the flag measurably `false`, the approach changed from a mapper feature to a `BeanSerializerModifier` that sorts by field declaration position |

## Infrastructure interruptions

| | |
|---|---|
| podman machine stopped mid-run (`unable to connect to Podman socket`) | ~90 s, 18:08:30Z |
| Red Hat PostgreSQL image env-var names differ from Docker Hub's | ~60 s, first container start |
| `oc exec` with a login shell corrupted the first tar stream | ~60 s, 17:48Z |
| **total** | **~3.5 minutes of 56** |

## Harness changes

**None.** No scaffold or harness code was modified. The following were reused
unmodified: `bootstrap-destination.py`, `check-datasource-decision.py`,
`reset-parity-db.sh`, `compare-scenario-parity.py`, `compare-runtime-parity.py`,
`compose-parity-receipt.py`, `run-parity.py`, `admit-migration-plan.py`,
`generate-product-tests.py`, `commit-generated-tests.py`. New code written for the
experiment lives in `tools/` and `policy/` and touches nothing in the scaffold.
