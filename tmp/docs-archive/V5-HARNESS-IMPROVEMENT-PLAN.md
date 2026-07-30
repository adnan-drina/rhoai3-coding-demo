# Stage 080 harness improvement plan (V5 evidence + guidance Tier A)

Written 2026-07-29.

**Status: SUPERSEDED for execution sequencing by
[`V6-LEAD-PLAN.md`](V6-LEAD-PLAN.md)** (still useful as WS-A/WS-B detail).
Do not implement until findings §9 / V6 plan §7 operator sign-off. P0 =
fabrication-proof acceptance **before** any re-run.

**Goal:** durable process and guide improvements for *future* migration runs —
not a ship-at-all-costs patch of the live cart V5 run.

**Non-goals for this program:** forcing S05/M5/acceptance green on the current
workspace by hand-injecting endpoints or k8s env; replacing M1–M5; wiring
OpenRewrite; adopting Spring compatibility extensions.

Authority for Spring→Quarkus *guide* content:
[`SPRING-TO-QUARKUS-GUIDANCE-REVIEW.md`](SPRING-TO-QUARKUS-GUIDANCE-REVIEW.md)
(Tier A/B/C). Authority for *process* defects: live V5 dual-diligence on
`coolstore-cart-round3` (S05), plus harness sources under
`stages/080-ai-autonomous-migration/scaffold-repo/quarkus-migration-scaffold/`.

---

## 1. Two workstreams (keep separate PRs)

| WS | Name | Nature | May touch scripts? |
|----|------|--------|--------------------|
| **WS-A** | Spring→Quarkus **Tier A guide enrichment** | Docs/skills only | **No** |
| **WS-B** | V5 **durable process / gate** fixes | plan-lint, sensors, EXECUTION enforcement, instruments | **Yes** (harness only) |

Do **not** mix WS-A and WS-B in one PR. Guides must stay reviewable without
process risk; process fixes need instruments and careful rollout.

Deferred (unchanged from guidance review Tier B/C + V5 “later”): curated
OpenRewrite wiring, Windup `infer`→`recipe` reclass, multi-module M1
preflight, Spring compat, community BOM, mid-run intervention on live S05.

---

## 2. WS-A — Tier A guide enrichment (candidate; held)

When prep sign-off allows, implement **only** Tier A items from the guidance
umbrella. Agent brief (copy into the implementation session):

### 2.1 Implement (Tier A only)

Enrich agent-facing guides under
`stages/080-ai-autonomous-migration/scaffold-repo/quarkus-migration-scaffold/`:

| File | What to add |
|------|-------------|
| `.hermes/skills/migration-harness/MAPPINGS.md` | Diff in **Full** columns from quarkusio `annotation-map.md`, `config-map.md`, `dependency-map.md` (gap-fill). Book Ch3 REST tables (modernize to `quarkus-rest`). ExceptionHandler/Advice → `@ServerExceptionMapper`. DI nuances (`@Primary`, `@Conditional*`, cache, StartupEvent). Flyway + snake_case naming-strategy + `%prod` datasource notes — keep **`validate`**, not `update`. Spring Data → Panache**Repository** (not active-record default). Config profiles. Explicit **REJECT** box for `quarkus-spring-*`. Optional Snowdrop rule-card shape on key rows. List curated OpenRewrite source recipes as **future** `recipe:` candidates only (not wired). |
| `.opencode/skills/quarkus-rest-conventions.md` | Global mapper vs `@RestControllerAdvice`; void→204 where missing |
| `.opencode/skills/quarkus-persistence-conventions.md` | Spring Data ↔ PanacheRepository example; Flyway+validate; naming-strategy warning |
| `.opencode/skills/project-test-standards.md` | `@QuarkusTest` shared lifecycle vs SpringBootTest; optional `@QuarkusIntegrationTest` note |
| `AGENTS.md` | `@ApplicationScoped` default; never add `quarkus-spring-*` |
| Optionally `PLANNING.md` / `BRIEF-TEMPLATE.md` | One line: extensions→models→resources→config→tests; richer “Decided target shapes” |

Read authority docs in this order before editing:

1. `docs/SPRING-TO-QUARKUS-GUIDANCE-REVIEW.md`
2. `docs/QUARKUSIO-SKILLS-MIGRATE-SPRING.md`
3. `docs/QUARKUS-FOR-SPRING-DEVELOPERS.md`
4. `docs/OPENREWRITE-SPRINGBOOT-TO-QUARKUS.md` (document candidates in MAPPINGS only)
5. `docs/MAIN-THREAD-SPRING-TO-QUARKUS.md`, `docs/SNOWDROP-SPRINGBOOT-TO-QUARKUS-GUIDE.md`

