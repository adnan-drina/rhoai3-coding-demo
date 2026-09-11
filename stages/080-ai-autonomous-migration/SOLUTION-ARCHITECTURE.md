# Stage 080 — Solution Architecture (v3: fix-until-green)

**Architecture status:** accepted design; implemented and locally fixture-tested (2026-09-09 review round applied: transactional acceptance, measurement contract, native continuation, conservative bootstrap); real toolchain execution, autonomous migration, and runtime parity are unproven. Supersedes v2 (capability planner) on 2026-09-08.

This is the solution architecture for Stage 080, not for the whole workshop and not an execution file for a destination workspace. The [stage README](README.md) owns the demo journey. This document owns the migration design, authority boundaries, invariants, and proof gates. Runtime procedures remain in [operations](../../docs/OPERATIONS.md); destination code and skills remain in `scaffold-repo/`.

| Evidence label | Meaning |
|---|---|
| **Implemented** | Present in the repository, executable, with a selftest that includes the negative case |
| **Demonstrated** | Exercised in a retained live run |
| **Accepted design** | Architecture decision to implement; not runtime proof |
| **Unknown** | Not established; must not be inferred |

Same-PR rule: a change to Stage 080 behavior must update this document and the README maturity projection together.

---

## 1. Executive decision

Migration is **one mechanical loop**. There is no planner in the sense of an ownership map, a capability graph, or a step table authored by anyone:

> **Frozen evidence → deterministic bootstrap → work list computed by tools → fail-closed admission → one Hermes card per step → tools accept or revert → repeat until the list is empty → runtime parity**

The governing decisions:

1. **The work list is the plan.** MTA mandatory incidents, JDK compiler diagnostics, failing tests, and runtime-parity mismatches, each with a file locus, clustered by file, in a fixed order. It is recomputed by tools after every change and never written by a model or a human.
2. **A strict progress measure decides.** The tuple *(mandatory incidents, compile errors, failing tests, parity mismatches)* must strictly decrease lexicographically with no new mandatory incident, or the step is reverted. Strict decrease is the termination argument.
3. **AI proposes; tools decide.** A worker edits only the head cluster's write set. It never authors the list, the measure, the acceptance, or a decision. A cluster that fails the attempt threshold becomes a human's card and the loop stops until the human clears it (pilot rule: a deferral is never routed around).
4. **Product tooling only, permissively licensed.** MTA CLI 8.2 (analysis), the pinned toolchain JDK's compiler API (structure and diagnostics), Maven and surefire (build and tests), Hermes v0.20.5 (cards), git (state). No third-party analysis library, no source-available recipe bundle, no regex extraction.
5. **The Spring-compatibility path first.** The deterministic bootstrap targets the Quarkus Spring compatibility extensions; the native path is the same loop with a second mapping catalog and one more work-list source (`org.springframework` imports), applied class by class as the Quarkus guidance recommends.

Spec Kit, the typed partition, the ownership map, the capability DAG, the context probe, and bytecode reconciliation are removed. None of them has a compatibility path.

---

## 2. Scope and product pins

| Component | Stage responsibility | Pin or posture |
|---|---|---|
| Red Hat Developer Hub | Self-service migration project creation | Platform-managed |
| Red Hat OpenShift Dev Spaces | Per-run workspace with legacy read-only and destination writable | Platform-managed |
| MTA CLI | Mandatory incidents on the frozen source and on the destination after every step; the canary rule proves the effective ruleset | `pins.mta_cli` **8.2** product line; measured binary version and sha256 recorded in every receipt; an Operator freezes `artifact_sha256` from a measured receipt; kantra is provisional and non-admissible |
| JDK compiler API (`javax.lang.model`, `com.sun.source`, `javax.tools`) | Structural inventory of the frozen source (`JdkModelExtract.java`) and compiler diagnostics of the destination (`JdkDiagnostics.java`) | `pins.structure_extractor` **jdk-21** = the toolchain JDK; the launcher refuses on a feature-release mismatch; no third-party library, no separate license |
| Maven + surefire | Offline build and tests of the destination | Compiler and surefire plugin pins; offline (`-o`) after the warm-up |
| Hermes Agent Kanban | One card per loop step; native dispatch and review | **v0.20.5**, build **2026.8.19** |
| Red Hat build of Quarkus | Destination platform, compat path first | BOM **3.27.3.SP1-redhat-00002** (`pins.quarkus_platform`) |
| git | Loop state: every accepted step is a commit; every rejected step is a revert | Workspace repository |

