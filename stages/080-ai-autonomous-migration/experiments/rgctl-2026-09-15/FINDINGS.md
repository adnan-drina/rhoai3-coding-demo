# What rgctl contributed, and what actually found the defects

Tool: **rgctl v0.4.12**, pinned GitHub release
`rgctl-0.4.12-aarch64-apple-darwin.tar.gz`, sha256
`3e1ef9fdcac5c156f217b742b3d88ab72c06fbbf52d62bfb3c321922173616df`, verified against
the release's own `SHA256SUMS.txt`. Repository `github.com/sshaaf/rgctl`. No Homebrew
formula or tap exists; the release binary is the only path without a Rust toolchain.

Source identity: frozen `spring-petclinic-rest` 2.6.2, digest
`322a6149734fd8ce09b638a57312106dce879ec9ab5aa2263939a22c38ac6fd4`, matching the
official v9 freeze receipt — so the v9 source captures are bound to the same input
and were reused rather than re-recorded.

Invocations, all verified against `--help` for this version:

```
rgctl discover . --with-cfg --with-harmonic --with-kantra --kantra-target quarkus \
       --export-migration-hints --migration-preset risk_mitigation
rgctl discover . --exclude ".derived,target,.hermes,verification,evidence" --with-cfg --with-harmonic
rgctl -f json gql "MATCH (a:Class)-[:IMPLEMENTS]->(b) RETURN a,b LIMIT 200"
rgctl -f json blast-radius <node-uuid>
rgctl metrics --communities | --pagerank | --betweenness
rgctl export --export-format json --export-output <file>
rgctl -f json check --policy-file policy/policy.json
```

Speed is not in question. `discover` indexed 111 files to 2408 nodes / 8344 edges in
**573 ms** and re-indexed in 316 ms; every query answered in tens of milliseconds.
Nothing below is a performance complaint.

---

## Where the graph changed what I did

**G-1 — centrality chose the first work unit, and it was right.**
`discover` reported `Top hotspot: DataAccessException (PageRank 0.0268)`, 3.2x the
second-ranked node. I made retiring the Spring DAO/ORM exception surface work unit 1
on that basis, departing from rgctl's own proposed order, which schedules `service`
7th of 14. The uncapped compiler census confirmed it independently: 107 of 233
diagnostics belonged to that surface, and one coordinated 13-file edit removed 108.
Honest qualifier: the compiler census said the same thing, in the same 30 seconds,
without the graph.

**G-2 — the domain-crossing baseline was genuinely informative.**
`export` plus a package-to-domain map showed the destination has **no
`rest -> repository` edge**: controllers reach data only through the service facade.
That is a real architectural fact about the migrated tree, measured rather than
assumed, and it is what made `["rest","repository"]` a defensible blocking rule
rather than a guess. See `POLICY.md`.

## Where the graph was wrong, empty, or misleading

**F-1 — the community decomposition IS the package tree.**
`--export-migration-hints --migration-preset risk_mitigation` produced 14 steps whose
labels are exactly the 14 Java package names, plus one spurious community for
`.mvn/wrapper`. `max_blast` is `0.0` on every step. For a 58-file layered application
this is `ls src/main/java` with extra decimals.
(`evidence/this-run/rgctl-migration-plan-source.json`.)

**F-2 — the proposed order was computed against a tree that no longer exists.**
Two of its fourteen steps are `repository.jdbc` and `repository.jpa`, both retired by
ADR-004. The plan is derived from the source and knows nothing of the accepted
decisions, so a quarter of it is empty. It also schedules `service` 7th although its
own centrality output ranks that package's dominant type 1st.

**F-3 — the relation that mattered most is not in the graph.**
The ADR-012 obligation is "an implementation per non-Spring-Data parent interface",
carried by seven declarations of the form
`SpringDataXRepository extends XRepository, Repository<X,Integer>`. rgctl's `EXTENDS`
relation contains **none** of those seven edges. One
`grep -E '^public (interface|class)'` over the package returned the complete, correct
picture in one command, and that is what work unit 5 was built from.

**F-4 — `IMPLEMENTS` and `EXTENDS` are not consistently directed.**
Of 22 `IMPLEMENTS` edges some run implementation->interface
(`JdbcPetRepositoryImpl -> PetRepository`) and others run interface->implementation
(`ClinicService -> ClinicServiceImpl`, `VetRepository -> JdbcVetRepositoryImpl`).
`EXTENDS` shows `Person -> Vet`, `Person -> Owner`, `BaseEntity -> Role`, all
backwards. Any rule that depends on edge direction — which is exactly what
`forbidden_crossings` is — inherits this.

