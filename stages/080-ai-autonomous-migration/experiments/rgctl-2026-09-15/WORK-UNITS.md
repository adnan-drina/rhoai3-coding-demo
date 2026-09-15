# Work-unit manifest — rgctl experiment, spring-petclinic-rest → Quarkus

Source identity: frozen `spring-petclinic-rest` 2.6.2, digest
`322a6149734fd8ce09b638a57312106dce879ec9ab5aa2263939a22c38ac6fd4`
(matches the v9 freeze receipt `evidence/producers/freeze.json`, so the v9
source captures under `verification/source-oracles/` and `verification/scenarios/`
are bound to this same input and are reusable).

Destination decisions preserved unchanged from the official run's `decisions.yaml`
(ADR-001..016): RHBQ 3.27.3.SP1-redhat-00002 Spring-compat path, JDK 21,
PostgreSQL 16, build profiles `prod,spring-data-jpa`, retirements ADR-004..007,
ADR-012 fragment adapters, ADR-013 coverage-threshold retirement, ADR-014
security ruling, ADR-015 product tests, ADR-016 root redirect.

## Measured baseline (not estimated)

| Measure | Value | How measured |
|---|---|---|
| Main sources after ADR retirements | 58 `.java` | bootstrap-destination receipt, 244 changes |
| Generated OpenAPI DTO sources | 20 `.java` | `target/generated-sources/openapi` |
| **True compile diagnostics** | **233** | `javac -Xmaxerrs 100000` over main + generated sources |
| Diagnostics Maven *reports* | 100 | `mvn compile` — javac's default `-Xmaxerrs 100` cap |

> **Finding B-1 (corrected).** `mvn compile` reports exactly 100 errors because
> javac's default error cap is 100; the uncapped figure is 233. Both facts stand.
> An earlier revision inferred from them that the official loop's progress measure
> was capped. **That inference is withdrawn.** The official loop measures with the
> uncapped JDK diagnostics checker: v9's own
> `evidence/official-v9/steps.json` opens at commit `b196f1e3`,
> `reason: "bootstrap-destination baseline"`, `measure.compile_errors: 233` — the
> same number — and descends 233 → 217 → 203 → 179 → 170 → … → 0. No official
> measure is capped. What survives is only that `mvn compile` is not a safe source
> for a diagnostic count.

## Tool observations vs. planning conclusions

**Tool observation (rgctl 0.4.12 `discover`):** 111 files → 2408 nodes, 8344 edges;
1717 communities at modularity 0.43; 21 circular dependencies; **top hotspot
`DataAccessException`, PageRank 0.0268** — 3.2× the second-ranked node.

**Tool observation (rgctl `--export-migration-hints --migration-preset risk_mitigation`):**
14 steps whose labels are exactly the 14 Java package names (plus one spurious
community for `.mvn/wrapper`). `max_blast: 0.0` on every step. Proposed order:
`model → repository → util → repository.jdbc → service.clinicService →
repository.jpa → service → service.userService → mapper → rest →
repository.springdatajpa → security → root`.

**Planning conclusion (mine):** the community decomposition is isomorphic to the
package tree and therefore adds nothing over `ls src/main/java`. The *centrality*
result does carry information and I used it: it independently ranks
`DataAccessException` first, which the compiler census confirms (107 of 233
diagnostics belong to the Spring DAO/ORM exception surface). I therefore depart
from rgctl's proposed order, which schedules `service` at step 7 of 14.

## Units

### WU-1 — Retire the Spring DAO/ORM exception surface
- **Outcome:** no `org.springframework.dao` / `org.springframework.orm` reference
  remains; not-found behaviour (source returns `null` → controller 404) preserved
  by a destination-owned unchecked exception.
- **Files/symbols:** `service/ClinicService.java` (26 `throws DataAccessException`),
  `service/ClinicServiceImpl.java` (69 diagnostics incl. 6 `catch
  (ObjectRetrievalFailureException|EmptyResultDataAccessException)`),
  `util/EntityUtils.java` (throws site), `repository/{Owner,Pet,PetType,Specialty,
  User,Vet,Visit}Repository.java`, `repository/springdatajpa/SpringData*.java`,
  `service/UserService*.java`.