Non-goals: a Kubernetes Hermes operator, LLM-generated task decomposition, silent model failover, automatic architecture decisions, OpenRewrite as a planning authority, and claiming filesystem containment from Hermes profiles or hooks alone.

---

## 3. System context and trust boundaries

```mermaid
flowchart LR
  RHDH["Developer Hub template"] --> WS["Dev Spaces workspace"]
  WS --> LEG["Frozen legacy source (read-only)"]
  WS --> DST["Destination repository (writable, git)"]
  LEG --> M1["M1 evidence: freeze, build, JDK model, MTA, bundle"]
  M1 --> BOOT["Bootstrap: compat mapping + pins (deterministic)"]
  BOOT --> VERIFY["Verify: JDK diagnostics, surefire, MTA rescan"]
  VERIFY --> WL["Work list (tools only)"]
  WL --> SEAL{"Admission"}
  SEAL -->|ADMITTED| K4["K4: one card (head cluster)"]
  SEAL -->|INCONCLUSIVE| HUMAN["decisions.yaml / pins / manual card"]
  K4 --> CARD["Hermes M3 card: edit the write set"]
  CARD --> VERIFY
  VERIFY --> ADV{"measure strictly decreased?"}
  ADV -->|yes| COMMIT["commit → next card"] --> K4
  ADV -->|no| REVERT["revert → same cluster, next attempt"] --> K4
  WL -->|empty| M4["M4 VERIFY: oracles, parity, rescan"]
  MAAS["OpenShift AI MaaS"] --> CARD
```

Trust boundaries:

- The legacy tree is immutable evidence. Agents read it but never repair it in place.
- Destination writes are limited to the head cluster's write set. Tests are never writable. The K2 hook is an accident guardrail, not an OS security boundary.
- Models receive work only through governed Hermes profiles and MaaS. External-provider use is explicit and never a silent fallback.
- `evidence/planning/` and `verification/` are tool outputs. The only human-authored planning input is `decisions.yaml`, and every entry cites an ADR.
- Merge authority remains the software supply-chain pipeline; neither a worker nor a human comment creates `ACCEPT`.

---

## 4. Authority model

| Decision or action | Deterministic tool | AI-assisted, mechanically checked | Human ADR required |
|---|:---:|:---:|:---:|
| Freeze source, classify files, record tool receipts | ✓ | | |
| Inventory types, entry points, dependency order | ✓ | | Catalog changes only |
| Bootstrap the destination (pom, properties, main class) | ✓ | | Mapping-catalog changes only |
| Compute the work list, cluster, order, measure | ✓ | | Never |
| Admit the next step | ✓ | | Never |
| Mint the next Hermes card | ✓ | | Never |
| Edit code inside the head cluster's write set | | ✓ | |
| Accept or revert a step | ✓ | AI may explain a rejection | Never |
| Retire a work-list item as not applicable | | | ✓ (`decisions.not_applicable`, one item, one ADR) |
| Retire a source file (e.g. a Spring AOP aspect Quarkus cannot host) | bootstrap deletes exactly the listed paths | | ✓ (`decisions.retired_sources`, one file, one ADR, one reason) |
| Own a cluster after the attempt threshold | | | ✓ (manual card; the run cannot close while it is open) |
| Define the runtime oracles and accepted business behavior | ✓ (source-recorded) | | Oracle definition |

An ADR may retire an item or choose the platform and the threshold. It may not waive a compile error, a failing test, or a parity mismatch.

---

## 5. The work list

`evidence/planning/worklist.json` (`planner.worklist`, schema `worklist.schema.json`).