Reference only (gitignored): `tmp/quarkusio-skills/`, book extracts, Snowdrop clone.

### 2.2 Hard constraints (never relax)

Native Quarkus only; side-by-side scaffold; RH BOM **3.27.3.SP1**; delete main
class; constructor injection; Flyway + `database.generation=validate` for DB
apps; `quarkus-rest*`; M1–M5 + sensors + factory remain the process.

### 2.3 Do not do in WS-A

- Change `outer-loop.sh`, `supervisor.sh`, `sensors.sh`, `analyze.sh`,
  `recipe-transform.sh`, or Windup joins
- Install quarkusio/skills as orchestrator or recommend Spring compat
- Wire OpenRewrite / community BOM / `Quarkus.run`
- Weaken Flyway+validate, constructor injection, or factory gates
- Leave `// TODO: Migration required` in application source
- Edit stage README unless a one-line accuracy fix is required
- Commit unless explicitly asked

### 2.4 WS-A validation / done

- Diff review: every added mapping is Full-path / native, not compat
- Modernize 2021 book names (`resteasy-*` → `quarkus-rest` / `quarkus-rest-jackson`)
- Mark implemented Tier A rows in
  [`SPRING-TO-QUARKUS-GUIDANCE-REVIEW.md`](SPRING-TO-QUARKUS-GUIDANCE-REVIEW.md)
  §4/§5 (short “Implemented” notes) — do **not** claim Tier B done
- Static review only (no live cart re-run required)

---

## 3. WS-B — V5 durable process fixes (after or parallel to WS-A)

Evidence from cart V5 S05 (observer dual-diligence). Prefer failing at **M3 /
static / preflight** over Phase E after a long M4.

### 3.1 Tier 0 — close known lint holes (do first in WS-B)

| ID | Defect | Fix |
|----|--------|-----|
| B0.1 | `plan-lint` acceptance check skipped when a comment sits between `acceptance:` and `path:` (live `migration.yaml` shape) | Parse with comment/blank tolerance (or minimal YAML load); path must appear in `tasks.md` |
| B0.2 | Instruments case #10 uses uncommented YAML only | Add instrument case using **commented** `acceptance.path` (must still `LINT:acceptance` when unmapped) |
| B0.3 | Re-run plan-lint against real scaffold `migration.yaml` in CI/instruments | Fail closed if S05-shaped tasks omit the path |

### 3.2 Tier 1 — ship contracts unskippable

| ID | Defect | Fix |
|----|--------|-----|
| B1.1 | Acceptance unowned by M4 (Phase E correction exists but is brittle) | Prefer M3 task + static/preflight handler exists; plan-lint: exact path in a task **and** substance naming a Java `@Path` that serves it (also fix B0.1 comment parse) |
| B1.2 | `preserve: CATALOG_ENDPOINT` satisfied by `application.properties` string alone | Typed preserve (or convention): env integrations require a task + presence under **`k8s/`** (Deployment `env`), not only props; update `preserved_integrations` in `sensors.sh` accordingly |
| B1.3 | Endpoint `@Path("/cart")` vs contract `/api/cart/...` | Pin public API prefix in profile/MAPPINGS/tasks; static check that cart resource `@Path` matches acceptance prefix |
| B1.4 | Soft §7 tokens (“idempotent”) → vacuous GREEN tests | Decisive oracles (status codes, **quantities**); prefer `rewrite` + golden test; **do not** default to “two adds → qty unchanged” — decide additive vs replace in findings §7.2/§9 |
| B1.5 | Acceptance curl gate fakeable (200 + len>0 / object→1) | Strengthen gate and/or keep source fabrication-watch as control (findings D5/D6) |

### 3.3 Tier 2 — duration / orchestration waste

**ROI priority for wall-clock** (see findings §3.7): B2.1 → B2.2 → B2.3 → B2.4
before large authoring/doc sweeps.