- **Evidence for the grouping:** `throws` clauses on an interface and on every
  override must change in one edit — removing the clause from `ClinicService`
  alone leaves `ClinicServiceImpl` legal but removing it from the impl first is
  also legal, while a *partial* sweep across the seven repository interfaces and
  their three implementation families is not. Graph centrality ranks the type
  first; the compiler census assigns it 107/233.
- **Prerequisites:** none. Runs first.
- **Completion checks:** uncapped diagnostic census drops by ≥100; zero
  `org.springframework.dao|orm` imports; the six not-found catch sites still
  return `null` on a missing id.

### WU-2 — Retire Spring bean-scoping and transaction annotations
- **Outcome:** `@Profile("spring-data-jpa")` → `@IfBuildProfile("spring-data-jpa")`
  (ADR-011 activates `prod,spring-data-jpa`); `org.springframework.transaction.
  annotation.Transactional` → `jakarta.transaction.Transactional`.
- **Files/symbols:** 15 `repository/springdatajpa/*` files (`@Profile`, 30
  diagnostics); `service/{Clinic,User}ServiceImpl.java` and 6 REST controllers
  (`@Transactional`, 29 diagnostics).
- **Evidence:** `grep` of the declarations; `@Profile` appears on exactly the 15
  files ADR-011's active profile list governs. `readOnly = true` has no Jakarta
  equivalent and is dropped — recorded as a behavioural note, not a silent edit.
- **Prerequisites:** none; independent of WU-1 (disjoint symbol sets), but
  sequenced second because it touches the same repository files.
- **Completion checks:** census drops by ≥55; `@IfBuildProfile` count == source
  `@Profile` count (15).

### WU-3 — Spring MVC web surface → Quarkus REST
- **Outcome:** `BindingResult`/`FieldError` validation, `@CrossOrigin`,
  `UriComponentsBuilder` Location construction and `HttpServletResponse` replaced
  while preserving status codes, response bodies and `Location` headers.
- **Files/symbols:** `rest/BindingErrorsResponse.java`, the 8 `*RestController`
  classes, `rest/ExceptionControllerAdvice.java`. 47 diagnostics.
- **Evidence:** the v9 source captures under `verification/source-oracles/`
  record the exact status/Location for all 34 entry points; the v9 parity receipt
  records CORS preflight and `sc:read-root` as the two hard FAILs.
- **Prerequisites:** WU-1 (controllers call `ClinicService` methods whose `throws`
  clauses WU-1 removes).
- **Completion checks:** census drops to 0 for `rest/`; `quarkus.http.cors`
  configured from the source `@CrossOrigin` policies, not invented.

### WU-4 — Retire Spring beans/core utilities in the model
- **Outcome:** `MutableSortDefinition`/`PropertyComparator` sorting,
  `ToStringCreator`, `@DateTimeFormat` replaced preserving ordering semantics.
- **Files:** `model/{Owner,Pet,Vet,Visit}.java`. 16 diagnostics.
- **Evidence:** leaf package; nothing in the graph or the source depends on these
  helpers outside the four model classes.
- **Prerequisites:** none.
- **Completion checks:** census 0 for `model/`; `getPets()` still returns
  name-ascending order (asserted against the v9 `ep_*getOwner*` capture).

### WU-5 — Spring Data fragment adapters (ADR-012)
- **Outcome:** an implementation exists for every method the seven
  `SpringDataXRepository` interfaces inherit from a **non**-Spring-Data parent.
- **Files:** `repository/springdatajpa/SpringData{Owner,Pet,PetType,Specialty,
  User,Vet,Visit}Repository.java` and their `*Impl`/`*Override` fragments.
- **Evidence:** **source inspection, not the graph.** `grep -E '^public
  (interface|class)'` over the package returns all seven `extends XRepository,
  Repository<X,Integer>` declarations. rgctl's `EXTENDS` relation contains **none**
  of these seven edges (see FINDINGS F-3).
- **Prerequisites:** WU-1, WU-2 (the files must parse).
- **Completion checks:** clean `mvn package`; Quarkus augmentation reports no
  unimplemented repository method.

### WU-6 — Security switch (ADR-014)
- **Outcome:** `petclinic.security.enable` honoured in both modes; `@PreAuthorize`
  role semantics retained; Basic auth against the JPA identity store.