**F-5 — framework and interface dispatch is unresolved, and the gap is silent.**
The baseline shows `rest -> service`: 7 `Uses` edges and **zero `Calls`**, though the
eight controllers call `ClinicService` methods on nearly every line. `rest -> mapper`
by contrast has 34 `Calls`. The difference tracks method-name ambiguity: every service
and repository method name also exists on an implementation type, while mapper method
names are unique. Consequence: 189 of 291 application functions report
`impact_zone_size: 0`, including every controller entry point. An impact threshold read
off this distribution measures the resolver, not the code.

**F-6 — the top hotspot is not addressable by the impact command.**
`blast-radius DataAccessException` answers `Node not found`. `blast-radius` resolves
Function nodes only, and the type `discover` names as the top hotspot is a Class node.
The headline of the index cannot be fed to the tool's main impact query.

**F-7 — symbol disambiguation: the documented form does not work.**
On an ambiguous name the tool prints
`Remediation: rgctl blast-radius "ClassName::method"`. That form returns the same
ambiguity error, and so does `--class ClassName`. The working handles are the node
UUID — which `gql` does not return (F-8) — and the ambiguity error message itself,
which does print UUIDs.

**F-8 — `gql "... RETURN n"` does not return node ids.**
The policy schema is keyed by node UUID and the documentation says UUIDs come from
`gql ... RETURN n`. They do not: `gql` returns `binding`, `file`, `node`,
`qualified_name`, `type` and no `id`. `metrics` returns UUIDs with no names.
`export --export-format json` is the only practical way to build a domain map, and
that is what `policy/build-policy.py` uses.

**F-9 — the embedded Kantra catalog in the release binary is a fixture.**
`discover --with-kantra --kantra-target quarkus` reported
`catalog_id: fixture@9d8becbc49495aff`,
`ruleset: rgctl-fixture-rules:target=quarkus`, `evaluated_rules: 1`, zero violations.
The documented ~2.6k-rule Konveyor `stable/java` catalog is not in the 0.4.12 release
binary. It is not a substitute for the MTA findings; the official run's
`evidence/mta-findings.json` was copied out and used instead. MTA CLI 8.2 was not
installed locally and was not needed, since the v9 findings bind to the same frozen
digest. (`evidence/this-run/rgctl-kantra-findings.json`.)

---

## What actually found each defect

| Defect | Found by |
|---|---|
| Spring DAO/ORM exception surface (107 diagnostics) | compiler census; **graph centrality agreed** |
| `@Profile` / `@Transactional` families (59) | compiler census |
| Spring MVC web surface (47) | compiler census |
| Model utility retirement (16) | compiler census |
| **ADR-012 fragment adapters x7** | **source inspection**; the graph has no such edge (F-3) |
| `ValidatorTests` bound to Spring's validator adapter | `mvn package` test compile |
| Jackson enforces creator `required` -> 400 on a valid recorded body | **runtime**, replaying the recorded source request |
| Absent container arrives null -> NPE in the mapper | **runtime** |
| Creator-first property order breaks every body digest | **runtime** |
| Root redirect must be absolute (ADR-016) | **runtime** + source capture |
| `@CrossOrigin` response shape (origin `*`, single method, no credentials header) | **runtime** + source capture |
| `application/json;charset=UTF-8` vs `application/json` | **runtime** + source capture |
| Hibernate 6 refuses the source's column-name HQL -> 500 on every cascading delete | **runtime** |
| PetType cascade order fails the flush under Hibernate 6 | **runtime** |
| `@ControllerAdvice` never sees a transaction-time failure | **runtime** |
| `quarkus.http.auth.basic` is build-time, so the switch cannot select the mechanism | **runtime**, the platform's own warning |
| Seed dataset and identity sequences differ between the two engine assets | **parity comparison** |
| The source's own `src/test/resources` turns security ON under `@QuarkusTest` | **generated-test run** |

Eleven of eighteen were found only by running the packaged artifact against recorded
source requests. **Zero** were found by the relationship graph that were not already
on the compiler's list.

---

## B-1: the measure the existing loop reads is saturated

`mvn compile` on the bootstrapped tree reports exactly **100** errors. `javac` with
`-Xmaxerrs 100000` over the same sources plus the generated DTOs reports **233**. The
100 is javac's default error cap.

A loop whose acceptance rule is "the global diagnostic count must fall" is reading a
saturated counter: until a repair removes more than 133 diagnostics the reported
number stays pinned at 100 and every correct repair scores as no progress. WU-1
removed 108 real diagnostics; under the capped measure it would have moved the number
from 100 to 100.

`tools/diag.sh` is the uncapped census used throughout.
`evidence/this-run/javac-baseline.log` is the raw output.