| Source | Items | Kind |
|---|---|---|
| MTA rescan of the destination (`verification/mta-rescan/findings.json`); before the first rescan, the frozen-source obligations from the evidence bundle | one item per mandatory incident, content-addressed over rule, locus, variables and message; nothing dropped, `GLOBAL` locus kept | `build` / `config` / `incident` by path |
| JDK compiler diagnostics (`JdkDiagnostics.java` over the destination with the offline classpath) | every `ERROR`; an unresolvable build is one `pom.xml` item | `compile` (or `build`) |
| surefire reports (ElementTree) | every failing test | `test` |
| parity verdicts (`verification/parity/*.json`) | every `FAIL` | `parity` |

Items cluster by file. Order key: kind rank (build → config → compile → incident → test → parity), then dependency depth for compile clusters (leaf types first, from the JDK model's type references), then path. The head cluster is the next card. A cluster's write set is its file (plus `pom.xml` for build items).

The measure is `(mandatory_incidents, compile_errors, failing_tests)`; parity is reported beside it and judged by M4. Every component is known only when its tool ran in this verification and produced a report (`verification/build/run.json`): tests that did not run, an empty surefire directory, a `mvn test` failure with no recorded failing test, or a skipped rescan make the measure unknown and the loop does not advance. A step is accepted iff the tuple strictly decreases lexicographically **and** no mandatory obligation appears that was absent before. Obligation identity is line-free (rule, file, variables, message): moving code is not a new obligation. Removing a Spring annotation may add compile errors while removing an incident: that is progress.

Tests are never in a write set. A failing test scopes its production twin; when no twin can be derived the cluster is a typed blocker (`SCOPE_UNDERIVED`) for a human or ADR.

The bundle is environment-independent (machine paths are stripped from receipts), so two workspaces that froze the same source seal the same bundle.

---

## 6. Bootstrap (step 0)

`bootstrap-destination` (stdlib only: ElementTree, line-based properties) produces the deterministic baseline from `.hermes/planning/catalogs/compat-mapping.json` and `pins.json`:

1. import `pom.xml` and `src/` from the frozen analysis copy (packages kept);
2. pom: drop `spring-boot-starter-parent`, import the pinned `quarkus-bom`, map every listed starter and JDBC driver to its Quarkus Spring-compatibility or runtime extension, drop the Spring Boot plugin, add the pinned Quarkus plugin, pin compiler and surefire; an unmapped `org.springframework.boot` dependency is removed and surfaces again as a compiler or rescan item, never guessed;
3. configuration: rename mapped property keys and documented values; drop keys the catalog marks as having no Quarkus equivalent (recorded);
4. delete the `@SpringBootApplication` class only when it is a trivial launcher (no fields, no other annotation, no method but `main`); a launcher that declares beans or configuration is kept and recorded as `MAIN_CLASS_NOT_TRIVIAL`.

A Spring Boot dependency with no catalog row stays in the pom and is recorded as `UNMAPPED_DEPENDENCY`; a block exits 1 and keeps admission `INCONCLUSIVE` (`BOOTSTRAP_BLOCKED`) until a catalog row or an ADR resolves it. Nothing is removed on a block. The import never overwrites a file the destination already has, so a repeated bootstrap changes nothing after the baseline. Every mapping row is a documented Quarkus guide mapping; versions come only from pins. The receipt is sealed by admission and bound to the bundle digest. After the bootstrap the compiler produces the real plan.

---

## 7. Admission

`evidence/planning/admission-receipt.json` v2 seals the bundle, the work list, the bootstrap receipt, `decisions.yaml`, every contract file, and the tool pins, and records `activation`, `measure`, `head`, `loop_complete`.

Fail-closed boundaries, each with a permanent negative test:

| Block | Meaning |
|---|---|
| `TOOL_UNPINNED` / `TOOL_PIN_MISMATCH` | a mandatory producer (JDK model, MTA CLI) is not pinned, or its receipt disagrees with the pin on status, version, or digest |
| `MTA_MISSING` / `MTA_PROVENANCE` / `CANARY_MISSING` / `INCIDENTS_NOT_CONSERVED` | analysis absent, not the pinned 8.2 artifact, canary silent, or an incident lost between the tool and the list |
| `STRUCTURE_MISSING` / `ZERO_ENTRY_POINTS` | no admitted structural evidence, or nothing to verify parity against |
| `PLANNER_NOT_ACTIVATED` / `PLANNER_PILOT_SEAL` | the activation gate (§9) |
| `MISSING_DECISION` / `ADR_NOT_ACCEPTED` / `PLATFORM_UNKNOWN` | `decisions.yaml` incomplete or citing an unaccepted ADR |
| `BOOTSTRAP_MISSING` / `BOOTSTRAP_STALE` | no deterministic baseline, or one bound to another bundle |
| `MEASURE_UNKNOWN` / `WORKLIST_STALE` | a tool did not run in this verification, or the list belongs to another bundle |
| `BOOTSTRAP_BLOCKED` | the bootstrap recorded a non-trivial launcher or an unmapped dependency |
| `MANUAL_CLUSTER` / `SCOPE_UNDERIVED` | a deferred (human-owned) cluster, or a cluster with no derivable production scope; the loop stops |

`ADMITTED` means "the loop may run its next step from this exact state". `COMPAT_FAIL` means the bundle or the work list fails its schema: a planner defect. The receipt digest binds every idempotency key and every K1 body.

---

## 8. Hermes execution model (K1–K4)

- **K4** converts the sealed work list into **exactly one** `kanban_create` payload per step: `M3 c:<cluster>` for the head cluster, or `M4 VERIFY` when the list is empty and nothing is deferred. Key `k4:<cluster>:<attempt>:<receipt16>`; parent = the previous accepted step's card plus the M2 card. K4 re-derives the activation verdict and the tool pins from `pins.json` itself; a receipt text never overrides them. Zero commands unless ADMITTED. `k4_mint.py` appends the captured task id to `evidence/receipts/k4/mints.json`.
- **K1** bodies carry `receipt_sha256`, `worklist_sha256`, cluster id/kind/attempt, the write set, the item ids, and the artifact digests. No graph, no MTA prose, no acceptance text.
- **K3** proves the live board equals the loop's expected cards: every accepted step's card and the one open card, matched only by native idempotency key or by K4's mint receipts (never title or body), chained by parent. Only registered control cards (`verification/loop/cards.json`: the M2 card, registered once from its own environment, and its M1 ancestor) are exempt; an execution card is never exempt, so the previous accepted card stays in the expected set. Continuation is proven through `advance.py` → `k4_mint.py --exec` against a file-backed fake board; not yet on the pinned Hermes.
- **K2** vetoes worker graph mutation (`kanban_create`, `kanban_link`, swarm, decompose, direct `hermes kanban create|link`, `daemon --force`) and product writes outside the sandbox. Guardrail, not containment.
- **The card procedure** (`fix-until-green`): `brief.py` → edit the write set → `run-verify.sh` (acceptance: JDK diagnostics, fresh surefire reports with the `mvn test` exit status, MTA rescan, packaging/startup when green; diagnostic: classpath + compiler only and cannot feed advance) → `advance.py`, the acceptance transaction. It promotes only when the card is the issued one (`verification/loop/issued.json`, written by K4 and bound to the minted `t_*`), the product tree is exactly the tree verify.py measured (`candidate_sha256`), every changed path is inside the write set, and the measure strictly decreased with no new obligation; then it commits exactly those paths, snapshots the reports, rebuilds the list, re-admits, and mints the next card with this card as parent. An unknown measure records `VERIFICATION_PENDING` (candidate retained, attempt not counted, K4 does not mint). Otherwise it discards the candidate in index and working tree, restores the accepted reports, counts the attempt, and re-issues the cluster; at `decisions.thresholds.max_attempts` it defers and the loop **stops** (pilot rule). `verification/loop/` is the protected journal; the sealed list is rebuilt, never edited.
- **M4 VERIFY** runs the source-recorded oracles (`capture-source-oracles`), runtime parity for every entry point, the pre-verdict runner, and the MTA rescan assertion, and composes the verdict from measured exits.

dest-init mints M1 ANALYZE always and M2 PLAN (child of M1) only under an activated or pilot-sealed planner. Never M3 or M4 from dest-init.

---

## 9. Activation gate and pilot seal

`pins.planner.activation ∈ {not-activated, pilot, activated}`, read independently by `assert-planner-activated.py` (first M2 step), admission, and K4.

- `not-activated` (golden): dest-init mints M1 only; admission never ADMITS; K4 emits nothing; M3 and M4 do not exist.
- `pilot`: `pins.planner.pilot = {run_id, authorized_by, evidence_bundle_sha256}` admits exactly one bundle. A different bundle, a missing `authorized_by`, or a re-freeze is refused. A pilot never flips to `activated`.
- `activated`: named Operator GO after one live campaign demonstrates all of the following (fixture-green evidence does not count):

1. Repeated M1 on the same frozen source yields byte-identical bundle, work list and receipt.
2. Every MTA mandatory incident, every compiler error, and every failing test is a work-list item; none is lost between the tool and the list.
3. A step that introduces a mandatory incident is reverted; a step that does not decrease the measure is reverted.
4. K4 emits zero commands for a non-ADMITTED receipt and for a forged one.
5. The bootstrap on PetClinic REST compiles far enough to produce a real, non-empty work list.
6. A real board equals the expected cards after every mint; the foreign-card audit is clean.
7. One cluster completes accept → next card; one is reverted; one is deferred and cleared by a human.
8. The list reaches empty and M4 records runtime parity, not merely compile and rescan.
9. Every retired item cites a `decisions.yaml` entry and ADR; no planning artifact was hand-edited.

---

## 10. Current implementation impact

| Asset | Disposition |
|---|---|
| Freeze, build receipt, JDK-model inventory, MTA 8.2 receipts, evidence bundle | **Kept**; bundle trimmed to source, structure, entry points, obligations, receipts |
| Ownership map, four partition policies, capability DAG, transformation projection, resolution ledger | **Deleted** (`planner.ownership`, `planner.dag`, `planner.ledger`) |
| Context probe, jQAssistant reconciliation | **Deleted** (`probe-spring-bindings`, `enrich-legacy-bytecode`) |
| Platform API index | **Deleted** (no symbol projection on the compat path) |
| `execute-admitted-increment`, `plan-migration-increments`, `verify-live-kanban-dag` | **Replaced** by `fix-until-green`, `build-worklist`, `verify-live-kanban-loop` |
| K1 / K4 / K3 | **Adapted** to the work list (one card per step, attempt in the key, mint receipts as provenance) |
| K2, pins, activation and pilot seal, MTA provenance and canary, source oracles, M4 gates | **Kept** |
| Spec Kit | **Removed**; no compatibility path (residue scan in `validate.sh`) |

New: `planner.worklist`, `planner.cards`, `bootstrap-destination`, `compat-mapping.json`, `JdkDiagnostics.java`, the loop scripts, admission v2.

---

## 11. Maturity

| Area | Maturity |
|---|---|
| Freeze, build receipt, evidence bundle (environment-independent) | IMPLEMENTED; freeze run locally on a Spring fixture |
| JDK-model extractor | IMPLEMENTED on the JDK compiler API; run inside the selftest on a Spring fixture without a classpath (annotation values from the syntax tree) |
| MTA CLI 8.2 provenance, canary, incident conservation | IMPLEMENTED with negatives; `mta_cli` pinned to the 8.2 line, digest to be frozen from a measured receipt; not executed live |
| Deterministic bootstrap (compat mapping) | IMPLEMENTED with an idempotence test on a fake legacy pom; not run on PetClinic |
| Work list, order, measure, progress rule | IMPLEMENTED with unit and end-to-end tests |
| JDK diagnostics tool | IMPLEMENTED; run locally on the Spring fixture (18 errors, no classpath) |
| Loop (verify, accept, revert, defer, human clear, M4 on empty) | IMPLEMENTED end to end on the http specimen with simulated tool outputs and a real git repository; the 2026-09-09 review counterexamples (invented cluster, post-verification edit, out-of-scope test edit, staged revert, rejected reports, unrun/failed tools, line movement, unresolved test scope, stop on deferral, second-card continuation) are permanent tests |
| Admission v2 with every boundary | IMPLEMENTED with per-boundary negatives, forged-receipt and pilot-seal counterexamples |
| K1 / K4 / K3 (one card per step, provenance-only matching) | IMPLEMENTED against a fake board |
| K2 graph-mutation veto | IMPLEMENTED for the documented tool names; the real v0.20.5 worker tool surface is not captured |
| M4 source oracles and parity receipt | IMPLEMENTED with a local HTTP stub |
| Native lifecycle on the pinned Hermes (accept, reject, review, deferral) | NOT DEMONSTRATED; continuation proven only against a file-backed fake board |
| The producer → bootstrap → verify chain on real code (spring-petclinic-rest, local JDK 21 + Maven, Red Hat GA repository) | DEMONSTRATED 2026-09-09 by `build-worklist/scripts/rehearse-legacy.sh`: bootstrap `ok` (BOM probe, legacy-version carry-over, ADR-003 retirement), 675 compiler errors in 81 files → 62 clusters, head `model/BaseEntity.java`; incidents UNKNOWN (no MTA CLI on that host) |
| Anything on a live workspace, board, or the MTA CLI | NOT DEMONSTRATED |

Principal risks: the compat mapping's coverage on a real starter set (unmapped dependencies become loop work, which is correct but may be long); local minima where a step reduces the measure without being semantically right (tests and parity are in the measure, and tests are never writable); sequential-only execution; the surefire runner on a partially migrated tree.

Decisions still required: the MTA CLI 8.2 binary in the overlay with its checksum frozen before admission; the pilot seal (bound to source, baseline, receipt, board and expiry) after the acceptance and continuation defects are proven on the pinned Hermes; capture of the worker tool names and schemas per profile for K2. `decisions.yaml` (platform ADR-001, attempt threshold ADR-002 = 3) is in place.

---

## 12. Documentation and contribution boundaries

| Question | Authoritative home |
|---|---|
| What does a participant click and observe? | [Stage README](README.md) |
| What is the target design and what is proven? | This document |
| What runs in the destination workspace? | `scaffold-repo/quarkus-migration-scaffold/` |
| How is the stage deployed and operated? | [Operations](../../docs/OPERATIONS.md) |
| How are failures diagnosed and recovered? | [Troubleshooting](../../docs/TROUBLESHOOTING.md) |
| What is deferred? | [Backlog](../../BACKLOG.md) |

Architects bind design here. Implementers change the kernel and skills against a cited section. Reviewers provide evidence and challenge maturity labels. Destination workers never edit this file or any sealed planning artifact.

### Primary references

- [MTA 8.2 CLI documentation](https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.2/html-single/using_the_migration_toolkit_for_applications_command-line_interface/index)
- [Hermes Kanban documentation](https://hermes-agent.nousresearch.com/docs/user-guide/features/kanban)
- [Hermes Kanban worker lanes](https://hermes-agent.nousresearch.com/docs/user-guide/features/kanban-worker-lanes)
- [JDK compiler API (`jdk.compiler` module)](https://docs.oracle.com/en/java/javase/21/docs/api/jdk.compiler/module-summary.html)
- [Quarkus: migrating from Spring](https://quarkus.io/spring/migrate/), [Spring DI](https://quarkus.io/guides/spring-di), [Spring Web](https://quarkus.io/guides/spring-web), [Spring Data JPA](https://quarkus.io/guides/spring-data-jpa), [Spring Boot properties](https://quarkus.io/guides/spring-boot-properties)
- [Migrating Code At Scale With LLMs At Google (FSE 2025)](https://arxiv.org/abs/2504.09691) — the change-location + LLM + verification loop this design follows