- **Prerequisites:** WU-5 (application must boot).
- **Completion checks:** disabled mode answers 200 anonymously; enabled mode
  answers 401 anonymously and 200 for `admin`.

### WU-7 — Root redirect and OpenAPI (ADR-016)
- **Outcome:** root answers 302 with `Location: /petclinic/swagger-ui/index.html`.
- **Prerequisites:** WU-3.

### WU-8 — Package, boot, seed, verify
- **Outcome:** `mvn package` green; packaged artifact boots against local
  PostgreSQL 16; reset/seed reproducible; source-vs-destination parity run.

## Sequence and rationale

`WU-1 → WU-2 → WU-4 → WU-3 → WU-5 → WU-8(package/boot) → WU-6 → WU-7 → WU-8(parity)`

Departures from rgctl's proposed order, and why:
1. rgctl schedules `service` 7th; I run it 1st. The compiler census and rgctl's own
   centrality both put the DAO exception surface first; the `scheduled` ordering
   ignores its own centrality output (`max_blast: 0.0` everywhere).
2. rgctl schedules `repository.jdbc` and `repository.jpa` as steps 4 and 6. ADR-004
   retired both packages; they do not exist in the destination. The migration plan
   was computed against the **source** tree and has no knowledge of the accepted
   retirements, so a third of its steps are empty.
3. rgctl schedules `rest` 10th; I run it 4th, because reaching a packaged, booting
   application early is the only way to expose the 403/CORS/redirect class of
   defect that dominated the official run's M4 verdict.

## Final status of every unit

| unit | outcome | evidence | app commit |
|---|---|---|---|
| WU-1 Spring DAO/ORM exception surface | **done**, one coordinated 13-file edit, census 233 -> 125 | `evidence/this-run/javac-baseline.log`, `tools/diag.sh` | `3f4ae25` |
| WU-2 `@Profile` / `@Transactional` | **done**, 17 files, census 125 -> 64; 15 `@IfBuildProfile` == 15 source `@Profile` | | `e6e3629` |
| WU-4 model utilities | **done**, census 64 -> 48; ordering semantics reproduced from `PropertyComparator`'s own null/ignore-case rules | | `7d68878` |
| WU-3 Spring MVC web surface | **done**, census 48 -> 0; extended by R-1 to the retained test | | `c29c03f`, `d9c4584` |
| WU-5 ADR-012 fragment adapters | **done**, all seven in one unit; `mvn package` BUILD SUCCESS | augmentation log | `52c4b73` |
| WU-6 ADR-014 conditional authorization | **done**, 32 `@PreAuthorize` expressions, role expressions verbatim | | `418e825` |
| WU-7 root redirect / OpenAPI (ADR-016) | **done**, 302 with the literal legacy address, absolute from the request base | `sc:read-root` PASS | `c6552d7` |
| WU-8 package, boot, seed, verify | **done**, 5 parity runs | `evidence/this-run/parity-*.json` | `c6552d7`, `5f157e4` |
| **WU-9** Hibernate 6 HQL strictness *(new, R-4)* | **done**, 8 queries in 4 source fragments | | `3670d56` |
| **WU-10** cascade order + exception mapping + identity sequences *(new, R-4)* | **done** | | `5f157e4` |
| **WU-11** ADR-014 enabled mode *(new)* | **done**, both modes from one artifact | | `23fb8d3` |
| ADR-015 product tests | **generated and executed**, 17 cases, 16 pass | `evidence/this-run/generated-tests*.{json,log}` | `b34e3ea` |

Final: **17 of 18 parity scenarios PASS**, **20 of 34 entry points PASS**,
**16 of 17 generated product tests PASS**, both security modes verified.

## Revisions

Four scope changes, all recorded with their trigger, in `INTERVENTIONS.md`. In
summary: R-1 the retained test source (found by `mvn package`); R-2 a bean-type
ambiguity in the fragment adapters (found by augmentation); R-3 the seed dataset,
serialization order and absolute `Location` (found by parity run 1); R-4 Hibernate 6
HQL strictness, cascade order, exception mapping and identity sequences (found by
parity runs 2 and 3).

Three of the four were discovered by **running** the artifact, not by planning it.
None was predictable from the compiler, the relationship graph or the static findings.