| ID | Defect | Fix |
|----|--------|-----|
| B2.1 | Hermes sleep/poll → orphan opencode → ~20–40 min wait | Supervisor (or wrapper) owns worker lifecycle; foreground `opencode` with long timeout; residual kill/cap after N minutes then verify-and-commit |
| B2.2 | Denied heredocs / `python -c` hang ~5 min | Fast-fail deny list (seconds); reinforce EXECUTION allowlisted scripts only |
| B2.3 | Verify-and-commit re-spawns opencode by default | Spawn worker only if dirty tree **and** sensors RED |
| B2.4 | Already-complete preserve tasks (e.g. T-010 props already present) | Probe + fast path commit / skip opencode |

### 3.4 Tier 3 — authoring quality (guides + lint, light process)

| ID | Defect | Fix |
|----|--------|-----|
| B3.1 | `plan.md` ↔ `tasks.md` drift (different T-009/T-010 meanings) | plan-lint or outer-loop check: task ids/titles consistent across plan/tasks, or drop plan from gate surface |
| B3.2 | Wrong legacy paths in task `Location:` | Substance/package checks already partial — extend to flag `legacyPackage` paths in Location when `targetPackage` is set |
| B3.3 | STORY_SCOPE reverts necessary §7 support types | Document scope exception pattern; expand scope for ExceptionMapper / IfExists when contract requires; bank “own getIdempotent in service story” in BRIEF/SEQUENCING |

### 3.5 WS-B validation / done

- New/updated cases in `.hermes/harness/tests/instruments.sh` for B0–B1
- `plan-lint` + `sensors.sh static` fail on the V5 hole reproductions
- No live requirement to re-run full cart for merge; a focused dry-run on a
  fixture tree is enough. After merge, next e2e is the proving run.

---

## 4. Suggested PR sequence

| PR | Content | Depends on |
|----|---------|------------|
| **PR-A1** | WS-A: MAPPINGS + OpenCode skills + AGENTS (+ optional PLANNING/BRIEF one-liners); mark Tier A implemented in guidance umbrella | Guidance review (done) |
| **PR-B1** | WS-B Tier 0: acceptance YAML parse + instruments | None (can parallel PR-A1) |
| **PR-B2** | WS-B Tier 2 (ROI 1–3): worker lifecycle, fast deny, verify/already-complete — **wall-clock first** per findings §3.7 | PR-B1 optional |
| **PR-B3** | WS-B Tier 1: preserve→k8s, acceptance substance, API path pin, gate honesty (B1.5) | PR-B1 |
| **PR-B4** | WS-B Tier 3: plan/tasks drift, Location package, scope guidance, oracles | PR-A1 helpful for shape text |

Live V5 cart run: **observe only** until natural end (or explicit abort). Do
not land WS-B fixes into the running workspace mid-S05. Capture Phase E
failure signatures into instruments when they appear.

---

## 5. Relationship to other docs

| Doc | Role |
|-----|------|
| [`SPRING-TO-QUARKUS-GUIDANCE-REVIEW.md`](SPRING-TO-QUARKUS-GUIDANCE-REVIEW.md) | Pattern Tier A/B/C — WS-A implements A only |
| Companion Spring→Quarkus analysis docs | Source notes for WS-A |
| [`V5-FINDINGS-AND-PREP.md`](V5-FINDINGS-AND-PREP.md) | Findings catalog + prep gate — **read first** |
| [`V5-RUN-MONITOR.md`](V5-RUN-MONITOR.md) | Live run log (may lag); not the backlog |
| This file | Candidate PR sequence after prep sign-off |
| Stage 080 README | Touch only for one-line accuracy after PRs land |

---

## 6. Success criteria (program level)

Next e2e migration should:

1. **Fail at M3** if `acceptance.path` or k8s-backed preserve env is untasked
   (not at Phase E after hours of M4).
2. **Fail at static/preflight** if props mention `CATALOG_ENDPOINT` but
   Deployment env does not.
3. Keep **native Full-path** guidance coherent in MAPPINGS/skills (WS-A) so
   workers stop inventing compat or wrong persistence defaults.
4. Cut orphan-worker and deny-tax classes of waste (WS-B Tier 2) without
   weakening factory gates.

---

## 7. Immediate next action (preparation, not coding)

1. Work [`V5-FINDINGS-AND-PREP.md`](V5-FINDINGS-AND-PREP.md): finish evidence
   (§7.1), analysis workshops (§7.2), design freeze (§7.3).
2. Observe live M5/ship/acceptance; append Phase E rows to findings §8.
3. Only after operator decision in findings §9: pick first PR (likely B1 / A1
   parse fix, or WS-A if guides are prioritized) and implement with instruments
   first.
